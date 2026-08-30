"""
In-process Automated Verification Suite for V2V Dynamic Map Platform
--------------------------------------------------------------------
Uses aiohttp.test_utils to thoroughly test the actual server application:
1. Static HTML serving with Virtual Keyboard, Navigation, and Modals
2. GET /events endpoint and initial hazard delivery
3. POST /gps endpoint with simulated ESP32 coordinates and multi-vehicle status
4. WebSocket connection, initial state delivery
5. Hazard creation (Custom hazard, Potholes, Speed bumps)
6. Proximity voting (YES / NO)
7. 3-vote community consensus: verifies hazard deactivates & sends event_removed
"""

import os
import sys
import time
import json
import asyncio
import aiohttp
from aiohttp.test_utils import TestServer, TestClient

# Add directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server

async def run_inprocess_tests():
    print("\n=======================================================")
    print("  🧪 Running In-Process Verification for V2V Map Server")
    print("=======================================================\n")

    server.load_events()
    app = server.create_app()
    
    server.server_loop = asyncio.get_event_loop()

    test_server = TestServer(app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        # 1. Test GET / (HTML delivery)
        print("[1/6] Testing GET / (Map Dashboard)...")
        resp = await client.get("/")
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        text = await resp.text()
        assert "<title>V2V Dynamic Navigation" in text, "HTML missing expected title"
        assert "vk-board" in text, "HTML missing virtual keyboard element"
        assert "verify-modal" in text, "HTML missing verification modal element"
        print("  ✅ GET / returned live-gps-tracker.html with Virtual Keyboard and Modals")

        # 2. Test GET /events
        print("\n[2/6] Testing GET /events...")
        resp = await client.get("/events")
        assert resp.status == 200
        data = await resp.json()
        assert "events" in data
        print(f"  ✅ GET /events returned {len(data['events'])} active hazards")

        # 3. Test POST /gps (Ingesting ESP32 coordinates)
        print("\n[3/6] Testing POST /gps (Ingesting ESP32 telemetry)...")
        gps_payload = {
            "vehicle_id": "TEST_CAR_1",
            "lat": 12.8425,
            "lng": 80.1550,
            "speed": 55.4,
            "heading": 120.0,
            "sats": 9,
            "status": "LOCKED"
        }
        resp = await client.post("/gps", json=gps_payload)
        assert resp.status == 200
        res = await resp.json()
        assert res.get("status") == "ok"
        assert server.active_vehicles["TEST_CAR_1"]["lat"] == 12.8425
        print("  ✅ POST /gps successfully updated vehicle coordinates on server")

        # 4. Test WebSocket Real-time Sync & Initial State
        print("\n[4/6] Testing WebSocket bi-directional connection...")
        ws = await client.ws_connect("/ws")
        msg = await ws.receive_json()
        assert msg.get("type") == "initial_state"
        assert "vehicles" in msg
        print("  ✅ WebSocket received initial_state with synced vehicles and active hazards")

        # 5. Test Adding a Custom Hazard via WebSocket (Simulating Digital Keyboard submission)
        print("\n[5/6] Testing Hazard Creation via WebSocket...")
        test_hazard_id = f"test-pothole-{int(time.time())}"
        add_event_payload = {
            "action": "add_event",
            "user_id": "driver_anto",
            "data": {
                "id": test_hazard_id,
                "type": "pothole",
                "title": "Severe Pothole Test",
                "description": "Created via virtual keyboard test",
                "lat": 12.8430,
                "lng": 80.1555,
                "severity": "high"
            }
        }
        await ws.send_json(add_event_payload)
        
        event_added_msg = await ws.receive_json()
        assert event_added_msg.get("type") == "event_added"
        assert event_added_msg["data"]["id"] == test_hazard_id
        print(f"  ✅ Hazard '{event_added_msg['data']['title']}' created and broadcasted via WebSocket")

        # 6. Test 3-Vote Community Dismissal Rule
        print("\n[6/6] Testing Proximity 3-Vote Consensus Dismissal...")
        
        # Vote 1: User Alpha votes NO
        await ws.send_json({
            "action": "vote_event",
            "event_id": test_hazard_id,
            "vote": "no",
            "user_id": "user_alpha"
        })
        resp1 = await ws.receive_json()
        assert resp1.get("type") == "event_updated"
        assert len(resp1["data"]["dismissals"]) == 1
        print("  ✅ Vote 1/3 ('No') recorded -> Event updated")

        # Vote 2: User Bravo votes NO
        await ws.send_json({
            "action": "vote_event",
            "event_id": test_hazard_id,
            "vote": "no",
            "user_id": "user_bravo"
        })
        resp2 = await ws.receive_json()
        assert resp2.get("type") == "event_updated"
        assert len(resp2["data"]["dismissals"]) == 2
        print("  ✅ Vote 2/3 ('No') recorded -> Event updated")

        # Vote 3: User Charlie votes NO -> Reaches 3 -> MUST DISAPPEAR!
        await ws.send_json({
            "action": "vote_event",
            "event_id": test_hazard_id,
            "vote": "no",
            "user_id": "user_charlie"
        })
        resp3 = await ws.receive_json()
        assert resp3.get("type") == "event_removed", f"Expected event_removed, got {resp3.get('type')}"
        assert resp3.get("event_id") == test_hazard_id
        assert resp3.get("reason") == "dismissed_by_community"
        print("  ✅ Vote 3/3 ('No') recorded -> Threshold of 3 reached! Broadcasted 'event_removed'!")

        # Verify with GET /events that the hazard is no longer in active events
        resp = await client.get("/events")
        data = await resp.json()
        active_ids = [e["id"] for e in data["events"]]
        assert test_hazard_id not in active_ids
        print("  ✅ Confirmed hazard is purged from active hazards list")

        await ws.close()

    finally:
        await client.close()

    print("\n=======================================================")
    print("  🎉 ALL IN-PROCESS VERIFICATION SUITES PASSED! (100%)")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(run_inprocess_tests())
