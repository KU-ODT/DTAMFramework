import asyncio
import websockets
import json

async def test():
    uri = "ws://127.0.0.1:8095/ws/dtam?role=monitoring&source=test"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "register", "role": "monitoring", "source": "test"}))
        await asyncio.sleep(1)
        print("Sending 2001...")
        await ws.send(json.dumps({
            "type": "message",
            "mid": "2001",
            "payload": {"timestamp": "2026-04-24T00:00:00Z", "scenarioFileName": "test"}
        }))
        await asyncio.sleep(2)
        print("Done")

asyncio.run(test())
