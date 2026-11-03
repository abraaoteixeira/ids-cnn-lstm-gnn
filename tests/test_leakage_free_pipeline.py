"""
tests/test_leakage_free_pipeline.py

Suíte de testes automatizados contra vazamento de dados (Data Leakage),
poluição de rótulos, desalinhamento de índices temporais, topologias artificiais,
violação de causalidade em Snapshots Temporais G_t = (V_t, E_t) e uso de grafos legados
em `preprocessor.py` e `train.py`.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch
from sklearn.preprocessing import StandardScaler
from torch_geometric.data import Data

import preprocessor as pp
import train as tr


def _make_base_df() -> pd.DataFrame:
    """Cria um DataFrame determinístico com ordem temporal explícita para testes."""
    return pp.generate_test_sample(n=120, seed=123)


def _identity_scaler(n_features: int) -> StandardScaler:
    scaler = StandardScaler()
    scaler.mean_ = np.zeros((n_features,), dtype=np.float32)
    scaler.scale_ = np.ones((n_features,), dtype=np.float32)
    scaler.var_ = np.ones((n_features,), dtype=np.float32)
    scaler.n_features_in_ = n_features
    return scaler


def test_outlier_in_test_does_not_contaminate_train_scaler_or_pearson():
    """
    Prova que injetar um outlier extremo (1e9) e inverter rótulos na partição de teste
    NÃO altera a seleção de features (Pearson), nem a média/desvio do StandardScaler,
    nem os tensores do grafo de treino.
    """
    df_clean = _make_base_df()
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
    scaler = _identity_scaler(1)

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
    df = _make_base_df()
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


def test_temporal_snapshots_causality_no_future_edges_and_window_labels():
    """
    Verifica nos snapshots temporais G_t = (V_t, E_t):
      1. Isolamento temporal e ausência de arestas futuras: uma comunicação em t=65s..75s (janela 2)
         NÃO aparece como nó nem aresta na janela 0 (t=0s..10s).
      2. Correção dos rótulos por janela: o host 10.0.0.1 que é benigno na janela 0 (target=0) e
         ataca na janela 2 (target=1) recebe y=0 na janela 0 e y=1 na janela 2.
      3. Snapshots vazios: o intervalo [30s, 60s) (janela 1) sem eventos é ignorado com segurança,
         e um DataFrame vazio retorna `[]`.
      4. Preservação das sequências de features dentro de cada snapshot sem contaminação futura.
    """
    assert pp.build_temporal_snapshots(pd.DataFrame(), top_features=["f0"], window_sec=30.0) == []

    df = pd.DataFrame(
        [
            # Janela 0: [1000, 1030) -> 10.0.0.1 envia apenas tráfego benigno para 10.0.1.1
            {"Stime": 1000.0, "srcip": "10.0.0.1", "dstip": "10.0.1.1", "f0": 11.0, "f1": 1.0, "Label": 0},
            {"Stime": 1010.0, "srcip": "10.0.0.1", "dstip": "10.0.1.1", "f0": 22.0, "f1": 2.0, "Label": 0},
            # Janela 1: [1030, 1060) -> VAZIA (nenhum fluxo)
            # Janela 2: [1060, 1090) -> 10.0.0.1 passa a atacar 10.0.1.2, e 10.0.0.9 ataca 10.0.1.99
            {"Stime": 1065.0, "srcip": "10.0.0.1", "dstip": "10.0.1.2", "f0": 999.0, "f1": 90.0, "Label": 1},
            {"Stime": 1075.0, "srcip": "10.0.0.9", "dstip": "10.0.1.99", "f0": 888.0, "f1": 80.0, "Label": 1},
        ]
    )
    scaler = _identity_scaler(2)
    snapshots = pp.build_temporal_snapshots(
        df,
        top_features=["f0", "f1"],
        window_sec=30.0,
        seq_len=3,
        time_col="Stime",
        target_col="Label",
        scaler=scaler,
    )

    # Deve conter exatamente 2 snapshots (janelas 0 e 2; a janela 1 vazia foi ignorada)
    assert len(snapshots) == 2
    g0, g2 = snapshots[0], snapshots[1]
    assert g0.window_id == 0
    assert g2.window_id == 2

    # 1. Ausência de nós e arestas futuras em g0
    assert set(g0.ip2idx.keys()) == {"10.0.0.1", "10.0.1.1"}
    assert "10.0.1.2" not in g0.ip2idx, "Destino futuro 10.0.1.2 vazou para o snapshot passado g0!"
    assert "10.0.0.9" not in g0.ip2idx, "Atacante futuro 10.0.0.9 vazou para o snapshot passado g0!"

    # 2. Rótulo por janela: 10.0.0.1 é benigno (0) em g0 e atacante (1) em g2
    idx_1_g0 = g0.ip2idx["10.0.0.1"]
    assert int(g0.y[idx_1_g0].item()) == 0, "10.0.0.1 foi rotulado como atacante antes de atacar!"
    idx_1_g2 = g2.ip2idx["10.0.0.1"]
    assert int(g2.y[idx_1_g2].item()) == 1, "10.0.0.1 deveria ser rotulado como atacante na janela g2!"
    assert int(g2.y[g2.ip2idx["10.0.1.2"]].item()) == 0, "Vítima passiva 10.0.1.2 recebeu label=1 em g2!"

    # 3. Preservação de sequência em g0 (padding 0.0 seguido de 11.0, 22.0; sem o 999.0 futuro!)
    seq_g0 = g0.x[idx_1_g0, :, 0].numpy().tolist()
    assert seq_g0 == [0.0, 11.0, 22.0], f"Sequência de features em g0 corrompida ou contaminada pelo futuro: {seq_g0}"


def test_dataloader_snapshot_aggregation_and_legacy_single_graph_rejection():
    """
    Verifica:
      1. `train.load_or_split_graphs` rejeita grafos únicos legados (`isinstance(raw_obj, Data)`),
         impedindo que grafos pré-processados sem isolamento sejam divididos após o fato.
      2. `train.train_and_evaluate` opera sobre listas de snapshots (`train_snapshots`, `val_snapshots`,
         `test_snapshots`) com `DataLoader`, agregando as predições de todos os snapshots de teste.
      3. `feature_scope='ebpf_compatible'` remove colunas L7/pós-conexão (`service`, `res_bdy_len`, etc.).
    """
    legacy_single_graph = Data(
        x=torch.randn(10, 5, 4),
        edge_index=torch.tensor([[0, 1], [1, 0]], dtype=torch.long),
        y=torch.zeros(10, dtype=torch.long),
    )
    with pytest.raises(ValueError, match="único grafo histórico"):
        tr.load_or_split_graphs(legacy_single_graph, device=torch.device("cpu"))

    df = pp.generate_test_sample(n=180, seed=77)
    # Adiciona coluna L7 pós-conexão para testar filtragem de escopo eBPF
    df["res_bdy_len"] = df["target"] * 5000.0

    bundle = pp.build_inductive_splits(
        df,
        target_col="target",
        time_col="timestamp",
        k=10,
        seq_len=5,
        window_sec=30.0,
        feature_scope="ebpf_compatible",
    )

    assert "res_bdy_len" in bundle["dropped_l7_posthoc_cols"]
    assert "res_bdy_len" not in bundle["top_features"]
    assert all(not f.startswith("service_") for f in bundle["top_features"])

    assert len(bundle["train_snapshots"]) >= 2
    assert len(bundle["val_snapshots"]) >= 1
    assert len(bundle["test_snapshots"]) >= 1

    # Garantir que as janelas de treino, validação e teste não se sobrepõem no tempo
    max_train_t = max(g.t_end for g in bundle["train_snapshots"])
    min_val_t = min(g.t_start for g in bundle["val_snapshots"])
    max_val_t = max(g.t_end for g in bundle["val_snapshots"])
    min_test_t = min(g.t_start for g in bundle["test_snapshots"])
    assert max_train_t <= min_val_t + 30.0
    assert max_val_t <= min_test_t + 30.0

    expected_test_nodes = sum(int(g.x.shape[0]) for g in bundle["test_snapshots"])

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt = str(Path(tmpdir) / "ckpt_snap.pth")
        res = tr.train_and_evaluate(
            train_g=bundle["train_snapshots"],
            val_g=bundle["val_snapshots"],
            test_g=bundle["test_snapshots"],
            epochs=3,
            lr=0.002,
            patience=3,
            seed=42,
            checkpoint_out=ckpt,
            batch_size=2,
        )
        assert len(res["y_test_true"]) == expected_test_nodes, (
            f"A avaliação deveria agregar todos os {expected_test_nodes} nós dos snapshots de teste, "
            f"mas retornou {len(res['y_test_true'])}."
        )
        assert res["graph_stats"]["test"]["num_snapshots"] == len(bundle["test_snapshots"])
        assert "ms_per_snapshot" in res["test_latency"]
        assert "us_per_node" in res["test_latency"]


def test_checkpoint_periodic_save_and_resume():
    """
    Verifica que o salvamento periódico de estado (`resume_state_out`) permite interromper o
    treinamento na época 2 e retomá-lo automaticamente até a época 4 (`resume=True`), restaurando
    a época anterior (`resumed_from_epoch == 2`) para tolerância a quedas de sessão no Google Colab.
    """
    df = pp.generate_test_sample(n=120, seed=99)
    bundle = pp.build_inductive_splits(df, target_col="target", time_col="timestamp", k=8, seq_len=4, window_sec=60.0)

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt = str(Path(tmpdir) / "model.pth")
        resume_file = str(Path(tmpdir) / "model.pth.resume.pt")

        # Fase 1: Treina até a época 2 e salva o estado periódico
        res_part1 = tr.train_and_evaluate(
            train_g=bundle["train_snapshots"],
            val_g=bundle["val_snapshots"],
            test_g=bundle["test_snapshots"],
            epochs=2,
            lr=0.002,
            patience=5,
            seed=42,
            checkpoint_out=ckpt,
            resume=False,
            resume_state_out=resume_file,
            save_every=1,
        )
        assert Path(resume_file).exists(), "O arquivo de estado de retomada não foi criado!"
        assert res_part1["resumed_from_epoch"] == 0

        # Fase 2: Simula reconexão do Colab/G15 retomando da época 2 até a época 4
        res_part2 = tr.train_and_evaluate(
            train_g=bundle["train_snapshots"],
            val_g=bundle["val_snapshots"],
            test_g=bundle["test_snapshots"],
            epochs=4,
            lr=0.002,
            patience=5,
            seed=42,
            checkpoint_out=ckpt,
            resume=True,
            resume_state_out=resume_file,
            save_every=1,
        )
        assert res_part2["resumed_from_epoch"] == 2, (
            f"Deveria ter retomado da época 2, mas resumed_from_epoch={res_part2['resumed_from_epoch']}"
        )
        saved_state = torch.load(resume_file, map_location="cpu", weights_only=False)
        assert saved_state["epoch"] == 4

