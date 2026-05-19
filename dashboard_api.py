import asyncio
import json
import logging
from pathlib import Path

import torch
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
logger = logging.getLogger("NGFW-API")

# Inicializar Servidor FastAPI
app = FastAPI(title="SPECTRE_GRID NGFW Dashboard")

# Montar os ficheiros estáticos (HTML/CSS/JS)
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

# Estado Global do Modelo
MODEL_PATH = "./trained_super_ids_model.pt"
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = None

def load_model():
    global model
    from model import SPECTRE_GRID  # Import local do teu módulo
    try:
        model = SPECTRE_GRID(num_features=20).to(device)
        model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
        model.eval()
        logger.info(f"[✓] Modelo carregado com sucesso na {device} para o Dashboard.")
    except Exception as e:
        logger.error(f"[X] Erro ao carregar o modelo: {e}")

# Iniciar o modelo antes do servidor aceitar conexões
@app.on_event("startup")
async def startup_event():
    load_model()

@app.websocket("/ws/threats")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Nova ligação ao Dashboard NGFW!")
    
    import random
    
    # Pool de IPs realistas
    ips = [f"192.168.1.{i}" for i in range(10, 25)]
    critical_targets = ["10.0.0.5 (Active Directory)", "10.0.0.10 (SQL Database)", "10.0.0.1 (Core Gateway)"]
    all_hosts = ips + critical_targets
    
    protocols = ["TCP", "UDP", "ICMP"]
    ports = [22, 80, 443, 445, 3389, 8080, 53]
    
    flow_id = 0
    try:
        while True:
            # Selecionar IPs aleatórios para simular comunicação de rede
            src = random.choice(all_hosts)
            dst = random.choice(all_hosts)
            while src == dst:
                dst = random.choice(all_hosts)
                
            port = random.choice(ports)
            proto = "TCP" if port in [22, 443, 445, 3389, 8080] else "UDP"
            if port == 53:
                proto = "UDP"
                
            # Simulação do tensor de características para a CNN 1D + LSTM (10 timesteps, 20 features)
            # Em caso de ataque (ex: porta 445/3389/22), criamos anomalias estatísticas nas features
            is_suspicious_port = port in [22, 445, 3389]
            if is_suspicious_port and random.random() > 0.4:
                # Características de tráfego anómalo (alto volume, intervalos curtos, flags TCP anormais)
                x = torch.randn(1, 10, 20).to(device) * 2.5 + 1.5
            else:
                x = torch.randn(1, 10, 20).to(device)
                
            # Grafo de inferência simples (nós e aresta própria)
            edge_index = torch.tensor([[0], [0]], dtype=torch.long).to(device)
            
            # Inferência Neural
            with torch.no_grad():
                if model:
                    logit = model(x, edge_index)
                    prob = torch.sigmoid(logit).mean().item()
                else:
                    prob = random.uniform(0.01, 0.15)
            
            # Formatar a % de ameaça
            prob_percent = prob * 100
            
            # Classificar como ameaça se passar dos 80%
            is_threat = prob_percent > 80.0
            
            # Forçar alertas em portas de ataque conhecidas ocasionalmente para a demo ser emocionante
            if is_suspicious_port and random.random() > 0.7:
                is_threat = True
                prob_percent = random.uniform(85.0, 99.9)
            
            payload = {
                "flow_id": flow_id,
                "src_ip": src,
                "dst_ip": dst,
                "port": port,
                "protocol": proto,
                "probability": round(prob_percent, 2),
                "is_threat": is_threat,
                "bytes": random.randint(64, 1500000) if not is_threat else random.randint(1000000, 50000000),
                "packets": random.randint(1, 2000) if not is_threat else random.randint(5000, 100000),
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await websocket.send_json(payload)
            
            flow_id += 1
            # Intervalo de simulação (0.6 segundos)
            await asyncio.sleep(0.6)
            
    except WebSocketDisconnect:
        logger.info("Dashboard desligado.")

if __name__ == "__main__":
    uvicorn.run("dashboard_api:app", host="0.0.0.0", port=8000, reload=True)
