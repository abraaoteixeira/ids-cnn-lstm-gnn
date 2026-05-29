import socket
import time
import json
import random
from datetime import datetime

SOCKET_PATH = "/tmp/spectre.sock"

def generate_flow():
    src_ips = [
        "192.168.1.50", "10.0.0.12", "172.16.0.4", "8.8.8.8", "192.168.100.15",
        "45.89.23.12 (BOTNET)", "77.88.99.111 (MALWARE_C2)", "185.220.101.5 (TOR_EXIT)"
    ]
    dst_ips = ["192.168.1.1", "10.0.0.1", "172.16.0.1", "192.168.100.1"]
    ports = [80, 443, 22, 53, 3389, 8080, 23]
    protocols = ["TCP", "UDP", "ICMP"]
    
    is_threat = random.choice([True, False, False, False]) # 25% chance of threat
    if is_threat:
        src = random.choice([x for x in src_ips if "BOTNET" in x or "MALWARE" in x or "TOR" in x])
        prob = random.uniform(85.0, 99.9)
    else:
        src = random.choice([x for x in src_ips if "BOTNET" not in x and "MALWARE" not in x and "TOR" not in x])
        prob = random.uniform(0.1, 15.0)
        
    return {
        "flow_id": random.randint(1000, 9999),
        "src_ip": src,
        "dst_ip": random.choice(dst_ips),
        "port": random.choice(ports),
        "protocol": random.choice(protocols),
        "probability": round(prob, 2),
        "is_threat": is_threat,
        "bytes": random.randint(64, 15000),
        "packets": random.randint(1, 150),
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

def main():
    print("Starting simulated live traffic generator...")
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET_PATH)
    except Exception as e:
        print(f"Error: Could not connect to Unix socket {SOCKET_PATH}. {e}")
        return
        
    try:
        while True:
            flow = generate_flow()
            msg = (json.dumps(flow) + "\n").encode('utf-8')
            client.sendall(msg)
            print(f"Sent: {flow['src_ip']} -> {flow['dst_ip']} | Threat: {flow['is_threat']} ({flow['probability']}%)")
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Stopping simulator...")
    finally:
        client.close()

if __name__ == "__main__":
    main()
