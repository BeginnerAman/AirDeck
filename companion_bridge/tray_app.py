"""
AirDeck Pro v3.0 — Windows System Tray & Native Pairing Controller
Provides background running in the Windows taskbar with zero console disruption,
single-instance focus restoration, and clean process lifecycle termination.
"""

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import List, Optional

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

import pystray
from PIL import Image, ImageDraw
import pyperclip
import uvicorn

import server
from core.config import config
from core.crypto import get_or_create_ssl_cert
from core.discovery import discovery_service
from core.input_driver import input_driver
from core.logger import logger
from core.media_driver import media_driver
from core.network import get_primary_lan_ip, allocate_server_port
from core.security import security_engine
from core.single_instance import SingleInstance


def create_tray_icon() -> Image.Image:
    """Load high-res AirDeck brand icon or generate crisp fallback for Windows notification area."""
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent.resolve()
    else:
        base_dir = Path(__file__).parent.resolve()

    icon_png = base_dir / "airdeck_icon.png"
    if icon_png.exists():
        try:
            return Image.open(icon_png).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        except Exception:
            pass

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, 60, 60], radius=16, fill=(108, 99, 255, 255))
    draw.rounded_rectangle([12, 12, 52, 52], radius=10, fill=(18, 18, 24, 255))
    draw.ellipse([25, 25, 39, 39], fill=(108, 99, 255, 255))
    return img


