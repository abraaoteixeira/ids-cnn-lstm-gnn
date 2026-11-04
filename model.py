"""
model.py

Arquitetura `SPECTRE_GRID` (CNN1D -> LSTM -> GATConv -> Classificador)

O modelo segue a metodologia do artigo ICICNIS-2024 de Ananthi et al.:
- CNN1D: Extrai padrões temporais locais nas Top-20 features.
- LSTM: Captura dependências temporais de longo prazo e evita Vanishing Gradient.
- GATConv: Realiza Message Passing topológico (IPs são nós, fluxos são arestas).
  Quando `use_gat=False`, opera como baseline temporal puro `CNN1D -> LSTM -> FC` sem camada GAT.
- Classificador FC: Prediz probabilidade binária de intrusão por nó.

Comentários em Português explicando shapes e fluxo de dados.
"""
from typing import Optional, Tuple

import logging
import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from torch_geometric.nn import GATConv
except Exception as e:
    raise RuntimeError("torch_geometric não encontrado. Instale conforme o README.") from e

logging.basicConfig(level=logging.INFO)


class SPECTRE_GRID(nn.Module):
    """
    Modelo STGNN que combina:
      - CNN1D (Perfilador Temporal): Extrai padrões na dimensão temporal das Top-20 features.
      - LSTM (Historiador Temporal): Captura dependências de longo prazo.
      - GATConv (Estrategista Topológico): Message Passing no grafo (nós=IPs, arestas=fluxos).
        Pode ser desativado (`use_gat=False`) para ablação estrutural pura (CNN-LSTM sem GAT).
      - Classificador FC: Logit binário para predição de intrusão.

    Entradas esperadas:
      x: Tensor [N, seq_len, num_features] — sequências temporais de features por nó
      edge_index: Tensor [2, E] — índices de arestas dirigidas do grafo

    Saída:
      logits: Tensor [N] (logits binários; usar BCEWithLogitsLoss para treino)
    """

    def __init__(
        self,
        num_features: int = 20,
        seq_len: int = 10,
        cnn_out_channels: int = 32,
        lstm_hidden_size: int = 64,
        gnn_hidden_size: int = 64,
        gat_heads: int = 4,
        dropout: float = 0.3,
        use_gat: bool = True,
        use_residual: bool = False,
    ) -> None:
        super().__init__()
        self.num_features = num_features
        self.seq_len = seq_len
        self.cnn_out_channels = cnn_out_channels
        self.lstm_hidden_size = lstm_hidden_size
        self.gnn_hidden_size = gnn_hidden_size
        self.gat_heads = gat_heads
        self.dropout = dropout
        self.use_gat = use_gat
        self.use_residual = use_residual

        # =====================================================================
        # CAMADA 1: CNN1D (Extração de Padrões Temporais)
        # =====================================================================
        self.cnn = nn.Sequential(
            nn.Conv1d(in_channels=num_features, out_channels=cnn_out_channels, kernel_size=3, padding=1),
            nn.BatchNorm1d(cnn_out_channels),
            nn.ReLU(),
            nn.Conv1d(in_channels=cnn_out_channels, out_channels=cnn_out_channels, kernel_size=3, padding=1),
            nn.BatchNorm1d(cnn_out_channels),
            nn.ReLU(),
        )

        # =====================================================================
        # CAMADA 2: LSTM (Captura Temporal)
        # =====================================================================
        self.lstm = nn.LSTM(
            input_size=cnn_out_channels,
            hidden_size=lstm_hidden_size,
            num_layers=1,
            batch_first=True,
            bidirectional=False,
            dropout=0.0,
        )

        # =====================================================================
        # CAMADA 3: GATConv (Message Passing Topológico — opcional para baseline puro CNN-LSTM)
        # =====================================================================
        if self.use_gat:
            self.gat = GATConv(
                in_channels=lstm_hidden_size,
                out_channels=gnn_hidden_size,
                heads=gat_heads,
                concat=True,
                dropout=dropout,
            )
            fc_input_dim = gnn_hidden_size * gat_heads
            self.residual_proj = nn.Linear(lstm_hidden_size, fc_input_dim) if self.use_residual else None
        else:
            self.gat = None
            self.residual_proj = None
            fc_input_dim = lstm_hidden_size

        # =====================================================================
        # CAMADA 4: Classificador Final (Fully Connected)
        # =====================================================================
        self.classifier = nn.Sequential(
            nn.Linear(fc_input_dim, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """
        Forward pass com comentários detalhados sobre transformações de shapes.
        """
        num_feat = x.size(2)
        if num_feat != self.num_features:
            logging.warning(f"Número de features de entrada ({num_feat}) ≠ esperado ({self.num_features})")

        x_cnn = x.transpose(1, 2)  # [N, num_features, seq_len]
        cnn_out = self.cnn(x_cnn)  # [N, cnn_out_channels, seq_len]

        cnn_out_transpose = cnn_out.transpose(1, 2)  # [N, seq_len, cnn_out_channels]
        _, (h_n, _) = self.lstm(cnn_out_transpose)
        h_last = h_n[-1]  # [N, lstm_hidden_size]

        if self.use_gat and self.gat is not None:
            feat_out = self.gat(h_last, edge_index)  # [N, gnn_hidden_size * gat_heads]
            if self.use_residual and self.residual_proj is not None:
                feat_out = feat_out + self.residual_proj(h_last)
        else:
            feat_out = h_last  # [N, lstm_hidden_size] (CNN-LSTM puro)

        logits = self.classifier(feat_out).squeeze(-1)  # [N]
        return logits

    def forward_xai(self, x: torch.Tensor, edge_index: torch.Tensor) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Forward pass alternativo para XAI (eXplainable AI).
        Retorna os logits e os pesos de atenção do GATConv para o Dashboard visualizar.
        """
        x_cnn = x.transpose(1, 2)
        cnn_out = self.cnn(x_cnn)
        cnn_out_transpose = cnn_out.transpose(1, 2)
        _, (h_n, _) = self.lstm(cnn_out_transpose)
        h_last = h_n[-1]

        if self.use_gat and self.gat is not None:
            gat_out, attention = self.gat(h_last, edge_index, return_attention_weights=True)
            if self.use_residual and self.residual_proj is not None:
                gat_out = gat_out + self.residual_proj(h_last)
            logits = self.classifier(gat_out).squeeze(-1)
            return logits, attention

        logits = self.classifier(h_last).squeeze(-1)
        empty_attn = (edge_index, torch.ones((edge_index.size(1), 1), device=x.device))
        return logits, empty_attn


if __name__ == "__main__":
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logging.info(f"Teste do modelo em device: {device}")

    N = 16
    seq_len = 10
    num_features = 20

    x = torch.randn(N, seq_len, num_features, device=device)
    edge_index = torch.tensor([[0, 1, 2, 3], [1, 2, 3, 4]], dtype=torch.long, device=device)

    model = SPECTRE_GRID(num_features=num_features, seq_len=seq_len, use_gat=True).to(device)
    logits = model(x, edge_index)

    model_pure = SPECTRE_GRID(num_features=num_features, seq_len=seq_len, use_gat=False).to(device)
    logits_pure = model_pure(x, edge_index)

    logging.info(f"Input x shape: {x.shape}")
    logging.info(f"Edge index shape: {edge_index.shape}")
    logging.info(f"Output logits shape (GAT): {logits.shape} | (Pure CNN-LSTM): {logits_pure.shape}")
    logging.info("✓ Teste de integridade passou com sucesso!")
