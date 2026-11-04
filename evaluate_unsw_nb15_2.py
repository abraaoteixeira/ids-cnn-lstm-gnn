"""Script de Avaliação Independente Cega no dataset externo UNSW-NB15_2.csv (IEEE/IFIP NOMS 2027).

Avalia os checkpoints congelados da Fase 2 (treinados exclusivamente no horizonte ativo de UNSW-NB15_1)
sobre uma captura independente posterior (UNSW-NB15_2.csv) contendo tráfego benigno e ataques reais,
sem qualquer reajuste de hiperparâmetros, vocabulário ou normalizadores (refitted_on_external = False).
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch_geometric.loader import DataLoader

from model import SPECTRE_GRID
from preprocessor import (
    load_dataset_csv,
    transform_external_dataframe_to_snapshots,
)
from run_phase2_experiments import (
    LOADER_EXCLUDE_KEYS,
    apply_bidirectional_edges,
    apply_reverse_edges,
    apply_self_loop_only,
    evaluate_snapshots,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def run_evaluation(
    csv2_path: str = "data/raw/benchmarks/UNSW-NB15_2.csv",
    ref_bundle_path: str = "data/processed/unsw_full_ebpf_30s.pt",
    out_bundle_path: str = "data/processed/unsw_nb15_2_external_30s.pt",
    report_out_path: str = "data/processed/g15_external_unsw_nb15_2_eval_report.json",
    slice_start: int = 400000,
    slice_end: int = 600000,
    seeds: List[int] = [42, 123, 1337],
    batch_size: int = 8,
):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logging.info(f"Dispositivo de avaliação: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    # 1. Carrega referência de treino para garantir zero reajuste (zero leakage)
    logging.info(f"Carregando bundle de referência: {ref_bundle_path}")
    ref_bundle = torch.load(ref_bundle_path, map_location="cpu", weights_only=False)
    top_features = ref_bundle["top_features"]
    feature_scope = ref_bundle.get("feature_scope", "ebpf_compatible")
    logging.info(f"Top-20 features de referência congeladas: {top_features}")

    # 2. Carrega slice de 200.000 registros de UNSW-NB15_2 contendo campanha ativa de ataques
    logging.info(f"Carregando {csv2_path}...")
    df2 = load_dataset_csv(csv2_path, nrows=None)
    logging.info("Ordenando UNSW-NB15_2 cronologicamente por Stime (mergesort)...")
    df2_sorted = df2.sort_values("Stime", kind="mergesort").reset_index(drop=True)
    sub_df = df2_sorted.iloc[slice_start:slice_end].copy().reset_index(drop=True)
    n_attacks = int(sub_df["Label"].sum())
    logging.info(f"Recorte [{slice_start}..{slice_end}] extraído: {len(sub_df)} registros, {n_attacks} ataques ({n_attacks/len(sub_df)*100:.2f}%)")

    # 3. Transforma em snapshots de 30s usando estritamente o scaler e features de UNSW-NB15_1
    if os.path.exists(out_bundle_path):
        logging.info(f"Bundle externo já existe em {out_bundle_path}. Carregando...")
        ext_bundle = torch.load(out_bundle_path, map_location="cpu", weights_only=False)
    else:
        logging.info("Construindo snapshots temporais de 30s para UNSW-NB15_2 com estatísticas congeladas...")
        ext_bundle = transform_external_dataframe_to_snapshots(
            df=sub_df,
            reference_bundle=ref_bundle,
            window_sec=30.0,
            seq_len=10,
            time_col="Stime",
            target_col="Label",
        )
        torch.save(ext_bundle, out_bundle_path)
        logging.info(f"Bundle salvo com sucesso em {out_bundle_path}")

    ext_snapshots = ext_bundle["external_snapshots"]
    snap_summary = ext_bundle["snapshot_summary"]["external"]
    logging.info(
        f"Snapshots gerados: {len(ext_snapshots)} | Nós Totais: {snap_summary['total_nodes']} "
        f"(Benignos: {snap_summary['benign_nodes_0']}, Atacantes: {snap_summary['attack_nodes_1']}) | "
        f"Arestas Totais: {snap_summary['total_edges']}"
    )

    variants = [
        "cnn_lstm_pure",
        "gat_self_loop",
        "cnn_lstm_gat",
        "gat_reverse",
        "gat_bidir",
        "gat_residual",
    ]

    criterion = nn.BCEWithLogitsLoss()
    results = {}

    for var in variants:
        results[var] = {}
        for seed in seeds:
            ckpt_path = Path("data/processed") / f"g15_{var}_seed{seed}_30s_best.pth"
            if not ckpt_path.is_file():
                logging.warning(f"Checkpoint {ckpt_path} não encontrado, pulando...")
                continue

            # Aplica transformação topológica específica da variante
            if var in ("cnn_lstm_pure", "gat_self_loop"):
                snaps_v = [apply_self_loop_only(g) for g in ext_snapshots]
            elif var == "gat_reverse":
                snaps_v = [apply_reverse_edges(g) for g in ext_snapshots]
            elif var == "gat_bidir":
                snaps_v = [apply_bidirectional_edges(g) for g in ext_snapshots]
            else:
                snaps_v = ext_snapshots

            loader = DataLoader(
                snaps_v,
                batch_size=batch_size,
                shuffle=False,
                exclude_keys=LOADER_EXCLUDE_KEYS,
            )

            model = SPECTRE_GRID(
                num_features=len(top_features),
                seq_len=10,
                use_gat=(var != "cnn_lstm_pure"),
                use_residual=(var == "gat_residual"),
            ).to(device)

            state_dict = torch.load(ckpt_path, map_location=device, weights_only=True)
            model.load_state_dict(state_dict)
            model.eval()

            _, metrics, _, _, lat = evaluate_snapshots(
                model=model,
                loader=loader,
                criterion=criterion,
                device=device,
                num_snapshots=len(snaps_v),
            )

            cm = metrics["confusion_matrix"]
            logging.info(
                f"[{var} | Seed {seed}] F1={metrics['f1_score']:.4f} | "
                f"Prec={metrics['precision']:.4f} | Rec={metrics['recall']:.4f} | FPR={metrics['fpr']:.4f} | "
                f"CM={{TN: {cm['tn']}, FP: {cm['fp']}, FN: {cm['fn']}, TP: {cm['tp']}}} | "
                f"Latência={lat['ms_per_snapshot']:.3f} ms/snap ({lat['us_per_node']:.2f} us/node)"
            )

            results[var][f"seed_{seed}"] = {
                "checkpoint": str(ckpt_path),
                "metrics": metrics,
                "latency": lat,
            }

    final_report = {
        "evaluation_title": "Avaliação Independente em Captura Externa Contendo Ataques (UNSW-NB15_2.csv)",
        "protocol": "Zero-Leakage Frozen Evaluation (refitted_on_external = False)",
        "source_dataset": "UNSW-NB15_2.csv",
        "dataset_sha256": "6130ad02873cc6069ae695cf2844f2e8c2e9a9a1b7532dd82ab8f202757cacf8",
        "slice_range": f"{slice_start}..{slice_end}",
        "slice_rows": len(sub_df),
        "slice_attack_flows": n_attacks,
        "slice_attack_flow_rate": float(n_attacks / len(sub_df)),
        "num_snapshots_30s": len(ext_snapshots),
        "snapshot_summary": snap_summary,
        "reference_bundle_used": ref_bundle_path,
        "refitted_on_external": False,
        "device": str(device),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "torch_version": torch.__version__,
        "results_by_variant": results,
    }

    Path(report_out_path).write_text(json.dumps(final_report, indent=2, ensure_ascii=False), encoding="utf-8")
    logging.info(f"Relatório de avaliação independente salvo em {report_out_path}")
    return final_report


if __name__ == "__main__":
    run_evaluation()
