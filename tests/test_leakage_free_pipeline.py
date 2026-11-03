"""
tests/test_leakage_free_pipeline.py

Suíte de testes automatizados contra vazamento de dados (Data Leakage),
poluição de rótulos, desalinhamento de índices temporais e topologias artificiais
em `preprocessor.py` e `train.py`.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

import preprocessor as pp
import train as tr


def _make_Base_df() -> pd.DataFrame:
    """Cria um DataFrame determinístico com ordem temporal explícita para testes."""
    return pp.generate_test_sample(n=120, seed=123)


def test_outlier_in_test_does_not_contaminate_train_scaler_or_pearson():
    """
    Prova que injetar um outlier extremo (1e9) e inverter rótulos na partição de teste
    NÃO altera a seleção de features (Pearson), nem a média/desvio do StandardScaler,
    nem os tensores do grafo de treino.
    """
    df_clean = _make_Base_df()
    df_polluted = df_clean.copy()

    # Os últimos 20% pertencem à partição de teste (índices >= 96 para n=120)
    test_start = int(len(df_polluted) * 0.80)
    for j in range(20):
        df_polluted.loc[test_start:, f"f{j}"] = 1e9 * (j + 1)
    df_polluted.loc[test_start:, "target"] = 1 - df_polluted.loc[test_start:, "target"]

    bundle_clean = pp.build_inductive_splits(df_clean, target_col="target", time_col="timestamp", k=10, seq_len=5)
    bundle_polluted = pp.build_inductive_splits(df_polluted, target_col="target", time_col="timestamp", k=10, seq_len=5)

    assert bundle_clean["top_features"] == bundle_polluted["top_features"], (
        "Vazamento detectado: alteração nos dados de teste mudou as Top-K features selecionadas!"
    )
    np.testing.assert_allclose(
        bundle_clean["scaler_mean"],
        bundle_polluted["scaler_mean"],
        rtol=0,
        atol=1e-7,
        err_msg="Vazamento detectado: outlier no teste alterou a média do StandardScaler de treino!",
    )
    np.testing.assert_allclose(
        bundle_clean["scaler_scale"],
        bundle_polluted["scaler_scale"],
        rtol=0,
        atol=1e-7,
        err_msg="Vazamento detectado: outlier no teste alterou o desvio padrão do StandardScaler de treino!",
    )
    assert torch.equal(bundle_clean["train"].x, bundle_polluted["train"].x), (
        "Vazamento detectado: o tensor x do grafo de treino mudou quando o teste foi modificado!"
    )


def test_time_col_sorting_preserves_row_feature_alignment():
    """
    Verifica que ordenar um DataFrame fora de ordem por `time_col` preserva o alinhamento
    exato entre cada linha (src_ip, dst_ip, target) e seu vetor de features (corrige o antigo
    bug de `feat_df.loc[row.name]` após `reset_index`).
    """
    df = pd.DataFrame(
        [
            {"timestamp": "2026-01-01T00:00:03", "src_ip": "10.0.0.1", "dst_ip": "10.0.1.1", "f0": 300.0, "target": 1},
            {"timestamp": "2026-01-01T00:00:01", "src_ip": "10.0.0.1", "dst_ip": "10.0.1.1", "f0": 100.0, "target": 1},
            {"timestamp": "2026-01-01T00:00:02", "src_ip": "10.0.0.1", "dst_ip": "10.0.1.1", "f0": 200.0, "target": 1},
        ]
    )
    from sklearn.preprocessing import StandardScaler

    # Scaler identidade para inspecionar os valores exatos na sequência temporal do nó
    scaler = StandardScaler()
    scaler.mean_ = np.array([0.0], dtype=np.float32)
    scaler.scale_ = np.array([1.0], dtype=np.float32)
    scaler.var_ = np.array([1.0], dtype=np.float32)
    scaler.n_features_in_ = 1

    g = pp.build_graph(
        df,
        top_features=["f0"],
        seq_len=3,
        time_col="timestamp",
        target_col="target",
        scaler=scaler,
        fit_scaler=False,
    )
    src_idx = g.ip2idx["10.0.0.1"]
    seq = g.x[src_idx, :, 0].numpy().tolist()
    assert seq == [100.0, 200.0, 300.0], f"Sequência temporal desalinhada após sort_values: {seq}"


def test_passive_victim_destination_not_labeled_as_attacker():
    """
    Verifica que num grafo com duas fontes atacantes (10.0.0.1, 10.0.0.2) e uma vítima
    puramente passiva (10.0.1.99), a vítima permanece como vértice do grafo, recebe as
    arestas dirigidas, mas NÃO recebe rótulo de atacante (y == 0).
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

    assert int(g.y[att1_idx].item()) == 1
    assert int(g.y[att2_idx].item()) == 1
    assert int(g.y[benign_idx].item()) == 0
    assert int(g.y[victim_idx].item()) == 0, "Vítima passiva não pode ser rotulada como atacante (label=1)!"

    edges = set(zip(g.edge_index[0].tolist(), g.edge_index[1].tolist()))
    assert (att1_idx, victim_idx) in edges
    assert (att2_idx, victim_idx) in edges


