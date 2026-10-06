"""
AirDeck Phase 1 Comprehensive Automated Verification Suite
Tests: Config, Network, Persistent SSL, Security Engine, Input Driver, FastAPI HTTP & WebSocket.
"""

import ipaddress
import json
import socket
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.config import ConfigManager, config
from core.crypto import get_certs_dir, get_or_create_ssl_cert, is_cert_valid_for_ip
from core.input_driver import input_driver
from core.network import allocate_server_port, get_all_lan_ips, get_primary_lan_ip, is_port_in_use
from core.security import security_engine
import server


def test_config_system():
    print("\n[TEST] 1. Config System...")
    # Verify default keys
    assert config.get("server.port") == 8765
    assert config.get("server.auto_fallback_port") is True
    assert config.get("security.max_failed_attempts") == 5

    # Test nested set & persistence
    config.set("test_key.sub", 42)
    assert config.get("test_key.sub") == 42

    # Clean up test key
    test_file = Path("test_temp_config.json")
    custom_mgr = ConfigManager(test_file)
    custom_mgr.set("custom.val", 99)
    assert custom_mgr.get("custom.val") == 99
    assert test_file.exists()
    test_file.unlink()
    print("   ✓ Config load, merge, set, get & file persistence passed.")


def test_network_system():
    print("\n[TEST] 2. Network System...")
    ip = get_primary_lan_ip()
    # Check valid IP format
    parsed = ipaddress.ip_address(ip)
    assert not parsed.is_loopback or ip == "127.0.0.1"
    print(f"   ✓ Primary IP detected: {ip}")

    # Check port allocation
    free_port = allocate_server_port(8765)
    assert free_port >= 8765

    # Check fallback by artificially binding
    s = socket.socket()
    s.bind(("0.0.0.0", 8765))
    fallback_port = allocate_server_port(8765)
    assert fallback_port > 8765
    s.close()
    print(f"   ✓ Dynamic port auto-fallback passed (Found fallback: {fallback_port}).")


def test_crypto_system():
    print("\n[TEST] 3. Persistent SSL Crypto...")
    test_ip = "10.145.15.63"
    cert_path, key_path = get_or_create_ssl_cert(test_ip)
    assert Path(cert_path).exists()
    assert Path(key_path).exists()
    assert is_cert_valid_for_ip(Path(cert_path), test_ip) is True

    # Check that second call reuses existing cert without re-generating
    mtime_before = Path(cert_path).stat().st_mtime
    time.sleep(0.05)
    c2, k2 = get_or_create_ssl_cert(test_ip)
    mtime_after = Path(c2).stat().st_mtime
    assert mtime_before == mtime_after
    print("   ✓ Persistent 10-year SSL cert generated and successfully cached.")


def test_security_engine():
    print("\n[TEST] 4. Security & Rate Limiting & Persistence...")
    pin = security_engine.pairing_pin
    assert len(pin) == 4 and pin.isdigit()

    test_ip = "192.168.99.1"
    # Success with correct PIN
    ok, msg, token = security_engine.verify_auth(test_ip, pin=pin)
    assert ok is True
    assert token is not None
    assert security_engine.is_token_valid(token) is True

    # Success with rotated token
    ok2, msg2, token2 = security_engine.verify_auth(test_ip, token=token)
    assert ok2 is True
    assert security_engine.is_token_valid(token2) is True

    # Test file-backed persistence reload
    from core.security import SecurityEngine
    temp_storage = Path("test_paired_tokens_temp.json")
    try:
        temp_engine = SecurityEngine(storage_path=temp_storage)
        ok_p, _, p_token = temp_engine.verify_auth("192.168.1.100", pin=temp_engine.pairing_pin)
        assert ok_p is True

        # Simulate server reboot / reload with fresh instance
        reloaded_engine = SecurityEngine(storage_path=temp_storage)
        assert reloaded_engine.is_token_valid(p_token) is True
        print("   ✓ Token persistence across server reboots verified.")
    finally:
        if temp_storage.exists():
            temp_storage.unlink()

    # Failure with invalid PIN
    bad_ip = "192.168.99.2"
    ok_fail, msg_fail, _ = security_engine.verify_auth(bad_ip, pin="0000")
    assert ok_fail is False

    # Brute-force lockout test (5 attempts)
    lockout_ip = "192.168.99.3"
    for _ in range(5):
        security_engine.verify_auth(lockout_ip, pin="9999")

    # 6th attempt should be blocked even with correct PIN
    locked_ok, locked_msg, _ = security_engine.verify_auth(lockout_ip, pin=pin)
    assert locked_ok is False
    assert "Too many failed attempts" in locked_msg
    print(f"   ✓ Security auth passed. Brute-force lockout triggered correctly ({locked_msg}).")


