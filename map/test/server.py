"""
V2V Dynamic Multi-Vehicle Map & Hazard Server for Linux Mint & Cloud
--------------------------------------------------------------------
- Supports multiple ESP32 nodes posting GPS/IMU data with unique vehicle_id
- Web clients connect over WebSocket (/ws) to view live fleet & road hazards
- Ingests GPS over USB Serial or HTTP POST to /gps
- Synchronizes hazards with 3-vote community consensus removal
- Ready for free cloud deployment (Render, Railway, Fly.io, Cloudflare Tunnels)
"""

import os
import sys
import time
import json
import uuid
import asyncio
import threading
from typing import Dict, Any, Set
from aiohttp import web

# Optional PySerial support for direct ESP32 USB connection
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_FILE = os.path.join(BASE_DIR, "events.json")

# In-memory server state: Dict[vehicle_id, dict]
active_vehicles: Dict[str, Dict[str, Any]] = {
    "MY_CAR": {
        "vehicle_id": "MY_CAR",
        "lat": 12.8406,
        "lng": 80.1534,
        "heading": 0.0,
        "speed": 0.0,
        "alt": 0.0,
        "sats": 0,
        "status": "WAITING_FOR_LOCK",
        "ts": None
    }
}

# Active hazards: Dict[event_id, dict]
active_events: Dict[str, Dict[str, Any]] = {}
websocket_clients: Set[web.WebSocketResponse] = set()
server_loop = None

DISMISSAL_THRESHOLD = 3  # 3 'No' votes remove the hazard

def load_events():
    """Load persistent events from JSON file."""
    global active_events
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, "r") as f:
                data = json.load(f)
                active_events = {item["id"]: item for item in data if item.get("active", True)}
                print(f"[Events] Loaded {len(active_events)} active hazards from {EVENTS_FILE}")
        except Exception as e:
            print(f"[Events] Warning: Could not load {EVENTS_FILE}: {e}")
            active_events = {}
    else:
        sample_hazards = [
            {
                "id": "haz-pothole-1",
                "type": "pothole",
                "title": "Deep Pothole",
                "description": "Severe road crater on right lane",
                "lat": 12.8415,
                "lng": 80.1542,
                "severity": "high",
                "created_at": time.time(),
                "created_by": "System",
                "confirmations": ["user_seed_1"],
                "dismissals": [],
                "active": True
            },
            {
                "id": "haz-bump-1",
                "type": "speed_bump",
                "title": "Unmarked Speed Bump",
                "description": "High dangerous speed breaker without paint",
                "lat": 12.8428,
                "lng": 80.1555,
                "severity": "medium",
                "created_at": time.time(),
                "created_by": "System",
                "confirmations": ["user_seed_2"],
                "dismissals": [],
                "active": True
            },
            {
                "id": "haz-roadblock-1",
                "type": "roadblock",
                "title": "Pipeline Construction",
                "description": "Left lane blocked with barricades",
                "lat": 12.8440,
                "lng": 80.1568,
                "severity": "high",
                "created_at": time.time(),
                "created_by": "System",
                "confirmations": ["user_seed_3"],
                "dismissals": [],
                "active": True
            }
        ]
        active_events = {h["id"]: h for h in sample_hazards}
        save_events()

def save_events():
    """Save active events to JSON file."""
    try:
        with open(EVENTS_FILE, "w") as f:
            json.dump(list(active_events.values()), f, indent=2)
    except Exception as e:
        print(f"[Events] Warning: Could not save {EVENTS_FILE}: {e}")

async def broadcast(message: dict):
    """Send JSON message to all active WebSocket clients."""
    if not websocket_clients:
        return
    dead = set()
    for ws in list(websocket_clients):
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    if dead:
        websocket_clients.difference_update(dead)

def broadcast_threadsafe(message: dict):
    """Safely call broadcast from background serial threads."""
    if server_loop and server_loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast(message), server_loop)

