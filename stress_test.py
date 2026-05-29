import socket
import time
import json
import sqlite3
import os

# SOCKET_PATH = "/tmp/spectre.sock"
TOTAL_MESSAGES = 20000

print(f"--- Iniciando STRESS TEST: {TOTAL_MESSAGES} Mensagens ---")

SOCKET_PATH = "/tmp/spectre.sock"
if os.path.exists(SOCKET_PATH):
    print("Conectando via UNIX Socket...")
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET_PATH)
    except Exception as e:
        print(f"ERRO: Não foi possível conectar no Unix Socket {SOCKET_PATH}. {e}")
        exit(1)
else:
    print("Conectando via TCP Socket...")
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(('127.0.0.1', 9000))
    except Exception as e:
        print(f"ERRO: Não foi possível conectar na porta 9000. Certifique-se de que o backend está rodando. {e}")
        exit(1)

payload = {
    "flow_id": 9999,
    "src_ip": "10.0.0.99 (ALVO SUSPEITO)",
    "dst_ip": "127.0.0.1",
    "port": 80,
    "protocol": "TCP",
    "probability": 99.5,
    "is_threat": True,
    "bytes": 5000,
    "packets": 50,
    "timestamp": "12:00:00"
}

msg = (json.dumps(payload) + "\n").encode('utf-8')

start_time = time.time()

for _ in range(TOTAL_MESSAGES):
    client.sendall(msg)

client.close()
end_time = time.time()
elapsed = end_time - start_time

print(f"Envio concluído em {elapsed:.4f} segundos ({(TOTAL_MESSAGES/elapsed):.2f} msgs/seg).")

# Aguardar os workers assíncronos gravarem no BD
print("Aguardando 3 segundos para as filas do BD sincronizarem...")
time.sleep(3)

# Verifica quantos entraram no BD Go
try:
    conn_go = sqlite3.connect('dashboard_go/spectre_history_go.db')
    cursor = conn_go.cursor()
    cursor.execute("SELECT COUNT(*) FROM threat_log")
    count_go = cursor.fetchone()[0]
    conn_go.close()
    print(f"[GO DB] Registros inseridos: {count_go}")
except:
    print("[GO DB] Não encontrado ou erro ao ler.")

# Verifica quantos entraram no BD Python
try:
    conn_py = sqlite3.connect('spectre_history_v2.db')
    cursor = conn_py.cursor()
    cursor.execute("SELECT COUNT(*) FROM threat_log")
    count_py = cursor.fetchone()[0]
    conn_py.close()
    print(f"[PYTHON V2 DB] Registros inseridos: {count_py}")
except:
    print("[PYTHON V2 DB] Não encontrado ou erro ao ler.")

print("--- Fim do Teste ---")
