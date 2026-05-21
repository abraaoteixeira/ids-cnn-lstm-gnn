import socket
import json
import time
import random

SOCKET_PATH = "/tmp/spectre.sock"

def send_flow(sock, flow_id, src_ip, dst_ip, port, protocol, probability, is_threat, bytes_count, packets_count):
    payload = {
        "flow_id": flow_id,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "port": port,
        "protocol": protocol,
        "probability": round(probability, 2),
        "is_threat": is_threat,
        "bytes": bytes_count,
        "packets": packets_count,
        "timestamp": time.strftime("%H:%M:%S")
    }
    msg = json.dumps(payload) + "\n"
    sock.sendall(msg.encode('utf-8'))
    print(f"Enviado: {msg.strip()}")

def main():
    print(f"Conectando ao Unix Socket: {SOCKET_PATH}...")
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        print("Conectado com sucesso! Iniciando simulação de tráfego...")
    except Exception as e:
        print(f"Erro ao conectar ao socket: {e}")
        print("Certifique-se de que a API (dashboard_api.py) está rodando e ativa.")
        return

    ips_normais = ["192.168.1.15", "10.0.0.4", "10.0.0.8", "192.168.100.22"]
    servidores = ["192.168.100.5", "10.0.0.1", "10.0.0.10"]
    ip_atacante = "185.220.101.66"

    try:
        # Fase 1: Tráfego Normal de Produção (10 segundos)
        print("\n=== FASE 1: ENVIANDO TRÁFEGO NORMAL ===")
        for i in range(15):
            src = random.choice(ips_normais)
            dst = random.choice(servidores)
            port = random.choice([80, 443, 22])
            prob = random.uniform(1.0, 15.0)
            bytes_c = random.randint(1000, 50000)
            packets = random.randint(5, 50)
            
            send_flow(sock, i, src, dst, port, "TCP", prob, False, bytes_c, packets)
            time.sleep(0.8)

        # Fase 2: Varredura de Portas / Portscan (Início da Anomalia)
        print("\n=== FASE 2: DETECTANDO INÍCIO DE ANOMALIA (PORTSCAN) ===")
        for i in range(15, 25):
            dst = "192.168.100.5" # Servidor de Produção WSL
            port = i * 23 # Portas rotativas
            prob = 30.0 + (i - 15) * 5.5 # Risco subindo gradativamente
            bytes_c = 64 # Pacotes SYN pequenos
            packets = 1
            
            send_flow(sock, i, ip_atacante, dst, port, "TCP", prob, False, bytes_c, packets)
            time.sleep(0.6)

        # Fase 3: Ataque Crítico / Tentativa de Exploração (APT Alert)
        print("\n=== FASE 3: ATAQUE DETECTADO PELO MODELO GNN ===")
        for i in range(25, 35):
            dst = "192.168.100.5"
            port = 80
            prob = random.uniform(85.0, 99.9) # Risco crítico
            bytes_c = random.randint(100000, 5000000) # Carga alta
            packets = random.randint(100, 500)
            
            #is_threat = True
            send_flow(sock, i, ip_atacante + " (ALVO SUSPEITO)", dst, port, "TCP", prob, True, bytes_c, packets)
            time.sleep(1.0)

        # Fase 4: Mitigação e Tráfego Residual
        print("\n=== FASE 4: BLOQUEIO XDP_DROP ATIVO ===")
        for i in range(35, 45):
            # Outros IPs continuam trafegando normalmente
            src = random.choice(ips_normais)
            dst = random.choice(servidores)
            port = random.choice([80, 443])
            prob = random.uniform(1.0, 10.0)
            bytes_c = random.randint(2000, 15000)
            packets = random.randint(4, 20)
            
            send_flow(sock, i, src, dst, port, "TCP", prob, False, bytes_c, packets)
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\nSimulação interrompida pelo usuário.")
    finally:
        sock.close()
        print("Simulação encerrada.")

if __name__ == "__main__":
    main()
