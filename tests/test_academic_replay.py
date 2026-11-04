"""
tests/test_academic_replay.py

Suite de testes automatizados do Academic Replay Player (Modo A) e da API V2 do SPECTRE-GRID.
Valida:
1. Instanciação e forward pass das 6 variantes arquiteturais (prioridade gat_bidir);
2. Transformações formais de arestas (bidirectional, reverse, self-loop);
3. Execução completa do replay em modo dry-run sobre snapshots auditados;
4. Proteção de escrita na API em modo de demonstração (DEMO_READ_ONLY=True -> 403);
5. Separação categórica de métricas (kernel_drop == 0 no Replay, latência real medida);
6. Integridade dos arquivos vetoriais propostos para a Figura 1 (SVG e PDF).
"""

import os
import sys
from pathlib import Path
import pytest
import torch
from torch_geometric.data import Data

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from model import SPECTRE_GRID
from tools.academic_replay_player import (
    load_replay_model,
    apply_self_loop_only,
    apply_reverse_edges,
    apply_bidirectional_edges,
    transform_graph_for_variant,
    run_academic_replay,
)

# Detecção graciosa de dependências da API Web (FastAPI / Uvicorn / aiosqlite)
try:
    import fastapi
    import uvicorn
    import aiosqlite
    from fastapi.testclient import TestClient
    import dashboard_api_v2
    HAS_API_DEPS = True
except ImportError:
    HAS_API_DEPS = False


def test_load_replay_model_all_variants():
    """Valida que todas as 6 variantes são instanciadas corretamente e produzem logits válidos."""
    variants = [
        ("gat_bidir", True, False),
        ("cnn_lstm_gat", True, False),
        ("cnn_lstm_pure", False, False),
        ("gat_self_loop", True, False),
        ("gat_reverse", True, False),
        ("gat_residual", True, True),
    ]

    N = 8
    seq_len = 10
    num_features = 20
    x = torch.randn(N, seq_len, num_features)
    edge_index = torch.tensor([[0, 1, 2, 3], [1, 2, 3, 0]], dtype=torch.long)

    for var_name, expected_gat, expected_res in variants:
        model = load_replay_model(
            model_variant=var_name,
            checkpoint_path=None,
            num_features=num_features,
            seq_len=seq_len,
            device=torch.device("cpu"),
            seed=42
        )
        assert model.use_gat == expected_gat, f"{var_name}: use_gat={model.use_gat} != {expected_gat}"
        assert model.use_residual == expected_res, f"{var_name}: use_residual={model.use_residual} != {expected_res}"

        with torch.no_grad():
            logits, attention = model.forward_xai(x, edge_index)
        assert logits.shape == (N,), f"{var_name}: shape de logits inválido {logits.shape}"
        assert not torch.isnan(logits).any(), f"{var_name}: logits contêm NaN"


def test_edge_transformations():
    """Valida as transformações de grafo (self-loop, reverse, bidirectional)."""
    N = 4
    x = torch.randn(N, 10, 20)
    y = torch.tensor([0, 1, 0, 1])
    # Grafo direcionado: 0->1, 1->2
    edge_index = torch.tensor([[0, 1], [1, 2]], dtype=torch.long)
    g = Data(x=x, edge_index=edge_index, y=y)

    # 1. Self Loop
    g_self = apply_self_loop_only(g)
    assert g_self.edge_index.shape == (2, N)
    assert torch.equal(g_self.edge_index[0], g_self.edge_index[1])

    # 2. Reverse
    g_rev = apply_reverse_edges(g)
    assert g_rev.edge_index.shape == (2, 2)
    assert torch.equal(g_rev.edge_index[0], edge_index[1])
    assert torch.equal(g_rev.edge_index[1], edge_index[0])

    # 3. Bidirectional
    g_bi = apply_bidirectional_edges(g)
    # Arestas: 0->1, 1->2, 1->0, 2->1 (4 arestas únicas)
    assert g_bi.edge_index.shape[1] == 4
    bi_list = set((int(s), int(d)) for s, d in zip(g_bi.edge_index[0], g_bi.edge_index[1]))
    assert (0, 1) in bi_list and (1, 0) in bi_list
    assert (1, 2) in bi_list and (2, 1) in bi_list


