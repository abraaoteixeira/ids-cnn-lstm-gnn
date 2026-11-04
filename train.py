"""
train.py
Motor de treino STGNN livre de vazamento de dados (Leakage-Free) com suporte a:
 - Snapshots Temporais Discretos G_t = (V_t, E_t) via `torch_geometric.loader.DataLoader`.
 - Particionamento disjunto em 3 vias: Treino (60%), Validação (20%) e Teste Reservado (20%).
 - Rejeição de grafos históricos individuais pré-processados globalmente.
 - Salvamento periódico e retomada automática de estado (`--resume` / `--save_every`) para
   tolerância a desconexões no Google Colab Pro (persistência em Google Drive) e no Dell G15.
 - Sementes aleatórias fixadas para reprodutibilidade científica.
 - Novo forward pass em `model.eval()` APÓS `optimizer.step()` (nunca reutiliza logits pré-gradiente).
 - LR Scheduler e Early Stopping guiados EXCLUSIVAMENTE pelo F1 agregado do conjunto de Validação.
 - Conjunto de Teste avaliado uma única vez ao final, após recarregar o melhor checkpoint de validação.
 - Registro completo de Precision, Recall, F1-Score, False Positive Rate (FPR), Matriz de Confusão e
   Latência de Inferência (ms por snapshot e µs por nó).
"""

import argparse
import json
import logging
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
try:
    import seaborn as sns
except ImportError:
    sns = None
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

from model import SPECTRE_GRID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

LOADER_EXCLUDE_KEYS = ["ip2idx", "idx2ip", "scaler", "top_features", "topology_mode"]


