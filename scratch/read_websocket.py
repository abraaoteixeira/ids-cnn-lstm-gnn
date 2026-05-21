import asyncio
import websockets
import json

async def read_alerts():
    url = "ws://127.0.0.1:8000/ws/threats"
    print(f"Lendo do WebSocket {url}...")
    try:
        async with websockets.connect(url) as websocket:
            print("Conectado! Aguardando mensagens/historico...")
            # Set a timeout so we don't block forever
            try:
                while True:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(msg)
                    print(f"Recebido: {json.dumps(data, indent=2)}")
            except asyncio.TimeoutError:
                print("Leitura concluída (timeout).")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    asyncio.run(read_alerts())
