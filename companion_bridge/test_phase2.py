"""
AirDeck Phase 2 Comprehensive Automated Verification Suite
Tests: mDNS / ZeroConf Service Broadcast, REST Discovery & Health APIs (/api/info, /api/pair/check).
"""

import json
import socket
from pathlib import Path

from fastapi.testclient import TestClient

from core.discovery import discovery_service, SERVICE_TYPE
from core.network import get_primary_lan_ip
from core.security import security_engine
import server


def test_zeroconf_discovery():
    print("\n[TEST] 1. ZeroConf mDNS Service Broadcast...")
    ip = get_primary_lan_ip()
    port = 8765

    # Start discovery
    discovery_service.start(ip, port, "AirDeck Test Node")
    assert discovery_service.is_active is True
    assert discovery_service._service_info is not None

    # Inspect service metadata
    info = discovery_service._service_info
    assert info.port == port
    assert info.type == SERVICE_TYPE
    assert b"3.0.0" in info.properties[b"version"]
    assert b"true" in info.properties[b"ssl"]
    print(f"   ✓ mDNS registered: {info.name} at {ip}:{port}")

    # Stop discovery
    discovery_service.stop()
    assert discovery_service.is_active is False
    print("   ✓ mDNS service successfully unregistered.")


def test_rest_discovery_api():
    print("\n[TEST] 2. REST Discovery API (/api/info & /api/pair/check)...")
    client = TestClient(server.app)

    # 1. /api/info
    res = client.get("/api/info")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "online"
    assert data.get("version") == "3.0.0"
    assert data.get("hostname") == socket.gethostname()
    assert "airdeck-" in data.get("mdns_hostname")
    assert "features" in data
    assert "webcam" in data["features"]
    assert "microphone" in data["features"]
    print(f"   ✓ /api/info returned valid node metadata (Hostname: {data.get('hostname')}).")

    # 2. /api/pair/check (Invalid token)
    res_invalid = client.get("/api/pair/check?token=invalid_token_123")
    assert res_invalid.status_code == 200
    assert res_invalid.json().get("valid") is False
    print("   ✓ /api/pair/check correctly rejected invalid token.")

    # 3. /api/pair/check (Valid token)
    valid_token = security_engine.master_token
    res_valid = client.get(f"/api/pair/check?token={valid_token}")
    assert res_valid.status_code == 200
    assert res_valid.json().get("valid") is True
    print("   ✓ /api/pair/check correctly verified active pairing token.")


def test_regression_websocket_and_routes():
    print("\n[TEST] 3. Phase 1 & 2 Regression Verification...")
    client = TestClient(server.app)

    # Static assets still resolving
    assert client.get("/").status_code == 200
    assert client.get("/manifest.json").status_code == 200
    assert client.get("/sw.js").status_code == 200

    # WebSocket handshake still works with dynamic token
    pin = security_engine.pairing_pin
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"t": "auth", "pin": pin}))
        resp = json.loads(ws.receive_text())
        assert resp.get("t") == "auth_ok"
        token = resp.get("token")
        assert token is not None

        # Verify new token works on REST check
        check = client.get(f"/api/pair/check?token={token}").json()
        assert check.get("valid") is True

    print("   ✓ Full WebSocket and REST integration verified.")


if __name__ == "__main__":
    print("=" * 60)
    print("     AirDeck Pro — Phase 2 Test & Verification Suite")
    print("=" * 60)
    test_zeroconf_discovery()
    test_rest_discovery_api()
    test_regression_websocket_and_routes()
    print("\n" + "=" * 60)
    print(" [ALL TESTS PASSED] Phase 2 is 100% verified and operational!")
    print("=" * 60)
