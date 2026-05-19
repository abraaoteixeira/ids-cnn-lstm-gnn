"""
preprocessor.py

Pipeline de engenharia de features e construção de grafo STGNN.

Funcionalidades:
 - One-Hot Encoding para 'protocol_type', 'service', 'flag'
 - Cálculo da correlação de Pearson com a label 'target' e seleção automática das Top-20 features
 - Persistência da lista Top-20 em JSON
 - Construção de um torch_geometric.data.Data com x: [num_nodes, seq_len, 20]
 - Função `generate_test_sample()` para validar o pipeline com dados sintéticos

Salva o grafo em `data/processed/network_graph.pt` e o ficheiro de features em `data/processed/top20_features.json`.
"""
import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler

try:
    from torch_geometric.data import Data
except Exception as e:
    raise RuntimeError("torch_geometric não encontrado. Instale conforme o README.") from e

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


PROCESSED_DIR = Path('data') / 'processed'
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def _map_target_to_binary(series: pd.Series) -> pd.Series:
    # Converte labels textuais para binário: 0 = normal/benign, 1 = ataque
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(int)
    s = series.astype(str).str.lower().str.strip()
    benign = set(['normal', 'normal.', 'benign', 'benign.','0'])
    return (~s.isin(benign)).astype(int)


