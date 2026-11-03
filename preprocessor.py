"""
preprocessor.py

Pipeline de engenharia de features e construção de grafos STGNN livre de vazamento de dados (Leakage-Free).

Protocolo Experimental Rigoroso:
 1. Particionamento temporal/sequencial disjunto (Treino 60% / Validação 20% / Teste 20%) ANTES de qualquer transformação aprendida.
 2. One-Hot Encoding ajustado no vocabulário de treino e alinhado em validação/teste.
 3. Seleção das Top-20 features (Correlação Linear de Pearson) calculada EXCLUSIVAMENTE no conjunto de treino.
 4. Padronização (StandardScaler) ajustada (fit) EXCLUSIVAMENTE no conjunto de treino e aplicada via transform() em validação e teste.
 5. Construção independente de grafos por partição (avaliação indutiva sem contaminação de arestas futuras):
    - Ordenação temporal prévia à extração matricial (corrige desalinhamento de índices).
    - Rotulagem restrita ao IP emissor do ataque (não contamina vítimas passivas com label=1).
    - Proibição de grafos sequenciais artificiais (i -> i+1) quando não há colunas de IP; modo tabular opcional usa apenas auto-loops (i -> i).
"""
import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler

try:
    from torch_geometric.data import Data
except Exception as e:
    raise RuntimeError("torch_geometric não encontrado. Instale conforme o README.") from e

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PROCESSED_DIR = Path("data") / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

UNSW_NB15_COLUMNS = [
    "srcip", "sport", "dstip", "dsport", "proto", "state", "dur", "sbytes", "dbytes",
    "sttl", "dttl", "sloss", "dloss", "service", "Sload", "Dload", "Spkts", "Dpkts",
    "swin", "dwin", "stcpb", "dtcpb", "smeansz", "dmeansz", "trans_depth", "res_bdy_len",
    "Sjit", "Djit", "Stime", "Ltime", "Sintpkt", "Dintpkt", "tcprtt", "synack", "ackdat",
    "is_sm_ips_ports", "ct_state_ttl", "ct_flw_http_mthd", "is_ftp_login", "ct_ftp_cmd",
    "ct_srv_src", "ct_srv_dst", "ct_dst_ltm", "ct_src_ltm", "ct_src_dport_ltm",
    "ct_dst_sport_ltm", "ct_dst_src_ltm", "attack_cat", "Label",
]

METADATA_EXCLUDE_COLS = {
    "src_ip", "dst_ip", "src", "dst", "source", "destination", "src_host", "dst_host",
    "source_ip", "dest_ip", "srcip", "dstip", "ipv4_src_addr", "ipv4_dst_addr",
    "timestamp", "time", "stime", "ltime", "flow_id", "flow id", "attack_cat", "attack",
}


def _map_target_to_binary(series: pd.Series) -> pd.Series:
    """Converte labels textuais ou numéricas para binário: 0 = benigno/normal, 1 = ataque."""
    if pd.api.types.is_numeric_dtype(series):
        return (series.fillna(0).astype(float) != 0.0).astype(int)
    s = series.astype(str).str.lower().str.strip()
    benign = {"normal", "normal.", "benign", "benign.", "0", "0.0", "false", "nan", ""}
    return (~s.isin(benign)).astype(int)


