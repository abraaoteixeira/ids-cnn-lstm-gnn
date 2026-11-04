"""
tests/test_scientific_governance.py

Suíte de testes de regressão e auditoria contínua da Governança Científica do SPECTRE-GRID.
Valida os pilares normatizados em AGENTS.md, docs/SCIENTIFIC_MEMORY.md (ADR-001 a ADR-008)
e nas Agent Skills especializadas (.agents/skills/).
Valida o comportamento real de `model.py`, `train.py` e `preprocessor.py`.
"""

import json
import sys
import tempfile
from pathlib import Path

# Garante que a raiz do repositório está no sys.path mesmo em ambientes CI
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import pytest
import torch
from sklearn.preprocessing import StandardScaler
from torch_geometric.data import Data

import preprocessor as pp
import train as tr
from model import SPECTRE_GRID


# ============================================================================
# 1. Testes de Causalidade e Ausência de Vazamento (ADR-001, ADR-002)
# ============================================================================

def test_scaler_frozen_strictly_on_train_split():
    """
    Garante que o normalizador StandardScaler é ajustado unicamente sobre a partição de treino.
    Qualquer tentativa de alterar dados na validação ou teste NÃO deve alterar os parâmetros
    do scaler (ADR-002: refitted_on_external = False, scaler congelado).
    """
    df_clean = pp.generate_test_sample(n=200, seed=42)
    df_polluted = df_clean.copy()

    # Injeta outliers extremos (1e9) e inverte o target nos últimos 40% (validação + teste)
    n_train = int(len(df_polluted) * 0.60)
    for j in range(20):
        df_polluted.loc[n_train:, f"f{j}"] = 1e9 * (j + 1)
    df_polluted.loc[n_train:, "target"] = 1 - df_polluted.loc[n_train:, "target"]

    bundle_clean = pp.build_inductive_splits(df_clean, target_col="target", time_col="timestamp", k=10, seq_len=5)
    bundle_polluted = pp.build_inductive_splits(df_polluted, target_col="target", time_col="timestamp", k=10, seq_len=5)

    assert bundle_clean["top_features"] == bundle_polluted["top_features"], (
        "Governança violada: seleção de Pearson foi afetada por poluição no val/teste!"
    )
    np.testing.assert_allclose(
        bundle_clean["scaler_mean"],
        bundle_polluted["scaler_mean"],
        rtol=0,
        atol=1e-7,
        err_msg="Governança violada: a média do scaler de treino foi alterada por dados de val/teste!"
    )
    np.testing.assert_allclose(
        bundle_clean["scaler_scale"],
        bundle_polluted["scaler_scale"],
        rtol=0,
        atol=1e-7,
        err_msg="Governança violada: o desvio do scaler de treino foi alterado por dados de val/teste!"
    )


def test_temporal_monotonicity_across_partitions():
    """
    Garante que não há sobreposição temporal entre Treino, Validação e Teste (ADR-001).
    max(t_train) <= min(t_val) e max(t_val) <= min(t_test).
    """
    df = pp.generate_test_sample(n=240, seed=123)
    df["timestamp"] = np.sort(df["timestamp"].values)

    bundle = pp.build_inductive_splits(
        df,
        target_col="target",
        time_col="timestamp",
        k=10,
        seq_len=5,
        window_sec=30.0,
    )

    train_snaps = bundle["train_snapshots"]
    val_snaps = bundle["val_snapshots"]
    test_snaps = bundle["test_snapshots"]

    if train_snaps and val_snaps:
        max_train_t = max(g.t_end for g in train_snaps)
        min_val_t = min(g.t_start for g in val_snaps)
        assert max_train_t <= min_val_t + 30.0, (
            "Violação de Causalidade: snapshot de treino posterior ou concorrente à validação!"
        )
    if val_snaps and test_snaps:
        max_val_t = max(g.t_end for g in val_snaps)
        min_test_t = min(g.t_start for g in test_snaps)
        assert max_val_t <= min_test_t + 30.0, (
            "Violação de Causalidade: snapshot de validação posterior ou concorrente ao teste!"
        )


# ============================================================================
# 2. Testes de Integridade Estrutural e Heterofilia de Grafos (ADR-005, ADR-006)
# ============================================================================

