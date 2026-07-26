#!/bin/bash
set -e

echo "==========================================================="
echo "SPECTRE-GRID: Instalador de Dependencias eBPF/XDP"
echo "Ambiente: Ubuntu / WSL2"
echo "==========================================================="

if [ "$EUID" -ne 0 ]; then
  echo "Por favor, rode este script como root (sudo ./setup_ebpf_env.sh)"
  exit 1
fi

echo "[*] Atualizando repositorios..."
apt-get update

echo "[*] Instalando ferramentas de compilacao (Clang/LLVM) e LibBPF..."
apt-get install -y clang llvm libbpf-dev build-essential pkg-config

echo "[*] Instalando cabecalhos do Kernel do Linux..."
apt-get install -y linux-headers-$(uname -r) linux-tools-common linux-tools-$(uname -r)

echo "[*] Instalando dependencias extras (iproute2 para manipular XDP manualmente, caso necessario)..."
apt-get install -y iproute2

echo "==========================================================="
echo "Instalacao concluida!"
echo "Verifique se o compilador BPF esta ativo com: clang -target bpf -O2 -c ..."
echo "==========================================================="