def load_dataset_csv(csv_path: str, nrows: Optional[int] = None) -> pd.DataFrame:
    """
    Carrega CSV de tráfego, removendo espaços extras em nomes de colunas e detectando
    automaticamente arquivos UNSW-NB15 sem cabeçalho (49 colunas).
    """
    sample = pd.read_csv(csv_path, nrows=5, header=None, low_memory=False)
    first_val = str(sample.iloc[0, 0]).strip()
    is_ip_first = first_val.count(".") == 3 and all(p.isdigit() for p in first_val.split(".") if p)

    if sample.shape[1] == 49 and is_ip_first:
        logging.info("Detectado formato UNSW-NB15 bruto (49 colunas sem cabeçalho).")
        df = pd.read_csv(csv_path, names=UNSW_NB15_COLUMNS, header=None, nrows=nrows, low_memory=False)
        for col in ["sport", "dsport", "ct_ftp_cmd", "ct_flw_http_mthd", "is_ftp_login"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    else:
        df = pd.read_csv(csv_path, nrows=nrows, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]

    return df


def one_hot_encode(
    df: pd.DataFrame,
    cols: List[str],
    expected_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Aplica One-Hot Encoding às colunas categóricas presentes.
    Se `expected_columns` for informado (em validação/teste), alinha estritamente as colunas
    ao vocabulário visto no treino sem vazar categorias de validação/teste.
    """
    df = df.copy()
    present = [c for c in cols if c in df.columns]
    if present:
        df = pd.get_dummies(df, columns=present, prefix=present, drop_first=False, dtype=float)
    if expected_columns is not None:
        df = df.reindex(columns=expected_columns, fill_value=0.0)
    return df


def split_dataframe_temporal(
    df: pd.DataFrame,
    time_col: Optional[str] = None,
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Divide o DataFrame em três partições disjuntas (Treino / Validação / Teste) respeitando
    a ordem temporal ou de captura ANTES de qualquer ajuste estatístico.
    """
    if not (0.0 < train_ratio < 1.0) or not (0.0 < val_ratio < 1.0) or (train_ratio + val_ratio >= 1.0):
        raise ValueError("train_ratio e val_ratio devem ser positivos e somar menos que 1.0")

    if time_col and time_col in df.columns:
        df_sorted = df.sort_values(time_col, kind="mergesort").reset_index(drop=True)
    else:
        df_sorted = df.reset_index(drop=True)

    n = len(df_sorted)
    if n < 5:
        raise ValueError(f"DataFrame muito pequeno ({n} linhas) para divisão em treino/val/teste.")

    n_train = max(1, int(n * train_ratio))
    n_val = max(1, int(n * val_ratio))
    if n_train + n_val >= n:
        n_train = max(1, n - 2)
        n_val = 1

    train_df = df_sorted.iloc[:n_train].copy().reset_index(drop=True)
    val_df = df_sorted.iloc[n_train : n_train + n_val].copy().reset_index(drop=True)
    test_df = df_sorted.iloc[n_train + n_val :].copy().reset_index(drop=True)

    return train_df, val_df, test_df


def select_topk_pearson(
    df: pd.DataFrame,
    target_col: str,
    k: int = 20,
    exclude_cols: Optional[List[str]] = None,
) -> List[str]:
    """
    Seleciona as Top-K features numéricas pela correlação linear absoluta de Pearson (|r|)
    com a coluna alvo. Deve ser executada EXCLUSIVAMENTE sobre o DataFrame de treino.
    """
    if target_col not in df.columns:
        raise KeyError(f"target_col '{target_col}' não encontrado no DataFrame")

    df_work = df.copy()
    y_bin = _map_target_to_binary(df_work[target_col])

    excluded = {c.lower() for c in METADATA_EXCLUDE_COLS}
    excluded.add(target_col.lower())
    if exclude_cols:
        excluded.update(c.lower() for c in exclude_cols)

    numeric_cols = [
        c for c in df_work.select_dtypes(include=[np.number, "bool"]).columns
        if c.lower() not in excluded
    ]
    if not numeric_cols:
        raise ValueError("Nenhuma coluna numérica disponível para seleção de features.")

    clean_num = (
        df_work[numeric_cols]
        .astype(np.float64)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    corrs = clean_num.corrwith(y_bin).abs().fillna(0.0)
    corrs = corrs.sort_values(ascending=False)
    topk = corrs.head(k).index.tolist()
    logging.info(f"Top-{len(topk)} features selecionadas (Pearson no treino): {topk}")
    return topk


def fit_feature_scaler(train_df: pd.DataFrame, top_features: List[str]) -> StandardScaler:
    """Ajusta o StandardScaler exclusivamente nas observações de treino."""
    clean_train = (
        train_df[top_features]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .astype(np.float32)
    )
    scaler = StandardScaler()
    scaler.fit(clean_train.values)
    return scaler


def build_graph(
    df: pd.DataFrame,
    top_features: List[str],
    seq_len: int = 10,
    time_col: Optional[str] = None,
    src_cols_priority: Optional[List[str]] = None,
    dst_cols_priority: Optional[List[str]] = None,
    target_col: str = "target",
    scaler: Optional[StandardScaler] = None,
    fit_scaler: bool = False,
    allow_row_fallback: bool = False,
) -> Data:
    """
    Constrói um grafo PyG (Data) com x: [num_nodes, seq_len, len(top_features)].

    Garantias de Integridade Científica:
      - Ordena o DataFrame por `time_col` ANTES de extrair a matriz de features, evitando
        o bug de desalinhamento de índices (`feat_df.loc[row.name]`).
      - Se `scaler` for fornecido, aplica apenas `scaler.transform()` (sem re-fit em val/test).
      - Apenas o nó emissor (`src_ip`) recebe rótulo de atacante (`label=1`) quando emite
        um fluxo malicioso; destinos passivos (`dst_ip`) permanecem no grafo com `label=0`
        (a menos que eles mesmos emitam fluxos de ataque).
      - Se colunas de IP não existirem, rejeita a construção de grafo topológico por padrão
        (`allow_row_fallback=False`). Quando `allow_row_fallback=True` é usado para baselines
        tabulares, cria apenas auto-loops `(i, i)`, jamais ligando linhas adjacentes arbitrárias.
    """
    if src_cols_priority is None:
        src_cols_priority = ["IPV4_SRC_ADDR", "src_ip", "srcip", "src", "source", "src_host", "source_ip", "Source IP"]
    if dst_cols_priority is None:
        dst_cols_priority = ["IPV4_DST_ADDR", "dst_ip", "dstip", "dst", "destination", "dst_host", "dest_ip", "Destination IP"]

    src_col = next((c for c in src_cols_priority if c in df.columns), None)
    dst_col = next((c for c in dst_cols_priority if c in df.columns), None)

    # 1. Ordenar cronologicamente ANTES de extrair a matriz de features (evita bug de índice)
    if time_col and time_col in df.columns:
        df_proc = df.sort_values(time_col, kind="mergesort").reset_index(drop=True)
    else:
        df_proc = df.reset_index(drop=True)

    # 2. Extrair e padronizar features respeitando o scaler de treino
    feat_df = (
        df_proc[top_features]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .astype(np.float32)
    )
    flat = feat_df.values.astype(np.float32)

    if scaler is not None:
        if fit_scaler:
            flat_scaled = scaler.fit_transform(flat)
        else:
            flat_scaled = scaler.transform(flat)
    else:
        scaler = StandardScaler()
        flat_scaled = scaler.fit_transform(flat)

    flat_scaled = np.nan_to_num(flat_scaled, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    has_target = target_col in df_proc.columns
    y_rows = _map_target_to_binary(df_proc[target_col]).values if has_target else np.zeros(len(df_proc), dtype=np.int64)

    # 3. Construção do grafo por endpoints IP reais
    if src_col and dst_col:
        valid_mask = df_proc[src_col].notna() & df_proc[dst_col].notna()
        df_valid = df_proc.loc[valid_mask].reset_index(drop=True)
        flat_valid = flat_scaled[valid_mask.values]
        y_valid = y_rows[valid_mask.values]

        src_vals = df_valid[src_col].astype(str).values
        dst_vals = df_valid[dst_col].astype(str).values

        nodes = sorted(set(src_vals).union(set(dst_vals)))
        ip2idx = {ip: i for i, ip in enumerate(nodes)}
        num_nodes = len(ip2idx)

        out_vectors: Dict[int, List[np.ndarray]] = defaultdict(list)
        in_vectors: Dict[int, List[np.ndarray]] = defaultdict(list)
        edge_counts: Dict[Tuple[int, int], int] = {}
        edge_attrs: Dict[Tuple[int, int], np.ndarray] = {}
        node_labels = np.zeros((num_nodes,), dtype=np.int64)

        num_feat = len(top_features)
        for row_idx in range(len(df_valid)):
            s_idx = ip2idx[src_vals[row_idx]]
            d_idx = ip2idx[dst_vals[row_idx]]
            feats = flat_valid[row_idx]

            out_vectors[s_idx].append(feats)
            in_vectors[d_idx].append(feats)

            ekey = (s_idx, d_idx)
            if ekey not in edge_counts:
                edge_counts[ekey] = 0
                edge_attrs[ekey] = np.zeros((num_feat,), dtype=np.float32)
            edge_counts[ekey] += 1
            edge_attrs[ekey] += feats

            # Apenas o emissor do fluxo malicioso recebe rótulo de atacante
            if y_valid[row_idx] == 1:
                node_labels[s_idx] = 1

        node_features = np.zeros((num_nodes, seq_len, num_feat), dtype=np.float32)
        for idx in range(num_nodes):
            # Prioriza histórico de envio; se for vítima puramente passiva, usa histórico recebido
            vecs = out_vectors.get(idx) or in_vectors.get(idx) or []
            if not vecs:
                continue
            trunc = np.asarray(vecs[-seq_len:], dtype=np.float32)
            if trunc.shape[0] < seq_len:
                pad = np.zeros((seq_len - trunc.shape[0], num_feat), dtype=np.float32)
                arr = np.vstack([pad, trunc])
            else:
                arr = trunc
            node_features[idx] = arr

        if not edge_counts:
            edge_index = torch.empty((2, 0), dtype=torch.long)
            edge_attr = None
        else:
            edges = list(edge_counts.keys())
            edge_index = torch.tensor([[e[0] for e in edges], [e[1] for e in edges]], dtype=torch.long)
            edge_attr = torch.tensor(
                np.array([edge_attrs[e] / edge_counts[e] for e in edges], dtype=np.float32),
                dtype=torch.float32,
            )

        x = torch.tensor(node_features, dtype=torch.float32)
        y = torch.tensor(node_labels, dtype=torch.long)

        data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y=y)
        data.ip2idx = ip2idx
        data.idx2ip = {v: k for k, v in ip2idx.items()}
        data.scaler = scaler
        data.top_features = list(top_features)
        data.topology_mode = "observed_ip_graph"
        return data

    # 4. Tratamento quando não há colunas de IP
    if not allow_row_fallback:
        raise ValueError(
            "Colunas de IP de origem/destino não encontradas no DataFrame. "
            "Para evitar a criação de topologia artificial ligando linhas consecutivas, "
            "forneça um dataset com identificadores de host ou ative explicitamente "
            "`allow_row_fallback=True` para baseline tabular com auto-loops."
        )

    logging.warning(
        "Colunas src/dst ausentes — construindo baseline tabular com auto-loops (i -> i), "
        "sem arestas sequenciais artificiais entre registros distintos."
    )
    n_rows = len(df_proc)
    num_feat = len(top_features)
    node_features = np.zeros((n_rows, seq_len, num_feat), dtype=np.float32)
    node_features[:, -1, :] = flat_scaled
    node_labels = y_rows.astype(np.int64)

    if n_rows == 0:
        edge_index = torch.empty((2, 0), dtype=torch.long)
    else:
        idx_arange = np.arange(n_rows, dtype=np.int64)
        edge_index = torch.tensor(np.vstack([idx_arange, idx_arange]), dtype=torch.long)

    x = torch.tensor(node_features, dtype=torch.float32)
    y = torch.tensor(node_labels, dtype=torch.long)
    data = Data(x=x, edge_index=edge_index, edge_attr=None, y=y)
    data.scaler = scaler
    data.top_features = list(top_features)
    data.ip2idx = {i: i for i in range(n_rows)}
    data.idx2ip = {i: i for i in range(n_rows)}
    data.topology_mode = "tabular_self_loop_baseline"
    return data


def build_inductive_splits(
    df: pd.DataFrame,
    target_col: str = "target",
    time_col: Optional[str] = None,
    k: int = 20,
    seq_len: int = 10,
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
    categorical_cols: Optional[List[str]] = None,
    allow_row_fallback: bool = False,
) -> Dict[str, object]:
    """
    Executa o protocolo experimental completo sem vazamento de informações:
      1. Particionamento temporal/sequencial disjunto (60% treino / 20% val / 20% teste).
      2. One-Hot Encoding ajustado apenas no treino e alinhado em val/teste.
      3. Seleção de features por Pearson ajustada apenas no treino.
      4. StandardScaler ajustado apenas no treino.
      5. Grafos construídos independentemente para treino, validação e teste.
    """
    if categorical_cols is None:
        categorical_cols = ["protocol_type", "service", "flag", "proto", "state"]

    train_raw, val_raw, test_raw = split_dataframe_temporal(
        df, time_col=time_col, train_ratio=train_ratio, val_ratio=val_ratio
    )

    train_enc = one_hot_encode(train_raw, categorical_cols)
    expected_cols = list(train_enc.columns)
    val_enc = one_hot_encode(val_raw, categorical_cols, expected_columns=expected_cols)
    test_enc = one_hot_encode(test_raw, categorical_cols, expected_columns=expected_cols)

    top_features = select_topk_pearson(train_enc, target_col=target_col, k=k)
    scaler = fit_feature_scaler(train_enc, top_features)

    train_graph = build_graph(
        train_enc,
        top_features,
        seq_len=seq_len,
        time_col=time_col,
        target_col=target_col,
        scaler=scaler,
        fit_scaler=False,
        allow_row_fallback=allow_row_fallback,
    )
    val_graph = build_graph(
        val_enc,
        top_features,
        seq_len=seq_len,
        time_col=time_col,
        target_col=target_col,
        scaler=scaler,
        fit_scaler=False,
        allow_row_fallback=allow_row_fallback,
    )
    test_graph = build_graph(
        test_enc,
        top_features,
        seq_len=seq_len,
        time_col=time_col,
        target_col=target_col,
        scaler=scaler,
        fit_scaler=False,
        allow_row_fallback=allow_row_fallback,
    )

    return {
        "protocol": "inductive_temporal_60_20_20",
        "train": train_graph,
        "val": val_graph,
        "test": test_graph,
        "top_features": top_features,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "split_rows": {
            "train": len(train_raw),
            "val": len(val_raw),
            "test": len(test_raw),
        },
    }


def generate_test_sample(out_csv: Optional[str] = None, n: int = 300, seed: int = 42) -> pd.DataFrame:
    """
    Gera um DataFrame sintético determinístico para testes de fumaça do pipeline.
    Inclui separação clara entre hosts atacantes (10.0.0.1..10.0.0.15) e hosts benignos
    (10.0.0.16..10.0.0.50) comunicando-se com servidores (10.0.1.1..10.0.1.20).
    """
    import random
    from datetime import datetime, timedelta

    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    rows = []
    now = datetime(2026, 1, 1, 12, 0, 0)
    proto_choices = ["tcp", "udp", "icmp"]
    service_choices = ["http", "ftp", "ssh", "dns"]
    flag_choices = ["SF", "S1", "REJ"]

    for i in range(n):
        ts = (now + timedelta(seconds=i * 2)).isoformat()
        is_attack = 1 if (i % 4 == 0) else 0
        if is_attack:
            src = f"10.0.0.{rng.randint(1, 15)}"
        else:
            src = f"10.0.0.{rng.randint(16, 50)}"
        dst = f"10.0.1.{rng.randint(1, 20)}"
        proto = rng.choice(proto_choices)
        service = rng.choice(service_choices)
        flag = rng.choice(flag_choices)

        feats = {}
        for j in range(20):
            base = float(np_rng.normal(loc=2.5 if (is_attack and j < 6) else 0.0, scale=0.8))
            feats[f"f{j}"] = base

        row = {
            "timestamp": ts,
            "src_ip": src,
            "dst_ip": dst,
            "protocol_type": proto,
            "service": service,
            "flag": flag,
            "target": is_attack,
        }
        row.update(feats)
        rows.append(row)

    df = pd.DataFrame(rows)
    if out_csv:
        p = Path(out_csv)
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, index=False)
        logging.info(f"Sample CSV salvo em {p}")
    return df


def parse_args():
    p = argparse.ArgumentParser(description="Preprocessor Leakage-Free: Split 60/20/20, Top-20 Pearson, Graph Builder")
    p.add_argument("--input_csv", required=False, help="CSV de input (se omitido, usa generate_test_sample)")
    p.add_argument("--time_col", default=None, help="Coluna de tempo (ex: Stime, timestamp)")
    p.add_argument("--seq_len", type=int, default=10)
    p.add_argument("--target_col", default="target")
    p.add_argument("--max_rows", type=int, default=None, help="Limite opcional de linhas lidas do CSV")
    p.add_argument("--allow_row_fallback", action="store_true", help="Permitir baseline com auto-loops se não houver IPs")
    p.add_argument("--output_pt", default=str(PROCESSED_DIR / "network_graph_splits.pt"))
    p.add_argument("--topk_json", default=str(PROCESSED_DIR / "top20_features_clean.json"))
    return p.parse_args()


def main():
    args = parse_args()
    logging.info("Preprocessor (Leakage-Free) iniciado")

    if args.input_csv:
        df = load_dataset_csv(args.input_csv, nrows=args.max_rows)
    else:
        logging.info("Nenhum input_csv fornecido; gerando amostra sintética determinística...")
        df = generate_test_sample(n=600)
        if args.time_col is None:
            args.time_col = "timestamp"

    target_col = args.target_col
    if target_col not in df.columns and "Label" in df.columns:
        target_col = "Label"

    time_col = args.time_col
    if time_col is None:
        for candidate in ["Stime", "timestamp", "Timestamp", "time"]:
            if candidate in df.columns:
                time_col = candidate
                break

    bundle = build_inductive_splits(
        df,
        target_col=target_col,
        time_col=time_col,
        k=20,
        seq_len=args.seq_len,
        allow_row_fallback=args.allow_row_fallback,
    )

    out_json = Path(args.topk_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(bundle["top_features"], f, indent=2)
    logging.info(f"Top-20 features (ajustadas apenas no treino) salvas em {out_json}")

    out_pt = Path(args.output_pt)
    out_pt.parent.mkdir(parents=True, exist_ok=True)
    torch.save(bundle, str(out_pt))
    logging.info(
        f"Partições indutivas salvas em {out_pt} | "
        f"Treino: {bundle['train'].x.shape[0]} nós ({bundle['train'].edge_index.shape[1]} arestas) | "
        f"Val: {bundle['val'].x.shape[0]} nós ({bundle['val'].edge_index.shape[1]} arestas) | "
        f"Teste: {bundle['test'].x.shape[0]} nós ({bundle['test'].edge_index.shape[1]} arestas)"
    )


if __name__ == "__main__":
    main()