def set_deterministic_seed(seed: int = 42) -> None:
    """Fixa sementes de Python, NumPy e PyTorch para reprodutibilidade."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_args():
    parser = argparse.ArgumentParser(description="Treino Reprodutível e Sem Vazamento do IDS STGNN (Snapshots Temporais)")
    parser.add_argument("--data_path", required=True, help="Caminho para o arquivo de partições/snapshots (.pt)")
    parser.add_argument("--epochs", type=int, default=30, help="Número de épocas")
    parser.add_argument("--batch_size", type=int, default=8, help="Snapshots por mini-batch no DataLoader")
    parser.add_argument("--lr", type=float, default=0.001, help="Taxa de aprendizado")
    parser.add_argument("--patience", type=int, default=7, help="Paciência do Early Stopping (na validação)")
    parser.add_argument("--seed", type=int, default=42, help="Semente aleatória")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu", help="cuda/cpu")
    parser.add_argument(
        "--checkpoint_out",
        default="data/processed/best_model_clean.pth",
        help="Caminho para salvar o melhor checkpoint selecionado na validação",
    )
    parser.add_argument(
        "--resume_state_out",
        default=None,
        help="Arquivo de estado completo para retomada após interrupção (default: <checkpoint_out>.resume.pt)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Retoma automaticamente o treinamento a partir de --resume_state_out se existir",
    )
    parser.add_argument(
        "--save_every",
        type=int,
        default=1,
        help="Frequência (em épocas) para salvar o estado de retomada periódica",
    )
    parser.add_argument(
        "--report_out",
        default="data/processed/clean_evaluation_report.json",
        help="Relatório JSON auditável com métricas de validação, teste reservado e latência",
    )
    parser.add_argument(
        "--cm_out",
        default="data/processed/confusion_matrix_clean.png",
        help="Caminho para salvar a Matriz de Confusão do teste reservado",
    )
    parser.add_argument(
        "--ablation_no_graph",
        action="store_true",
        help="Substitui arestas entre hosts por apenas auto-loops (GAT com self-loops)",
    )
    parser.add_argument(
        "--model_variant",
        default="cnn_lstm_gat",
        choices=["cnn_lstm_gat", "cnn_lstm_pure", "gat_self_loop", "gat_reverse", "gat_bidir", "gat_residual"],
        help=(
            "Variante arquitetural: 'cnn_lstm_gat' (completo src->dst), 'cnn_lstm_pure' (sem GAT), "
            "'gat_self_loop' (apenas auto-loops), 'gat_reverse' (arestas reversas dst->src), "
            "'gat_bidir' (arestas bidirecionais src<->dst) ou 'gat_residual' (GAT com conexão residual)"
        ),
    )
    parser.add_argument(
        "--val_only",
        action="store_true",
        help="Modo exploratório: treina e avalia APENAS na validação, sem consultar o conjunto de teste reservado",
    )
    parser.add_argument(
        "--dataset_sha256",
        default=None,
        help="SHA256 opcional do CSV de origem para registro de auditoria no relatório JSON",
    )
    return parser.parse_args()


def save_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, save_path: str) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    plt.figure(figsize=(6, 5))
    if sns is not None:
        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Blues",
            xticklabels=["Normal (0)", "Ataque (1)"],
            yticklabels=["Normal (0)", "Ataque (1)"],
        )
    else:
        plt.imshow(cm, cmap="Blues")
        for i in range(2):
            for j in range(2):
                plt.text(j, i, str(cm[i, j]), ha="center", va="center", color="black")
        plt.xticks([0, 1], ["Normal (0)", "Ataque (1)"])
        plt.yticks([0, 1], ["Normal (0)", "Ataque (1)"])
    plt.ylabel("Rótulo Verdadeiro")
    plt.xlabel("Previsão do Modelo")
    plt.title("Matriz de Confusão - Teste Reservado (Held-Out)")
    plt.tight_layout()

    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    plt.savefig(save_path)
    plt.close()
    logging.info(f"Matriz de Confusão salva em: {save_path}")


def _normalize_to_graph_list(obj: Union[Data, List[Data]], device: torch.device) -> List[Data]:
    """Normaliza um grafo único ou lista de snapshots para `List[Data]` no dispositivo alvo."""
    if isinstance(obj, Data):
        return [obj.to(device)]
    if isinstance(obj, (list, tuple)):
        out = [g.to(device) for g in obj if isinstance(g, Data) and g.x.shape[0] > 0]
        if not out:
            raise ValueError("A lista de snapshots fornecida está vazia (nenhum grafo com nós > 0).")
        return out
    raise TypeError(f"Esperado Data ou List[Data], recebido: {type(obj)}")


def load_or_split_graphs(
    raw_obj: object,
    device: torch.device,
    seed: int = 42,
) -> Tuple[List[Data], List[Data], List[Data], Dict[str, object]]:
    """
    Carrega exclusivamente bundles pré-particionados (train/val/test ou train_snapshots/val_snapshots/test_snapshots)
    gerados pelo protocolo livre de vazamento (`preprocessor.py`).
    Rejeita grafos históricos individuais (`isinstance(raw_obj, Data)`) pois dividir um grafo único após
    seleção de features e normalização globais viola o isolamento metodológico.
    """
    if isinstance(raw_obj, Data):
        raise ValueError(
            "Arquivo contém um único grafo histórico pré-processado globalmente. "
            "Dividir um grafo após StandardScaler/Pearson globais não garante ausência de vazamento. "
            "Gere as partições e snapshots temporais com `preprocessor.py` antes de treinar."
        )

    if not isinstance(raw_obj, dict):
        raise TypeError(f"Formato de dados não suportado em --data_path: {type(raw_obj)}")

    meta: Dict[str, object] = {
        "protocol": raw_obj.get("protocol", "inductive_bundle"),
        "feature_scope": raw_obj.get("feature_scope", "unknown"),
        "window_sec": raw_obj.get("window_sec", None),
        "top_features": raw_obj.get("top_features", []),
        "split_rows": raw_obj.get("split_rows", {}),
    }

    if "train_snapshots" in raw_obj and "val_snapshots" in raw_obj and "test_snapshots" in raw_obj:
        train_list = _normalize_to_graph_list(raw_obj["train_snapshots"], device)
        val_list = _normalize_to_graph_list(raw_obj["val_snapshots"], device)
        test_list = _normalize_to_graph_list(raw_obj["test_snapshots"], device)
        return train_list, val_list, test_list, meta

    if "train" in raw_obj and "val" in raw_obj and "test" in raw_obj:
        train_list = _normalize_to_graph_list(raw_obj["train"], device)
        val_list = _normalize_to_graph_list(raw_obj["val"], device)
        test_list = _normalize_to_graph_list(raw_obj["test"], device)
        return train_list, val_list, test_list, meta

    raise KeyError("O bundle em --data_path deve conter ('train_snapshots', 'val_snapshots', 'test_snapshots') ou ('train', 'val', 'test').")


def edge_statistics(graphs: Union[Data, List[Data]]) -> Dict[str, object]:
    """
    Contabiliza estatísticas estruturais de um grafo ou lista de snapshots temporais:
    número de snapshots, total de nós, arestas totais, auto-loops, arestas reais entre hosts e balanço de classes.
    """
    g_list = [graphs] if isinstance(graphs, Data) else list(graphs)
    total_nodes = 0
    total_edges = 0
    self_loops = 0
    cross_host = 0
    benign_0 = 0
    attack_1 = 0

    for g in g_list:
        total_nodes += int(g.x.shape[0])
        if g.edge_index.numel() > 0:
            src, dst = g.edge_index[0], g.edge_index[1]
            total_edges += int(src.numel())
            self_loops += int((src == dst).sum().item())
            cross_host += int((src != dst).sum().item())
        benign_0 += int((g.y == 0).sum().item())
        attack_1 += int((g.y == 1).sum().item())

    return {
        "num_snapshots": len(g_list),
        "nodes": total_nodes,
        "total_edges": total_edges,
        "self_loops": self_loops,
        "cross_host_edges": cross_host,
        "benign_nodes_0": benign_0,
        "attack_nodes_1": attack_1,
    }


def apply_self_loop_only(graph: Data) -> Data:
    """Usado em estudos de ablação: remove arestas entre hosts distintos, mantendo apenas auto-loops."""
    n = graph.x.shape[0]
    idx = torch.arange(n, dtype=torch.long, device=graph.x.device)
    edge_index = torch.stack([idx, idx], dim=0)
    return Data(x=graph.x, edge_index=edge_index, y=graph.y)


def apply_reverse_edges(graph: Data) -> Data:
    """Variante experimental: inverte a direção das arestas observadas (dst -> src)."""
    if graph.edge_index.numel() == 0:
        return Data(x=graph.x, edge_index=graph.edge_index, y=graph.y)
    rev_ei = torch.stack([graph.edge_index[1], graph.edge_index[0]], dim=0)
    return Data(x=graph.x, edge_index=rev_ei, y=graph.y)


def apply_bidirectional_edges(graph: Data) -> Data:
    """Variante experimental: torna o grafo bidirecional (src -> dst e dst -> src)."""
    if graph.edge_index.numel() == 0:
        return Data(x=graph.x, edge_index=graph.edge_index, y=graph.y)
    rev_ei = torch.stack([graph.edge_index[1], graph.edge_index[0]], dim=0)
    bi_ei = torch.unique(torch.cat([graph.edge_index, rev_ei], dim=1), dim=1)
    return Data(x=graph.x, edge_index=bi_ei, y=graph.y)


def compute_heterophily_and_node_group_metrics(
    orig_graphs: List[Data],
    y_pred_concat: np.ndarray,
) -> Dict[str, object]:
    """
    Calcula a contagem de arestas entre classes (0->0, 1->0, 0->1, 1->1) nos snapshots originais
    e decompõe a taxa de falsos positivos (FPR) entre:
      - Vítimas benignas alvejadas por atacantes (>= 1 aresta recebida 1 -> 0 na janela)
      - Hosts benignos não alvejados (0 arestas 1 -> 0 recebidas na janela)
    """
    e00 = e01 = e10 = e11 = 0
    fp_targeted = tn_targeted = 0
    fp_untargeted = tn_untargeted = 0
    offset = 0

    for g in orig_graphs:
        y = g.y.detach().cpu()
        ei = g.edge_index.detach().cpu()
        n = int(y.numel())
        preds_g = y_pred_concat[offset : offset + n] if len(y_pred_concat) >= offset + n else np.zeros((n,), dtype=np.int64)
        offset += n

        if ei.numel() > 0:
            mask = ei[0] != ei[1]
            u_cross, v_cross = ei[0][mask], ei[1][mask]
            yu, yv = y[u_cross], y[v_cross]
            e00 += int(((yu == 0) & (yv == 0)).sum().item())
            e01 += int(((yu == 0) & (yv == 1)).sum().item())
            e10 += int(((yu == 1) & (yv == 0)).sum().item())
            e11 += int(((yu == 1) & (yv == 1)).sum().item())
        else:
            u_cross = torch.empty((0,), dtype=torch.long)
            v_cross = torch.empty((0,), dtype=torch.long)

        for idx in range(n):
            if int(y[idx].item()) == 0:
                in_sources = u_cross[v_cross == idx] if u_cross.numel() > 0 else torch.empty((0,), dtype=torch.long)
                targeted = bool((y[in_sources] == 1).any().item()) if in_sources.numel() > 0 else False
                pred_label = int(preds_g[idx])
                if targeted:
                    if pred_label == 1:
                        fp_targeted += 1
                    else:
                        tn_targeted += 1
                else:
                    if pred_label == 1:
                        fp_untargeted += 1
                    else:
                        tn_untargeted += 1

    tot_targeted = fp_targeted + tn_targeted
    tot_untargeted = fp_untargeted + tn_untargeted
    return {
        "cross_host_edges_by_label": {
            "0_to_0": e00,
            "1_to_0": e10,
            "0_to_1": e01,
            "1_to_1": e11,
        },
        "benign_targeted_by_attacker": {
            "total": tot_targeted,
            "fp": fp_targeted,
            "tn": tn_targeted,
            "fpr": round(fp_targeted / tot_targeted, 6) if tot_targeted > 0 else 0.0,
        },
        "benign_untargeted": {
            "total": tot_untargeted,
            "fp": fp_untargeted,
            "tn": tn_untargeted,
            "fpr": round(fp_untargeted / tot_untargeted, 6) if tot_untargeted > 0 else 0.0,
        },
    }


def compute_classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, object]:
    """Calcula Accuracy, Precision, Recall, F1, FPR e Matriz de Confusão (TN, FP, FN, TP)."""
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = (int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1]))
    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    return {
        "accuracy": round(acc, 6),
        "precision": round(prec, 6),
        "recall": round(rec, 6),
        "f1_score": round(f1, 6),
        "fpr": round(fpr, 6),
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    }


@torch.no_grad()
def evaluate_snapshots(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    num_snapshots: int = 1,
) -> Tuple[float, Dict[str, object], np.ndarray, np.ndarray, Dict[str, float]]:
    """
    Executa um NOVO forward pass em modo `model.eval()` agregando predições de todos os snapshots
    do `DataLoader` (validação ou teste) e medindo a latência de inferência.
    """
    model.eval()
    total_loss = 0.0
    total_nodes = 0
    all_true: List[np.ndarray] = []
    all_pred: List[np.ndarray] = []

    if device.type == "cuda" and torch.cuda.is_available():
        torch.cuda.synchronize(device)
    t0 = time.perf_counter()

    for batch in loader:
        batch = batch.to(device)
        n_batch = int(batch.x.size(0))
        if n_batch == 0:
            continue
        logits = model(batch.x, batch.edge_index)
        loss = float(criterion(logits, batch.y.float()).item())
        probs = torch.sigmoid(logits)
        preds = (probs >= 0.5).long()

        total_loss += loss * n_batch
        total_nodes += n_batch
        all_true.append(batch.y.detach().cpu().numpy())
        all_pred.append(preds.detach().cpu().numpy())

    if device.type == "cuda" and torch.cuda.is_available():
        torch.cuda.synchronize(device)
    elapsed_sec = max(1e-9, time.perf_counter() - t0)

    y_true = np.concatenate(all_true, axis=0) if all_true else np.zeros((0,), dtype=np.int64)
    y_pred = np.concatenate(all_pred, axis=0) if all_pred else np.zeros((0,), dtype=np.int64)
    avg_loss = total_loss / max(1, total_nodes)
    metrics = compute_classification_metrics(y_true, y_pred)

    latency = {
        "total_eval_ms": round(elapsed_sec * 1e3, 4),
        "ms_per_snapshot": round((elapsed_sec * 1e3) / max(1, num_snapshots), 4),
        "us_per_node": round((elapsed_sec * 1e6) / max(1, total_nodes), 4),
    }
    return avg_loss, metrics, y_true, y_pred, latency


def _forward_train_batch(model: nn.Module, batch: Data) -> torch.Tensor:
    """
    Executa forward em modo de treino. Se um mini-batch contiver apenas 1 nó total,
    coloca temporariamente camadas BatchNorm1d em modo eval() para evitar ValueError.
    """
    if batch.x.size(0) == 1:
        bn_modules = [m for m in model.modules() if isinstance(m, nn.BatchNorm1d)]
        for m in bn_modules:
            m.eval()
        logits = model(batch.x, batch.edge_index)
        for m in bn_modules:
            m.train()
        return logits
    return model(batch.x, batch.edge_index)


def train_and_evaluate(
    train_g: Union[Data, List[Data]],
    val_g: Union[Data, List[Data]],
    test_g: Union[Data, List[Data]],
    epochs: int = 30,
    lr: float = 0.001,
    patience: int = 7,
    seed: int = 42,
    device: Optional[torch.device] = None,
    checkpoint_out: str = "data/processed/best_model_clean.pth",
    ablation_no_graph: bool = False,
    model_variant: str = "cnn_lstm_gat",
    val_only: bool = False,
    batch_size: int = 8,
    resume: bool = False,
    resume_state_out: Optional[str] = None,
    save_every: int = 1,
) -> Dict[str, object]:
    """
    Executa o ciclo completo de treinamento com `torch_geometric.loader.DataLoader` sobre snapshots
    temporais, guiado exclusivamente pela validação, com salvamento periódico/retomada de estado e
    avaliação única no conjunto de teste reservado (exceto se `val_only=True`).
    """
    set_deterministic_seed(seed)

    first_train = train_g[0] if isinstance(train_g, (list, tuple)) else train_g
    if device is None:
        device = first_train.x.device

    orig_train_list = _normalize_to_graph_list(train_g, device)
    orig_val_list = _normalize_to_graph_list(val_g, device)
    orig_test_list = _normalize_to_graph_list(test_g, device)

    effective_variant = "gat_self_loop" if (ablation_no_graph and model_variant == "cnn_lstm_gat") else model_variant
    if effective_variant in ("gat_self_loop", "cnn_lstm_pure") or ablation_no_graph:
        train_list = [apply_self_loop_only(g) for g in orig_train_list]
        val_list = [apply_self_loop_only(g) for g in orig_val_list]
        test_list = [apply_self_loop_only(g) for g in orig_test_list]
    elif effective_variant == "gat_reverse":
        train_list = [apply_reverse_edges(g) for g in orig_train_list]
        val_list = [apply_reverse_edges(g) for g in orig_val_list]
        test_list = [apply_reverse_edges(g) for g in orig_test_list]
    elif effective_variant == "gat_bidir":
        train_list = [apply_bidirectional_edges(g) for g in orig_train_list]
        val_list = [apply_bidirectional_edges(g) for g in orig_val_list]
        test_list = [apply_bidirectional_edges(g) for g in orig_test_list]
    else:
        train_list = orig_train_list
        val_list = orig_val_list
        test_list = orig_test_list

    use_gat = effective_variant != "cnn_lstm_pure"
    use_residual = effective_variant == "gat_residual"

    train_loader = DataLoader(train_list, batch_size=batch_size, shuffle=False, exclude_keys=LOADER_EXCLUDE_KEYS)
    val_loader = DataLoader(val_list, batch_size=batch_size, shuffle=False, exclude_keys=LOADER_EXCLUDE_KEYS)
    test_loader = DataLoader(test_list, batch_size=batch_size, shuffle=False, exclude_keys=LOADER_EXCLUDE_KEYS)

    sample_g = train_list[0]
    model = SPECTRE_GRID(
        num_features=sample_g.x.shape[2],
        seq_len=sample_g.x.shape[1],
        cnn_out_channels=32,
        lstm_hidden_size=64,
        gnn_hidden_size=64,
        gat_heads=4,
        use_gat=use_gat,
        use_residual=use_residual,
    ).to(device)

    # Calcula pos_weight apenas nos snapshots de treino para lidar com desbalanceamento
    n_pos = float(sum(int((g.y == 1).sum().item()) for g in train_list))
    n_neg = float(sum(int((g.y == 0).sum().item()) for g in train_list))
    if n_pos > 0 and n_neg > 0:
        pos_weight = torch.tensor([min(max(n_neg / n_pos, 0.5), 10.0)], dtype=torch.float32, device=device)
        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    else:
        criterion = nn.BCEWithLogitsLoss()

    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=3)

    best_val_f1 = -1.0
    best_val_metrics: Dict[str, object] = {}
    best_epoch = 0
    epochs_no_improve = 0
    start_epoch = 1
    resumed_from_epoch = 0
    epoch_history: List[Dict[str, object]] = []

    if resume_state_out is None:
        resume_state_out = f"{checkpoint_out}.resume.pt"

    os.makedirs(os.path.dirname(checkpoint_out) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(resume_state_out) or ".", exist_ok=True)

    if resume and os.path.exists(resume_state_out):
        state = torch.load(resume_state_out, map_location=device, weights_only=False)
        model.load_state_dict(state["model_state_dict"])
        optimizer.load_state_dict(state["optimizer_state_dict"])
        scheduler.load_state_dict(state["scheduler_state_dict"])
        best_val_f1 = float(state.get("best_val_f1", -1.0))
        best_val_metrics = state.get("best_val_metrics", {})
        best_epoch = int(state.get("best_epoch", 0))
        epochs_no_improve = int(state.get("epochs_no_improve", 0))
        resumed_from_epoch = int(state.get("epoch", 0))
        epoch_history = list(state.get("epoch_history", []))
        start_epoch = resumed_from_epoch + 1
        if "python_rng_state" in state:
            random.setstate(state["python_rng_state"])
        if "numpy_rng_state" in state:
            np.random.set_state(state["numpy_rng_state"])
        if "torch_cpu_rng_state" in state:
            torch_cpu_state = state["torch_cpu_rng_state"]
            if isinstance(torch_cpu_state, torch.Tensor):
                torch.set_rng_state(torch_cpu_state.cpu().to(torch.uint8))
        if torch.cuda.is_available() and "torch_cuda_rng_state" in state and state["torch_cuda_rng_state"] is not None:
            try:
                torch.cuda.set_rng_state_all([s.cpu().to(torch.uint8) for s in state["torch_cuda_rng_state"]])
            except Exception:
                pass
        logging.info(
            f"[RESUME] Retomando treinamento a partir da época {start_epoch} "
            f"(última concluída: {resumed_from_epoch}, melhor Val F1={best_val_f1:.4f} na época {best_epoch})."
        )

    train_wall_t0 = time.perf_counter()

    for epoch in range(start_epoch, epochs + 1):
        # 1. Passo de Treinamento (exclusivamente nos snapshots de treino)
        model.train()
        epoch_train_loss = 0.0
        epoch_train_nodes = 0

        for batch in train_loader:
            batch = batch.to(device)
            n_b = int(batch.x.size(0))
            if n_b == 0:
                continue
            optimizer.zero_grad()
            train_logits = _forward_train_batch(model, batch)
            train_loss = criterion(train_logits, batch.y.float())
            train_loss.backward()
            optimizer.step()

            epoch_train_loss += float(train_loss.item()) * n_b
            epoch_train_nodes += n_b

        avg_train_loss = epoch_train_loss / max(1, epoch_train_nodes)

        # 2. Passo de Validação (NOVO forward pass agregando todos os snapshots de val; test NÃO é tocado)
        val_loss, val_metrics, _, _, _ = evaluate_snapshots(
            model, val_loader, criterion, device, num_snapshots=len(val_list)
        )
        val_f1 = float(val_metrics["f1_score"])

        scheduler.step(val_f1)

        epoch_history.append(
            {
                "epoch": epoch,
                "train_loss": round(avg_train_loss, 6),
                "val_loss": round(val_loss, 6),
                "val_precision": val_metrics["precision"],
                "val_recall": val_metrics["recall"],
                "val_f1": val_metrics["f1_score"],
                "val_fpr": val_metrics["fpr"],
            }
        )

        logging.info(
            f"Época {epoch:03d}/{epochs} | Train Loss: {avg_train_loss:.4f} | "
            f"Val Loss: {val_loss:.4f} | Val F1: {val_f1:.4f} | "
            f"Val Prec: {val_metrics['precision']:.4f} | Val Rec: {val_metrics['recall']:.4f} | "
            f"Val FPR: {val_metrics['fpr']:.4f}"
        )

        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_val_metrics = val_metrics
            best_epoch = epoch
            epochs_no_improve = 0
            torch.save(model.state_dict(), checkpoint_out)
        else:
            epochs_no_improve += 1

        # Salvar estado periódico completo para retomada segura em caso de queda da sessão Colab/SSH
        if save_every > 0 and (epoch % save_every == 0 or epoch == epochs):
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "scheduler_state_dict": scheduler.state_dict(),
                    "best_val_f1": best_val_f1,
                    "best_val_metrics": best_val_metrics,
                    "best_epoch": best_epoch,
                    "epochs_no_improve": epochs_no_improve,
                    "epoch_history": epoch_history,
                    "seed": seed,
                    "python_rng_state": random.getstate(),
                    "numpy_rng_state": np.random.get_state(),
                    "torch_cpu_rng_state": torch.get_rng_state(),
                    "torch_cuda_rng_state": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
                },
                resume_state_out,
            )

        if epochs_no_improve >= patience:
            logging.info(
                f"Early Stopping acionado na época {epoch} (baseado na Validação). "
                f"Melhor época: {best_epoch} (Val F1={best_val_f1:.4f})."
            )
            break

    training_wall_time_sec = round(max(0.0, time.perf_counter() - train_wall_t0), 4)

    # 3. Recarregar o melhor checkpoint escolhido na Validação
    state_dict = torch.load(checkpoint_out, map_location=device, weights_only=True)
    model.load_state_dict(state_dict)

    _, best_val_eval_metrics, y_val_true, y_val_pred, val_latency = evaluate_snapshots(
        model, val_loader, criterion, device, num_snapshots=len(val_list)
    )
    if not best_val_metrics:
        best_val_metrics = best_val_eval_metrics

    val_node_group_metrics = compute_heterophily_and_node_group_metrics(orig_val_list, y_val_pred)

    if val_only:
        logging.info(
            f"[VAL-ONLY MODE] Melhor Época: {best_epoch} | Val Acc: {best_val_metrics['accuracy']:.4f} | "
            f"Val Prec: {best_val_metrics['precision']:.4f} | Val Rec: {best_val_metrics['recall']:.4f} | "
            f"Val F1: {best_val_metrics['f1_score']:.4f} | Val FPR: {best_val_metrics['fpr']:.4f} | "
            f"Val Latência: {val_latency['ms_per_snapshot']:.3f} ms/snapshot ({val_latency['us_per_node']:.2f} us/nó) | "
            f"Tempo Treino: {training_wall_time_sec:.2f}s | Val CM: {best_val_metrics['confusion_matrix']}"
        )
        logging.info("[VAL-ONLY MODE] Avaliação do conjunto de teste reservado ignorada para preservar isolamento experimental.")
        test_loss = None
        test_metrics = None
        y_test_true = np.zeros((0,), dtype=np.int64)
        y_test_pred = np.zeros((0,), dtype=np.int64)
        test_latency = None
    else:
        test_loss, test_metrics, y_test_true, y_test_pred, test_latency = evaluate_snapshots(
            model, test_loader, criterion, device, num_snapshots=len(test_list)
        )
        logging.info(
            f"[TESTE RESERVADO / HELD-OUT] Acc: {test_metrics['accuracy']:.4f} | "
            f"Prec: {test_metrics['precision']:.4f} | Rec: {test_metrics['recall']:.4f} | "
            f"F1: {test_metrics['f1_score']:.4f} | FPR: {test_metrics['fpr']:.4f} | "
            f"Latência: {test_latency['ms_per_snapshot']:.3f} ms/snapshot ({test_latency['us_per_node']:.2f} us/nó) | "
            f"CM: {test_metrics['confusion_matrix']}"
        )

    return {
        "model_variant": effective_variant,
        "val_only": bool(val_only),
        "best_epoch": best_epoch,
        "resumed_from_epoch": resumed_from_epoch,
        "training_wall_time_sec": training_wall_time_sec,
        "validation_best": best_val_metrics,
        "validation_node_group_metrics": val_node_group_metrics,
        "epoch_history": epoch_history,
        "validation_latency": val_latency,
        "y_val_true": y_val_true,
        "y_val_pred": y_val_pred,
        "test_held_out": test_metrics,
        "test_latency": test_latency,
        "test_loss": round(test_loss, 6) if test_loss is not None else None,
        "y_test_true": y_test_true,
        "y_test_pred": y_test_pred,
        "graph_stats": {
            "train": edge_statistics(train_list),
            "val": edge_statistics(val_list),
            "test": edge_statistics(test_list),
        },
    }


def get_git_commit() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


def main():
    args = parse_args()
    set_deterministic_seed(args.seed)
    device = torch.device(args.device)
    logging.info(f"Treinamento iniciado em {device.type.upper()} | Seed: {args.seed}")

    raw_obj = torch.load(args.data_path, map_location=device, weights_only=False)
    train_list, val_list, test_list, meta = load_or_split_graphs(raw_obj, device, args.seed)

    logging.info(
        f"Snapshots carregados ({meta.get('protocol')}) | "
        f"Treino: {edge_statistics(train_list)} | Val: {edge_statistics(val_list)} | Teste: {edge_statistics(test_list)}"
    )

    result = train_and_evaluate(
        train_g=train_list,
        val_g=val_list,
        test_g=test_list,
        epochs=args.epochs,
        lr=args.lr,
        patience=args.patience,
        seed=args.seed,
        device=device,
        checkpoint_out=args.checkpoint_out,
        ablation_no_graph=args.ablation_no_graph,
        model_variant=args.model_variant,
        val_only=args.val_only,
        batch_size=args.batch_size,
        resume=args.resume,
        resume_state_out=args.resume_state_out,
        save_every=args.save_every,
    )

    if args.val_only and len(result["y_val_true"]) > 0:
        save_confusion_matrix(result["y_val_true"], result["y_val_pred"], save_path=args.cm_out)
    elif not args.val_only and len(result["y_test_true"]) > 0:
        save_confusion_matrix(result["y_test_true"], result["y_test_pred"], save_path=args.cm_out)

    gpu_name = torch.cuda.get_device_name(0) if (device.type == "cuda" and torch.cuda.is_available()) else None
    report = {
        "git_commit": get_git_commit(),
        "dataset_sha256": args.dataset_sha256 or (raw_obj.get("dataset_sha256") if isinstance(raw_obj, dict) else None),
        "seed": args.seed,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "device": str(device),
        "gpu_name": gpu_name,
        "torch_version": torch.__version__,
        "data_path": str(args.data_path),
        "protocol": meta.get("protocol"),
        "feature_scope": meta.get("feature_scope"),
        "window_sec": meta.get("window_sec"),
        "model_variant": result["model_variant"],
        "ablation_no_graph": bool(args.ablation_no_graph),
        "val_only": bool(args.val_only),
        "top_features": meta.get("top_features", []),
        "split_rows": meta.get("split_rows", {}),
        "graph_stats": result["graph_stats"],
        "best_epoch": result["best_epoch"],
        "best_epoch_on_validation": result["best_epoch"],
        "resumed_from_epoch": result["resumed_from_epoch"],
        "training_wall_time_sec": result["training_wall_time_sec"],
        "validation_metrics": result["validation_best"],
        "validation_node_group_metrics": result["validation_node_group_metrics"],
        "epoch_history": result["epoch_history"],
        "validation_latency": result["validation_latency"],
        "held_out_test_metrics": result["test_held_out"],
        "inference_latency": result["test_latency"],
        "test_mask_used_in_scheduler_or_checkpoint": False,
        "fresh_eval_forward_after_optimizer_step": True,
    }

    report_path = Path(args.report_out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logging.info(f"Relatório de avaliação auditável salvo em: {report_path}")


if __name__ == "__main__":
    main()