def one_hot_encode(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    present = [c for c in cols if c in df.columns]
    if not present:
        logging.info('Nenhuma coluna categórica para one-hot encoding encontrada.')
        return df
    logging.info(f'Aplicando One-Hot Encoding às colunas: {present}')
    df = pd.get_dummies(df, columns=present, prefix=present, drop_first=False)
    return df


def select_topk_pearson(df: pd.DataFrame, target_col: str, k: int = 20) -> List[str]:
    if target_col not in df.columns:
        raise KeyError(f"target_col '{target_col}' não encontrado no DataFrame")
    logging.info('Convertendo target para binário (se necessário)')
    df[target_col] = _map_target_to_binary(df[target_col])

    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    if target_col in numeric:
        numeric.remove(target_col)
    if not numeric:
        raise ValueError('Nenhuma coluna numérica disponível para correlação.')

    logging.info('Calculando correlações de Pearson (absolutas) com o target...')
    corrs = df[numeric].corrwith(df[target_col]).abs()
    corrs = corrs.sort_values(ascending=False)
    topk = corrs.head(k).index.tolist()
    logging.info(f'Top-{len(topk)} features selecionadas: {topk}')
    return topk


def build_graph(
    df: pd.DataFrame,
    top_features: List[str],
    seq_len: int = 10,
    time_col: Optional[str] = None,
    src_cols_priority: List[str] = None,
    dst_cols_priority: List[str] = None,
) -> Data:
    """
    Constroi um grafo PyG com x: [num_nodes, seq_len, len(top_features)].

    Lógica de identificação de nós:
      - Procura colunas típicas: src_ip, src, source, src_host
      - Idem para destino
      - Se não houver colunas de origem/destino, cria nós por índice de linha e liga linhas consecutivas
    """
    if src_cols_priority is None:
        src_cols_priority = ['src_ip', 'src', 'source', 'src_host', 'source_ip']
    if dst_cols_priority is None:
        dst_cols_priority = ['dst_ip', 'dst', 'destination', 'dst_host', 'dest_ip']

    # selecionar coluna src/dst disponível
    src_col = next((c for c in src_cols_priority if c in df.columns), None)
    dst_col = next((c for c in dst_cols_priority if c in df.columns), None)

    logging.info(f'Usando src_col={src_col} dst_col={dst_col}')

    # Prepare features: extract top_features
    feat_df = df[top_features].fillna(0).copy()

    # Optionally standardize features across all node-time observations
    scaler = StandardScaler()
    flat = feat_df.values.astype(np.float32)
    logging.info('Ajustando StandardScaler nas features selecionadas...')
    flat_scaled = scaler.fit_transform(flat)
    feat_df.loc[:, :] = flat_scaled

    # Node mapping
    if src_col and dst_col:
        nodes = pd.unique(df[[src_col, dst_col]].values.ravel('K'))
        nodes = [n for n in nodes if pd.notna(n)]
        nodes = sorted(nodes)
        ip2idx = {ip: i for i, ip in enumerate(nodes)}
        num_nodes = len(ip2idx)
        logging.info(f'Encontrados {num_nodes} nós (IPs/hosts)')

        # For each node, keep a list of feature vectors in chronological/order appearance
        node_vectors = defaultdict(list)
        edge_counts = {}
        edge_attrs = {}
        node_labels = np.zeros((num_nodes,), dtype=np.int64)

        # iterate rows in time order if time_col given
        if time_col and time_col in df.columns:
            df_proc = df.sort_values(time_col).reset_index(drop=True)
        else:
            df_proc = df.reset_index(drop=True)

        for _, row in df_proc.iterrows():
            s = row[src_col]
            d = row[dst_col]
            if pd.isna(s) or pd.isna(d):
                continue
            s_idx = ip2idx.get(s)
            d_idx = ip2idx.get(d)
            feats = feat_df.loc[row.name].values.astype(np.float32)

            # append feature vector to both source and destination sequences
            node_vectors[s_idx].append(feats)
            node_vectors[d_idx].append(feats)

            # edge aggregation (directed)
            ekey = (s_idx, d_idx)
            if ekey not in edge_counts:
                edge_counts[ekey] = 0
                edge_attrs[ekey] = np.zeros((len(top_features),), dtype=np.float32)
            edge_counts[ekey] += 1
            edge_attrs[ekey] += feats

            # node label: if 'target' column exists and indicates anomaly -> mark node
            if 'target' in df_proc.columns:
                t = _map_target_to_binary(pd.Series([row['target']])).iloc[0]
                if t == 1:
                    node_labels[s_idx] = 1
                    node_labels[d_idx] = 1

        # Build node feature tensor with padding/truncation to seq_len
        num_feat = len(top_features)
        node_features = np.zeros((num_nodes, seq_len, num_feat), dtype=np.float32)
        for idx in range(num_nodes):
            vecs = node_vectors.get(idx, [])
            if len(vecs) == 0:
                continue
            # take last seq_len
            trunc = np.array(vecs[-seq_len:], dtype=np.float32)
            if trunc.shape[0] < seq_len:
                pad = np.zeros((seq_len - trunc.shape[0], num_feat), dtype=np.float32)
                arr = np.vstack([pad, trunc])
            else:
                arr = trunc
            node_features[idx] = arr

        # edges
        if len(edge_counts) == 0:
            edge_index = torch.empty((2, 0), dtype=torch.long)
            edge_attr = None
        else:
            edges = list(edge_counts.keys())
            edge_index = torch.tensor([[e[0] for e in edges], [e[1] for e in edges]], dtype=torch.long)
            edge_attr = torch.tensor([edge_attrs[e] / edge_counts[e] for e in edges], dtype=torch.float32)

        x = torch.tensor(node_features, dtype=torch.float32)
        y = torch.tensor(node_labels, dtype=torch.long)

        data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y=y)
        data.ip2idx = ip2idx
        data.idx2ip = {v: k for k, v in ip2idx.items()}
        data.scaler = scaler

        return data

    else:
        # Fallback: create nodes per row index and edges between consecutive rows
        logging.info('Nenhuma coluna src/dst encontrada — criando nós por índice de linha e ligando consecutivos')
        N = len(df)
        num_feat = len(top_features)
        node_features = np.zeros((N, seq_len, num_feat), dtype=np.float32)
        node_labels = np.zeros((N,), dtype=np.int64)

        for i, row in df.iterrows():
            feats = feat_df.loc[row.name].values.astype(np.float32)
            # place at last time step
            node_features[i, -1, :] = feats
            if 'target' in df.columns:
                node_labels[i] = _map_target_to_binary(pd.Series([row['target']])).iloc[0]

        # edges between consecutive nodes
        if N <= 1:
            edge_index = torch.empty((2, 0), dtype=torch.long)
            edge_attr = None
        else:
            src = np.arange(0, N - 1, dtype=np.int64)
            dst = np.arange(1, N, dtype=np.int64)
            edge_index = torch.tensor([src, dst], dtype=torch.long)
            edge_attr = None

        x = torch.tensor(node_features, dtype=torch.float32)
        y = torch.tensor(node_labels, dtype=torch.long)
        data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y=y)
        data.scaler = scaler
        data.ip2idx = {i: i for i in range(N)}
        data.idx2ip = {i: i for i in range(N)}
        return data


