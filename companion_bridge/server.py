"""
AirDeck Pro — Wireless Hardware Companion Bridge (Server v2.0 Enterprise)

Modular Architecture:
  - Non-Blocking Concurrency: Input driver, Video and Audio threads decoupled from asyncio.
  - Zero-Trust Security Engine: Dynamic 4-digit PIN + Persistent Token Handshake + Brute Force Protection.
  - Persistent SSL Infrastructure: Eliminates repeating browser security warnings.
  - Intelligent Multi-NIC IP Binding & Port Auto-Fallback.
  - Hardware Media Driver Manager: Decoupled virtual camera and virtual audio lifecycle.
"""

import argparse
import asyncio
import io
import json
import os
import platform
import socket
import sys
import threading
from pathlib import Path
from typing import Optional

# Prevent windowed / GUI NoneType sys.stdout.isatty crashes
class SafeStream:
    def write(self, s):
        pass
    def flush(self):
        pass
    def isatty(self):
        return False
    def reconfigure(self, **kwargs):
        pass

if sys.stdout is None:
    sys.stdout = SafeStream()
if sys.stderr is None:
    sys.stderr = SafeStream()

# Fix Windows console UnicodeEncodeError for QR codes
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pyperclip
import qrcode
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles

# Core Subsystems
from core.config import config
from core.crypto import get_or_create_ssl_cert
from core.discovery import discovery_service
from core.input_driver import input_driver
from core.macro_manager import macro_manager
from core.media_driver import media_driver
from core.network import get_primary_lan_ip, allocate_server_port
from core.security import security_engine
from core.telemetry import get_system_telemetry

active_clients = 0
clients_lock = threading.Lock()
active_server_port = 8765


def show_qr(url: str):
    """Render an inverted QR code in the terminal."""
    try:
        qr = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(url)
        qr.make(fit=True)
        try:
            qr.print_ascii(invert=True)
        except Exception:
            try:
                if hasattr(sys.stdout, "buffer"):
                    f = io.StringIO()
                    qr.print_ascii(out=f, invert=True)
                    sys.stdout.buffer.write(f.getvalue().encode("utf-8", errors="replace"))
                    sys.stdout.buffer.flush()
                else:
                    qr.print_tty()
            except Exception:
                print(f"   [QR Link] {url}")
    except Exception:
        print(f"   [QR Link] {url}")


# ════════════════════════════════════════════════════════════════
#  FASTAPI APPLICATION & ROUTING
# ════════════════════════════════════════════════════════════════

from contextlib import asynccontextmanager
from fastapi import Depends, Header, HTTPException, Query, Request, status

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    discovery_service.stop()
    input_driver.stop()
    media_driver.cleanup_all()

app = FastAPI(title="AirDeck Pro v3.0", docs_url=None, redoc_url=None, lifespan=lifespan)

if getattr(sys, "frozen", False):
    STATIC_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "static"
else:
    STATIC_DIR = Path(__file__).parent / "static"


