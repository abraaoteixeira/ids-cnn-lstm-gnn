import asyncio
import websockets
import sys

async def main():
    uri = "ws://localhost:8001/ws/threats"
    print(f"Connecting to {uri} from Windows...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected successfully from Windows!")
            for _ in range(3):
                message = await websocket.recv()
                print(f"Received: {message[:100]}...")
            print("WebSocket is working perfectly from Windows!")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())