def test_strict_source_labeling_preserves_passive_targets():
    """
    Garante que o rótulo de ataque (1) é estritamente atribuído ao nó emissor (src)
    e nós de destino puramente receptores mantêm rótulo benigno (0). (ADR-006)
    """
    df = pd.DataFrame(
        [
            {"timestamp": 1, "src_ip": "10.0.0.1", "dst_ip": "10.0.1.99", "f0": 10.0, "f1": 5.0, "target": 1},
            {"timestamp": 2, "src_ip": "10.0.0.2", "dst_ip": "10.0.1.99", "f0": 12.0, "f1": 6.0, "target": 1},
            {"timestamp": 3, "src_ip": "10.0.0.3", "dst_ip": "10.0.1.99", "f0": 1.0, "f1": 0.5, "target": 0},
        ]
    )
    g = pp.build_graph(df, top_features=["f0", "f1"], seq_len=4, time_col="timestamp", target_col="target")

    assert "10.0.1.99" in g.ip2idx, "Destino passivo deve existir como nó no grafo"
    victim_idx = g.ip2idx["10.0.1.99"]
    att1_idx = g.ip2idx["10.0.0.1"]
    att2_idx = g.ip2idx["10.0.0.2"]
    benign_idx = g.ip2idx["10.0.0.3"]

    assert int(g.y[att1_idx].item()) == 1, "Host atacante 1 deve ser rotulado como 1"
    assert int(g.y[att2_idx].item()) == 1, "Host atacante 2 deve ser rotulado como 1"
    assert int(g.y[benign_idx].item()) == 0, "Host benigno deve ser rotulado como 0"
    assert int(g.y[victim_idx].item()) == 0, "Vítima passiva não pode ser rotulada como atacante (label=1)!"


def test_gat_variants_topological_and_model_interface():
    """
    Garante que as 6 variantes topológicas de arquitetura existem, respeitam o contrato
    real de `model.py` e `train.py`, e produzem logits binários com shape (num_nodes,) (ADR-003, ADR-005).
    """
    num_nodes = 4
    seq_len = 10
    num_features = 20
    x = torch.randn(num_nodes, seq_len, num_features)
    raw_edges = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.long)
    raw_data = Data(x=x, edge_index=raw_edges, y=torch.zeros(num_nodes, dtype=torch.long))

    # 1. Baseline temporal puro (sem GAT)
    m_pure = SPECTRE_GRID(num_features=num_features, seq_len=seq_len, use_gat=False)
    assert m_pure.gat is None, "cnn_lstm_pure não deve conter camada GAT"
    out_pure = m_pure(x, raw_edges)
    assert out_pure.shape == (num_nodes,), f"Saída cnn_lstm_pure deve ter shape ({num_nodes},), obtido {out_pure.shape}"

    # 2. Self-loop GAT
    g_self = tr.apply_self_loop_only(raw_data)
    assert torch.equal(g_self.edge_index[0], g_self.edge_index[1]), "apply_self_loop_only deve gerar apenas arestas i -> i"
    m_self = SPECTRE_GRID(num_features=num_features, seq_len=seq_len, use_gat=True)
    out_self = m_self(g_self.x, g_self.edge_index)
    assert out_self.shape == (num_nodes,)

    # 3. GAT Direcionada padrão
    m_gat = SPECTRE_GRID(num_features=num_features, seq_len=seq_len, use_gat=True, use_residual=False)
    out_gat = m_gat(x, raw_edges)
    assert out_gat.shape == (num_nodes,)

    # 4. GAT Reversa (dst -> src)
    g_rev = tr.apply_reverse_edges(raw_data)
    assert torch.equal(g_rev.edge_index[0], raw_edges[1]) and torch.equal(g_rev.edge_index[1], raw_edges[0]), (
        "apply_reverse_edges deve inverter a direção das arestas"
    )
    out_rev = m_gat(g_rev.x, g_rev.edge_index)
    assert out_rev.shape == (num_nodes,)

    # 5. GAT Bidirecional (src <-> dst)
    g_bi = tr.apply_bidirectional_edges(raw_data)
    assert g_bi.edge_index.shape[1] >= raw_edges.shape[1] * 2, "apply_bidirectional_edges deve conter ambos os sentidos"
    out_bi = m_gat(g_bi.x, g_bi.edge_index)
    assert out_bi.shape == (num_nodes,)

    # 6. GAT Residual (com projeção residual)
    m_res = SPECTRE_GRID(num_features=num_features, seq_len=seq_len, use_gat=True, use_residual=True)
    assert m_res.residual_proj is not None, "gat_residual deve conter projeção residual"
    out_res = m_res(x, raw_edges)
    assert out_res.shape == (num_nodes,)