async def verify_auth_token(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> str:
    """Validate Bearer token from Header or Query parameter."""
    auth_tok = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            auth_tok = parts[1].strip()
        elif len(parts) == 1:
            auth_tok = parts[0].strip()
    elif token:
        auth_tok = token.strip()

    if not auth_tok or not security_engine.is_token_valid(auth_tok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid authentication token required.",
        )
    return auth_tok


# Static & PWA Routes
@app.get("/", response_class=HTMLResponse)
async def serve_root():
    index_file = STATIC_DIR / "index.html"
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/sw.js")
async def serve_sw():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


@app.get("/favicon.ico")
async def serve_favicon():
    return Response(status_code=204)


# REST Discovery & Telemetry APIs
@app.get("/api/info")
async def get_server_info():
    """Expose server capability, pairing state, and driver health."""
    primary_ip = get_primary_lan_ip()
    hostname = socket.gethostname()
    hw_status = media_driver.get_hardware_status()
    return {
        "status": "online",
        "name": f"AirDeck Pro v3.0 ({hostname})",
        "version": "3.0.0",
        "hostname": hostname,
        "mdns_hostname": f"airdeck-{hostname.lower()}.local",
        "ip": primary_ip,
        "port": active_server_port,
        "features": {
            "webcam": hw_status["webcam"]["available"],
            "microphone": hw_status["microphone"]["available"],
            "speaker": hw_status["speaker"]["available"],
        },
        "hardware": hw_status,
        "active_clients": active_clients,
    }


@app.get("/api/pair/check")
async def check_pairing_token(token: str = ""):
    """Validate whether a stored client token is authorized."""
    return {"valid": bool(token and security_engine.is_token_valid(token))}


@app.get("/api/media/status")
async def get_media_status():
    """Diagnostic health check for virtual webcam and microphone."""
    return media_driver.get_hardware_status()


@app.get("/api/telemetry")
async def get_telemetry(_auth: str = Depends(verify_auth_token)):
    """Live CPU, RAM, Battery, and Uptime metrics (Authenticated)."""
    return get_system_telemetry()


@app.get("/api/macros")
async def get_macros(_auth: str = Depends(verify_auth_token)):
    """Retrieve active Stream Deck macros (Authenticated)."""
    return macro_manager.get_macros()


@app.post("/api/macros")
async def create_macro(macro: dict, _auth: str = Depends(verify_auth_token)):
    """Add or save custom Stream Deck macro (Authenticated)."""
    return macro_manager.add_macro(macro)


@app.delete("/api/macros/{macro_id}")
async def remove_macro(macro_id: str, _auth: str = Depends(verify_auth_token)):
    """Delete a macro by ID (Authenticated)."""
    return {"ok": macro_manager.delete_macro(macro_id)}


@app.post("/api/macros/reset")
async def restore_default_macros(_auth: str = Depends(verify_auth_token)):
    """Reset macros to factory defaults (Authenticated)."""
    return macro_manager.reset_defaults()


# SSL Root Certificate Installation Route for Mobile Devices
@app.get("/cert")
@app.get("/api/cert/download")
async def download_ssl_certificate():
    """Download the AirDeck local SSL certificate for phone trust installation."""
    from core.crypto import get_certs_dir
    cert_path = get_certs_dir() / "airdeck_cert.pem"
    if cert_path.exists():
        return FileResponse(
            cert_path,
            media_type="application/x-x509-ca-cert",
            filename="airdeck_cert.crt",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
                "Content-Disposition": "attachment; filename=\"airdeck_cert.crt\"",
            },
        )
    return Response(status_code=404, content="Certificate not generated yet.")


@app.post("/api/system/shutdown")
async def system_shutdown():
    """Cleanly exit AirDeck process (used by Control Panel and QR Window)."""
    import time
    def _delayed_exit():
        time.sleep(0.3)
        discovery_service.stop()
        input_driver.stop()
        media_driver.cleanup_all()
        os._exit(0)

    threading.Thread(target=_delayed_exit, daemon=True, name="AirDeck-ShutdownWorker").start()
    return {"ok": True, "message": "AirDeck shutting down..."}


