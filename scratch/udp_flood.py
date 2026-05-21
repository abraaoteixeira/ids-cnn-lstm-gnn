import socket
import time

def flood():
    # Cria socket UDP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target_ip = "192.168.100.5" # IP do eth8 no WSL
    target_port = 9999
    
    print(f"Enviando rajada de 200 pacotes UDP para {target_ip}:{target_port}...")
    for i in range(200):
        # Envia pacotes com tamanho flutuante para simular comportamento real
        payload = b"X" * (512 + (i % 512))
        s.sendto(payload, (target_ip, target_port))
        # Um micro delay para não estourar buffers internos instantaneamente
        time.sleep(0.005)
    print("Rajada concluída!")

if __name__ == "__main__":
    flood()
