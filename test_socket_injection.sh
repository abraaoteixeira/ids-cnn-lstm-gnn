#!/bin/bash
# Injeta dados de teste no socket do SPECTRE GRID para validar o pipeline
SOCKET="/tmp/spectre.sock"

echo "[TEST] Iniciando injeção de dados de teste no socket..."

for i in $(seq 1 20); do
    TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    PROB=$(awk -v seed=$RANDOM 'BEGIN{srand(seed); printf "%.2f", rand() * 0.5}')
    BYTES=$(awk -v seed=$RANDOM 'BEGIN{srand(seed); printf "%d", 500 + rand() * 3000}')
    PKTS=$(awk -v seed=$RANDOM 'BEGIN{srand(seed); printf "%d", 1 + rand() * 10}')
    ATTN=$(awk -v seed=$RANDOM 'BEGIN{srand(seed); printf "%.2f", rand() * 0.4}')
    
    SRC_IPS=("8.8.8.8" "1.1.1.1" "172.22.80.1" "192.168.100.1" "185.220.101.5")
    SRC=${SRC_IPS[$((RANDOM % 5))]}
    DST="172.22.80.252"

    JSON="{\"timestamp\":\"$TS\",\"src_ip\":\"$SRC\",\"dst_ip\":\"$DST\",\"port\":443,\"protocol\":\"TCP\",\"probability\":$PROB,\"is_threat\":false,\"bytes\":$BYTES,\"packets\":$PKTS,\"attention_weight\":$ATTN}"
    
    echo "$JSON" | nc -q1 -U "$SOCKET" 2>/dev/null
    echo "[TEST] Evento $i enviado: src=$SRC bytes=$BYTES prob=$PROB"
    sleep 0.5
done

echo "[TEST] Injeção concluída."
