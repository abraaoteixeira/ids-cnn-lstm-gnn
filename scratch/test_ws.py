import asyncio
import websockets

async def hello():
    uri = "ws://127.0.0.1:8000/ws/threats"
    async with websockets.connect(uri) as websocket:
        print("Connected!")
        for _ in range(3):
            msg = await websocket.recv()
            print(msg)

try:
    asyncio.run(hello())
except Exception as e:
    print("Error:", e)
