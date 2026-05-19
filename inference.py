"""
inference.py

Inferência flexível SPECTRE_GRID.
- Com --data: constrói grafo real via preprocessor.py e executa inferência nos nós reais.
- Sem --data: dry-run com dados mock (demonstrativo).

Suporta modelos TorchScript (.pt) e state_dict (.pth).
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import torch

from model import SPECTRE_GRID


# Configuração de Logging Profissional
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("IDS-Inference")


def load_model_flexible(model_path: str, device: torch.device, num_features: int = 20, seq_len: int = 10):
    """
    Tentativa flexível de carregar um modelo. Prioriza TorchScript se o ficheiro for um módulo scriptado,
    caso contrário instancia `SPECTRE_GRID` e carrega o `state_dict`.
    """
    p = Path(model_path)
    if not p.exists():
        raise FileNotFoundError(f"Modelo não encontrado: {model_path}")

    # Try to load as TorchScript first
    try:
        module = torch.jit.load(str(p), map_location=device)
        logger.info(f"Modelo TorchScript carregado: {p}")
        return module, 'scripted'
    except Exception:
        logger.info("Não é um TorchScript válido — tentando carregar state_dict como modelo Python.")

    # Fallback: instantiate python model and load state_dict
    model = SPECTRE_GRID(num_features=num_features, seq_len=seq_len).to(device)
    state = torch.load(str(p), map_location=device)
    # Support for saving either full state_dict or full model
    if isinstance(state, dict):
        model.load_state_dict(state)
    else:
        # assume saved state_dict or scripted model — try load_state_dict anyway
        try:
            model.load_state_dict(state.state_dict())
        except Exception:
            raise RuntimeError("Formato de ficheiro desconhecido para model_path")

    model.eval()
    logger.info(f"Modelo PyTorch (state_dict) carregado: {p}")
    return model, 'python'


def format_alerts_by_ip(probs: torch.Tensor, idx2ip: dict):
    """
    Exibe alertas de cibersegurança com IPs reais da topologia de rede.
    """
    print("\n" + "=" * 70)
    print("  ALERTAS DE CIBERSEGURANÇA — SPECTRE_GRID (DADOS REAIS)")
    print("=" * 70)

    # Separar ameaças e tráfego normal
    threats = []
    normals = []

    for i, p in enumerate(probs):
        prob_pct = float(p.item() * 100)
        ip_label = str(idx2ip.get(i, f"Nó {i}"))
        if prob_pct > 70:
            threats.append((ip_label, prob_pct))
        else:
            normals.append((ip_label, prob_pct))

    # Exibir ameaças primeiro (vermelho)
    if threats:
        print(f"\n  🛑 AMEAÇAS DETETADAS: {len(threats)}")
        print("  " + "-" * 66)
        for ip, prob in sorted(threats, key=lambda x: x[1], reverse=True):
            color = "\033[91m"  # vermelho
            reset = "\033[0m"
            severity = "CRÍTICO" if prob > 90 else "ALTO" if prob > 80 else "MÉDIO"
            print(f"  {color}[{severity:>7}] {ip:<40} → {prob:6.2f}%{reset}")

    # Resumo do tráfego normal
    if normals:
        print(f"\n  ✅ TRÁFEGO NORMAL: {len(normals)} nós")
        print("  " + "-" * 66)
        # Mostrar apenas os top-5 com maior probabilidade
        top_normals = sorted(normals, key=lambda x: x[1], reverse=True)[:5]
        for ip, prob in top_normals:
            color = "\033[94m"  # azul
            reset = "\033[0m"
            print(f"  {color}[   INFO] {ip:<40} → {prob:6.2f}%{reset}")
        if len(normals) > 5:
            print(f"  \033[90m  ... e mais {len(normals) - 5} nós com risco baixo\033[0m")

    print("\n" + "=" * 70)
    print(f"  RESUMO: {len(probs)} nós analisados | "
          f"{len(threats)} ameaças | {len(normals)} normais")
    print("=" * 70 + "\n")


def format_alerts_mock(probs: torch.Tensor):
    """
    Exibe alertas em modo dry-run (sem IPs reais — dados mock).
    """
    print("\n" + "=" * 60)
    print(" ALERTAS DE CIBERSEGURANÇA — DRY-RUN (DADOS MOCK) ")
    print("=" * 60)
    for i, p in enumerate(probs):
        prob_pct = float(p.item() * 100)
        status = "[ALERTA CRÍTICO]" if prob_pct > 70 else "[INFO]"
        color = "\033[91m" if prob_pct > 70 else "\033[94m"
        reset = "\033[0m"
        print(f"{color}{status} Fluxo {i} | Probabilidade de Intrusão: {prob_pct:.2f}%{reset}")
    print("=" * 60 + "\n")


def run_inference_real(csv_path: str, model_path: str, features_path: Optional[str],
                       device: torch.device, seq_len: int = 10, target_col: str = 'target'):
    """
    Inferência com dados reais: lê CSV → preprocessor → grafo PyG → modelo → alertas por IP.
    """
    from preprocessor import one_hot_encode, select_topk_pearson, build_graph

    logger.info(f"Carregando dataset real: {csv_path}")
    df = pd.read_csv(csv_path)
    logger.info(f"Dataset carregado: {len(df)} linhas × {len(df.columns)} colunas")

    # Detectar coluna target (compatibilidade NSL-KDD: 'class' ou 'target')
    if target_col not in df.columns:
        if 'class' in df.columns:
            df['target'] = df['class']
            logger.info("Coluna 'class' mapeada para 'target'.")
        elif 'label' in df.columns:
            df['target'] = df['label']
            logger.info("Coluna 'label' mapeada para 'target'.")
        else:
            logger.warning("Nenhuma coluna target encontrada. Usando target=0 para todos os nós.")
            df['target'] = 0

    # One-Hot Encoding
    df_enc = one_hot_encode(df, ['protocol_type', 'service', 'flag'])

    # Selecionar Top-20 features (ou carregar de JSON se fornecido)
    if features_path and Path(features_path).exists():
        with open(features_path, 'r') as f:
            top_features = json.load(f)
        # Validar que as features existem no dataframe
        missing = [feat for feat in top_features if feat not in df_enc.columns]
        if missing:
            logger.warning(f"Features ausentes no dataset: {missing}. Recalculando Top-20...")
            top_features = select_topk_pearson(df_enc, 'target', k=20)
        else:
            logger.info(f"Top-20 features carregadas de {features_path}")
    else:
        top_features = select_topk_pearson(df_enc, 'target', k=20)
        logger.info(f"Top-20 features calculadas por Pearson: {top_features}")

    # Construir grafo
    time_col = 'timestamp' if 'timestamp' in df_enc.columns else None
    data = build_graph(df_enc, top_features, seq_len=seq_len, time_col=time_col)
    logger.info(f"Grafo construído: {data.x.shape[0]} nós | {data.edge_index.shape[1]} arestas")

    # Mover dados para device
    data.x = data.x.to(device)
    data.edge_index = data.edge_index.to(device)

    # Carregar modelo
    num_features = data.x.shape[2]
    model, mode = load_model_flexible(model_path, device, num_features=num_features, seq_len=seq_len)

    # Inferência
    with torch.no_grad():
        logits = model(data.x, data.edge_index)
        probs = torch.sigmoid(logits)

    # Exibir alertas com IPs reais
    idx2ip = getattr(data, 'idx2ip', {i: f"Nó {i}" for i in range(data.x.shape[0])})
    format_alerts_by_ip(probs, idx2ip)

    return probs, idx2ip


def run_inference_mock(model_path: str, device: torch.device):
    """
    Inferência dry-run com dados mock (demonstrativo).
    """
    model, mode = load_model_flexible(model_path, device)

    N = 5
    seq_len = 10
    num_features = 20

    mock_data_x = torch.randn(N, seq_len, num_features, device=device)
    mock_edges = torch.tensor(
        [[i for i in range(N - 1)], [i + 1 for i in range(N - 1)]],
        dtype=torch.long, device=device
    )

    with torch.no_grad():
        logits = model(mock_data_x, mock_edges)
        probs = torch.sigmoid(logits)

    format_alerts_mock(probs)

    return probs


def run_inference(csv_path: Optional[str], model_path: str, features_path: Optional[str],
                  device_str: str = None):
    """
    Ponto de entrada principal. Delega para inferência real ou mock conforme os argumentos.
    """
    device = torch.device(device_str if device_str else ('cuda' if torch.cuda.is_available() else 'cpu'))
    logger.info(f"Device: {device}")

    if csv_path:
        logger.info("Modo: INFERÊNCIA COM DADOS REAIS")
        return run_inference_real(csv_path, model_path, features_path, device)
    else:
        logger.info("Modo: DRY-RUN (dados mock)")
        return run_inference_mock(model_path, device)


def parse_args():
    p = argparse.ArgumentParser(
        description='Inferência SPECTRE_GRID — suporta dados reais (CSV) ou dry-run (mock)'
    )
    p.add_argument('--data', dest='csv_path', required=False,
                   help='CSV de tráfego (ex: data/raw/KDDTrain_compat.csv). Se omitido, executa dry-run.')
    p.add_argument('--model', dest='model_path', required=True,
                   help='Caminho para o modelo (.pt TorchScript ou .pth state_dict)')
    p.add_argument('--features', dest='features_path', required=False,
                   help='JSON com top features (ex: data/processed/top20_features.json). Se omitido, recalcula.')
    p.add_argument('--device', dest='device', required=False,
                   help='cuda|cpu (auto-detecta se omitido)')
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    try:
        run_inference(args.csv_path, args.model_path, args.features_path, args.device)
    except Exception as e:
        logger.error(f"Erro na inferência: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
