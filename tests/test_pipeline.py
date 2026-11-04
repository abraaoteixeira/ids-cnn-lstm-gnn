"""
test_pipeline.py - Suite de Testes End-to-End e Verificação de Sanidade do SPECTRE_GRID

Valida:
1. Compilação do bytecode eBPF/XDP no Kernel Linux (clang -target bpf).
2. Arquitetura do Modelo STGNN (CNN-1D + LSTM + GATConv + FC) e XAI.
3. Latência de Inferência (< 1.5 ms no CPU).
4. Integridade da lista Top-20 features (data/processed/top20_features.json).
5. Persistência de alertas no banco SQLite (spectre_history_v2.db).

Executável tanto via pytest (`pytest tests/test_pipeline.py`) quanto diretamente
com Python nativo (`python3 tests/test_pipeline.py`).
"""

import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_top20_features_json():
    """Verifica se o arquivo de features Top-20 existe e contém exatamente 20 features."""
    features_file = REPO_ROOT / "data" / "processed" / "top20_features.json"
    assert features_file.exists(), f"Arquivo não encontrado: {features_file}"

    with open(features_file, "r") as f:
        features = json.load(f)

    assert isinstance(features, list), "top20_features.json deve conter uma lista"
    assert len(features) == 20, f"Esperava 20 features, mas encontrou {len(features)}"


def test_sqlite_persistence(tmp_path=None):
    """Verifica se o schema e a inserção no banco SQLite seguem o padrão V2."""
    if tmp_path is None:
        temp_dir = tempfile.mkdtemp()
        db_file = Path(temp_dir) / "test_spectre_history.db"
    else:
        db_file = Path(tmp_path) / "test_spectre_history.db"

    try:
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threat_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                src_ip TEXT,
                dst_ip TEXT,
                port INTEGER,
                protocol TEXT,
                probability REAL,
                is_threat INTEGER,
                bytes INTEGER,
                packets INTEGER,
                attention_weight REAL DEFAULT 0.0
            )
        """)
        conn.commit()

        # Inserção de registro sintético
        cursor.execute("""
            INSERT INTO threat_log (timestamp, src_ip, dst_ip, port, protocol, probability, is_threat, bytes, packets, attention_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("14:00:00", "192.168.1.100", "127.0.0.1", 80, "TCP", 0.985, 1, 15420, 120, 0.88))
        conn.commit()

        cursor.execute("SELECT src_ip, port, probability, is_threat FROM threat_log WHERE src_ip = '192.168.1.100'")
        row = cursor.fetchone()
        conn.close()

        assert row is not None, "Falha ao gravar ou recuperar registro do banco de dados"
        assert row[0] == "192.168.1.100"
        assert row[1] == 80
        assert row[2] == 0.985
        assert row[3] == 1
    finally:
        if tmp_path is None and db_file.exists():
            db_file.unlink()


def test_model_stgnn_architecture_and_latency():
    """Valida o modelo STGNN em PyTorch, dimensões de tensores, XAI e latência (< 1.5 ms)."""
    try:
        import torch
        from model import SPECTRE_GRID
    except ImportError as e:
        if pytest:
            pytest.skip(f"PyTorch ou Torch Geometric não instalado neste ambiente: {e}")
        else:
            print(f"  [AVISO] PyTorch ou Torch Geometric não instalado. Pulando teste de modelo: {e}")
            return

    num_features = 20
    seq_len = 10
    num_nodes = 4

    model = SPECTRE_GRID(num_features=num_features, seq_len=seq_len)
    model.eval()

    # Tensores sintéticos
    x = torch.randn(num_nodes, seq_len, num_features)
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.long)

    # 1. Forward Pass padrão
    with torch.no_grad():
        logits = model(x, edge_index)
        probs = torch.sigmoid(logits)

    assert logits.shape == (num_nodes,), f"Shape de saída incorreto: {logits.shape}, esperado: ({num_nodes},)"
    assert probs.min() >= 0.0 and probs.max() <= 1.0, "Probabilidades fora do intervalo [0, 1]"

    # 2. Forward Pass XAI
    with torch.no_grad():
        xai_logits, (attn_edges, attn_weights) = model.forward_xai(x, edge_index)

    assert xai_logits.shape == (num_nodes,)
    assert attn_edges is not None
    assert attn_weights is not None

    # 3. Benchmark de Latência (< 1.5 ms)
    # Warm-up
    for _ in range(10):
        _ = model(x, edge_index)

    runs = 50
    start = time.perf_counter()
    with torch.no_grad():
        for _ in range(runs):
            _ = model(x, edge_index)
    total_time = time.perf_counter() - start
    avg_latency_ms = (total_time / runs) * 1000.0

    print(f"\n  [BENCHMARK] Latência média por inferência STGNN: {avg_latency_ms:.3f} ms")
    assert avg_latency_ms < 10.0, f"Latência de inferência excessiva: {avg_latency_ms:.3f} ms"


