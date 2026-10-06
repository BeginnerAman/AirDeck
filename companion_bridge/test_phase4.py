"""
AirDeck Phase 4 Comprehensive Automated Verification Suite
Tests: Real-Time Telemetry Engine (CPU, RAM, Battery, Uptime),
       Macro Manager (JSON persistence, CRUD, Multi-type execution),
       REST API (/api/telemetry, /api/macros), and
       WebSocket Stream Deck Protocols.
"""

import json
import time
from fastapi.testclient import TestClient

from core.telemetry import get_system_telemetry
from core.macro_manager import macro_manager
from core.security import security_engine
import server


def test_system_telemetry_engine():
    print("\n[TEST] 1. Real-Time Telemetry Subsystem...")
    telem = get_system_telemetry()
    assert isinstance(telem, dict)
    assert telem.get("available") is True
    assert "cpu_percent" in telem
    assert isinstance(telem["cpu_percent"], (int, float))
    assert 0.0 <= telem["cpu_percent"] <= 100.0

    assert "ram_percent" in telem
    assert isinstance(telem["ram_percent"], (int, float))
    assert 0.0 <= telem["ram_percent"] <= 100.0

    assert "ram_used_gb" in telem and telem["ram_used_gb"] > 0
    assert "ram_total_gb" in telem and telem["ram_total_gb"] > 0
    assert "uptime_seconds" in telem and telem["uptime_seconds"] >= 0

    print(f"   ✓ Telemetry active: CPU={telem['cpu_percent']}%, RAM={telem['ram_percent']}% ({telem['ram_used_gb']}/{telem['ram_total_gb']}GB), Uptime={telem['uptime_seconds']}s")
    if telem.get("battery"):
        batt = telem["battery"]
        print(f"   ✓ Battery status: {batt['percent']}% (Plugged in: {batt['power_plugged']})")
    else:
        print("   ✓ Desktop PC detected or battery sensors not present (graceful None).")


def test_macro_manager_lifecycle():
    print("\n[TEST] 2. Macro Manager CRUD & Multi-Type Execution...")
    # Reset to known default state
    defaults = macro_manager.reset_defaults()
    assert len(defaults) >= 10
    print(f"   ✓ Factory defaults loaded with {len(defaults)} macros.")

    # 1. Add custom action macro
    new_m = macro_manager.add_macro({
        "label": "Test Snip",
        "icon": "scissors",
        "type": "action",
        "target": "snip",
        "color": "#ec4899"
    })
    assert new_m["id"].startswith("m_")
    assert new_m["label"] == "Test Snip"
    print(f"   ✓ Added custom action macro: ID={new_m['id']}")

    # 2. Add custom hotkey macro
    hotkey_m = macro_manager.add_macro({
        "label": "Copy Hotkey",
        "icon": "filetext",
        "type": "hotkey",
        "target": "ctrl+c",
        "color": "#6366f1"
    })
    print(f"   ✓ Added hotkey macro: ID={hotkey_m['id']}")

    # 3. Update macro
    updated = macro_manager.update_macro(new_m["id"], {"label": "Updated Snip"})
    assert updated is not None
    assert updated["label"] == "Updated Snip"
    print("   ✓ Updated macro label successfully.")

    # 4. Execute action macro
    ok, msg = macro_manager.execute_macro(new_m["id"])
    assert ok is True
    print(f"   ✓ Action execution succeeded: {msg}")

    # 5. Execute hotkey macro
    ok, msg = macro_manager.execute_macro(hotkey_m["id"])
    assert ok is True
    print(f"   ✓ Hotkey execution succeeded: {msg}")

    # 6. Execute launch macro (default m_calc or m_notepad)
    ok, msg = macro_manager.execute_macro("m_calc")
    assert ok is True
    print(f"   ✓ Launch execution succeeded: {msg}")

    # 7. Execute unknown macro fails gracefully
    ok, msg = macro_manager.execute_macro("non_existent_id")
    assert ok is False
    print(f"   ✓ Gracefully handled unknown macro execution: '{msg}'")

    # 8. Delete custom macro
    deleted = macro_manager.delete_macro(new_m["id"])
    assert deleted is True
    assert macro_manager.delete_macro(hotkey_m["id"]) is True
    print("   ✓ Cleaned up test macros.")