class AirDeckTrayApp:
    def __init__(self, port: Optional[int] = None):
        self.ip = get_primary_lan_ip()
        base_port = port or int(config.get("server.port", 8765))
        auto_fallback = bool(config.get("server.auto_fallback_port", True))
        max_attempts = int(config.get("server.max_port_attempts", 10))
        self.port = allocate_server_port(base_port, max_attempts=max_attempts, auto_fallback=auto_fallback)

        # Synchronize active port with server module
        server.active_server_port = self.port

        self.pin = security_engine.pairing_pin
        self.token = security_engine.master_token
        self.hostname = socket.gethostname()
        self.mdns_host = f"airdeck-{self.hostname.lower()}.local"
        self.direct_url = f"https://{self.ip}:{self.port}"
        self.mdns_url = f"https://{self.mdns_host}:{self.port}"
        self.auto_pair_url = f"{self.direct_url}/?token={self.token}"

        self.srv = None
        self.server_thread = None
        self.tray_icon = None
        self._children: List[subprocess.Popen] = []

    def start_server(self):
        """Run Uvicorn server in a dedicated background daemon thread."""
        cert_path, key_path = get_or_create_ssl_cert(self.ip)

        # Start mDNS advertisement
        discovery_service.start(self.ip, self.port, f"AirDeck Pro v3.0 ({self.hostname})")

        bind_host = config.get("server.host", "0.0.0.0")
        srv_config = uvicorn.Config(
            server.app,
            host=bind_host,
            port=self.port,
            ssl_keyfile=key_path,
            ssl_certfile=cert_path,
            log_level="warning",
            log_config=None,
        )
        self.srv = uvicorn.Server(srv_config)
        self.server_thread = threading.Thread(
            target=self.srv.run,
            daemon=True,
            name="AirDeck-UvicornServer",
        )
        self.server_thread.start()

    def show_control_panel(self):
        """Open the Desktop Control Panel in an isolated subprocess."""
        try:
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--control-panel"]
            else:
                cp_script = Path(__file__).parent / "core" / "control_panel.py"
                cmd = [sys.executable, str(cp_script)]
            # Pass server session info via env vars so control panel shows correct pairing data
            env = os.environ.copy()
            env["AIRDECK_PORT"] = str(self.port)
            env["AIRDECK_TOKEN"] = self.token
            env["AIRDECK_PIN"] = self.pin
            proc = subprocess.Popen(
                cmd,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            self._children.append(proc)
        except Exception as e:
            logger.error(f"[TRAY] Failed to open Control Panel: {e}")

    def show_qr_window(self):
        """Display pairing window in an isolated process to eliminate Tkinter threading crashes."""
        try:
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--qr-window", self.auto_pair_url, self.pin, self.mdns_url]
            else:
                qr_script = Path(__file__).parent / "core" / "qr_window.py"
                cmd = [sys.executable, str(qr_script), self.auto_pair_url, self.pin, self.mdns_url]
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            self._children.append(proc)
        except Exception:
            webbrowser.open(self.auto_pair_url)

    def copy_pin(self, icon, item):
        pyperclip.copy(self.pin)
        try:
            icon.notify(f"PIN {self.pin} copied to clipboard!", "AirDeck Pro v3.0")
        except Exception:
            pass

    def copy_url(self, icon, item):
        pyperclip.copy(self.auto_pair_url)
        try:
            icon.notify("Auto-pair URL copied to clipboard!", "AirDeck Pro v3.0")
        except Exception:
            pass

    def open_browser(self, icon, item):
        webbrowser.open(self.auto_pair_url)

    def on_exit(self, icon=None, item=None):
        """Perform a complete, graceful shutdown of all processes and background threads."""
        logger.info("Cleanly shutting down AirDeck Pro v3.0...")

        # 1. Terminate any active child subprocesses
        for proc in list(self._children):
            try:
                proc.terminate()
            except Exception:
                pass
        self._children.clear()

        # 2. Stop mDNS discovery, input drivers, and media pipelines
        try:
            discovery_service.stop()
            input_driver.stop()
            media_driver.cleanup_all()
        except Exception:
            pass

        # 3. Stop Uvicorn server
        if self.srv:
            self.srv.should_exit = True

        # 4. Stop tray icon
        if icon:
            try:
                icon.stop()
            except Exception:
                pass
        elif self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        # 5. Enforce zero-zombie OS exit
        time.sleep(0.2)
        os._exit(0)

    def run(self, show_qr_on_start: bool = True):
        self.start_server()
        time.sleep(0.5)

        if show_qr_on_start:
            self.show_qr_window()

        menu = pystray.Menu(
            pystray.MenuItem("Open Control Panel", lambda icon, item: self.show_control_panel(), default=True),
            pystray.MenuItem("Show Pairing QR Code", lambda icon, item: self.show_qr_window()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"AirDeck Pro v3.0 (Port {self.port})", None, enabled=False),
            pystray.MenuItem(f"Security PIN: {self.pin}", self.copy_pin),
            pystray.MenuItem("Copy Auto-Pair URL", self.copy_url),
            pystray.MenuItem("Open in Browser", self.open_browser),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit AirDeck", lambda icon, item: self.on_exit(icon, item)),
        )

        self.tray_icon = pystray.Icon(
            "AirDeck",
            create_tray_icon(),
            f"AirDeck Pro v3.0 (PIN: {self.pin})",
            menu=menu,
        )

        logger.info(f"AirDeck Pro v3.0 running in system tray (PIN: {self.pin}, Port: {self.port}).")
        self.tray_icon.run()


if __name__ == "__main__":
    if "--control-panel" in sys.argv:
        from core.control_panel import open_control_panel
        open_control_panel()
    elif "--qr-window" in sys.argv:
        from core.qr_window import show_pairing_window
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        url = args[0] if len(args) > 0 else "https://localhost:8765"
        pin = args[1] if len(args) > 1 else "0000"
        mdns = args[2] if len(args) > 2 else ""
        show_pairing_window(url, pin, mdns)
    else:
        # Enforce Single-Instance Mutex with Intelligent Foreground Window Focus
        mutex = SingleInstance()
        if mutex.is_running():
            logger.info("AirDeck is already running in background system tray. Bringing window to front.")
            if sys.platform == "win32":
                try:
                    import ctypes
                    hwnd = ctypes.windll.user32.FindWindowW(None, "AirDeck Pro v3.0 — Control Panel & Dashboard")
                    if not hwnd:
                        hwnd = ctypes.windll.user32.FindWindowW(None, "AirDeck Pro — Control Panel & Dashboard")
                    if not hwnd:
                        hwnd = ctypes.windll.user32.FindWindowW(None, "AirDeck Pro — Pair with Phone")
                    if hwnd:
                        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        ctypes.windll.user32.SetForegroundWindow(hwnd)
                        sys.exit(0)
                except Exception:
                    pass

            # If no UI window was currently open, launch Control Panel
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable, "--control-panel"])
            else:
                subprocess.Popen([sys.executable, str(Path(__file__).parent / "core" / "control_panel.py")])
            sys.exit(0)

        # Check for silent or minimized launch (e.g. from Windows autostart)
        silent = "--minimized" in sys.argv or "--silent" in sys.argv
        app = AirDeckTrayApp()
        app.run(show_qr_on_start=not silent)
