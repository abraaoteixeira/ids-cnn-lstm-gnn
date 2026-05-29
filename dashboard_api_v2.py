import asyncio
import os
import logging
import sqlite3
import json
import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configuração de Logging Premium
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (SPECTRE_API_V2) %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("SPECTRE_API_V2")

SOCKET_PATH = "/tmp/spectre.sock"
DB_PATH = "spectre_history_v2.db"
active_connections = set()
recent_lines = []

# ==============================================================================
# FILA ASSÍNCRONA DE ALTA PERFORMANCE (Desacoplamento I/O)
# ==============================================================================
# Evita que a gravação no disco trave a leitura do Unix Socket (vital para DDoS)
db_write_queue = asyncio.Queue(maxsize=100000)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
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
        await db.commit()
    logger.info("Base de dados aiosqlite 'spectre_history_v2.db' inicializada.")

async def db_writer_worker():
    """Consome a fila em background e faz batch inserts para ultra-performance."""
    logger.info("Worker Assíncrono de BD Iniciado.")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            while True:
                # Otimização: processamento em lote (batching) se houver pico
                items = []
                # Puxa o primeiro item (espera se vazio)
                item = await db_write_queue.get()
                items.append(item)
                
                # Esvazia rapidamente a fila para o mesmo lote
                while not db_write_queue.empty() and len(items) < 500:
                    items.append(db_write_queue.get_nowait())

                # Transação em Lote Otimizada
                await db.executemany("""
                    INSERT INTO threat_log (timestamp, src_ip, dst_ip, port, protocol, probability, is_threat, bytes, packets)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, items)
                await db.commit()

                for _ in items:
                    db_write_queue.task_done()
    except asyncio.CancelledError:
        logger.info("Worker de BD cancelado.")
    except Exception as e:
        logger.error(f"Erro fatal no worker de BD: {e}")

async def handle_unix_client(reader, writer):
    logger.info("Motor C++ conectado ao Unix Socket (V2 High Performance).")
    try:
        while True:
            data = await reader.readline()
            if not data:
                break
            message = data.decode('utf-8').strip()
            if message:
                # Parse JSON otimizado
                try:
                    payload = json.loads(message)
                    # Enfileira tupla formatada para evitar JSON overhead no BD Worker
                    tuple_data = (
                        payload.get("timestamp", ""),
                        payload.get("src_ip", ""),
                        payload.get("dst_ip", ""),
                        payload.get("port", 0),
                        payload.get("protocol", "TCP"),
                        payload.get("probability", 0.0),
                        1 if payload.get("is_threat", False) else 0,
                        payload.get("bytes", 0),
                        payload.get("packets", 0)
                    )
                    
                    # Se a fila estiver cheia, descarta log no BD mas não derruba socket (Backpressure protection)
                    if not db_write_queue.full():
                        db_write_queue.put_nowait(tuple_data)
                    else:
                        logger.warning("Fila de BD cheia! Descartando gravação SQL para manter IPC vivo.")
                except json.JSONDecodeError:
                    pass

                # Cache RAM RingBuffer O(1)
                recent_lines.append(message)
                if len(recent_lines) > 20:
                    recent_lines.pop(0)

                # Broadcast Async aos WebSockets (Fan-Out)
                # Removido bloqueio por cliente lento usando asyncio.gather
                if active_connections:
                    tasks = []
                    for ws in active_connections:
                        tasks.append(asyncio.create_task(ws.send_text(message)))
                    await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        logger.error(f"Erro no IPC Socket: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        logger.info("Motor C++ desconectado do Unix Socket.")

# Variável global para gerenciar a task do DB Writer
db_worker_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_worker_task
    # Startup
    await init_db()
    db_worker_task = asyncio.create_task(db_writer_worker())

    if os.name == 'posix':
        # Limpar socket anterior se existir
        if os.path.exists(SOCKET_PATH):
            try:
                os.remove(SOCKET_PATH)
            except Exception as e:
                logger.warning(f"Erro ao remover socket anterior {SOCKET_PATH}: {e}")
        server = await asyncio.start_unix_server(handle_unix_client, path=SOCKET_PATH)
        logger.info(f"API V2 Asynchronous Listener em Unix Socket: {SOCKET_PATH}")
    else:
        server = await asyncio.start_server(handle_unix_client, host='127.0.0.1', port=9000)
        logger.info(f"API V2 Asynchronous Listener em TCP: 127.0.0.1:9000")
        
    yield
    
    # Shutdown
    server.close()
    await server.wait_closed()
    if db_worker_task:
        db_worker_task.cancel()

app = FastAPI(title="SPECTRE_GRID NGFW Dashboard V2", lifespan=lifespan)

# CORS Total
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "dashboard_v2" / "dist"
if not static_dir.exists():
    # Fallback para o modo legado caso a build do React não tenha sido executada
    static_dir = Path(__file__).parent / "static_legacy"

app.mount("/assets", StaticFiles(directory=str(Path(__file__).parent / "dashboard_v2" / "dist" / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/api/history")
async def get_history(limit: int = 50, only_threats: bool = False):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT timestamp, src_ip, dst_ip, port, protocol, probability, is_threat, bytes, packets FROM threat_log"
            if only_threats:
                query += " WHERE is_threat = 1"
            query += " ORDER BY id DESC LIMIT ?"
            
            async with db.execute(query, (limit,)) as cursor:
                rows = await cursor.fetchall()
                
            result = [dict(r) for r in rows]
            # Formatar boolean para JS
            for r in result:
                r["is_threat"] = bool(r["is_threat"])
            return result
    except Exception as e:
        logger.error(f"Erro ao buscar histórico: {e}")
        return {"error": str(e)}

@app.post("/api/clear_history")
async def clear_history():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM threat_log")
            await db.commit()
        logger.info("Histórico DB V2 apagado.")
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}

@app.websocket("/ws/threats")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        for line in recent_lines:
            await websocket.send_text(line)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        active_connections.remove(websocket)

if __name__ == "__main__":
    uvicorn.run("dashboard_api_v2:app", host="0.0.0.0", port=8001, reload=True)