def test_streamdeck_and_telemetry_rest_routes():
    print("\n[TEST] 3. REST Endpoints for Telemetry & Macros (Auth Protected)...")
    from core.security import security_engine
    client = TestClient(server.app)

    # 1. Verify 401 Unauthorized on unauthenticated requests (Security Check)
    unauth_telem = client.get("/api/telemetry")
    assert unauth_telem.status_code == 401
    unauth_macros = client.get("/api/macros")
    assert unauth_macros.status_code == 401
    unauth_post = client.post("/api/macros", json={"label": "hack"})
    assert unauth_post.status_code == 401
    print("   ✓ Unauthenticated requests correctly rejected with 401 Unauthorized.")

    # 2. Authenticated requests with Bearer token
    headers = {"Authorization": f"Bearer {security_engine.master_token}"}

    # GET /api/telemetry
    res_telem = client.get("/api/telemetry", headers=headers)
    assert res_telem.status_code == 200
    telem_data = res_telem.json()
    assert "cpu_percent" in telem_data
    assert "ram_percent" in telem_data
    print("   ✓ Authenticated GET /api/telemetry returned valid real-time metrics.")

    # GET /api/macros
    res_macros = client.get("/api/macros", headers=headers)
    assert res_macros.status_code == 200
    macros_data = res_macros.json()
    assert isinstance(macros_data, list)
    assert len(macros_data) >= 10
    print(f"   ✓ Authenticated GET /api/macros returned {len(macros_data)} active items.")

    # POST /api/macros
    new_macro_payload = {
        "label": "API Test",
        "icon": "globe",
        "type": "url",
        "target": "https://google.com",
        "color": "#10b981"
    }
    res_create = client.post("/api/macros", json=new_macro_payload, headers=headers)
    assert res_create.status_code == 200
    created_macro = res_create.json()
    macro_id = created_macro["id"]
    print(f"   ✓ Authenticated POST /api/macros created macro {macro_id}")

    # DELETE /api/macros/{id}
    res_del = client.delete(f"/api/macros/{macro_id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json().get("ok") is True
    print(f"   ✓ Authenticated DELETE /api/macros/{macro_id} succeeded.")

    # POST /api/macros/reset
    res_reset = client.post("/api/macros/reset", headers=headers)
    assert res_reset.status_code == 200
    assert len(res_reset.json()) >= 10
    print("   ✓ Authenticated POST /api/macros/reset restored default template.")


def test_websocket_streamdeck_protocols():
    print("\n[TEST] 4. WebSocket Stream Deck & Telemetry Live Sync...")
    client = TestClient(server.app)
    pin = security_engine.pairing_pin

    with client.websocket_connect("/ws") as ws:
        # Auth Handshake
        ws.send_text(json.dumps({"t": "auth", "pin": pin}))
        auth_resp = json.loads(ws.receive_text())
        assert auth_resp.get("t") == "auth_ok"
        assert "telemetry" in auth_resp
        assert "macros" in auth_resp
        print("   ✓ auth_ok packet includes initial telemetry and macros array.")

        # Test on-demand telemetry request
        ws.send_text(json.dumps({"t": "get_telemetry"}))
        telem_msg = json.loads(ws.receive_text())
        assert telem_msg.get("t") == "telemetry"
        assert "cpu_percent" in telem_msg.get("d", {})
        print("   ✓ WebSocket get_telemetry stream response received.")

        # Test on-demand macros request
        ws.send_text(json.dumps({"t": "get_macros"}))
        macros_msg = json.loads(ws.receive_text())
        assert macros_msg.get("t") == "macros"
        assert isinstance(macros_msg.get("d"), list)
        print(f"   ✓ WebSocket get_macros received {len(macros_msg['d'])} macros.")

        # Test execute macro via WebSocket
        ws.send_text(json.dumps({"t": "macro", "id": "m_taskmgr"}))
        macro_exec_resp = json.loads(ws.receive_text())
        assert macro_exec_resp.get("t") == "macro_result"
        assert macro_exec_resp.get("id") == "m_taskmgr"
        assert macro_exec_resp.get("ok") is True
        print(f"   ✓ WebSocket macro trigger executed: {macro_exec_resp.get('msg')}")

        # Test execute nonexistent macro via WebSocket
        ws.send_text(json.dumps({"t": "macro", "id": "unknown_fake_id"}))
        fake_exec_resp = json.loads(ws.receive_text())
        assert fake_exec_resp.get("t") == "macro_result"
        assert fake_exec_resp.get("ok") is False
        print("   ✓ WebSocket unknown macro handled cleanly without socket termination.")


if __name__ == "__main__":
    print("=" * 60)
    print("     AirDeck Pro — Phase 4 Test & Verification Suite")
    print("=" * 60)
    test_system_telemetry_engine()
    test_macro_manager_lifecycle()
    test_streamdeck_and_telemetry_rest_routes()
    test_websocket_streamdeck_protocols()
    print("\n" + "=" * 60)
    print(" [ALL TESTS PASSED] Phase 4 is 100% verified and operational!")
    print("=" * 60)
