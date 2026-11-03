"""
train.py
Motor de treino STGNN livre de vazamento de dados (Leakage-Free):
 - Particionamento disjunto em 3 vias: Treino (60%), Validação (20%) e Teste Reservado (20%).
 - Sementes aleatórias fixadas para reprodutibilidade científica.
 - Novo forward pass em `model.eval()` APÓS `optimizer.step()` (nunca reutiliza logits pré-gradiente).
 - LR Scheduler e Early Stopping guiados EXCLUSIVAMENTE pelo F1 do conjunto de Validação.
 - Conjunto de Teste avaliado uma única vez ao final, após recarregar o melhor checkpoint de validação.
 - Registro completo de Precision, Recall, F1-Score, False Positive Rate (FPR) e Matriz de Confusão.
"""

import argparse
import json
import logging
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
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

from model import SPECTRE_GRID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def set_deterministic_seed(seed: int = 42) -> None:
    """Fixa sementes de Python, NumPy e PyTorch para reprodutibilidade."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_args():
    parser = argparse.ArgumentParser(description="Treino Reprodutível e Sem Vazamento do IDS STGNN")
    parser.add_argument("--data_path", required=True, help="Caminho para o arquivo de grafos (.pt)")
    parser.add_argument("--epochs", type=int, default=30, help="Número de épocas")
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
        "--report_out",
        default="data/processed/clean_evaluation_report.json",
        help="Relatório JSON auditável com métricas de validação e teste reservado",
    )
    parser.add_argument(
        "--cm_out",
        default="data/processed/confusion_matrix_clean.png",
        help="Caminho para salvar a Matriz de Confusão do teste reservado",
    )
    parser.add_argument(
        "--ablation_no_graph",
        action="store_true",
        help="Substitui arestas entre hosts por apenas auto-loops (avalia CNN+LSTM sem contexto relacional)",
    )
    return parser.parse_args()


def save_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, save_path: str) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    plt.figure(figsize=(6, 5))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=["Normal (0)", "Ataque (1)"],
        yticklabels=["Normal (0)", "Ataque (1)"],
    )
    plt.ylabel("Rótulo Verdadeiro")
    plt.xlabel("Previsão do Modelo")
    plt.title("Matriz de Confusão - Teste Reservado (Held-Out)")
    plt.tight_layout()

    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    plt.savefig(save_path)
    plt.close()
    logging.info(f"Matriz de Confusão salva em: {save_path}")


def extract_induced_subgraph(data: Data, node_indices: torch.Tensor) -> Data:
    """
    Extrai um subgrafo induzido contendo apenas os nós selecionados e as arestas
    cujos dois extremos pertencem a esse subconjunto (impede vazamento transdutivo).
    """
    node_indices = node_indices.long()
    num_total = data.x.shape[0]
    mapping = torch.full((num_total,), -1, dtype=torch.long, device=data.x.device)
    mapping[node_indices] = torch.arange(node_indices.numel(), dtype=torch.long, device=data.x.device)

    x_sub = data.x[node_indices]
    y_sub = data.y[node_indices]

    if data.edge_index.numel() > 0:
        src, dst = data.edge_index[0], data.edge_index[1]
        valid_edges = (mapping[src] >= 0) & (mapping[dst] >= 0)
        edge_index_sub = torch.stack([mapping[src[valid_edges]], mapping[dst[valid_edges]]], dim=0)
    else:
        edge_index_sub = torch.empty((2, 0), dtype=torch.long, device=data.x.device)

    return Data(x=x_sub, edge_index=edge_index_sub, y=y_sub)


def load_or_split_graphs(raw_obj: object, device: torch.device, seed: int) -> Tuple[Data, Data, Data, Dict[str, object]]:
    """
    Carrega as 3 partições indutivas (train/val/test) ou, caso receba um único grafo legado,
    particiona os nós em 3 subgrafos induzidos disjuntos (60% / 20% / 20%).
    """
    meta: Dict[str, object] = {}
    if isinstance(raw_obj, dict) and "train" in raw_obj and "val" in raw_obj and "test" in raw_obj:
        train_g = raw_obj["train"].to(device)
        val_g = raw_obj["val"].to(device)
        test_g = raw_obj["test"].to(device)
        meta["protocol"] = raw_obj.get("protocol", "inductive_bundle")
        meta["top_features"] = raw_obj.get("top_features", [])
        meta["split_rows"] = raw_obj.get("split_rows", {})
        return train_g, val_g, test_g, meta

    if isinstance(raw_obj, Data):
        data = raw_obj.to(device)
        num_nodes = data.x.shape[0]
        g = torch.Generator()
        g.manual_seed(seed)
        perm = torch.randperm(num_nodes, generator=g).to(device)

        n_train = max(1, int(0.60 * num_nodes))
        n_val = max(1, int(0.20 * num_nodes))
        if n_train + n_val >= num_nodes:
            n_train = max(1, num_nodes - 2)
            n_val = 1

        train_idx = perm[:n_train]
        val_idx = perm[n_train : n_train + n_val]
        test_idx = perm[n_train + n_val :]

        train_g = extract_induced_subgraph(data, train_idx)
        val_g = extract_induced_subgraph(data, val_idx)
        test_g = extract_induced_subgraph(data, test_idx)
        meta["protocol"] = "induced_subgraph_60_20_20"
        meta["top_features"] = getattr(data, "top_features", [])
        return train_g, val_g, test_g, meta

    raise TypeError(f"Formato de dados não suportado em --data_path: {type(raw_obj)}")


def edge_statistics(graph: Data) -> Dict[str, int]:
    """Contabiliza total de nós, arestas totais, auto-loops e arestas reais entre hosts distintos."""
    n_nodes = int(graph.x.shape[0])
    if graph.edge_index.numel() == 0:
        return {"nodes": n_nodes, "total_edges": 0, "self_loops": 0, "cross_host_edges": 0}
    src, dst = graph.edge_index[0], graph.edge_index[1]
    total = int(src.numel())
    self_loops = int((src == dst).sum().item())
    cross_host = int((src != dst).sum().item())
    return {
        "nodes": n_nodes,
        "total_edges": total,
        "self_loops": self_loops,
        "cross_host_edges": cross_host,
    }


def apply_self_loop_only(graph: Data) -> Data:
    """Usado em estudos de ablação: remove arestas entre hosts distintos, mantendo apenas auto-loops."""
    n = graph.x.shape[0]
    idx = torch.arange(n, dtype=torch.long, device=graph.x.device)
    edge_index = torch.stack([idx, idx], dim=0)
    return Data(x=graph.x, edge_index=edge_index, y=graph.y)


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
def evaluate_graph(model: nn.Module, graph: Data, criterion: nn.Module) -> Tuple[float, Dict[str, object], np.ndarray, np.ndarray]:
    """
    Executa um NOVO forward pass em modo `model.eval()` sobre o grafo informado.
    Nunca reutiliza logits calculados antes do `optimizer.step()`.
    """
    model.eval()
    logits = model(graph.x, graph.edge_index)
    loss = float(criterion(logits, graph.y.float()).item())
    probs = torch.sigmoid(logits)
    preds = (probs >= 0.5).long()

    y_true = graph.y.detach().cpu().numpy()
    y_pred = preds.detach().cpu().numpy()
    metrics = compute_classification_metrics(y_true, y_pred)
    return loss, metrics, y_true, y_pred


def train_and_evaluate(
    train_g: Data,
    val_g: Data,
    test_g: Data,
    epochs: int = 30,
    lr: float = 0.001,
    patience: int = 7,
    seed: int = 42,
    device: Optional[torch.device] = None,
    checkpoint_out: str = "data/processed/best_model_clean.pth",
    ablation_no_graph: bool = False,
) -> Dict[str, object]:
    """
    Executa o ciclo completo de treinamento guiado por validação e avaliação única no teste reservado.
    """
    set_deterministic_seed(seed)
    if device is None:
        device = train_g.x.device

    if ablation_no_graph:
        train_g = apply_self_loop_only(train_g)
        val_g = apply_self_loop_only(val_g)
        test_g = apply_self_loop_only(test_g)

    model = SPECTRE_GRID(
        num_features=train_g.x.shape[2],
        seq_len=train_g.x.shape[1],
        cnn_out_channels=32,
        lstm_hidden_size=64,
        gnn_hidden_size=64,
        gat_heads=4,
    ).to(device)

    # Calcula pos_weight apenas no conjunto de treino para lidar com desbalanceamento
    n_pos = float((train_g.y == 1).sum().item())
    n_neg = float((train_g.y == 0).sum().item())
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

    os.makedirs(os.path.dirname(checkpoint_out) or ".", exist_ok=True)

    for epoch in range(1, epochs + 1):
        # 1. Passo de Treinamento (exclusivamente em train_g)
        model.train()
        optimizer.zero_grad()
        train_logits = model(train_g.x, train_g.edge_index)
        train_loss = criterion(train_logits, train_g.y.float())
        train_loss.backward()
        optimizer.step()

        # 2. Passo de Validação (NOVO forward pass em val_g após atualização dos pesos; test_g NÃO é tocado)
        val_loss, val_metrics, _, _ = evaluate_graph(model, val_g, criterion)
        val_f1 = float(val_metrics["f1_score"])

        scheduler.step(val_f1)

        logging.info(
            f"Época {epoch:03d}/{epochs} | Train Loss: {train_loss.item():.4f} | "
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
            if epochs_no_improve >= patience:
                logging.info(
                    f"Early Stopping acionado na época {epoch} (baseado na Validação). "
                    f"Melhor época: {best_epoch} (Val F1={best_val_f1:.4f})."
                )
                break

    # 3. Recarregar o melhor checkpoint escolhido na Validação e avaliar o Teste Reservado UMA ÚNICA VEZ
    state_dict = torch.load(checkpoint_out, map_location=device, weights_only=True)
    model.load_state_dict(state_dict)
    test_loss, test_metrics, y_test_true, y_test_pred = evaluate_graph(model, test_g, criterion)

    logging.info(
        f"[TESTE RESERVADO / HELD-OUT] Acc: {test_metrics['accuracy']:.4f} | "
        f"Prec: {test_metrics['precision']:.4f} | Rec: {test_metrics['recall']:.4f} | "
        f"F1: {test_metrics['f1_score']:.4f} | FPR: {test_metrics['fpr']:.4f} | "
        f"CM: {test_metrics['confusion_matrix']}"
    )

    return {
        "best_epoch": best_epoch,
        "validation_best": best_val_metrics,
        "test_held_out": test_metrics,
        "test_loss": round(test_loss, 6),
        "y_test_true": y_test_true,
        "y_test_pred": y_test_pred,
        "graph_stats": {
            "train": edge_statistics(train_g),
            "val": edge_statistics(val_g),
            "test": edge_statistics(test_g),
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
    train_g, val_g, test_g, meta = load_or_split_graphs(raw_obj, device, args.seed)

    logging.info(
        f"Partições carregadas ({meta.get('protocol')}) | "
        f"Treino: {edge_statistics(train_g)} | Val: {edge_statistics(val_g)} | Teste: {edge_statistics(test_g)}"
    )

    result = train_and_evaluate(
        train_g=train_g,
        val_g=val_g,
        test_g=test_g,
        epochs=args.epochs,
        lr=args.lr,
        patience=args.patience,
        seed=args.seed,
        device=device,
        checkpoint_out=args.checkpoint_out,
        ablation_no_graph=args.ablation_no_graph,
    )

    save_confusion_matrix(result["y_test_true"], result["y_test_pred"], save_path=args.cm_out)

    report = {
        "git_commit": get_git_commit(),
        "seed": args.seed,
        "data_path": str(args.data_path),
        "protocol": meta.get("protocol"),
        "ablation_no_graph": bool(args.ablation_no_graph),
        "top_features": meta.get("top_features", []),
        "split_rows": meta.get("split_rows", {}),
        "graph_stats": result["graph_stats"],
        "best_epoch_on_validation": result["best_epoch"],
        "validation_metrics": result["validation_best"],
        "held_out_test_metrics": result["test_held_out"],
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
