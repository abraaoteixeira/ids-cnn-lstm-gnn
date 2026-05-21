import argparse
import json
import logging
import sys
from pathlib import Path
import torch
import pandas as pd
import numpy as np
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


def format_alerts(probs: torch.Tensor):
    print("\n" + "=" * 60)
    print(" ALERTAS DE CIBERSEGURANÇA EM TEMPO REAL ")
    print("=" * 60)
    for i, p in enumerate(probs):
        prob_pct = float(p.item() * 100)
        status = "[ALERTA CRÍTICO]" if prob_pct > 70 else "[INFO]"
        color = "\033[91m" if prob_pct > 70 else "\033[94m"
        reset = "\033[0m"
        print(f"{color}{status} Fluxo {i} | Probabilidade de Intrusão: {prob_pct:.2f}%{reset}")
    print("=" * 60 + "\n")


def run_inference(csv_path: str | None, model_path: str, features_path: str | None, device_str: str = None):
    device = torch.device(device_str if device_str else ('cuda' if torch.cuda.is_available() else 'cpu'))

    # load top features if provided (not required for dry-run)
    top_features = None
    if features_path:
        try:
            with open(features_path, 'r') as f:
                top_features = json.load(f)
        except Exception:
            logger.warning(f"Não foi possível carregar features de {features_path}. Seguindo com dados mock.")

    model, mode = load_model_flexible(model_path, device)

    # Prepare mock data (dry-run: não executar, apenas estrutura)
    # In production the preprocessor would build `x` and `edge_index` from `csv_path`
    N = 5
    seq_len = 10
    num_features = 20

    mock_data_x = torch.randn(N, seq_len, num_features, device=device)
    mock_edges = torch.tensor([[i for i in range(N-1)], [i+1 for i in range(N-1)]], dtype=torch.long, device=device)

    with torch.no_grad():
        if mode == 'scripted':
            logits = model(mock_data_x, mock_edges)
        else:
            logits = model(mock_data_x, mock_edges)

        probs = torch.sigmoid(logits)

    format_alerts(probs)


def parse_args():
    p = argparse.ArgumentParser(description='Inferência flexível SPECTRE_GRID (suporta .pt TorchScript ou .pth state_dict)')
    p.add_argument('--data', dest='csv_path', required=False, help='CSV de tráfego (opcional)')
    p.add_argument('--model', dest='model_path', required=True, help='Caminho para o modelo (.pt ou .pth)')
    p.add_argument('--features', dest='features_path', required=False, help='JSON com top features (opcional)')
    p.add_argument('--device', dest='device', required=False, help='cuda|cpu (opcional)')
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    try:
        run_inference(args.csv_path, args.model_path, args.features_path, args.device)
    except Exception as e:
        logger.error(f"Erro na inferência (DRY-RUN): {e}")
        sys.exit(1)
