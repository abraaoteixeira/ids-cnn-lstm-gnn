import json
import socket
import os
from datetime import datetime

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

local_ip = get_local_ip()
# Gera um IP atacante na mesma faixa de IP
subnet = ".".join(local_ip.split(".")[:3]) + "."
attacker_ip = subnet + "200"

alert = {
    "flow_id": 9999,
    "src_ip": f"{attacker_ip} (ATACANTE)",
    "dst_ip": f"{local_ip} (TEU IP)",
    "port": 445,
    "protocol": "TCP",
    "probability": 99.85,
    "is_threat": True,
    "bytes": 15002341,
    "packets": 48293,
    "timestamp": datetime.now().strftime("%H:%M:%S")
}

log_file = "data/logs/spectre_alerts.jsonl"
os.makedirs(os.path.dirname(log_file), exist_ok=True)

with open(log_file, "a") as f:
    f.write(json.dumps(alert) + "\n")

print(f"[✓] Ataque injetado com sucesso!")
print(f"    Origem: {attacker_ip} (Simulado)")
print(f"    Destino: {local_ip} (Teu Host)")
print(f"    Severidade GNN: 99.85%")
