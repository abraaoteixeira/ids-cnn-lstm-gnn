"""
run_phase2_experiments.py

Orquestrador científico reproduzível para a Fase 2 (IEEE/IFIP NOMS 2027):
  1. Auditoria cronológica do UNSW-NB15 (`Stime`, lacunas temporais, distribuição por decil e verificação de UNSW-NB15_2.csv).
  2. Re-geração do bundle `unsw_full_ebpf_30s.pt` (Modalidade A: `ebpf_compatible`, 200k linhas com 100% dos 22.215 ataques)
     incluindo `expected_encoded_columns` e `dataset_sha256`.
  3. Transformação congelada (sem reajuste de Pearson, One-Hot ou StandardScaler) dos 500.001 registros posteriores
     (`linhas 200.000..700.001`) em `unsw_tail500k_external_30s.pt` e avaliação independente de Falsos Positivos.
  4. Geração do bundle da Modalidade B (`ebpf_sensor_strict`, estritamente unidirecional XDP ingress) e treinamento
     de validação (`--val_only`).
  5. Ablação completa das 6 variantes (`cnn_lstm_pure`, `gat_self_loop`, `cnn_lstm_gat`, `gat_reverse`, `gat_bidir`,
     `gat_residual`) através de múltiplas seeds (`42`, `123`, `1337`), preservando o conjunto de teste (`--val_only`).
  6. Execução do módulo `benchmark_latency.py` com warmup de GPU e percentis p50/p95/p99 desagregados por etapa.
"""
import argparse
import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import torch

