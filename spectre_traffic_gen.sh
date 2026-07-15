#!/bin/bash
# =============================================================
# SPECTRE GRID - Traffic Generator (Daemon)
# Gera tráfego benigno contínuo na interface eth0 do WSL
# para manter o Dashboard V2 com métricas ativas.
# =============================================================

TARGETS=("8.8.8.8" "1.1.1.1" "8.8.4.4" "google.com" "cloudflare.com")
LOG="/tmp/spectre_traffic_gen.log"

echo "[TRAFFIC-GEN] Iniciado. PID=$$" >> "$LOG"

cleanup() {
    echo "[TRAFFIC-GEN] Encerrado via sinal." >> "$LOG"
    exit 0
}
trap cleanup SIGTERM SIGINT

while true; do
    # Ping round-robin nos alvos
    TARGET=${TARGETS[$((RANDOM % ${#TARGETS[@]}))]}
    ping -c 2 -i 0.5 "$TARGET" > /dev/null 2>&1

    # Acesso HTTP leve
    curl -s --max-time 3 "https://google.com" > /dev/null 2>&1
    curl -s --max-time 3 "https://cloudflare.com" > /dev/null 2>&1

    sleep 2
done