# ----------------- Serial Listener (ESP32 USB Direct) -----------------
class SerialGPSListener(threading.Thread):
    def __init__(self, preferred_port=None, baudrate=115200):
        super().__init__(daemon=True)
        self.preferred_port = preferred_port
        self.baudrate = baudrate
        self.running = True
        self.ser = None

    def run(self):
        if not SERIAL_AVAILABLE:
            return

        while self.running:
            try:
                port = self.preferred_port
                if not port:
                    ports = [p.device for p in serial.tools.list_ports.comports()]
                    usb_ports = [p for p in ports if 'USB' in p or 'ACM' in p]
                    if usb_ports:
                        port = usb_ports[0]

                if not port:
                    time.sleep(3)
                    continue

                print(f"[Serial] Connecting to ESP32 on {port}...")
                self.ser = serial.Serial(port, self.baudrate, timeout=1)
                print(f"[Serial] Connected to ESP32 on {port} at {self.baudrate} baud!")

                while self.running and self.ser.is_open:
                    line = self.ser.readline().decode('ascii', errors='ignore').strip()
                    if not line:
                        continue

                    if line.startswith("GPS:"):
                        parts = line[4:].split(',')
                        if len(parts) >= 2:
                            lat = float(parts[0])
                            lng = float(parts[1])
                            speed = float(parts[2]) if len(parts) > 2 else 0.0
                            heading = float(parts[3]) if len(parts) > 3 else 0.0
                            alt = float(parts[4]) if len(parts) > 4 else 0.0
                            sats = int(parts[5]) if len(parts) > 5 else 0

                            veh_data = {
                                "vehicle_id": "USB_ESP32",
                                "lat": lat,
                                "lng": lng,
                                "speed": speed,
                                "heading": heading,
                                "alt": alt,
                                "sats": sats,
                                "status": "LOCKED",
                                "ts": time.time()
                            }
                            active_vehicles["USB_ESP32"] = veh_data
                            broadcast_threadsafe({"type": "gps_update", "vehicle_id": "USB_ESP32", "data": veh_data})

            except Exception as e:
                if self.ser:
                    try:
                        self.ser.close()
                    except Exception:
                        pass
                    self.ser = None
                time.sleep(4)


