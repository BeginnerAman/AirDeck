"""
AirDeck Pro — Standalone Executable Builder
Automates PyInstaller bundling of AirDeck into a standalone Windows executable.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image
from tray_app import create_tray_icon

BASE_DIR = Path(__file__).parent.resolve()
STATIC_DIR = BASE_DIR / "static"


def generate_app_icon() -> Path:
    """Ensure professional multi-resolution Windows .ico file is present."""
    icon_path = BASE_DIR / "airdeck.ico"
    icon_png = BASE_DIR / "airdeck_icon.png"

    if icon_png.exists():
        try:
            img = Image.open(icon_png)
            img.save(str(icon_path), format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            print(f"[BUILD] Generated multi-resolution application icon: {icon_path.name}")
            return icon_path
        except Exception as e:
            print(f"[BUILD] Warning converting .ico from PNG: {e}")

    if icon_path.exists():
        return icon_path

    try:
        img = create_tray_icon()
        img.save(str(icon_path), format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
        print(f"[BUILD] Generated fallback application icon: {icon_path.name}")
    except Exception as e:
        print(f"[BUILD] Warning: Could not generate .ico: {e}")
    return icon_path


def build():
    print("=" * 60)
    print("      AirDeck Pro — Standalone Executable Builder")
    print("=" * 60)
    print(f"[BUILD] Source directory: {BASE_DIR}")
    print(f"[BUILD] Static assets:    {STATIC_DIR}")

    icon_path = generate_app_icon()

    # Build PyInstaller command
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", "AirDeck",
        "--windowed",  # No black console window
        "--add-data", f"{STATIC_DIR};static",
        "--add-data", f"{BASE_DIR / 'core'};core",
        "--hidden-import", "core",
        "--hidden-import", "core.config",
        "--hidden-import", "core.crypto",
        "--hidden-import", "core.network",
        "--hidden-import", "core.input_driver",
        "--hidden-import", "core.security",
        "--hidden-import", "core.qr_window",
        "--hidden-import", "core.discovery",
        "--hidden-import", "core.media_driver",
        "--hidden-import", "core.telemetry",
        "--hidden-import", "core.macro_manager",
        "--hidden-import", "core.autostart",
        "--hidden-import", "core.firewall",
        "--hidden-import", "core.control_panel",
        "--hidden-import", "core.logger",
        "--hidden-import", "core.single_instance",
        "--hidden-import", "psutil",
        "--hidden-import", "winreg",
        "--hidden-import", "zeroconf",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "pystray",
        "--hidden-import", "pynput.keyboard._win32",
        "--hidden-import", "pynput.mouse._win32",
        "--hidden-import", "cryptography",
        "--hidden-import", "pyperclip",
        "--hidden-import", "pyaudio",
        "--hidden-import", "pyaudiowpatch",
        "--exclude-module", "cv2",
    ]

    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    cmd.append(str(BASE_DIR / "tray_app.py"))

    print("[BUILD] Executing PyInstaller command (this may take 1-2 minutes)...")
    res = subprocess.run(cmd, cwd=str(BASE_DIR))

    if res.returncode == 0:
        dist_dir = BASE_DIR / "dist" / "AirDeck"
        exe_path = dist_dir / "AirDeck.exe"

        # Copy essential default JSON, icons, and batch helpers alongside .exe
        try:
            for fname in ["config.json", "macros.json", "allow_firewall.bat", "airdeck_icon.png", "airdeck.ico"]:
                src_f = BASE_DIR / fname
                if src_f.exists():
                    shutil.copy(src_f, dist_dir / fname)
                    print(f"[BUILD] Bundled {fname} into distribution folder.")
        except Exception as e:
            print(f"[BUILD] Warning copying distribution files: {e}")

        print()
        print("=" * 60)
        print(" [SUCCESS] AirDeck.exe built successfully!")
        print(f" Executable location: {exe_path}")
        print("=" * 60)
        return True
    else:
        print("[ERROR] Build failed with exit code:", res.returncode)
        return False


if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