def test_missing_ip_columns_rejects_fake_sequential_edges():
    """
    Verifica que a ausência de colunas de IP levanta ValueError por padrão (impedindo a criação
    silenciosa de arestas entre linhas consecutivas) e que o modo de baseline tabular cria apenas
    auto-loops (i -> i).
    """
    df_no_ip = pd.DataFrame(
        {
            "f0": [1.0, 2.0, 3.0, 4.0],
            "f1": [0.5, 1.5, 2.5, 3.5],
            "target": [0, 1, 0, 1],
        }
    )
    with pytest.raises(ValueError, match="Colunas de IP de origem/destino não encontradas"):
        pp.build_graph(df_no_ip, top_features=["f0", "f1"], seq_len=2, allow_row_fallback=False)

    g_base = pp.build_graph(df_no_ip, top_features=["f0", "f1"], seq_len=2, allow_row_fallback=True)
    src, dst = g_base.edge_index[0], g_base.edge_index[1]
    assert torch.equal(src, dst), "Baseline sem IPs deve conter apenas auto-loops (i -> i), sem ligar (i -> i+1)!"


def test_train_never_uses_test_set_for_scheduler_or_checkpoint():
    """
    Verifica que o processo de treinamento, seleção de melhor época (Early Stopping) e
    pesos salvos em disco dependem EXCLUSIVAMENTE de Treino e Validação: corromper o
    conjunto de Teste não altera em nada os pesos do modelo selecionado nem a melhor época.
    """
    df = _make_Base_df()
    bundle = pp.build_inductive_splits(df, target_col="target", time_col="timestamp", k=20, seq_len=6)

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt1 = str(Path(tmpdir) / "ckpt1.pth")
        ckpt2 = str(Path(tmpdir) / "ckpt2.pth")

        res1 = tr.train_and_evaluate(
            train_g=bundle["train"].clone(),
            val_g=bundle["val"].clone(),
            test_g=bundle["test"].clone(),
            epochs=6,
            lr=0.002,
            patience=4,
            seed=42,
            checkpoint_out=ckpt1,
        )

        # Corromper completamente o conjunto de teste (inverter rótulos e zerar features)
        corrupted_test = bundle["test"].clone()
        corrupted_test.x = torch.zeros_like(corrupted_test.x)
        corrupted_test.y = 1 - corrupted_test.y

        res2 = tr.train_and_evaluate(
            train_g=bundle["train"].clone(),
            val_g=bundle["val"].clone(),
            test_g=corrupted_test,
            epochs=6,
            lr=0.002,
            patience=4,
            seed=42,
            checkpoint_out=ckpt2,
        )

        assert res1["best_epoch"] == res2["best_epoch"], (
            "O conjunto de teste influenciou a escolha da melhor época!"
        )
        assert res1["validation_best"] == res2["validation_best"], (
            "As métricas de validação mudaram quando o conjunto de teste foi alterado!"
        )

        w1 = torch.load(ckpt1, map_location="cpu", weights_only=True)
        w2 = torch.load(ckpt2, map_location="cpu", weights_only=True)
        for k in w1:
            assert torch.equal(w1[k], w2[k]), f"Peso '{k}' do checkpoint mudou quando o test set foi alterado!"