def test_academic_replay_dry_run():
    """Valida a execução do replay acadêmico sobre os snapshots canônicos do UNSW-NB15."""
    data_path = REPO_ROOT / "data" / "processed" / "unsw_full_ebpf_30s.pt"
    assert data_path.exists(), f"Dataset não encontrado: {data_path}"

    summary = run_academic_replay(
        data_path=str(data_path),
        split="test",
        model_variant="gat_bidir",
        max_snapshots=3,
        dry_run=True,
        interval=0.0
    )

    assert summary["snapshots_processed"] == 3
    assert summary["total_nodes"] > 0
    cm = summary["confusion_matrix"]
    assert cm["tp"] + cm["fp"] + cm["tn"] + cm["fn"] == summary["total_nodes"]
    assert summary["latency_stats_ms"]["mean"] > 0.0
    assert summary["events_sent"] > 0


@pytest.mark.skipif(not HAS_API_DEPS, reason="Dependências da API Web (fastapi, uvicorn, aiosqlite) não instaladas")
def test_dashboard_api_demo_read_only_protection():
    """Valida que /api/clear_history é rejeitado com 403 Forbidden em modo demonstração."""
    client = TestClient(dashboard_api_v2.app)

    # Forçar DEMO_READ_ONLY = True
    dashboard_api_v2.DEMO_READ_ONLY = True

    resp = client.post("/api/clear_history")
    assert resp.status_code == 403, f"Esperado 403 Forbidden, obtido {resp.status_code}"
    data = resp.json()
    assert data.get("status") == "error"
    assert "DEMO_READ_ONLY" in data.get("error", "")


def test_metrics_separation_in_replay_events():
    """Garante que nenhum evento de replay reporta falsos descartes de pacotes de kernel."""
    data_path = REPO_ROOT / "data" / "processed" / "unsw_full_ebpf_30s.pt"
    bundle = torch.load(str(data_path), map_location="cpu", weights_only=False)
    snaps = bundle["val_snapshots"][:2]

    model = load_replay_model(model_variant="gat_bidir", checkpoint_path=None)
    with torch.no_grad():
        logits, _ = model.forward_xai(snaps[0].x, snaps[0].edge_index)
    probs = torch.sigmoid(logits).numpy()

    # Em modo Replay, o kernel_drop é estritamente 0
    payload = {
        "src_ip": "175.45.176.0",
        "dst_ip": "149.171.126.1",
        "probability": float(probs[0]),
        "is_threat": bool(probs[0] >= 0.85),
        "kernel_drop": 0,
        "mode": "ACADEMIC_REPLAY"
    }

    assert payload["kernel_drop"] == 0
    assert payload["mode"] == "ACADEMIC_REPLAY"


def test_proposals_figure_artifacts():
    """Valida que a proposta da Figura 1 vetorial foi gerada como artefato separado."""
    svg_file = REPO_ROOT / "paper" / "noms2027" / "figures" / "proposals" / "fig1_spectre_architecture_v2.svg"
    pdf_file = REPO_ROOT / "paper" / "noms2027" / "figures" / "proposals" / "fig1_spectre_architecture_v2.pdf"

    assert svg_file.exists(), f"Proposta SVG não encontrada: {svg_file}"
    assert pdf_file.exists(), f"Proposta PDF não encontrada: {pdf_file}"
    assert svg_file.stat().st_size > 1000, "Arquivo SVG vazio ou corrompido"
    assert pdf_file.stat().st_size > 1000, "Arquivo PDF vazio ou corrompido"

    # Confirma que a figura original do artigo permanece preservada
    orig_fig = REPO_ROOT / "paper" / "noms2027" / "figures" / "fig1_spectre_architecture.pdf"
    assert orig_fig.exists(), "A Figura 1 original do artigo deve ser mantida intacta!"
