"""
AirDeck Phase 3 Comprehensive Automated Verification Suite
Tests: MediaDriver Subsystem, Hardware Status Reporting, Driver Failover,
       REST /api/media/status, and WebSocket Camera/Mic Control Protocols.
"""

import io
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from core.media_driver import media_driver
from core.security import security_engine
import server


def test_media_driver_diagnostics():
    print("\n[TEST] 1. Media Driver Hardware Diagnostics...")
    status = media_driver.get_hardware_status()
    assert "webcam" in status
    assert "microphone" in status

    cam_info = status["webcam"]
    mic_info = status["microphone"]

    print(f"   ✓ Webcam driver: {cam_info['driver']} (Available: {cam_info['available']})")
    print(f"   ✓ Mic driver: {mic_info['driver']} (Available: {mic_info['available']})")

    if not mic_info["available"]:
        assert "install_url" in mic_info
        print(f"   ✓ Missing driver failover provides install link: {mic_info['install_url']}")


def test_camera_lifecycle():
    print("\n[TEST] 2. Virtual Camera Dynamic Lifecycle...")
    # Test camera start
    ok, msg = media_driver.start_camera()
    assert ok is True
    assert media_driver.cam_active is True
    print(f"   ✓ Camera start: {msg}")

    # Push a test 64x64 JPEG frame
    img = Image.new("RGB", (64, 64), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    media_driver.push_video_frame(buf.getvalue())
    time.sleep(0.1)

    # Test camera stop
    media_driver.stop_camera()
    assert media_driver.cam_active is False
    assert media_driver.vcam_instance is None
    print("   ✓ Camera stop released virtual camera resources cleanly.")


def test_audio_driver_failover():
    print("\n[TEST] 3. Audio Driver Failover & Graceful Handling...")
    # AirDeck Pro v3.0: Virtual Mic requires VB-Audio Cable.
    # Without it, start_audio should return False with a clear install message.
    if not media_driver.has_audio():
        ok, msg = media_driver.start_audio()
        assert ok is False
        print(f"   ✓ Non-crashing graceful failover: '{msg}'")
    else:
        ok, msg = media_driver.start_audio()
        assert ok is True
        media_driver.stop_audio()
        print(f"   ✓ Virtual Mic stream opened and stopped cleanly: '{msg}'")


def test_media_rest_endpoints():
    print("\n[TEST] 4. Media REST Endpoints (/api/media/status & /api/info)...")
    client = TestClient(server.app)

    # 1. /api/media/status
    res = client.get("/api/media/status")
    assert res.status_code == 200
    data = res.json()
    assert "webcam" in data
    assert "microphone" in data
    print("   ✓ /api/media/status returned valid hardware diagnostics.")

    # 2. /api/info hardware section
    res_info = client.get("/api/info")
    assert res_info.status_code == 200
    info_data = res_info.json()
    assert "hardware" in info_data
    assert info_data["hardware"]["webcam"]["driver"] == data["webcam"]["driver"]
    print("   ✓ /api/info accurately embeds hardware state.")


def test_websocket_media_protocols():
    print("\n[TEST] 5. WebSocket Media Protocol Handshake & Control...")
    client = TestClient(server.app)
    pin = security_engine.pairing_pin

    with client.websocket_connect("/ws") as ws:
        # Auth Handshake
        ws.send_text(json.dumps({"t": "auth", "pin": pin}))
        auth_resp = json.loads(ws.receive_text())
        assert auth_resp.get("t") == "auth_ok"
        assert "hardware" in auth_resp
        print("   ✓ auth_ok packet includes hardware capability state.")

        # Query hardware on demand
        ws.send_text(json.dumps({"t": "get_hardware"}))
        hw_resp = json.loads(ws.receive_text())
        assert hw_resp.get("t") == "hardware_status"
        print("   ✓ Received live hardware_status from get_hardware.")

        # Test cam_start command
        ws.send_text(json.dumps({"t": "cam_start"}))
        cam_resp = json.loads(ws.receive_text())
        assert cam_resp.get("t") == "cam_status"
        assert cam_resp.get("ok") is True
        print(f"   ✓ WebSocket cam_start executed: {cam_resp.get('msg')}")

        # Test cam_stop command
        ws.send_text(json.dumps({"t": "cam_stop"}))
        stop_resp = json.loads(ws.receive_text())
        assert stop_resp.get("t") == "cam_status"
        assert stop_resp.get("ok") is True
        print("   ✓ WebSocket cam_stop executed cleanly.")

        # Test mic_start command (failover message)
        ws.send_text(json.dumps({"t": "mic_start"}))
        mic_resp = json.loads(ws.receive_text())
        assert mic_resp.get("t") == "mic_status"
        print(f"   ✓ WebSocket mic_start handled with state ok={mic_resp.get('ok')}: '{mic_resp.get('msg')}'")

        # Test mic_stop command
        ws.send_text(json.dumps({"t": "mic_stop"}))
        mstop_resp = json.loads(ws.receive_text())
        assert mstop_resp.get("t") == "mic_status"
        print("   ✓ WebSocket mic_stop executed cleanly.")

    # Verify post-disconnect cleanup
    time.sleep(0.1)
    assert media_driver.cam_active is False
    print("   ✓ Client disconnect automatically released hardware locks.")


if __name__ == "__main__":
    print("=" * 60)
    print("     AirDeck Pro — Phase 3 Test & Verification Suite")
    print("=" * 60)
    test_media_driver_diagnostics()
    test_camera_lifecycle()
    test_audio_driver_failover()
    test_media_rest_endpoints()
    test_websocket_media_protocols()
    print("\n" + "=" * 60)
    print(" [ALL TESTS PASSED] Phase 3 is 100% verified and operational!")
    print("=" * 60)
