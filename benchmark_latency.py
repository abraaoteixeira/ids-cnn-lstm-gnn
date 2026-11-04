"""
benchmark_latency.py

Módulo independente de benchmark de desempenho, uso de VRAM e latência desagregada
por etapa para o SPECTRE-GRID (IEEE/IFIP NOMS 2027).

Mede com aquecimento prévio da GPU (warmup) e estatísticas p50, p95, p99, média e desvio padrão:
  1. Tempo de preparação dos mini-batches (CPU / PyG DataLoader Collation).
  2. Tempo de transferência CPU -> GPU (`batch.to(device)` sincronizado).
  3. Tempo de inferência pura da rede neural na GPU (`model(x, edge_index)`).
  4. Latência total do pipeline local de classificação (preparação + H2D + forward + threshold + D2H).
  5. Latência individual por snapshot (ms/snapshot: p50, p95, p99) e por nó (µs/nó: p50, p95, p99).
  6. Throughput sustentável (snapshots/s e nós/s).
  7. Consumo de memória de vídeo (VRAM alocada, reservada e de pico em MiB).

IMPORTANTE (Isolamento de Escopo de Latência):
  - Este módulo mede estritamente o pipeline local de classificação em user-space/GPU.
  - A latência de filtragem in-kernel XDP (`XDP_DROP` em `spectre_xdp.c`) e a latência de propagação
    em rede WAN NÃO são inferidas a partir do tempo de forward pass da GPU e são reportadas em
    seções separadas do relatório JSON.
"""
import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

