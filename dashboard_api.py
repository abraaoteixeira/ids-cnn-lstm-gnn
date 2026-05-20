import asyncio
import json
import os
import logging
from pathlib import Path
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

app = FastAPI(title="SPECTRE_GRID NGFW Dashboard")

# Montar os ficheiros estáticos (HTML/CSS/JS)
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

LOG_FILE = "data/logs/spectre_alerts.jsonl"

@app.websocket("/ws/threats")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Nova ligação ao Dashboard NGFW. Escutando telemetria real!")
    
    # Garante que a pasta e o ficheiro existem
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, 'w').close()

    # 1. Carregar histórico recente (últimas 20 linhas) para não carregar a tela vazia
    recent_lines = []
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            recent_lines = lines[-20:]
    except Exception as e:
        logger.error(f"Erro ao carregar histórico recente: {e}")

    for line in recent_lines:
        if line.strip():
            await websocket.send_text(line.strip())

    # 2. Escutar novas linhas em tempo real (tail -f)
    try:
        with open(LOG_FILE, "r") as f:
            # Pula para o final do ficheiro
            f.seek(0, os.SEEK_END)
            
            while True:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.1)
                    continue
                
                await websocket.send_text(line.strip())
                
    except WebSocketDisconnect:
        logger.info("Dashboard desligado pelo cliente.")
    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}")

if __name__ == "__main__":
    uvicorn.run("dashboard_api:app", host="0.0.0.0", port=8000, reload=True)
