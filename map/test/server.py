"""
Python GPS relay server for Linux Mint
----------------------------------------
- ESP32 #2 sends JSON GPS updates via HTTP POST to /gps
- Browsers open http://<this-machine-ip>:8080/ to view the live map,
  which connects to /ws over WebSocket to receive updates in real time.

Install once:
    pip3 install aiohttp

Run:
    python3 server.py

Then, on your phone/laptop on the same network:
    http://<this-machine-ip>:8080/

Find this machine's LAN IP with:  ip addr show
"""

import time
from aiohttp import web

latest_data = {"lat": None, "lng": None, "heading": 0, "speed": 0, "ts": None}
websocket_clients = set()


async def handle_gps_post(request):
    """ESP32 #2 posts JSON here or Simulator sends events."""
    global latest_data
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)

    if "lat" not in data or "lng" not in data:
        return web.json_response({"error": "lat/lng required"}, status=400)

    # Check if this is a hazard event (like a pothole)
    if "event" in data and data["event"] > 0:
        event_data = {
            "type": "event",
            "event_id": data["event"],
            "lat": float(data["lat"]),
            "lng": float(data["lng"])
        }
        print(f"[EVENT] {event_data}")
        dead = set()
        for ws in websocket_clients:
            try:
                await ws.send_json(event_data)
            except Exception:
                dead.add(ws)
        websocket_clients.difference_update(dead)
        return web.json_response({"status": "event recorded"})

    latest_data = {
        "lat": float(data["lat"]),
        "lng": float(data["lng"]),
        "heading": float(data.get("heading", 0)),
        "speed": float(data.get("speed", 0)),
        "ts": time.time(),
    }
    print(f"[GPS] {latest_data}")

    # Broadcast to every connected browser
    dead = set()
    for ws in websocket_clients:
        try:
            await ws.send_json(latest_data)
        except Exception:
            dead.add(ws)
    websocket_clients.difference_update(dead)

    return web.json_response({"status": "ok"})


async def handle_ws(request):
    """Browsers connect here to receive live GPS updates."""
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    websocket_clients.add(ws)
    print(f"[WS] browser connected. total={len(websocket_clients)}")

    # Send the last known fix immediately so the map isn't empty on load
    if latest_data["lat"] is not None:
        await ws.send_json(latest_data)

    try:
        async for _ in ws:
            pass  # browsers don't send anything, just listen
    finally:
        websocket_clients.discard(ws)
        print(f"[WS] browser disconnected. total={len(websocket_clients)}")

    return ws


async def handle_index(request):
    return web.FileResponse("./live-gps-tracker.html")


app = web.Application()
app.router.add_post("/gps", handle_gps_post)
app.router.add_get("/ws", handle_ws)
app.router.add_get("/", handle_index)

if __name__ == "__main__":
    print("Starting server on http://0.0.0.0:8080")
    print("  ESP32 should POST to:  http://<this-machine-LAN-IP>:8080/gps")
    print("  Open the map at:       http://<this-machine-LAN-IP>:8080/")
    web.run_app(app, host="0.0.0.0", port=8080)
