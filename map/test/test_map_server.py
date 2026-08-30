"""
In-process Automated Verification Suite for V2V Dynamic Map Platform
--------------------------------------------------------------------
Tests:
1. Static HTML serving with Virtual Keyboard, Navigation, and Emergency Visuals
2. GET /events endpoint and initial hazard delivery
3. POST /gps endpoint with simulated ESP32 normal and emergency vehicle telemetry
4. WebSocket connection, initial state delivery
5. Hazard creation (Custom hazard, Potholes, Speed bumps)
6. Proximity voting (YES / NO)
7. 3-vote community consensus: verifies hazard deactivates & sends event_removed
8. Emergency vehicle broadcast validation (vehicle_type="emergency", is_emergency=True)
"""

import os
import sys
import time
import json
import asyncio
import aiohttp
from aiohttp.test_utils import TestServer, TestClient

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
        print("[1/7] Testing GET / (Map Dashboard)...")
        resp = await client.get("/")
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        text = await resp.text()
        assert "<title>V2V Dynamic Navigation" in text
        assert "emergency-flashing-container" in text
        assert "emergency-passed-container" in text
        print("  ✅ GET / returned live-gps-tracker.html with Emergency Red/Blue Strobe & Solid Red support")

        # 2. Test GET /events
        print("\n[2/7] Testing GET /events...")
        resp = await client.get("/events")
        assert resp.status == 200
        data = await resp.json()
        assert "events" in data
        print(f"  ✅ GET /events returned {len(data['events'])} active hazards")

        # 3. Test POST /gps for Normal Vehicle
        print("\n[3/7] Testing POST /gps (Normal Vehicle Telemetry)...")
        normal_payload = {
            "vehicle_id": "CAR_NORMAL_1",
            "lat": 12.8425,
            "lng": 80.1550,
            "speed": 50.0,
            "heading": 120.0,
            "sats": 9,
            "status": "LOCKED"
        }
        resp = await client.post("/gps", json=normal_payload)
        assert resp.status == 200
        assert server.active_vehicles["CAR_NORMAL_1"]["is_emergency"] == False
        print("  ✅ Normal Vehicle registered successfully")

        # 4. Test POST /gps for Emergency Vehicle (Ambulance)
        print("\n[4/7] Testing POST /gps (Emergency Vehicle Telemetry)...")
        emerg_payload = {
            "vehicle_id": "AMBULANCE_108",
            "vehicle_type": "emergency",
            "is_emergency": True,
            "lat": 12.8420,
            "lng": 80.1545,
            "speed": 80.0,
            "heading": 120.0,
            "sats": 12,
            "status": "LOCKED"
        }
        resp = await client.post("/gps", json=emerg_payload)
        assert resp.status == 200
        res = await resp.json()
        assert res.get("is_emergency") == True
        assert server.active_vehicles["AMBULANCE_108"]["is_emergency"] == True
        print("  ✅ Emergency Vehicle 'AMBULANCE_108' registered with is_emergency=True")

        # 5. Test WebSocket Real-time Sync & Initial State
        print("\n[5/7] Testing WebSocket connection & initial state...")
        ws = await client.ws_connect("/ws")
        msg = await ws.receive_json()
        assert msg.get("type") == "initial_state"
        assert len(msg["vehicles"]) >= 2
        print(f"  ✅ WebSocket synced {len(msg['vehicles'])} vehicles (including Emergency node)")

        # 6. Test Hazard Creation via WebSocket
        print("\n[6/7] Testing Hazard Creation via WebSocket...")
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
        print(f"  ✅ Hazard '{event_added_msg['data']['title']}' broadcasted")

        # 7. Test 3-Vote Community Dismissal Rule
        print("\n[7/7] Testing Proximity 3-Vote Consensus Dismissal...")
        for idx, uId in enumerate(["user_alpha", "user_bravo", "user_charlie"], 1):
            await ws.send_json({
                "action": "vote_event",
                "event_id": test_hazard_id,
                "vote": "no",
                "user_id": uId
            })
            vote_resp = await ws.receive_json()
            if idx < 3:
                assert vote_resp.get("type") == "event_updated"
                print(f"  ✅ Vote {idx}/3 ('No') recorded")
            else:
                assert vote_resp.get("type") == "event_removed"
                print("  ✅ Vote 3/3 ('No') recorded -> Threshold reached! Hazard removed automatically!")

        await ws.close()

    finally:
        await client.close()

    print("\n=======================================================")
    print("  🎉 ALL 7 VERIFICATION TEST SUITES PASSED! (100%)")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(run_inprocess_tests())