# ----------------- HTTP Endpoints -----------------
async def handle_gps_post(request):
    """
    Any ESP32 module or client posts JSON here:
    {
      "vehicle_id": "CAR_ALPHA",
      "lat": 12.8406,
      "lng": 80.1534,
      "speed": 45.0,
      "heading": 180.0,
      "sats": 8,
      "event": 0
    }
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    if "lat" not in data or "lng" not in data:
        return web.json_response({"error": "lat and lng required"}, status=400)

    lat = float(data["lat"])
    lng = float(data["lng"])
    vehicle_id = str(data.get("vehicle_id", "ESP32_NODE")).strip() or "ESP32_NODE"

    # If ESP32 detected a hazard event (pothole from IMU, emergency button, etc.)
    if "event" in data and int(data["event"]) > 0:
        event_num = int(data["event"])
        type_mapping = {
            1: ("speed_warning", "Overspeed Zone"),
            2: ("traction_loss", "Slippery Road / Loss of Traction"),
            4: ("crash", "Major Crash Incident"),
            5: ("pothole", "Pothole Detected (IMU)"),
            8: ("emergency", "Emergency Vehicle Approaching"),
            9: ("hard_brake", "Sudden Hard Braking Ahead")
        }
        ev_type, ev_title = type_mapping.get(event_num, ("custom", f"Hazard #{event_num}"))
        new_event = {
            "id": f"haz-{vehicle_id}-{int(time.time() * 1000)}",
            "type": ev_type,
            "title": ev_title,
            "description": f"Reported by {vehicle_id} at {time.strftime('%H:%M:%S')}",
            "lat": lat,
            "lng": lng,
            "severity": "critical" if event_num in [4, 8] else "high",
            "created_at": time.time(),
            "created_by": vehicle_id,
            "confirmations": [vehicle_id],
            "dismissals": [],
            "active": True
        }
        active_events[new_event["id"]] = new_event
        save_events()
        print(f"[EVENT FROM {vehicle_id}] {new_event['title']} at ({lat:.5f}, {lng:.5f})")
        await broadcast({"type": "event_added", "data": new_event})
        return web.json_response({"status": "event_recorded", "event": new_event, "active_hazards_count": len(active_events)})

    # Standard Multi-Vehicle GPS update
    veh_data = {
        "vehicle_id": vehicle_id,
        "lat": lat,
        "lng": lng,
        "heading": float(data.get("heading", 0.0)),
        "speed": float(data.get("speed", 0.0)),
        "alt": float(data.get("alt", 0.0)),
        "sats": int(data.get("sats", 0)),
        "status": data.get("status", "LOCKED"),
        "ts": time.time()
    }
    active_vehicles[vehicle_id] = veh_data

    await broadcast({"type": "gps_update", "vehicle_id": vehicle_id, "data": veh_data})
    
    # Return active hazards count so ESP32 knows if there are nearby warnings
    return web.json_response({
        "status": "ok",
        "vehicle_id": vehicle_id,
        "active_hazards": len(active_events),
        "total_online_vehicles": len(active_vehicles)
    })


async def handle_events_get(request):
    """Return all active hazards."""
    return web.json_response({"events": list(active_events.values())})


async def handle_vehicles_get(request):
    """Return all active vehicle positions."""
    return web.json_response({"vehicles": list(active_vehicles.values())})


async def handle_event_create_post(request):
    """Create a new hazard via REST API."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    if "lat" not in data or "lng" not in data:
        return web.json_response({"error": "lat and lng required"}, status=400)

    event_id = data.get("id") or f"haz-{uuid.uuid4().hex[:8]}"
    ev = {
        "id": event_id,
        "type": data.get("type", "custom"),
        "title": data.get("title", "Custom Hazard").strip(),
        "description": data.get("description", "").strip(),
        "lat": float(data["lat"]),
        "lng": float(data["lng"]),
        "severity": data.get("severity", "medium"),
        "created_at": time.time(),
        "created_by": data.get("user_id", "Anonymous"),
        "confirmations": [data.get("user_id", "creator")],
        "dismissals": [],
        "active": True
    }
    active_events[event_id] = ev
    save_events()
    await broadcast({"type": "event_added", "data": ev})
    return web.json_response({"status": "created", "event": ev})


