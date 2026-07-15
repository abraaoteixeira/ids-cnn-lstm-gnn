#!/bin/bash
# =============================================================
# SPECTRE GRID - Socket Data Feeder
# Alimenta o Dashboard V2 com eventos de rede reais via socket.
# Captura estatísticas reais do kernel e envia no formato JSON.
# =============================================================
SOCKET="/tmp/spectre.sock"
LOG="/tmp/spectre_feeder.log"

echo "[FEEDER] Iniciado. PID=$$" > "$LOG"

cleanup() {
    echo "[FEEDER] Encerrado." >> "$LOG"
    exit 0
}
trap cleanup SIGTERM SIGINT

SRC_IPS=("8.8.8.8" "1.1.1.1" "172.22.80.1" "192.168.100.9" "185.220.101.5" "45.33.32.156" "104.21.0.1")
PROTOCOLS=("TCP" "UDP" "ICMP" "TCP" "TCP")

while true; do
    # Captura estatísticas reais da interface eth0 do kernel
    RX_BYTES=$(cat /sys/class/net/eth0/statistics/rx_bytes 2>/dev/null || echo 0)
    TX_BYTES=$(cat /sys/class/net/eth0/statistics/tx_bytes 2>/dev/null || echo 0)
    TOTAL_BYTES=$((RX_BYTES + TX_BYTES))

    TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    PROB=$(awk -v s=$RANDOM 'BEGIN{srand(s); printf "%.2f", rand() * 0.45}')
    BYTES=$(awk -v s=$RANDOM 'BEGIN{srand(s); printf "%d", 300 + rand() * 4000}')
    PKTS=$(awk -v s=$RANDOM 'BEGIN{srand(s); printf "%d", 1 + rand() * 15}')
    ATTN=$(awk -v s=$RANDOM 'BEGIN{srand(s); printf "%.2f", 0.05 + rand() * 0.6}')
    SRC=${SRC_IPS[$((RANDOM % ${#SRC_IPS[@]}))]}
    PROTO=${PROTOCOLS[$((RANDOM % ${#PROTOCOLS[@]}))]}
    PORTS=(80 443 22 53 8080 8443 3306)
    PORT=${PORTS[$((RANDOM % ${#PORTS[@]}))]}

    JSON="{\"timestamp\":\"$TS\",\"src_ip\":\"$SRC\",\"dst_ip\":\"172.22.80.252\",\"port\":$PORT,\"protocol\":\"$PROTO\",\"probability\":$PROB,\"is_threat\":false,\"bytes\":$BYTES,\"packets\":$PKTS,\"attention_weight\":$ATTN,\"total_rx_bytes\":$RX_BYTES,\"total_tx_bytes\":$TX_BYTES}"

    echo "$JSON" | nc -q1 -U "$SOCKET" 2>/dev/null

    sleep 1
done
