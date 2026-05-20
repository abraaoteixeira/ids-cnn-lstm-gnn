import asyncio
import os
import logging
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
active_connections = set()
recent_lines = []

async def handle_unix_client(reader, writer):
    logger.info("Novo motor C++ de fusão conectado ao Unix Socket.")
    try:
        while True:
            data = await reader.readline()
            if not data:
                break
            message = data.decode('utf-8').strip()
            if message:
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
    # Startup: Configurar e iniciar Unix Domain Socket Server
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