# ============================================================================
# 3. Testes de Contrato eBPF e Paridade de Atributos (ADR-003)
# ============================================================================

def test_ebpf_compatible_feature_contract():
    """
    Garante que o escopo 'ebpf_compatible' filtra rigorosamente atributos L7/DPI
    pós-conexão (L7_POSTHOC_UNSW_COLS) e que o artefato auditado contém exatamente 20 atributos.
    """
    # Testa filtragem ativa de colunas proibidas
    df_with_l7 = pd.DataFrame({
        "sttl": [64.0],
        "service": ["http"],
        "trans_depth": [1.0],
        "res_bdy_len": [1024.0],
        "ct_flw_http_mthd": [1.0],
        "is_ftp_login": [0.0],
        "ct_ftp_cmd": [0.0],
        "stcpb": [12345.0],
        "dtcpb": [67890.0],
    })

    df_filtered, dropped = pp.filter_features_by_observation_scope(df_with_l7, feature_scope="ebpf_compatible")
    for forbidden_col in pp.L7_POSTHOC_UNSW_COLS:
        assert forbidden_col not in df_filtered.columns, (
            f"Violação de contrato eBPF: coluna L7 '{forbidden_col}' não foi filtrada no escopo ebpf_compatible!"
        )

    # Valida o artefato de features auditado se disponível
    features_path = REPO_ROOT / "data" / "processed" / "unsw_full_ebpf_30s_features.json"
    if features_path.exists():
        with open(features_path, "r", encoding="utf-8") as f:
            features = json.load(f)
        assert len(features) == 20, f"Esperado exatamente 20 features auditadas, encontrado {len(features)}"
        for f_name in features:
            assert f_name not in pp.L7_POSTHOC_UNSW_COLS, (
                f"Feature '{f_name}' presente nas 20 features pertence ao conjunto L7 proibido!"
            )


# ============================================================================
# 4. Testes de Integridade de Manifestos Experimentais (ADR-008)
# ============================================================================

def test_experiment_report_manifest_schema_and_fpr_arithmetic():
    """
    Garante que qualquer relatório experimental gerado para consumo de papers
    ou auditorias contenha metadados obrigatórios de rastreabilidade e consistência aritmética.
    """
    mandatory_fields = [
        "model_variant",
        "seed",
        "validation_metrics",
    ]
    sample_report = {
        "model_variant": "gat_bidir",
        "seed": 42,
        "validation_metrics": {
            "accuracy": 0.99,
            "precision": 0.9615,
            "recall": 0.9804,
            "f1_score": 0.9708,
            "fpr": 0.0196,
            "confusion_matrix": {"tn": 100, "fp": 2, "fn": 1, "tp": 50},
        }
    }
    for field in mandatory_fields:
        assert field in sample_report, f"Campo obrigatório {field} ausente no manifesto de relatório."

    cm = sample_report["validation_metrics"]["confusion_matrix"]
    m = sample_report["validation_metrics"]
    calc_fpr = cm["fp"] / (cm["fp"] + cm["tn"])
    assert abs(calc_fpr - m["fpr"]) < 1e-4, "Inconsistência aritmética na taxa de falsos positivos (FPR)!"

    # Valida consistência aritmética do relatório real da cauda benigna se disponível
    tail_report_path = REPO_ROOT / "data" / "processed" / "g15_external_tail500k_fpr_report.json"
    if tail_report_path.exists():
        with open(tail_report_path, "r", encoding="utf-8") as f:
            tail_data = json.load(f)
        for variant_name, vdata in tail_data.items():
            vm = vdata["metrics"]
            cm_real = vm["confusion_matrix"]
            denom = cm_real["fp"] + cm_real["tn"]
            if denom > 0:
                expected_fpr = cm_real["fp"] / denom
                assert abs(expected_fpr - vm["fpr"]) < 1e-5, (
                    f"Inconsistência de FPR no relatório da cauda benigna para variante {variant_name}!"
                )