# ----------------- WebSocket Handler -----------------
async def handle_ws(request):
    """
    Bidirectional WebSocket connection for live telemetry, hazard sync, and voting.
    """
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    websocket_clients.add(ws)
    print(f"[WS] Client connected. Active clients: {len(websocket_clients)}")

    # Send initial state immediately: all vehicles + all active hazards
    initial_payload = {
        "type": "initial_state",
        "vehicles": list(active_vehicles.values()),
        "events": list(active_events.values())
    }
    await ws.send_json(initial_payload)

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    payload = json.loads(msg.data)
                    action = payload.get("action")

                    # 1. Add new event from Web Client (Digital Keyboard or Quick Hazard)
                    if action == "add_event":
                        data = payload.get("data", {})
                        event_id = data.get("id") or f"haz-{uuid.uuid4().hex[:8]}"
                        ev = {
                            "id": event_id,
                            "type": data.get("type", "custom"),
                            "title": data.get("title", "Custom Hazard").strip() or "Custom Hazard",
                            "description": data.get("description", "").strip(),
                            "lat": float(data["lat"]),
                            "lng": float(data["lng"]),
                            "severity": data.get("severity", "medium"),
                            "created_at": time.time(),
                            "created_by": payload.get("user_id", "Anonymous"),
                            "confirmations": [payload.get("user_id", "creator")],
                            "dismissals": [],
                            "active": True
                        }
                        active_events[event_id] = ev
                        save_events()
                        await broadcast({"type": "event_added", "data": ev})

                    # 2. Vote on an event ("Is the event still there?" YES / NO)
                    elif action == "vote_event":
                        event_id = payload.get("event_id")
                        vote = payload.get("vote")
                        user_id = payload.get("user_id", f"anon_{time.time()}")

                        if event_id in active_events:
                            ev = active_events[event_id]
                            confirmations = set(ev.get("confirmations", []))
                            dismissals = set(ev.get("dismissals", []))

                            if vote == "yes":
                                confirmations.add(user_id)
                                dismissals.discard(user_id)
                                ev["confirmations"] = list(confirmations)
                                ev["dismissals"] = list(dismissals)
                                save_events()
                                await broadcast({"type": "event_updated", "data": ev})

                            elif vote == "no":
                                dismissals.add(user_id)
                                confirmations.discard(user_id)
                                ev["dismissals"] = list(dismissals)
                                ev["confirmations"] = list(confirmations)

                                # 3 or more NO votes removes the hazard
                                if len(dismissals) >= DISMISSAL_THRESHOLD:
                                    ev["active"] = False
                                    del active_events[event_id]
                                    save_events()
                                    await broadcast({
                                        "type": "event_removed",
                                        "event_id": event_id,
                                        "reason": "dismissed_by_community",
                                        "dismissal_count": len(dismissals),
                                        "title": ev["title"]
                                    })
                                else:
                                    save_events()
                                    await broadcast({"type": "event_updated", "data": ev})

                    # 3. Simulated GPS Update
                    elif action == "sim_gps":
                        data = payload.get("data", {})
                        veh_id = data.get("vehicle_id", "SIM_CAR")
                        veh_data = {
                            "vehicle_id": veh_id,
                            "lat": float(data["lat"]),
                            "lng": float(data["lng"]),
                            "heading": float(data.get("heading", 0.0)),
                            "speed": float(data.get("speed", 0.0)),
                            "alt": float(data.get("alt", 0.0)),
                            "sats": int(data.get("sats", 10)),
                            "status": "SIMULATED",
                            "ts": time.time()
                        }
                        active_vehicles[veh_id] = veh_data
                        await broadcast({"type": "gps_update", "vehicle_id": veh_id, "data": veh_data})

                except Exception as e:
                    print(f"[WS Error] {e}")

            elif msg.type == web.WSMsgType.ERROR:
                print(f"[WS] Connection error: {ws.exception()}")
    finally:
        websocket_clients.discard(ws)
        print(f"[WS] Client disconnected. Active: {len(websocket_clients)}")

    return ws


async def handle_index(request):
    """Serve the live map frontend."""
    html_path = os.path.join(BASE_DIR, "live-gps-tracker.html")
    return web.FileResponse(html_path)


def create_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/ws", handle_ws)
    app.router.add_post("/gps", handle_gps_post)
    app.router.add_get("/events", handle_events_get)
    app.router.add_get("/vehicles", handle_vehicles_get)
    app.router.add_post("/events", handle_event_create_post)
    return app


if __name__ == "__main__":
    load_events()

    # Start USB Serial Background Thread if hardware connected
    serial_listener = SerialGPSListener()
    serial_listener.start()

    app = create_app()

    server_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(server_loop)

    port = int(os.environ.get("PORT", 8080))
    print("=" * 65)
    print(f"  🚀 V2V Dynamic Multi-Vehicle Map Server running on port {port}")
    print(f"  📡 Map Dashboard:  http://0.0.0.0:{port}/")
    print(f"  📍 GPS Ingest:     http://0.0.0.0:{port}/gps (HTTP POST)")
    print(f"  🔌 WebSocket:      ws://0.0.0.0:{port}/ws")
    print("=" * 65)

    web.run_app(app, host="0.0.0.0", port=port, loop=server_loop)
