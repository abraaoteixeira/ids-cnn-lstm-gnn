"""
model.py

Arquitetura `SPECTRE_GRID` (CNN1D -> LSTM -> GATConv -> Classificador)

O modelo segue a metodologia do artigo ICICNIS-2024 de Ananthi et al.:
- CNN1D: Extrai padrões temporais locais nas Top-20 features.
- LSTM: Captura dependências temporais de longo prazo e evita Vanishing Gradient.
- GATConv: Realiza Message Passing topológico (IPs são nós, fluxos são arestas).
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
      - Classificador FC: Logit binário para predição de intrusão.

    Entradas esperadas:
      x: Tensor [N, seq_len, num_features] — sequências temporais de features por nó
      edge_index: Tensor [2, E] — índices de arestas dirigidas do grafo

    Saída:
      logits: Tensor [N] (logits binários; usar BCEWithLogitsLoss para treino)

    Parâmetros:
      num_features (int): número de features por time-step (default 20, ICICNIS-2024)
      seq_len (int): comprimento da sequência temporal
      cnn_out_channels (int): canais de saída da CNN1D
      lstm_hidden_size (int): dimensão do hidden state da LSTM
      gnn_hidden_size (int): dimensão de saída do GATConv
      gat_heads (int): número de heads de atenção no GAT
      dropout (float): taxa de dropout para regularização
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
    ) -> None:
        super().__init__()
        self.num_features = num_features
        self.seq_len = seq_len
        self.cnn_out_channels = cnn_out_channels
        self.lstm_hidden_size = lstm_hidden_size
        self.gnn_hidden_size = gnn_hidden_size
        self.gat_heads = gat_heads
        self.dropout = dropout

        # =====================================================================
        # CAMADA 1: CNN1D (Extração de Padrões Temporais)
        # =====================================================================
        # Input: [N, seq_len, num_features]
        # Será convertido para [N, num_features, seq_len] para Conv1d
        # Conv1d operará sobre a dimensão temporal (seq_len)
        self.cnn = nn.Sequential(
            # Conv1d: in_channels=num_features, out_channels=cnn_out_channels, kernel_size=3
            nn.Conv1d(in_channels=num_features, out_channels=cnn_out_channels, kernel_size=3, padding=1),
            nn.BatchNorm1d(cnn_out_channels),
            nn.ReLU(),
            # Segunda camada convolucional
            nn.Conv1d(in_channels=cnn_out_channels, out_channels=cnn_out_channels, kernel_size=3, padding=1),
            nn.BatchNorm1d(cnn_out_channels),
            nn.ReLU(),
        )
        # Saída CNN: [N, cnn_out_channels, seq_len]

        # =====================================================================
        # CAMADA 2: LSTM (Captura Temporal)
        # =====================================================================
        # Após CNN, reshape para [N, seq_len, cnn_out_channels] para LSTM (batch_first=True)
        self.lstm = nn.LSTM(
            input_size=cnn_out_channels,
            hidden_size=lstm_hidden_size,
            num_layers=1,
            batch_first=True,
            bidirectional=False,
            dropout=0.0,  # dropout=0 com num_layers=1
        )
        # Saída LSTM: h_n (último hidden state): [1, N, lstm_hidden_size]
        # Usaremos h_n[-1] para obter [N, lstm_hidden_size]

        # =====================================================================
        # CAMADA 3: GATConv (Message Passing Topológico)
        # =====================================================================
        # Input: [N, lstm_hidden_size]
        # Output: [N, gnn_hidden_size * gat_heads] (concatenação)
        self.gat = GATConv(
            in_channels=lstm_hidden_size,
            out_channels=gnn_hidden_size,
            heads=gat_heads,
            concat=True,  # concatena múltiplos heads
            dropout=dropout,
        )
        # Saída GAT: [N, gnn_hidden_size * gat_heads]

        # =====================================================================
        # CAMADA 4: Classificador Final (Fully Connected)
        # =====================================================================
        # Reduz [N, gnn_hidden_size * gat_heads] para logit binário [N, 1]
        fc_input_dim = gnn_hidden_size * gat_heads
        self.classifier = nn.Sequential(
            nn.Linear(fc_input_dim, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),  # logit final (sem sigmoid; usar BCEWithLogitsLoss)
        )

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """
        Forward pass com comentários detalhados sobre transformações de shapes.

        Args:
          x: [N, seq_len, num_features] — sequências temporais por nó
          edge_index: [2, E] — arestas dirigidas do grafo

        Returns:
          logits: [N] — logits binários por nó (sem sigmoid; usar BCEWithLogitsLoss)

        Fluxo de Transformações (shapes):
          1. Input x: [N, seq_len, num_features]
          2. Reshape para CNN: [N, num_features, seq_len]
             - Conv1d espera (batch, channels, length)
          3. Após CNN1D: [N, cnn_out_channels, seq_len]
          4. Reshape para LSTM: [N, seq_len, cnn_out_channels]
          5. Após LSTM: h_last [N, lstm_hidden_size]
          6. Após GATConv: [N, gnn_hidden_size * gat_heads]
          7. Após classificador FC: [N, 1]
          8. Squeeze: [N]
        """

        N = x.size(0)
        seq_len = x.size(1)
        num_feat = x.size(2)

        if num_feat != self.num_features:
            logging.warning(f"Número de features de entrada ({num_feat}) ≠ esperado ({self.num_features})")

        # =====================================================================
        # ETAPA 1: CNN1D para processamento temporal
        # =====================================================================
        # Input: [N, seq_len, num_features]
        # Reshape para formato Conv1d: [N, num_features, seq_len]
        x_cnn = x.transpose(1, 2)  # [N, num_features, seq_len]
        
        # Aplicar CNN1D
        cnn_out = self.cnn(x_cnn)  # [N, cnn_out_channels, seq_len]

        # =====================================================================
        # ETAPA 2: LSTM para capturar dependências temporais
        # =====================================================================
        # Preparar entrada para LSTM: [N, seq_len, cnn_out_channels]
        cnn_out_transpose = cnn_out.transpose(1, 2)  # [N, seq_len, cnn_out_channels]
        
        # Executar LSTM (batch_first=True)
        lstm_out, (h_n, c_n) = self.lstm(cnn_out_transpose)
        # lstm_out: [N, seq_len, lstm_hidden_size]
        # h_n: [num_layers, N, lstm_hidden_size] = [1, N, lstm_hidden_size]
        
        # Extrair o último hidden state (representação temporal comprimida por nó)
        h_last = h_n[-1]  # [N, lstm_hidden_size]

        # =====================================================================
        # ETAPA 3: GATConv para Message Passing Topológico
        # =====================================================================
        # Input: [N, lstm_hidden_size]
        # edge_index: [2, E]
        gat_out = self.gat(h_last, edge_index)  # [N, gnn_hidden_size * gat_heads]

        # =====================================================================
        # ETAPA 4: Classificador Final (logit)
        # =====================================================================
        logits = self.classifier(gat_out).squeeze(-1)  # [N]

        return logits


if __name__ == "__main__":
    """
    Teste rápido de integridade do modelo com tensores aleatórios.
    """
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logging.info(f"Teste do modelo em device: {device}")

    # Parâmetros de teste
    N = 16  # número de nós
    seq_len = 10  # comprimento da sequência temporal
    num_features = 20  # top-20 features

    # Criar tensores de teste
    x = torch.randn(N, seq_len, num_features, device=device)  # [N, seq_len, 20]
    edge_index = torch.tensor([[0, 1, 2, 3], [1, 2, 3, 4]], dtype=torch.long, device=device)  # [2, E]

    # Instanciar modelo e enviar para device
    model = SPECTRE_GRID(num_features=num_features, seq_len=seq_len).to(device)
    
    # Forward pass
    logits = model(x, edge_index)  # [N]
    
    logging.info(f"Input x shape: {x.shape}")
    logging.info(f"Edge index shape: {edge_index.shape}")
    logging.info(f"Output logits shape: {logits.shape}")
    logging.info(f"✓ Teste de integridade passou com sucesso!")

# Legacy alias removed: use `SPECTRE_GRID` as the canonical model name.