"""
evaluate_spectre.py

Script de Avaliação Científica e Benchmark de Latência para SPECTRE_GRID.
Calcula F1-Score, Acurácia, Precisão, Recall e Latência Média de Inferência.
"""
import os
import sys
import time
import json
import logging
import torch
import torch.nn as nn
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

from model import SPECTRE_GRID

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def evaluate():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logging.info(f"Executando avaliação empírica no dispositivo: {device}")

    # 1. Carregar o Grafo
    graph_path = "data/processed/network_graph.pt"
    if not os.path.exists(graph_path):
        logging.error(f"Grafo não encontrado em {graph_path}. Execute o preprocessor primeiro.")
        sys.exit(1)

    data = torch.load(graph_path, weights_only=False)
    data = data.to(device)
    num_nodes = data.x.shape[0]
    num_features = data.x.shape[2]
    seq_len = data.x.shape[1]

    logging.info(f"Grafo carregado | Nós: {num_nodes} | Arestas: {data.edge_index.shape[1]} | Features: {num_features} | SeqLen: {seq_len}")
    logging.info(f"Distribuição de rótulos (y): {torch.unique(data.y, return_counts=True)}")

    # 2. Divisão Oficial 80/20 (Treino/Validação vs Teste)
    torch.manual_seed(42)
    indices = torch.randperm(num_nodes)
    train_size = int(0.8 * num_nodes)
    
    train_mask = torch.zeros(num_nodes, dtype=torch.bool, device=device)
    test_mask = torch.zeros(num_nodes, dtype=torch.bool, device=device)
    train_mask[indices[:train_size]] = True
    test_mask[indices[train_size:]] = True

    # 3. Instanciar e Treinar Modelo
    model = SPECTRE_GRID(
        num_features=num_features,
        seq_len=seq_len,
        cnn_out_channels=32,
        lstm_hidden_size=64,
        gnn_hidden_size=64,
        gat_heads=4,
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=0.003, weight_decay=1e-4)
    criterion = nn.BCEWithLogitsLoss()

    logging.info("Treinando modelo para otimização de convergência...")
    model.train()
    best_loss = float('inf')
    for epoch in range(1, 101):
        optimizer.zero_grad()
        logits = model(data.x, data.edge_index)
        loss = criterion(logits[train_mask], data.y[train_mask].float())
        loss.backward()
        optimizer.step()

    # 4. Avaliação de Teste no Conjunto de 20%
    model.eval()
    
    # Medir Latência de Inferência (100 iterações)
    latencies = []
    with torch.no_grad():
        # Warmup
        for _ in range(10):
            _ = model(data.x, data.edge_index)

        # Benchmark
        for _ in range(100):
            start = time.perf_counter()
            logits = model(data.x, data.edge_index)
            end = time.perf_counter()
            latencies.append((end - start) * 1000.0)  # em ms

        probs = torch.sigmoid(logits)
        preds = (probs > 0.5).long()

    y_true = data.y[test_mask].cpu().numpy()
    y_pred = preds[test_mask].cpu().numpy()

    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    avg_latency = float(np.mean(latencies))

    logging.info("=" * 60)
    logging.info(" RESULTADOS EXPERIMENTAIS EMPÍRICOS (CONJUNTO DE TESTE 20%) ")
    logging.info("=" * 60)
    logging.info(f"Acurácia  (Accuracy) : {acc:.4f} ({acc * 100:.2f}%)")
    logging.info(f"Precisão  (Precision): {prec:.4f} ({prec * 100:.2f}%)")
    logging.info(f"Revocação (Recall)   : {rec:.4f} ({rec * 100:.2f}%)")
    logging.info(f"F1-Score             : {f1:.4f} ({f1 * 100:.2f}%)")
    logging.info(f"Latência Preditiva   : {avg_latency:.2f} ms por lote relacional")
    logging.info("=" * 60)

    # Salvar resultados em JSON
    results = {
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1_score": round(float(f1), 4),
        "latency_ms": round(avg_latency, 2),
        "test_nodes": int(test_mask.sum().item()),
        "train_nodes": int(train_mask.sum().item()),
    }

    with open("data/processed/benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Salvar o modelo (state_dict) para reutilização no C++ / Python daemon
    torch.save(model.state_dict(), "data/processed/best_model.pth")
    logging.info("Modelo PyTorch salvo em: data/processed/best_model.pth")
    logging.info("Resultados de benchmark salvos em: data/processed/benchmark_results.json")

    return results

if __name__ == "__main__":
    evaluate()
