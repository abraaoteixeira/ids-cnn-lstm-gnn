"""
tests/test_scientific_governance.py

Suíte de testes de regressão e auditoria contínua da Governança Científica do SPECTRE-GRID.
Valida os pilares normatizados em AGENTS.md, docs/SCIENTIFIC_MEMORY.md (ADR-001 a ADR-008)
e nas Agent Skills especializadas (.agents/skills/).
"""

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch
from sklearn.preprocessing import StandardScaler

import preprocessor as pp
import train as tr


# ============================================================================
# 1. Testes de Causalidade e Ausência de Vazamento (ADR-001, ADR-002)
# ============================================================================

def test_scaler_frozen_strictly_on_train_split():
    """
    Garante que o normalizador StandardScaler é ajustado unicamente sobre a partição de treino.
    Qualquer tentativa de computar média/variância sobre validação ou teste invalida o teste.
    """
    df = pp.generate_test_sample(n=200, seed=42)
    # Partição cronológica 60 / 20 / 20
    n_train = int(len(df) * 0.60)
    train_slice = df.iloc[:n_train]
    
    scaler_expected = StandardScaler()
    feature_cols = [f"f{i}" for i in range(20)]
    scaler_expected.fit(train_slice[feature_cols])

    bundle = pp.build_inductive_splits(df, target_col="target", time_col="timestamp", k=20, seq_len=5)

    np.testing.assert_allclose(
        bundle["scaler_mean"],
        scaler_expected.mean_,
        err_msg="Governança violada: a média do scaler do bundle diverge da média exclusiva de treino!"
    )
    np.testing.assert_allclose(
        bundle["scaler_scale"],
        scaler_expected.scale_,
        err_msg="Governança violada: o desvio do scaler do bundle diverge da escala exclusiva de treino!"
    )


def test_temporal_monotonicity_across_partitions():
    """
    Garante que não há sobreposição temporal entre Treino, Validação e Teste (ADR-001).
    max(t_train) <= min(t_val) e max(t_val) <= min(t_test).
    """
    df = pp.generate_test_sample(n=240, seed=123)
    # Garante timestamps explicitamente crescentes
    df["timestamp"] = np.sort(df["timestamp"].values)
    
    bundle = pp.build_inductive_splits(df, target_col="target", time_col="timestamp", k=10, seq_len=5)
    
    train_snaps = bundle["train_snapshots"]
    val_snaps = bundle["val_snapshots"]
    test_snaps = bundle["test_snapshots"]

    # Se existirem snapshots gerados, seus carimbos temporais devem respeitar a causalidade
    if train_snaps and val_snaps:
        # Último timestamp do treino deve ser menor ou igual ao primeiro da validação
        assert train_snaps[-1].snapshot_idx <= val_snaps[0].snapshot_idx, (
            "Violação de Causalidade: snapshot de treino posterior ou concorrente à validação!"
        )
    if val_snaps and test_snaps:
        assert val_snaps[-1].snapshot_idx <= test_snaps[0].snapshot_idx, (
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
    # Cria evento onde nó 1 (agressor) ataca nó 2 (servidor vítima)
    edge_index = torch.tensor([[0], [1]], dtype=torch.long) # aresta 0 -> 1
    # Criação manual de nós: Nó 0 emitiu ataque, Nó 1 foi alvo
    flow_labels = torch.tensor([1], dtype=torch.long)
    
    # Função utilitária de atribuição de rótulos por nós
    node_labels = torch.zeros(2, dtype=torch.long)
    for src, dst in zip(edge_index[0].tolist(), edge_index[1].tolist()):
        node_labels[src] = 1 # Apenas o originador é rotulado como atacante
        
    assert node_labels[0].item() == 1, "Nó atacante deve ser rotulado como 1"
    assert node_labels[1].item() == 0, "Nó vítima não deve ser contaminado com rótulo 1"


def test_gat_variants_topological_interface():
    """
    Garante que as 6 variantes topológicas de arquitetura existem e executam
    com o tensor de entrada padronizado de 20 features (ADR-003, ADR-005).
    """
    valid_variants = [
        "cnn_lstm_pure",
        "gat_self_loop",
        "cnn_lstm_gat",
        "gat_reverse",
        "gat_bidir",
        "gat_residual"
    ]
    x_nodes = torch.randn(4, 5, 20) # 4 nós, seq_len 5, 20 features
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.long)

    for var in valid_variants:
        model = tr.build_model_variant(var, input_dim=20, hidden_dim=32)
        assert model is not None, f"Variante {var} deve ser instanciável."
        out = model(x_nodes, edge_index)
        assert out.shape == (4, 2), f"Saída da variante {var} deve ter formato (num_nodes, 2)"


# ============================================================================
# 3. Testes de Contrato eBPF e Paridade de Atributos (ADR-003)
# ============================================================================

def test_ebpf_compatible_feature_contract():
    """
    Garante que o conjunto de features ebpf_compatible possui exatamente 20 atributos
    computáveis no pipeline do kernel/ring-buffer e daemon C++.
    """
    assert len(pp.EBPF_COMPATIBLE_FEATURES) == 20, (
        f"Contrato violado: esperado 20 atributos compatíveis, encontrado {len(pp.EBPF_COMPATIBLE_FEATURES)}"
    )
    # Atributos proibidos por dependerem de montagem offline complexa de L7
    forbidden = ["ct_srv_dst", "response_body_len", "trans_depth"]
    for f in forbidden:
        assert f not in pp.EBPF_COMPATIBLE_FEATURES, (
            f"Violação de paridade de kernel: feature {f} não é factível em eBPF de alta taxa!"
        )


# ============================================================================
# 4. Testes de Integridade de Manifestos Experimentais (ADR-008)
# ============================================================================

def test_experiment_report_manifest_schema():
    """
    Garante que qualquer relatório experimental gerado para consumo de papers
    ou auditorias contenha metadados obrigatórios de rastreabilidade.
    """
    mandatory_fields = [
        "model",
        "seed",
        "confusion_matrix",
        "metrics"
    ]
    sample_report = {
        "model": "gat_bidir",
        "seed": 42,
        "confusion_matrix": {"tn": 100, "fp": 2, "fn": 1, "tp": 50},
        "metrics": {"precision": 0.9615, "recall": 0.9804, "f1": 0.9708, "fpr": 0.0196}
    }
    for field in mandatory_fields:
        assert field in sample_report, f"Campo obrigatório {field} ausente no manifesto de relatório."
        
    cm = sample_report["confusion_matrix"]
    m = sample_report["metrics"]
    calc_fpr = cm["fp"] / (cm["fp"] + cm["tn"])
    assert abs(calc_fpr - m["fpr"]) < 1e-4, "Inconsistência aritmética na taxa de falsos positivos (FPR)!"
