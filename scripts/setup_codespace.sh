#!/bin/bash
set -e

echo "==========================================================="
echo "SPECTRE_GRID: Setup Automático do Ambiente GitHub Codespaces"
echo "==========================================================="

echo "[1/4] Atualizando pacotes e instalando toolchain eBPF/C++..."
sudo apt-get update
sudo apt-get install -y \
    clang \
    llvm \
    libbpf-dev \
    bpftool \
    linux-libc-dev \
    build-essential \
    pkg-config \
    libelf-dev \
    zlib1g-dev \
    iproute2 \
    cmake \
    python3-pip \
    python3-dev

echo "[2/4] Instalando dependências de IA (PyTorch CPU & PyG)..."
pip install --upgrade pip
pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

pip install --no-cache-dir \
    torch_geometric \
    pandas \
    numpy \
    scikit-learn \
    fastapi \
    uvicorn \
    websockets \
    aiosqlite \
    pytest

echo "[3/4] Ajustando permissões de scripts..."
chmod +x scripts/*.sh 2>/dev/null || true
chmod +x *.sh 2>/dev/null || true

echo "[4/4] Executando verificação de sanidade..."
bash scripts/verify_codespace.sh

echo "==========================================================="
echo "✅ Setup do Codespace concluído com sucesso!"
echo "==========================================================="