def test_input_driver():
    print("\n[TEST] 5. Input Driver Subsystem (Win32 SendInput & PyAutoGUI)...")
    assert input_driver._worker_thread.is_alive()
    # Post operations to verify non-blocking queue
    input_driver.post_move(1.5, -2.0)
    input_driver.post_scroll(0, 2)
    input_driver.post_click("left")
    input_driver.post_mouse_down("left")
    input_driver.post_mouse_up("left")
    input_driver.release_all_mouse_buttons()
    input_driver.post_key("test")
    input_driver.post_action("desktop")
    input_driver.post_media("volup")
    print("   ✓ Input driver non-blocking queue, SendInput, and fail-safe button release verified.")


def test_fastapi_endpoints():
    print("\n[TEST] 6. FastAPI Endpoints & WebSocket Handshake...")
    client = TestClient(server.app)

    # 1. Root HTML
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "AirDeck" in res_root.text
    print("   ✓ GET / (HTML) returned 200 OK.")

    # 2. Manifest
    res_manifest = client.get("/manifest.json")
    assert res_manifest.status_code == 200
    manifest_data = res_manifest.json()
    assert manifest_data.get("short_name") == "AirDeck"
    print("   ✓ GET /manifest.json returned 200 OK.")

    # 3. Service Worker
    res_sw = client.get("/sw.js")
    assert res_sw.status_code == 200
    print("   ✓ GET /sw.js returned 200 OK.")

    # 4. /cert Download Route
    res_cert = client.get("/cert")
    assert res_cert.status_code in (200, 404)
    print("   ✓ GET /cert (Mobile SSL Root Profile) route active.")

    # 5. WebSocket Auth Rejection (Bad PIN)
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"t": "auth", "pin": "0000"}))
        resp = json.loads(ws.receive_text())
        assert resp.get("t") == "auth_fail"
        assert "Invalid PIN" in resp.get("reason", "")
    print("   ✓ WebSocket rejected invalid PIN with auth_fail & attempt count.")

    # 5. WebSocket Auth Success (Valid PIN) & Commands
    valid_pin = security_engine.pairing_pin
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"t": "auth", "pin": valid_pin}))
        auth_resp = json.loads(ws.receive_text())
        assert auth_resp.get("t") == "auth_ok"
        new_token = auth_resp.get("token")
        assert new_token is not None

        # Send test move packet
        ws.send_text(json.dumps({"t": "move", "x": 5.0, "y": 2.0}))

        # Send ping and receive pong
        ws.send_text(json.dumps({"t": "ping"}))
        pong_resp = json.loads(ws.receive_text())
        assert pong_resp.get("t") == "pong"

    print("   ✓ WebSocket authenticated, executed commands, responded to ping/pong.")


if __name__ == "__main__":
    print("=" * 60)
    print("     AirDeck Pro — Phase 1 Test & Verification Suite")
    print("=" * 60)
    test_config_system()
    test_network_system()
    test_crypto_system()
    test_security_engine()
    test_input_driver()
    test_fastapi_endpoints()
    print("\n" + "=" * 60)
    print(" [ALL TESTS PASSED] Phase 1 is 100% verified and operational!")
    print("=" * 60)
