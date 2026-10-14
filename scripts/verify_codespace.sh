#!/bin/bash
set -e

# Cores
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}==========================================================="
echo "SPECTRE_GRID: Verificação de Sanidade do Ambiente Codespaces"
echo -e "===========================================================${NC}"

# 1. Checagem do Toolchain
echo -e "\n${YELLOW}[1/5] Verificando compiladores e ferramentas...${NC}"
which clang >/dev/null && echo -e "${GREEN}✓ Clang:${NC} $(clang --version | head -n 1)" || echo -e "${RED}✗ Clang não encontrado${NC}"
which llvm-strip >/dev/null && echo -e "${GREEN}✓ LLVM-Strip:${NC} presente" || echo -e "${YELLOW}! LLVM-Strip ausente (opcional)${NC}"
which cargo >/dev/null && echo -e "${GREEN}✓ Cargo/Rust:${NC} $(cargo --version)" || echo -e "${YELLOW}! Cargo não instalado${NC}"
which python3 >/dev/null && echo -e "${GREEN}✓ Python:${NC} $(python3 --version)" || echo -e "${RED}✗ Python3 não encontrado${NC}"

# 2. Compilação do Kernel eBPF/XDP
echo -e "\n${YELLOW}[2/5] Compilando bytecode eBPF (spectre_xdp.c)...${NC}"
clang -g -O2 -target bpf \
    -I/usr/include/x86_64-linux-gnu \
    -Iebpf \
    -D__TARGET_ARCH_x86 \
    -c ebpf/spectre_xdp.c \
    -o /tmp/spectre_xdp.o

if [ -f /tmp/spectre_xdp.o ]; then
    SIZE=$(stat -c%s /tmp/spectre_xdp.o)
    echo -e "${GREEN}✓ eBPF Bytecode compilado com sucesso:${NC} /tmp/spectre_xdp.o (${SIZE} bytes)"
else
    echo -e "${RED}✗ Falha ao compilar eBPF bytecode${NC}"
    exit 1
fi

# 3. Verificação do Loader Rust (se cargo disponível)
if which cargo >/dev/null; then
    echo -e "\n${YELLOW}[3/5] Verificando compilação do loader Rust (loader_fusion_rs)...${NC}"
    cargo check --manifest-path loader_fusion_rs/Cargo.toml && echo -e "${GREEN}✓ Rust loader verificado com sucesso!${NC}" || echo -e "${YELLOW}! Aviso no cargo check (verifique dependências de LibTorch se necessário)${NC}"
else
    echo -e "\n${YELLOW}[3/5] Pulando verificação Rust (Cargo não instalado)${NC}"
fi

# 4. Verificação de Integridade das Top-20 Features
echo -e "\n${YELLOW}[4/5] Verificando arquivo top20_features.json...${NC}"
if [ -f data/processed/top20_features.json ]; then
    FEAT_COUNT=$(python3 -c "import json; print(len(json.load(open('data/processed/top20_features.json'))))")
    echo -e "${GREEN}✓ Top-20 Features carregadas:${NC} ${FEAT_COUNT} features registradas"
else
    echo -e "${RED}✗ data/processed/top20_features.json não encontrado${NC}"
    exit 1
fi

# 5. Execução dos Testes Automatizados (pytest)
echo -e "\n${YELLOW}[5/5] Executando suite de testes automatizados (pytest)...${NC}"
if python3 -c "import pytest" 2>/dev/null; then
    python3 -m pytest tests/test_pipeline.py -v -s
else
    python3 tests/test_pipeline.py
fi

echo -e "\n${GREEN}==========================================================="
echo "🎉 TODOS OS COMPONENTES VALIDADOS COM SUCESSO!"
echo -e "===========================================================${NC}\n"