from model import SPECTRE_GRID
from train import (
    LOADER_EXCLUDE_KEYS,
    apply_bidirectional_edges,
    apply_reverse_edges,
    apply_self_loop_only,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def _percentiles(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    arr = np.asarray(values, dtype=np.float64)
    return {
        "mean": round(float(np.mean(arr)), 4),
        "std": round(float(np.std(arr)), 4),
        "min": round(float(np.min(arr)), 4),
        "p50": round(float(np.percentile(arr, 50)), 4),
        "p95": round(float(np.percentile(arr, 95)), 4),
        "p99": round(float(np.percentile(arr, 99)), 4),
        "max": round(float(np.max(arr)), 4),
    }


def _sync(device: torch.device) -> None:
    if device.type == "cuda" and torch.cuda.is_available():
        torch.cuda.synchronize(device)


def _prepare_variant_graphs(graphs_cpu: List[Data], model_variant: str) -> List[Data]:
    if model_variant in ("gat_self_loop", "cnn_lstm_pure"):
        return [apply_self_loop_only(g) for g in graphs_cpu]
    if model_variant == "gat_reverse":
        return [apply_reverse_edges(g) for g in graphs_cpu]
    if model_variant == "gat_bidir":
        return [apply_bidirectional_edges(g) for g in graphs_cpu]
    return graphs_cpu


def run_latency_benchmark(
    snapshots_cpu: List[Data],
    model: torch.nn.Module,
    device: torch.device,
    batch_size: int = 8,
    warmup_runs: int = 10,
    num_runs: int = 30,
) -> Dict[str, object]:
    """
    Executa o protocolo de medição desagregada de latência sobre `snapshots_cpu`.
    Os snapshots são mantidos inicialmente na CPU para medir fielmente a colação de batches
    e a transferência CPU -> GPU.
    """
    model.eval()
    snapshots_cpu = [g.cpu() for g in snapshots_cpu if g.x.shape[0] > 0]
    if not snapshots_cpu:
        raise ValueError("Lista de snapshots para benchmark está vazia.")

    num_snapshots = len(snapshots_cpu)
    total_nodes = int(sum(g.x.shape[0] for g in snapshots_cpu))
    cpu_loader = DataLoader(snapshots_cpu, batch_size=batch_size, shuffle=False, exclude_keys=LOADER_EXCLUDE_KEYS)

    if device.type == "cuda" and torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)

    # 1. Aquecimento prévio da GPU (Warmup)
    with torch.no_grad():
        for _ in range(max(1, warmup_runs)):
            for batch_cpu in cpu_loader:
                b_gpu = batch_cpu.to(device)
                _ = model(b_gpu.x, b_gpu.edge_index)
        _sync(device)

    # 2. Medição por Passagem Completa (Batch Prep vs. H2D Transfer vs. GPU Inference vs. Pipeline Total)
    pass_batch_prep_ms: List[float] = []
    pass_cpu_to_gpu_ms: List[float] = []
    pass_gpu_infer_ms: List[float] = []
    pass_postproc_d2h_ms: List[float] = []
    pass_total_pipeline_ms: List[float] = []

    with torch.no_grad():
        for _ in range(max(1, num_runs)):
            _sync(device)
            t_pass_start = time.perf_counter()

            # (a) Colação/preparação dos mini-batches em CPU
            t0 = time.perf_counter()
            batches_cpu = [b for b in cpu_loader]
            t_prep = (time.perf_counter() - t0) * 1e3

            t_h2d = 0.0
            t_infer = 0.0
            t_post = 0.0

            for b_cpu in batches_cpu:
                # (b) Transferência CPU -> GPU
                _sync(device)
                t1 = time.perf_counter()
                b_gpu = b_cpu.to(device)
                _sync(device)
                t_h2d += (time.perf_counter() - t1) * 1e3

                # (c) Inferência pura da rede neural na GPU
                t2 = time.perf_counter()
                logits = model(b_gpu.x, b_gpu.edge_index)
                _sync(device)
                t_infer += (time.perf_counter() - t2) * 1e3

                # (d) Pós-processamento (sigmoid + threshold + transferência de decisão GPU -> CPU)
                t3 = time.perf_counter()
                preds = (torch.sigmoid(logits) >= 0.5).long().cpu()
                _ = preds.numpy()
                _sync(device)
                t_post += (time.perf_counter() - t3) * 1e3

            _sync(device)
            t_total = (time.perf_counter() - t_pass_start) * 1e3

            pass_batch_prep_ms.append(t_prep)
            pass_cpu_to_gpu_ms.append(t_h2d)
            pass_gpu_infer_ms.append(t_infer)
            pass_postproc_d2h_ms.append(t_post)
            pass_total_pipeline_ms.append(t_total)

    # 3. Medição Individual por Snapshot (Single-Snapshot Online Streaming Mode: batch_size=1)
    single_snap_infer_ms: List[float] = []
    single_snap_pipeline_ms: List[float] = []
    single_node_infer_us: List[float] = []
    single_node_pipeline_us: List[float] = []

    with torch.no_grad():
        for g_cpu in snapshots_cpu:
            n_nodes = max(1, int(g_cpu.x.shape[0]))
            _sync(device)
            t_s0 = time.perf_counter()
            g_gpu = g_cpu.to(device)
            _sync(device)

            t_inf0 = time.perf_counter()
            logits = model(g_gpu.x, g_gpu.edge_index)
            _sync(device)
            inf_ms = (time.perf_counter() - t_inf0) * 1e3

            _ = (torch.sigmoid(logits) >= 0.5).long().cpu()
            _sync(device)
            pipe_ms = (time.perf_counter() - t_s0) * 1e3

            single_snap_infer_ms.append(inf_ms)
            single_snap_pipeline_ms.append(pipe_ms)
            single_node_infer_us.append((inf_ms * 1e3) / n_nodes)
            single_node_pipeline_us.append((pipe_ms * 1e3) / n_nodes)

    vram_stats = {
        "allocated_mib": 0.0,
        "reserved_mib": 0.0,
        "peak_allocated_mib": 0.0,
    }
    if device.type == "cuda" and torch.cuda.is_available():
        vram_stats = {
            "allocated_mib": round(torch.cuda.memory_allocated(device) / (1024 ** 2), 3),
            "reserved_mib": round(torch.cuda.memory_reserved(device) / (1024 ** 2), 3),
            "peak_allocated_mib": round(torch.cuda.max_memory_allocated(device) / (1024 ** 2), 3),
        }

    mean_pipe_sec = max(1e-9, float(np.mean(pass_total_pipeline_ms)) / 1e3)
    mean_infer_sec = max(1e-9, float(np.mean(pass_gpu_infer_ms)) / 1e3)

    return {
        "split_evaluated_num_snapshots": num_snapshots,
        "split_evaluated_total_nodes": total_nodes,
        "batch_size": batch_size,
        "warmup_runs": warmup_runs,
        "measured_runs": num_runs,
        "vram_usage": vram_stats,
        "stage_breakdown_per_full_pass_ms": {
            "batch_preparation_cpu_ms": _percentiles(pass_batch_prep_ms),
            "cpu_to_gpu_transfer_ms": _percentiles(pass_cpu_to_gpu_ms),
            "pure_gpu_neural_inference_ms": _percentiles(pass_gpu_infer_ms),
            "postprocess_and_gpu_to_cpu_ms": _percentiles(pass_postproc_d2h_ms),
            "total_classification_pipeline_ms": _percentiles(pass_total_pipeline_ms),
        },
        "per_snapshot_streaming_latency": {
            "pure_neural_inference_ms_per_snapshot": _percentiles(single_snap_infer_ms),
            "classification_pipeline_ms_per_snapshot": _percentiles(single_snap_pipeline_ms),
        },
        "per_node_streaming_latency": {
            "pure_neural_inference_us_per_node": _percentiles(single_node_infer_us),
            "classification_pipeline_us_per_node": _percentiles(single_node_pipeline_us),
        },
        "throughput": {
            "pure_inference_snapshots_per_sec": round(num_snapshots / mean_infer_sec, 2),
            "pure_inference_nodes_per_sec": round(total_nodes / mean_infer_sec, 2),
            "full_pipeline_snapshots_per_sec": round(num_snapshots / mean_pipe_sec, 2),
            "full_pipeline_nodes_per_sec": round(total_nodes / mean_pipe_sec, 2),
        },
        "latency_scope_separation": {
            "neural_inference_latency_measured": True,
            "local_classification_pipeline_latency_measured": True,
            "end_to_end_wan_mitigation_latency_measured": False,
            "note": (
                "Os tempos acima referem-se exclusivamente ao pipeline local de preparação de grafos, "
                "transferência CPU->GPU e inferência neural. Não incluem latência de propagação de rede WAN "
                "nem o tempo de atualização de mapas BPF no kernel Linux."
            ),
        },
    }


def main():
    p = argparse.ArgumentParser(description="Benchmark independente de latência e VRAM do SPECTRE-GRID")
    p.add_argument("--data_path", required=True, help="Bundle de snapshots (.pt)")
    p.add_argument("--checkpoint", required=False, default=None, help="Checkpoint (.pth) opcional a carregar")
    p.add_argument(
        "--model_variant",
        default="cnn_lstm_gat",
        choices=["cnn_lstm_gat", "cnn_lstm_pure", "gat_self_loop", "gat_reverse", "gat_bidir", "gat_residual"],
    )
    p.add_argument("--split", default="val_snapshots", choices=["train_snapshots", "val_snapshots", "external_snapshots"])
    p.add_argument("--batch_size", type=int, default=8)
    p.add_argument("--warmup_runs", type=int, default=10)
    p.add_argument("--num_runs", type=int, default=30)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--output_json", default="data/processed/latency_benchmark_report.json")
    args = p.parse_args()

    device = torch.device(args.device)
    bundle = torch.load(args.data_path, map_location="cpu", weights_only=False)
    if args.split not in bundle:
        raise KeyError(f"Split '{args.split}' não encontrado em {args.data_path}. Disponíveis: {list(bundle.keys())}")

    raw_snaps = list(bundle[args.split])
    snaps = _prepare_variant_graphs(raw_snaps, args.model_variant)
    sample = snaps[0]

    use_gat = args.model_variant != "cnn_lstm_pure"
    use_residual = args.model_variant == "gat_residual"
    model = SPECTRE_GRID(
        num_features=sample.x.shape[2],
        seq_len=sample.x.shape[1],
        cnn_out_channels=32,
        lstm_hidden_size=64,
        gnn_hidden_size=64,
        gat_heads=4,
        use_gat=use_gat,
        use_residual=use_residual,
    ).to(device)

    if args.checkpoint and Path(args.checkpoint).is_file():
        model.load_state_dict(torch.load(args.checkpoint, map_location=device, weights_only=True))
        logging.info(f"Pesos carregados de: {args.checkpoint}")

    res = run_latency_benchmark(
        snapshots_cpu=snaps,
        model=model,
        device=device,
        batch_size=args.batch_size,
        warmup_runs=args.warmup_runs,
        num_runs=args.num_runs,
    )

    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        git_commit = "unknown"

    report = {
        "git_commit": git_commit,
        "device": str(device),
        "gpu_name": torch.cuda.get_device_name(0) if (device.type == "cuda" and torch.cuda.is_available()) else None,
        "torch_version": torch.__version__,
        "data_path": str(args.data_path),
        "checkpoint": str(args.checkpoint) if args.checkpoint else None,
        "model_variant": args.model_variant,
        "split": args.split,
        "benchmark": res,
    }

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logging.info(
        f"Benchmark concluído ({args.model_variant} em {device}) | "
        f"Inferência GPU por snapshot p50={res['per_snapshot_streaming_latency']['pure_neural_inference_ms_per_snapshot']['p50']} ms "
        f"(p95={res['per_snapshot_streaming_latency']['pure_neural_inference_ms_per_snapshot']['p95']} ms, "
        f"p99={res['per_snapshot_streaming_latency']['pure_neural_inference_ms_per_snapshot']['p99']} ms) | "
        f"Pipeline p50={res['per_snapshot_streaming_latency']['classification_pipeline_ms_per_snapshot']['p50']} ms | "
        f"VRAM Pico={res['vram_usage']['peak_allocated_mib']} MiB | Salvo em {out_path}"
    )


if __name__ == "__main__":
    main()