# ════════════════════════════════════════════════════════════════
#  WEBSOCKET ENDPOINT (With Security Handshake & Input/Media Drivers)
# ════════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    global active_clients
    await ws.accept()
    client_ip = ws.client.host if ws.client else "unknown"

    # ── Security Handshake (PIN or Token) ──────────────────────────
    authenticated = False
    try:
        raw_msg = await asyncio.wait_for(ws.receive(), timeout=30.0)

        # Check if message is JSON text
        if "text" not in raw_msg:
            await ws.send_text(json.dumps({"t": "auth_fail", "reason": "Expected text authentication"}))
            await ws.close(code=4401)
            return

        auth_data = json.loads(raw_msg["text"])
        if auth_data.get("t") == "auth":
            tok = auth_data.get("token")
            pin = auth_data.get("pin")

            ok, reason, new_token = security_engine.verify_auth(client_ip, token=tok, pin=pin)
            if ok:
                authenticated = True
                with clients_lock:
                    active_clients += 1
                await ws.send_text(json.dumps({
                    "t": "auth_ok",
                    "token": new_token,
                    "hardware": media_driver.get_hardware_status(),
                    "telemetry": get_system_telemetry(),
                    "macros": macro_manager.get_macros(),
                }))
                print(f"[WS] Device paired & verified: {client_ip} (Active clients: {active_clients})")
            else:
                await ws.send_text(json.dumps({"t": "auth_fail", "reason": reason}))
                await ws.close(code=4401)
                return
        else:
            await ws.close(code=4401)
            return

    except Exception:
        try:
            await ws.close(code=4401)
        except Exception:
            pass
        return

    # ── Authenticated Command Processing Loop ──────────────────────
    try:
        while True:
            msg = await ws.receive()

            # ── Binary payload: Webcam (0x01) or Mic (0x02) ────────
            raw = msg.get("bytes")
            if raw:
                marker = raw[0]
                payload = raw[1:]

                if marker == 0x01:
                    media_driver.push_video_frame(payload)
                elif marker == 0x02:
                    media_driver.push_audio_chunk(payload)
                continue

            # ── JSON text payload: Controls ───────────────────────
            text = msg.get("text")
            if not text:
                continue

            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue

            t = data.get("t")

            # Mouse move
            if t == "move":
                input_driver.post_move(data.get("x", 0), data.get("y", 0))

            # Touch session ended / finger lifted
            elif t == "move_end":
                input_driver.reset_sub_pixels()

            # Mouse click
            elif t == "click":
                input_driver.post_click(data.get("b", "left"))

            # Mouse down
            elif t == "mdown":
                input_driver.post_mouse_down(data.get("b", "left"))

            # Mouse up
            elif t == "mup":
                input_driver.post_mouse_up(data.get("b", "left"))

            # Wheel scroll
            elif t == "scroll":
                input_driver.post_scroll(int(data.get("x", 0)), int(data.get("y", 0)))

            # Keyboard text input
            elif t == "key":
                input_driver.post_key(data.get("d", ""))

            # Keyboard special key
            elif t == "skey":
                input_driver.post_special_key(data.get("k", ""))

            # Hotkey combo
            elif t == "hotkey":
                input_driver.post_hotkey(data.get("k", []))

            # System / Daily Power Actions
            elif t == "action":
                input_driver.post_action(data.get("a", ""))

            # Media control
            elif t == "media":
                input_driver.post_media(data.get("a", ""))

            # Camera control
            elif t == "cam_start":
                ok, cmsg = media_driver.start_camera()
                await ws.send_text(json.dumps({"t": "cam_status", "ok": ok, "msg": cmsg}))

            elif t == "cam_stop":
                media_driver.stop_camera()
                await ws.send_text(json.dumps({"t": "cam_status", "ok": True, "msg": "Camera stopped"}))

            # Mic control (Phone -> PC)
            elif t == "mic_start":
                ok, mmsg = media_driver.start_audio()
                await ws.send_text(json.dumps({"t": "mic_status", "ok": ok, "msg": mmsg}))

            elif t == "mic_stop":
                media_driver.stop_audio()
                await ws.send_text(json.dumps({"t": "mic_status", "ok": True, "msg": "Microphone stopped"}))

            # Wireless Extended Speaker (PC System Audio Loopback -> Phone)
            elif t == "speaker_start":
                loop = asyncio.get_running_loop()

                def _on_speaker_chunk(chunk_bytes: bytes):
                    # Packet format: 0x03 prefix + 16-bit PCM bytes
                    packet = b"\x03" + chunk_bytes
                    try:
                        asyncio.run_coroutine_threadsafe(ws.send_bytes(packet), loop)
                    except Exception:
                        pass

                ok, smsg = media_driver.start_speaker_stream(_on_speaker_chunk)
                await ws.send_text(json.dumps({"t": "speaker_status", "ok": ok, "msg": smsg}))

            elif t == "speaker_stop":
                media_driver.stop_speaker_stream()
                await ws.send_text(json.dumps({"t": "speaker_status", "ok": True, "msg": "Wireless speaker stopped"}))

            # Query hardware status on-demand
            elif t == "get_hardware":
                await ws.send_text(json.dumps({
                    "t": "hardware_status",
                    "data": media_driver.get_hardware_status(),
                }))

            # Stream Deck custom macro execution
            elif t == "macro":
                mid = data.get("id", "")
                ok, mmsg = macro_manager.execute_macro(mid)
                await ws.send_text(json.dumps({"t": "macro_result", "id": mid, "ok": ok, "msg": mmsg}))

            # Telemetry metrics poll
            elif t == "get_telemetry":
                await ws.send_text(json.dumps({
                    "t": "telemetry",
                    "d": get_system_telemetry(),
                }))

            # Macros definition poll
            elif t == "get_macros":
                await ws.send_text(json.dumps({
                    "t": "macros",
                    "d": macro_manager.get_macros(),
                }))

            # Clipboard get: Laptop -> Phone
            elif t == "clipget":
                clip_text = await asyncio.to_thread(pyperclip.paste)
                await ws.send_text(json.dumps({"t": "clip", "d": clip_text or ""}))

            # Clipboard set: Phone -> Laptop
            elif t == "clipset":
                val = data.get("d", "")
                await asyncio.to_thread(pyperclip.copy, val)

            # Heartbeat ping
            elif t == "ping":
                await ws.send_text(json.dumps({"t": "pong"}))

    except WebSocketDisconnect:
        print(f"[WS] Device disconnected ({client_ip})")
    except Exception as e:
        if "disconnect message has been received" not in str(e):
            print(f"[WS] Connection error: {e}")
    finally:
        input_driver.release_all_mouse_buttons()
        if authenticated:
            with clients_lock:
                active_clients = max(0, active_clients - 1)
            if active_clients <= 0:
                media_driver.cleanup_all()


