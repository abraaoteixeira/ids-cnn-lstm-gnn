import asyncio
import os
import logging
import sqlite3
import json
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import uvicorn

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("SPECTRE_API")

SOCKET_PATH = "/tmp/spectre.sock"
DB_PATH = "spectre_history.db"
active_connections = set()
recent_lines = []

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threat_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                src_ip TEXT,
                dst_ip TEXT,
                port INTEGER,
                protocol TEXT,
                probability REAL,
                is_threat INTEGER,
                bytes INTEGER,
                packets INTEGER
            )
        """)
        conn.commit()
        conn.close()
        logger.info("Base de dados SQLite 'spectre_history.db' inicializada com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao inicializar base de dados: {e}")

def log_flow_to_db(message_str):
    try:
        data = json.loads(message_str)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO threat_log (timestamp, src_ip, dst_ip, port, protocol, probability, is_threat, bytes, packets)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("timestamp", ""),
            data.get("src_ip", ""),
            data.get("dst_ip", ""),
            data.get("port", 0),
            data.get("protocol", "TCP"),
            data.get("probability", 0.0),
            1 if data.get("is_threat", False) else 0,
            data.get("bytes", 0),
            data.get("packets", 0)
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao registar fluxo no SQLite: {e}")

async def handle_unix_client(reader, writer):
    logger.info("Novo motor C++ de fusão conectado ao Unix Socket.")
    try:
        while True:
            data = await reader.readline()
            if not data:
                break
            message = data.decode('utf-8').strip()
            if message:
                # Salvar assincronamente no SQLite para evitar bloquear o loop de eventos
                await asyncio.to_thread(log_flow_to_db, message)

                # Armazenar no cache de histórico recente (máximo 20)
                recent_lines.append(message)
                if len(recent_lines) > 20:
                    recent_lines.pop(0)

                # Broadcast para todas as conexões de WebSocket ativas
                targets = list(active_connections)
                for ws in targets:
                    try:
                        await ws.send_text(message)
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"Erro no Unix Socket: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        logger.info("Motor C++ desconectado do Unix Socket.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inicializar BD SQLite
    init_db()

    # Configurar e iniciar Unix Domain Socket Server
    if os.path.exists(SOCKET_PATH):
        try:
            os.remove(SOCKET_PATH)
        except Exception as e:
            logger.error(f"Erro ao remover socket antigo: {e}")

    server = await asyncio.start_unix_server(handle_unix_client, path=SOCKET_PATH)
    try:
        os.chmod(SOCKET_PATH, 0o666)  # Permissão para qualquer processo ler/escrever
    except Exception as e:
        logger.warning(f"Não foi possível aplicar chmod 0666 no socket: {e}")
        
    logger.info(f"Servidor IPC Unix Socket iniciado em {SOCKET_PATH}")
    
    yield
    
    # Shutdown: Parar o servidor e remover o arquivo de soquete
    server.close()
    await server.wait_closed()
    if os.path.exists(SOCKET_PATH):
        try:
            os.remove(SOCKET_PATH)
        except Exception:
            pass
    logger.info("Servidor IPC Unix Socket encerrado.")

app = FastAPI(title="SPECTRE_GRID NGFW Dashboard", lifespan=lifespan)

# Montar os ficheiros estáticos (HTML/CSS/JS)
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/api/history")
async def get_history(limit: int = 50, only_threats: bool = False):
    def fetch():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        query = "SELECT timestamp, src_ip, dst_ip, port, protocol, probability, is_threat, bytes, packets FROM threat_log"
        if only_threats:
            query += " WHERE is_threat = 1"
        query += " ORDER BY id DESC LIMIT ?"
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for r in rows:
            result.append({
                "timestamp": r[0],
                "src_ip": r[1],
                "dst_ip": r[2],
                "port": r[3],
                "protocol": r[4],
                "probability": r[5],
                "is_threat": bool(r[6]),
                "bytes": r[7],
                "packets": r[8]
            })
        return result

    try:
        data = await asyncio.to_thread(fetch)
        return data
    except Exception as e:
        logger.error(f"Erro ao buscar histórico: {e}")
        return {"error": str(e)}

@app.post("/api/clear_history")
async def clear_history():
    def truncate():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM threat_log")
        conn.commit()
        conn.close()
    try:
        await asyncio.to_thread(truncate)
        logger.info("Histórico do banco de dados SQLite apagado pelo utilizador.")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Erro ao apagar histórico: {e}")
        return {"error": str(e)}

@app.websocket("/ws/threats")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    logger.info(f"Nova ligação de Dashboard via WebSocket. Ativos: {len(active_connections)}")
    
    try:
        # Enviar histórico recente em cache na RAM para carregar a tela preenchida
        for line in list(recent_lines):
            await websocket.send_text(line)
            
        # Manter a conexão aberta escutando por desconexão do cliente
        while True:
            await websocket.receive_text()  # Apenas para manter o canal aberto e detectar disconnect
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}")
    finally:
        active_connections.remove(websocket)
        logger.info(f"Ligação de Dashboard removida. Ativos: {len(active_connections)}")

if __name__ == "__main__":
    uvicorn.run("dashboard_api:app", host="0.0.0.0", port=8000, reload=True)