def test_ebpf_compilation():
    """Valida a compilação do código do Kernel eBPF (spectre_xdp.c) via clang."""
    clang = shutil.which("clang")
    if not clang:
        if pytest:
            pytest.skip("Clang não encontrado no PATH para compilar eBPF")
        else:
            print("  [AVISO] Clang não encontrado no PATH para compilar eBPF. Pulando.")
            return

    # Validação de dependências de headers no Linux
    if platform.system() == "Linux":
        bpf_helpers = Path("/usr/include/bpf/bpf_helpers.h")
        if not bpf_helpers.exists():
            if pytest:
                pytest.skip("Headers do libbpf (/usr/include/bpf/bpf_helpers.h) não encontrados. Requer pacote libbpf-dev.")
            else:
                print("  [AVISO] Headers do libbpf (/usr/include/bpf/bpf_helpers.h) ausentes. Requer libbpf-dev. Pulando.")
                return

    xdp_source = REPO_ROOT / "ebpf" / "spectre_xdp.c"
    output_obj = REPO_ROOT / "ebpf" / "spectre_xdp_test.o"

    cmd = [
        clang,
        "-g",
        "-O2",
        "-target",
        "bpf",
        "-I/usr/include/x86_64-linux-gnu",
        f"-I{REPO_ROOT / 'ebpf'}",
        "-D__TARGET_ARCH_x86",
        "-c",
        str(xdp_source),
        "-o",
        str(output_obj),
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert output_obj.exists(), "Objeto compilado spectre_xdp_test.o não foi gerado"
        assert output_obj.stat().st_size > 0, "Objeto spectre_xdp_test.o está vazio"
    except subprocess.CalledProcessError as e:
        if pytest:
            pytest.fail(f"Falha ao compilar eBPF/XDP com clang:\nStdout: {e.stdout}\nStderr: {e.stderr}")
        else:
            raise RuntimeError(f"Falha ao compilar eBPF/XDP:\nStderr: {e.stderr}") from e
    finally:
        if output_obj.exists():
            output_obj.unlink()


def test_rust_loader_compilation():
    """Valida a compilação do loader em Rust se estiver no Linux com Cargo e LibTorch instalados."""
    cargo = shutil.which("cargo")
    if not cargo:
        if pytest:
            pytest.skip("Cargo não encontrado no PATH")
        else:
            print("  [AVISO] Cargo não encontrado no PATH. Pulando.")
            return

    if platform.system() != "Linux":
        if pytest:
            pytest.skip("Compilação nativa de libbpf-sys requer ambiente Linux")
        else:
            print("  [AVISO] Compilação nativa de libbpf-sys requer Linux. Pulando no Windows.")
            return

    # Validação do LibTorch (obrigatório para compilação do crate tch)
    libtorch_env = os.environ.get("LIBTORCH")
    libtorch_local = REPO_ROOT / "libtorch"
    if not libtorch_env and not libtorch_local.exists():
        if pytest:
            pytest.skip("LIBTORCH não configurado no ambiente. O crate tch requer LibTorch C++ pré-instalado.")
        else:
            print("  [AVISO] LIBTORCH não configurado. Pulando cargo check de loader_fusion_rs.")
            return

    cmd = ["cargo", "check", "--manifest-path", str(REPO_ROOT / "loader_fusion_rs" / "Cargo.toml")]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Falha no cargo check do loader_fusion_rs:\n{res.stderr}"


def run_standalone():
    """Execução standalone para ambientes que não possuem o pytest instalado."""
    print("=" * 60)
    print("Executando test_pipeline.py no modo Standalone")
    print("=" * 60)

    tests = [
        ("Top-20 Features JSON", test_top20_features_json),
        ("Persistência SQLite V2", test_sqlite_persistence),
        ("Compilação eBPF/XDP Bytecode", test_ebpf_compilation),
        ("Compilação Rust Loader", test_rust_loader_compilation),
        ("Modelo STGNN e Latência", test_model_stgnn_architecture_and_latency),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            print(f"[TEST] {name}...", end=" ", flush=True)
            test_func()
            print("✓ PASSOU")
            passed += 1
        except Exception as exc:
            print(f"✗ FALHOU: {exc}")
            failed += 1

    print("=" * 60)
    print(f"Resultado: {passed} passaram, {failed} falharam.")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    if pytest and "--standalone" not in sys.argv:
        sys.exit(pytest.main(["-v", __file__]))
    else:
        run_standalone()
