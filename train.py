"""
train.py
Motor de treino STGNN com Early Stopping, LR Scheduler e Matriz de Confusão.
"""

import argparse
import logging
import sys
import os
import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

from model import SPECTRE_GRID

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.StreamHandler(sys.stdout)])

def parse_args():
    parser = argparse.ArgumentParser(description="Treino do IDS STGNN")
    parser.add_argument("--data_path", required=True, help="Caminho para o grafo (.pt)")
    parser.add_argument("--epochs", type=int, default=50, help="Número de épocas")
    parser.add_argument("--lr", type=float, default=0.001, help="Taxa de aprendizado")
    parser.add_argument("--batch_size", type=int, default=1, help="Batch size (nós agrupados)")
    parser.add_argument("--patience", type=int, default=7, help="Paciência do Early Stopping")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu", help="cuda/cpu")
    return parser.parse_args()

def save_confusion_matrix(y_true, y_pred, save_path="data/processed/confusion_matrix.png"):
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(6,5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=['Normal', 'Ataque'], yticklabels=['Normal', 'Ataque'])
    plt.ylabel('Rótulo Verdadeiro')
    plt.xlabel('Previsão do Modelo')
    plt.title('Matriz de Confusão - IDS')
    plt.tight_layout()
    
    # Garantir que a pasta existe antes de salvar
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path)
    plt.close()
    logging.info(f"Matriz de Confusão salva em: {save_path}")

def main():
    args = parse_args()
    device = torch.device(args.device)
    logging.info(f"Ambiente iniciado no dispositivo: {device.type.upper()}")

    # 1. Carregar os dados
    try:
        data = torch.load(args.data_path, map_location=device, weights_only=False)
        logging.info(f"Grafo carregado | Nós: {data.x.shape[0]} | Arestas: {data.edge_index.shape[1]}")
    except Exception as e:
        logging.error(f"Erro ao carregar os dados: {e}")
        sys.exit(1)

    num_nodes = data.x.shape[0]
    indices = torch.randperm(num_nodes)
    train_size = int(0.8 * num_nodes)
    
    train_mask = torch.zeros(num_nodes, dtype=torch.bool)
    test_mask = torch.zeros(num_nodes, dtype=torch.bool)
    train_mask[indices[:train_size]] = True
    test_mask[indices[train_size:]] = True

    # 2. Instanciar Modelo
    model = SPECTRE_GRID(
        num_features=data.x.shape[2],
        seq_len=data.x.shape[1],
        cnn_out_channels=32,
        lstm_hidden_size=64,
        gnn_hidden_size=64,
        gat_heads=4,
    ).to(device)
    
    # 3. Otimizador e Loss (BCEWithLogitsLoss é o correto para a arquitetura atual)
    optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)
    criterion = nn.BCEWithLogitsLoss()
    
    # LR Scheduler: Reduz a taxa de aprendizado se o F1 parar de melhorar
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=3, verbose=True)

    best_f1 = 0.0
    epochs_no_improve = 0

    logging.info("Iniciando Treinamento...")
    for epoch in range(1, args.epochs + 1):
        model.train()
        optimizer.zero_grad()
        
        logits = model(data.x, data.edge_index)
        
        loss = criterion(logits[train_mask], data.y[train_mask].float())
        loss.backward()
        optimizer.step()

        # 4. Avaliação
        model.eval()
        with torch.no_grad():
            # APLICAR SIGMOID ANTES DE AVALIAR
            probs = torch.sigmoid(logits)
            preds = (probs > 0.5).long()
            
            y_true = data.y[test_mask].cpu().numpy()
            y_pred = preds[test_mask].cpu().numpy()
            
            if len(set(y_true)) > 1: 
                acc = accuracy_score(y_true, y_pred)
                prec = precision_score(y_true, y_pred, zero_division=0)
                rec = recall_score(y_true, y_pred, zero_division=0)
                f1 = f1_score(y_true, y_pred, zero_division=0)
            else:
                acc, prec, rec, f1 = 0.0, 0.0, 0.0, 0.0

        scheduler.step(f1)

        logging.info(f"Época {epoch:03d}/{args.epochs} | Loss: {loss.item():.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f}")

        # 5. Early Stopping e Save Model
        if f1 > best_f1:
            best_f1 = f1
            epochs_no_improve = 0
            torch.save(model.state_dict(), "data/processed/best_model.pth")
            
            # Atualiza a matriz de confusão apenas quando encontra um modelo melhor
            save_confusion_matrix(y_true, y_pred)
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= args.patience:
                logging.warning(f"Early Stopping ativado na época {epoch}. Sem melhoria há {args.patience} épocas.")
                break

    logging.info(f"Treinamento concluído. Melhor F1-Score: {best_f1:.4f}")

if __name__ == "__main__":
    main()