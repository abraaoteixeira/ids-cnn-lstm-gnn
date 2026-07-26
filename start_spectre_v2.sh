#!/bin/bash

# ==============================================================================
# SPECTRE_GRID v2.0 - Script de Inicialização Rápida e Unificada
# ==============================================================================

# Cores para output premium
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}======================================================${NC}"
echo -e "${CYAN}    🚀 INICIANDO ECOSSISTEMA SPECTRE_GRID V2.0${NC}"
echo -e "${CYAN}======================================================${NC}"

# 1. Ativar o Ambiente Virtual
if [ -d ".venv_fast" ]; then
    echo -e "[*] Ativando ambiente virtual Python (.venv_fast)..."
    source .venv_fast/bin/activate
elif [ -d ".venv" ]; then
    echo -e "[*] Ativando ambiente virtual Python (.venv)..."
    source .venv/bin/activate
else
    echo -e "${YELLOW}[!] Ambiente virtual não encontrado. Usando Python do sistema...${NC}"
fi

# 2. Garantir pastas de dados e logs
mkdir -p data/logs

# 3. Subir a API Assíncrona FastAPI V2 em background (Porta 8001)
echo -e "[*] Levantando Servidor FastAPI V2 (Assíncrono)..."
nohup python3 dashboard_api_v2.py --host 0.0.0.0 --port 8001 > data/logs/api_v2.log 2>&1 &
API_PID=$!

# Aguarda 2 segundos para validar se a API inicializou com sucesso
sleep 2

if ps -p $API_PID > /dev/null; then
    echo -e "${GREEN}[OK] API V2 ativa no PID $API_PID.${NC}"
else
    echo -e "${RED}[ERRO] Falha ao iniciar a API FastAPI V2. Verifique os logs em data/logs/api_v2.log${NC}"
    exit 1
fi

# 4. Detecção de Interface de Rede para o XDP
ACTIVE_IFACE=$(ip route ls default | awk '{print $5}' | head -n 1)
if [ -z "$ACTIVE_IFACE" ]; then
    ACTIVE_IFACE=$(ip -o link show | awk -F': ' '$2 != "lo" {print $2; exit}')
fi
if [ -z "$ACTIVE_IFACE" ]; then
    ACTIVE_IFACE="lo"
fi

echo -e "\n${CYAN}======================================================${NC}"
echo -e "${GREEN}🔥 AMBIENTE OPERACIONAL COM SUCESSO!${NC}"
echo -e " - ${CYAN}API & Dashboard UI:${NC} http://localhost:8001"
echo -e " - ${CYAN}Socket Unix de Captura:${NC} /tmp/spectre.sock"
echo -e " - ${CYAN}Logs de Saída da API:${NC} tail -f data/logs/api_v2.log"
echo -e "${CYAN}======================================================${NC}"

echo -e "\n${YELLOW}💡 Para Alimentar o Dashboard com Fluxo de Dados:${NC}"
echo -e " 1. ${GREEN}Simulação de Ataque (Stress Test):${NC}"
echo -e "    python3 stress_test.py"
echo -e " 2. ${GREEN}Captura eBPF/XDP Real (Necessita Sudo/Root):${NC}"
echo -e "    sudo ./build/spectre_fusion $ACTIVE_IFACE"
echo -e " 3. ${GREEN}Parar o Servidor API V2:${NC}"
echo -e "    kill $API_PID\n"