from benchmark_latency import run_latency_benchmark
from model import SPECTRE_GRID
from preprocessor import (
    UNSW_NB15_COLUMNS,
    _parse_time_to_seconds,
    build_inductive_splits,
    load_dataset_csv,
    transform_external_dataframe_to_snapshots,
)
from train import (
    LOADER_EXCLUDE_KEYS,
    apply_bidirectional_edges,
    apply_reverse_edges,
    apply_self_loop_only,
    compute_classification_metrics,
    evaluate_snapshots,
    train_and_evaluate,
)
from torch_geometric.loader import DataLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit_dataset_chronology(csv_path: Path, out_json: Path) -> Dict[str, object]:
    logging.info("Auditando cronologia completa do UNSW-NB15.csv (700.001 linhas)...")
    df = load_dataset_csv(str(csv_path))
    t = _parse_time_to_seconds(df["Stime"])
    df["_t"] = t
    df_sorted = df.sort_values("_t", kind="mergesort").reset_index(drop=True)
    t_sorted = df_sorted["_t"].to_numpy(dtype=np.float64)
    diffs = np.diff(t_sorted)
    gaps_gt_60s = int((diffs > 60.0).sum())
    max_gap_sec = float(np.max(diffs)) if len(diffs) > 0 else 0.0

    atk_mask = df_sorted["Label"] == 1
    atk_indices = np.where(atk_mask.to_numpy())[0]
    first_atk_idx = int(atk_indices[0]) if len(atk_indices) > 0 else -1
    last_atk_idx = int(atk_indices[-1]) if len(atk_indices) > 0 else -1

    deciles = []
    n = len(df_sorted)
    for d in range(10):
        s = df_sorted.iloc[int(d * n / 10) : int((d + 1) * n / 10)]
        deciles.append(
            {
                "decile": d,
                "start_row": int(d * n / 10),
                "end_row": int((d + 1) * n / 10),
                "rows": int(len(s)),
                "t_min": float(s["_t"].min()),
                "t_max": float(s["_t"].max()),
                "attacks": int((s["Label"] == 1).sum()),
                "attack_rate": round(float((s["Label"] == 1).mean()), 6),
            }
        )

    other_csvs = [str(p) for p in Path("data").rglob("*.csv")]
    unsw2_exists = any("UNSW-NB15_2" in p or "UNSW_NB15_2" in p for p in other_csvs)

    audit = {
        "csv_path": str(csv_path),
        "dataset_sha256": compute_sha256(csv_path),
        "total_rows": int(n),
        "total_attacks": int(atk_mask.sum()),
        "t_min_epoch": float(t_sorted[0]),
        "t_max_epoch": float(t_sorted[-1]),
        "total_span_sec": float(t_sorted[-1] - t_sorted[0]),
        "first_attack_row_after_sort": first_atk_idx,
        "last_attack_row_after_sort": last_atk_idx,
        "active_attack_horizon_rows": 200000,
        "post_campaign_benign_tail_rows": int(n - 200000),
        "post_campaign_benign_tail_attacks": int((df_sorted.iloc[200000:]["Label"] == 1).sum()),
        "time_gaps_gt_60s": gaps_gt_60s,
        "max_time_gap_sec": max_gap_sec,
        "deciles": deciles,
        "available_csv_files": other_csvs,
        "unsw_nb15_2_present_locally": unsw2_exists,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    logging.info(f"Auditoria cronológica salva em {out_json}")
    return audit


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv_path", default="data/raw/benchmarks/UNSW-NB15.csv")
    p.add_argument("--out_dir", default="data/processed")
    p.add_argument("--tag_prefix", default="g15")
    p.add_argument("--seeds", nargs="+", type=int, default=[42, 123, 1337])
    p.add_argument(
        "--variants",
        nargs="+",
        default=["cnn_lstm_pure", "gat_self_loop", "cnn_lstm_gat", "gat_reverse", "gat_bidir", "gat_residual"],
    )
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--batch_size", type=int, default=8)
    p.add_argument("--patience", type=int, default=7)
    p.add_argument("--skip_external_tail", action="store_true")
    p.add_argument("--skip_modality_b", action="store_true")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = Path(args.csv_path)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        git_commit = "unknown"

    # 1. Auditoria cronológica e SHA256
    audit_path = out_dir / f"{args.tag_prefix}_dataset_chronology_audit.json"
    if audit_path.is_file():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        dataset_sha256 = audit["dataset_sha256"]
    else:
        audit = audit_dataset_chronology(csv_path, audit_path)
        dataset_sha256 = audit["dataset_sha256"]

    # 2. Bundle Modalidade A (ebpf_compatible, 200k linhas ativas, 30s)
    mod_a_bundle_path = out_dir / "unsw_full_ebpf_30s.pt"
    df_active = load_dataset_csv(str(csv_path), nrows=200000)
    bundle_a = build_inductive_splits(
        df_active,
        target_col="Label",
        time_col="Stime",
        k=20,
        seq_len=10,
        window_sec=30.0,
        feature_scope="ebpf_compatible",
    )
    bundle_a["dataset_sha256"] = dataset_sha256
    torch.save(bundle_a, str(mod_a_bundle_path))
    (out_dir / "unsw_full_ebpf_30s_features.json").write_text(
        json.dumps(bundle_a["top_features"], indent=2), encoding="utf-8"
    )
    logging.info(f"Bundle Modalidade A salvo em {mod_a_bundle_path}")

    # 3. Ablação multi-seed das 6 variantes na Modalidade A (--val_only)
    all_runs_summary: List[Dict[str, object]] = []
    for seed in args.seeds:
        for variant in args.variants:
            run_id = f"{args.tag_prefix}_{variant}_seed{seed}_30s"
            ckpt_path = out_dir / f"{run_id}_best.pth"
            res_path = out_dir / f"{run_id}_resume.pt"
            rep_path = out_dir / f"{run_id}_report.json"

            logging.info(f"=== [Modalidade A] Treinando {run_id} (--val_only) ===")
            if res_path.exists():
                res_path.unlink()

            result = train_and_evaluate(
                train_g=bundle_a["train_snapshots"],
                val_g=bundle_a["val_snapshots"],
                test_g=bundle_a["test_snapshots"],
                epochs=args.epochs,
                lr=0.001,
                patience=args.patience,
                seed=seed,
                device=device,
                checkpoint_out=str(ckpt_path),
                model_variant=variant,
                val_only=True,
                batch_size=args.batch_size,
                resume=True,
                resume_state_out=str(res_path),
                save_every=1,
            )

            report = {
                "git_commit": git_commit,
                "dataset_sha256": dataset_sha256,
                "modality": "Modality_A_offline_ebpf_compatible",
                "feature_scope": "ebpf_compatible",
                "window_sec": 30.0,
                "model_variant": variant,
                "seed": seed,
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "best_epoch": result["best_epoch"],
                "validation_metrics": result["validation_best"],
                "validation_node_group_metrics": result["validation_node_group_metrics"],
                "epoch_history": result["epoch_history"],
                "validation_latency": result["validation_latency"],
                "held_out_test_metrics": None,
                "device": str(device),
                "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                "torch_version": torch.__version__,
                "training_wall_time_sec": result["training_wall_time_sec"],
            }
            rep_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            all_runs_summary.append(report)

    # 4. Transformação congelada dos 500.001 registros posteriores (linhas 200.000..700.001) e avaliação de FPR
    if not args.skip_external_tail:
        tail_bundle_path = out_dir / "unsw_tail500k_external_30s.pt"
        logging.info("Transformando os 500.001 registros posteriores sem reajuste estatístico...")
        df_tail = load_dataset_csv(str(csv_path), skip_rows=200000)
        ext_bundle = transform_external_dataframe_to_snapshots(
            df_tail,
            reference_bundle=bundle_a,
            window_sec=30.0,
            seq_len=10,
            time_col="Stime",
            target_col="Label",
        )
        torch.save(ext_bundle, str(tail_bundle_path))

        ext_snaps_orig = ext_bundle["external_snapshots"]
        tail_eval_results = {}
        criterion = torch.nn.BCEWithLogitsLoss()
        for variant in ["cnn_lstm_pure", "gat_self_loop", "cnn_lstm_gat", "gat_reverse", "gat_bidir", "gat_residual"]:
            ckpt_path = out_dir / f"{args.tag_prefix}_{variant}_seed42_30s_best.pth"
            if not ckpt_path.is_file():
                continue
            if variant in ("cnn_lstm_pure", "gat_self_loop"):
                snaps_v = [apply_self_loop_only(g) for g in ext_snaps_orig]
            elif variant == "gat_reverse":
                snaps_v = [apply_reverse_edges(g) for g in ext_snaps_orig]
            elif variant == "gat_bidir":
                snaps_v = [apply_bidirectional_edges(g) for g in ext_snaps_orig]
            else:
                snaps_v = ext_snaps_orig

            loader_ext = DataLoader(snaps_v, batch_size=args.batch_size, shuffle=False, exclude_keys=LOADER_EXCLUDE_KEYS)
            model = SPECTRE_GRID(
                num_features=20,
                seq_len=10,
                use_gat=(variant != "cnn_lstm_pure"),
                use_residual=(variant == "gat_residual"),
            ).to(device)
            model.load_state_dict(torch.load(ckpt_path, map_location=device, weights_only=True))
            _, ext_metrics, _, _, ext_lat = evaluate_snapshots(
                model, loader_ext, criterion, device, num_snapshots=len(snaps_v)
            )
            tail_eval_results[variant] = {
                "external_rows": ext_bundle["external_rows"],
                "num_snapshots": len(snaps_v),
                "total_benign_nodes": ext_bundle["snapshot_summary"]["external"]["benign_nodes_0"],
                "total_attack_nodes": ext_bundle["snapshot_summary"]["external"]["attack_nodes_1"],
                "refitted_on_external": False,
                "metrics": ext_metrics,
                "latency": ext_lat,
            }
            logging.info(
                f"[Cauda Externa 500k | {variant}] Nós Benignos={ext_metrics['confusion_matrix']['tn'] + ext_metrics['confusion_matrix']['fp']} | "
                f"FP={ext_metrics['confusion_matrix']['fp']} | FPR={ext_metrics['fpr']*100:.2f}%"
            )
        (out_dir / f"{args.tag_prefix}_external_tail500k_fpr_report.json").write_text(
            json.dumps(tail_eval_results, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # 5. Modalidade B (ebpf_sensor_strict — apenas features unidirecionais XDP ingress)
    if not args.skip_modality_b:
        logging.info("Gerando bundle da Modalidade B (ebpf_sensor_strict, 200k linhas, 30s)...")
        mod_b_bundle_path = out_dir / "unsw_full_ebpf_sensor_strict_30s.pt"
        bundle_b = build_inductive_splits(
            df_active,
            target_col="Label",
            time_col="Stime",
            k=20,
            seq_len=10,
            window_sec=30.0,
            feature_scope="ebpf_sensor_strict",
        )
        bundle_b["dataset_sha256"] = dataset_sha256
        torch.save(bundle_b, str(mod_b_bundle_path))
        (out_dir / "unsw_full_ebpf_sensor_strict_30s_features.json").write_text(
            json.dumps(bundle_b["top_features"], indent=2), encoding="utf-8"
        )

        mod_b_results = {}
        for variant in ["cnn_lstm_pure", "gat_self_loop", "cnn_lstm_gat", "gat_residual"]:
            for seed in [42, 123]:
                run_id = f"{args.tag_prefix}_modB_{variant}_seed{seed}_30s"
                ckpt_path = out_dir / f"{run_id}_best.pth"
                res_path = out_dir / f"{run_id}_resume.pt"
                if res_path.exists():
                    res_path.unlink()
                res_b = train_and_evaluate(
                    train_g=bundle_b["train_snapshots"],
                    val_g=bundle_b["val_snapshots"],
                    test_g=bundle_b["test_snapshots"],
                    epochs=args.epochs,
                    lr=0.001,
                    patience=args.patience,
                    seed=seed,
                    device=device,
                    checkpoint_out=str(ckpt_path),
                    model_variant=variant,
                    val_only=True,
                    batch_size=args.batch_size,
                    resume=True,
                    resume_state_out=str(res_path),
                    save_every=1,
                )
                mod_b_results[f"{variant}_seed{seed}"] = {
                    "git_commit": git_commit,
                    "feature_scope": "ebpf_sensor_strict",
                    "top_features": bundle_b["top_features"],
                    "model_variant": variant,
                    "seed": seed,
                    "best_epoch": res_b["best_epoch"],
                    "validation_metrics": res_b["validation_best"],
                    "validation_node_group_metrics": res_b["validation_node_group_metrics"],
                    "training_wall_time_sec": res_b["training_wall_time_sec"],
                }
        (out_dir / f"{args.tag_prefix}_modality_b_ebpf_sensor_strict_report.json").write_text(
            json.dumps(mod_b_results, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # 6. Benchmark de latência e VRAM desagregado por etapa
    bench_summary = {}
    for variant in ["cnn_lstm_pure", "gat_self_loop", "cnn_lstm_gat", "gat_residual"]:
        ckpt_path = out_dir / f"{args.tag_prefix}_{variant}_seed42_30s_best.pth"
        snaps_raw = list(bundle_a["val_snapshots"])
        if variant in ("cnn_lstm_pure", "gat_self_loop"):
            snaps_v = [apply_self_loop_only(g) for g in snaps_raw]
        else:
            snaps_v = snaps_raw
        model = SPECTRE_GRID(
            num_features=20,
            seq_len=10,
            use_gat=(variant != "cnn_lstm_pure"),
            use_residual=(variant == "gat_residual"),
        ).to(device)
        if ckpt_path.is_file():
            model.load_state_dict(torch.load(ckpt_path, map_location=device, weights_only=True))
        bench_summary[variant] = run_latency_benchmark(
            snapshots_cpu=snaps_v,
            model=model,
            device=device,
            batch_size=args.batch_size,
            warmup_runs=10,
            num_runs=30,
        )
    (out_dir / f"{args.tag_prefix}_latency_vram_benchmark.json").write_text(
        json.dumps(bench_summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 7. Salvar resumo consolidado multi-seed
    (out_dir / f"{args.tag_prefix}_phase2_consolidated_summary.json").write_text(
        json.dumps(all_runs_summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logging.info("=== FASE 2 CONCLUÍDA COM SUCESSO ===")


if __name__ == "__main__":
    main()