def generate_test_sample(out_csv: Optional[str] = None, n: int = 100) -> pd.DataFrame:
    """
    Gera um DataFrame sintético semelhante ao NSL-KDD com colunas:
    timestamp, src_ip, dst_ip, protocol_type, service, flag, f0..f19, target
    """
    import random
    from datetime import datetime, timedelta

    rows = []
    now = datetime.utcnow()
    proto_choices = ['tcp', 'udp', 'icmp']
    service_choices = ['http', 'ftp', 'ssh', 'dns']
    flag_choices = ['SF', 'S1', 'REJ']

    for i in range(n):
        ts = now + timedelta(seconds=i * 5)
        src = f"10.0.0.{random.randint(1,50)}"
        dst = f"10.0.1.{random.randint(1,50)}"
        proto = random.choice(proto_choices)
        service = random.choice(service_choices)
        flag = random.choice(flag_choices)
        feats = {f'f{j}': float(np.random.rand()) for j in range(20)}
        target = 1 if np.random.rand() < 0.1 else 0
        row = {
            'timestamp': ts,
            'src_ip': src,
            'dst_ip': dst,
            'protocol_type': proto,
            'service': service,
            'flag': flag,
            'target': target,
        }
        row.update(feats)
        rows.append(row)

    df = pd.DataFrame(rows)
    if out_csv:
        p = Path(out_csv)
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, index=False)
        logging.info(f'Sample CSV saved to {p}')
    return df


def parse_args():
    p = argparse.ArgumentParser(description='Preprocessor: One-Hot, Top-20 Pearson, Graph builder')
    p.add_argument('--input_csv', required=False, help='CSV de input (se omitido, usar generate_test_sample)')
    p.add_argument('--time_col', default=None, help='Coluna de tempo (opcional)')
    p.add_argument('--seq_len', type=int, default=10)
    p.add_argument('--target_col', default='target')
    p.add_argument('--output_pt', default=str(PROCESSED_DIR / 'network_graph.pt'))
    p.add_argument('--topk_json', default=str(PROCESSED_DIR / 'top20_features.json'))
    return p.parse_args()


def main():
    args = parse_args()
    logging.info('Preprocessor iniciado')

    if args.input_csv:
        df = pd.read_csv(args.input_csv)
    else:
        logging.info('Nenhum input_csv fornecido; a gerar amostra de teste...')
        df = generate_test_sample()

    # One-Hot
    df_enc = one_hot_encode(df, ['protocol_type', 'service', 'flag'])

    # Select top-20
    topk = select_topk_pearson(df_enc, args.target_col, k=20)
    # persistir lista
    with open(args.topk_json, 'w', encoding='utf-8') as f:
        json.dump(topk, f, indent=2)
    logging.info(f'Top-20 features guardadas em {args.topk_json}')

    # Build graph
    data = build_graph(df_enc, topk, seq_len=args.seq_len, time_col=args.time_col)

    # save
    out = Path(args.output_pt)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(data, str(out))
    logging.info(f'Grafo salvo em {out}')


if __name__ == '__main__':
    main()
