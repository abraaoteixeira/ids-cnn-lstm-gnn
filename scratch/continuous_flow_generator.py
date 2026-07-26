import json
import socket
import os
import time
import random
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

def main():
    local_ip = get_local_ip()
    subnet = ".".join(local_ip.split(".")[:3]) + "."
    
    # Conhecidos na rede local
    clients = [subnet + str(i) for i in [15, 33, 47, 98, 112]]
    attacker = subnet + "200"
    gateway = subnet + "1"
    
    log_file = "data/logs/spectre_alerts.jsonl"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    print(f"=== GERADOR DE FLUXOS SPECTRE_GRID INICIADO ===")
    print(f"IP Local (WSL): {local_ip}")
    print(f"IP Atacante Simulado: {attacker}")
    print(f"Gravando em: {log_file}")
    
    flow_id = 1000
    
    try:
        while True:
            # 85% normal, 15% ataque
            is_attack = random.random() < 0.15
            
            if is_attack:
                src = attacker
                dst = local_ip
                port = random.choice([22, 80, 443, 445, 8080])
                protocol = random.choice(["TCP", "UDP"])
                prob = round(random.uniform(85.0, 99.9), 2)
                is_threat = True
                bytes_count = random.randint(500000, 15000000)
                packets_count = random.randint(1000, 50000)
            else:
                src = random.choice(clients + [gateway])
                dst = local_ip
                port = random.choice([80, 443, 123, 53])
                protocol = random.choice(["TCP", "UDP"])
                prob = round(random.uniform(0.1, 15.0), 2)
                is_threat = False
                bytes_count = random.randint(64, 15000)
                packets_count = random.randint(1, 20)
            
            alert = {
                "flow_id": flow_id,
                "src_ip": src + (" (ATACANTE)" if is_attack else ""),
                "dst_ip": dst + " (WSL)",
                "port": port,
                "protocol": protocol,
                "probability": prob,
                "is_threat": is_threat,
                "bytes": bytes_count,
                "packets": packets_count,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            
            with open(log_file, "a") as f:
                f.write(json.dumps(alert) + "\n")
            
            print(f"[{alert['timestamp']}] Flow {flow_id}: {src} -> {dst} | Prob: {prob}% | Threat: {is_threat}")
            
            flow_id += 1
            time.sleep(random.uniform(1.0, 2.5))
            
    except KeyboardInterrupt:
        print("\nGerador finalizado pelo utilizador.")

if __name__ == '__main__':
    main()
