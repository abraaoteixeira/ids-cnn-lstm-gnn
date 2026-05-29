#!/bin/bash

echo "[*] Iniciando a Sequência de Ignição do SPECTRE_GRID..."

# Garantir que a pasta para gravação dos logs existe
mkdir -p data/logs

# 1. Descoberta Automática da Placa de Rede
if [ -z "$ACTIVE_IFACE" ]; then
    ACTIVE_IFACE=$(ip route ls default | awk '{print $5}' | head -n 1)
fi

# Se não achou rota padrão, tenta pegar a primeira interface física/virtual ativa que não seja loopback
if [ -z "$ACTIVE_IFACE" ]; then
    ACTIVE_IFACE=$(ip -o link show | awk -F': ' '$2 != "lo" {print $2; exit}')
fi

# Se ainda assim estiver vazio (ex: ambiente de sandbox isolado), usa loopback como último recurso de simulação/teste
if [ -z "$ACTIVE_IFACE" ]; then
    ACTIVE_IFACE="lo"
fi
echo "[+] Interface detectada para o eBPF: $ACTIVE_IFACE"

# 2. Subindo o Backend + Frontend Unificado (FastAPI) em background
echo "[+] Levantando o Servidor Unificado FastAPI (Porta 8001)..."
source .venv_wsl/bin/activate
nohup uvicorn dashboard_api_v2:app --host 0.0.0.0 --port 8001 > data/logs/api_output.log 2>&1 &
API_PID=$!

# 3. Acoplando o Motor de Fusão no Kernel (Data Plane)
echo "[+] Acoplando o motor C++/eBPF na interface $ACTIVE_IFACE..."
cd build
# Roda o C++ em background (Pode requerer digitação de senha sudo se não estiver no sudoers sem senha)
sudo nohup ./spectre_fusion $ACTIVE_IFACE > ../data/logs/fusion_output.log 2>&1 &
FUSION_PID=$!
cd ..

# Aguardar 1 segundo para validar se os processos continuam ativos
sleep 1

echo "======================================================"
echo "🚀 SPECTRE_GRID TOTALMENTE OPERACIONAL!"
echo " - Dashboard e API disponíveis em: http://localhost:8001"
echo " - logs salvos na pasta: ./data/logs/"
echo " - PIDs dos processos: API/FRONT($API_PID) | MOTOR($FUSION_PID)"
echo " - Para parar tudo, rode: kill $API_PID && sudo kill $FUSION_PID"
echo "======================================================"