# Mount static assets under `/static`
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ════════════════════════════════════════════════════════════════
#  SERVER LAUNCHER & CLI ENTRYPOINT
# ════════════════════════════════════════════════════════════════

def run_server(port: Optional[int] = None, host: Optional[str] = None):
    """Start the AirDeck server with dynamic network & certificate provisioning."""
    primary_ip = get_primary_lan_ip()
    base_port = port or int(config.get("server.port", 8765))
    bind_host = host or config.get("server.host", "0.0.0.0")

    # Allocate available port with auto-fallback
    global active_server_port
    auto_fallback = bool(config.get("server.auto_fallback_port", True))
    max_attempts = int(config.get("server.max_port_attempts", 10))
    active_port = allocate_server_port(base_port, max_attempts=max_attempts, auto_fallback=auto_fallback)
    active_server_port = active_port

    # Start ZeroConf mDNS discovery
    hostname = socket.gethostname()
    mdns_host = f"airdeck-{hostname.lower()}.local"
    discovery_service.start(primary_ip, active_port, f"AirDeck ({hostname})")

    url = f"https://{primary_ip}:{active_port}"
    mdns_url = f"https://{mdns_host}:{active_port}"
    auto_pair_url = f"{url}/?token={security_engine.master_token}"
    cert_path, key_path = get_or_create_ssl_cert(primary_ip)

    hw_info = media_driver.get_hardware_status()
    vcam_ok = hw_info["webcam"]["available"]
    audio_ok = hw_info["microphone"]["available"]

    print()
    print("=" * 64)
    print("       AirDeck Pro — Wireless Hardware Companion Suite v3.0")
    print("=" * 64)
    print(f"\n   Direct IP  : {url}")
    print(f"   mDNS Host  : {mdns_url}")
    print(f"   Auto-Pair  : {auto_pair_url}\n")
    print("   +-------------------------------------------------------+")
    print(f"   |  SECURITY PAIRING PIN:  [  {security_engine.pairing_pin}  ]                    |")
    print("   |  Scan QR below for 1-Tap Instant Auto-Pairing         |")
    print("   +-------------------------------------------------------+\n")
    show_qr(auto_pair_url)
    print()
    print("   Active Features & Drivers:")
    print("   ✓ Trackpad & Adaptive High-Speed Scroll Strip")
    print("   ✓ Non-Blocking Win32 Input Worker Thread (0ms Latency)")
    print("   ✓ Native Mobile Keyboard & Voice Typing")
    print("   ✓ Tactile Volume Controls (+ / - / Mute)")
    print("   ✓ Daily Power Tools: Desktop, Alt-Tab, Screenshot, Lock PC")
    print("   ✓ Instant Bi-directional Clipboard Sync")
    print("   ✓ Persistent SSL & In-Memory Mobile Root Profile Download")
    print("   ✓ mDNS / ZeroConf Discovery (airdeck.local)")
    print(f"   ✓ HD Virtual Webcam    : {hw_info['webcam']['driver']}")
    print(f"   ✓ Studio Microphone    : {hw_info['microphone']['driver']}")
    print(f"   ✓ Extended Speaker (PC) : {'Active (WASAPI Loopback)' if hw_info['speaker']['available'] else 'Not Available'}")
    print()
    print("=" * 64)
    print()

    uvicorn.run(
        app,
        host=bind_host,
        port=active_port,
        ssl_keyfile=key_path,
        ssl_certfile=cert_path,
        log_level="warning",
        log_config=None,
    )


def main():
    parser = argparse.ArgumentParser(description="AirDeck Pro Companion Suite")
    parser.add_argument("--tray", action="store_true", help="Launch in Windows System Tray mode")
    parser.add_argument("--minimized", action="store_true", help="Start minimized in system tray without showing QR window")
    parser.add_argument("--silent", action="store_true", help="Start silently in background")
    parser.add_argument("--port", type=int, default=None, help="Custom server port")
    args = parser.parse_args()

    if args.tray or args.minimized or args.silent:
        from core.single_instance import SingleInstance
        mutex = SingleInstance()
        if mutex.is_running():
            print("[INFO] AirDeck is already running in background system tray.")
            return

        try:
            from tray_app import AirDeckTrayApp
            tray = AirDeckTrayApp(port=args.port)
            tray.run(show_qr_on_start=not (args.minimized or args.silent))
            return
        except Exception as e:
            print(f"[INFO] System tray launch error ({e}), falling back to CLI mode.")

    run_server(port=args.port)


if __name__ == "__main__":
    main()
