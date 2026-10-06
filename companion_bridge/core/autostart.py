"""
AirDeck Core Autostart Subsystem
Manages Windows Registry run-on-boot configuration using the Windows standard winreg module.
"""

import os
import sys
from pathlib import Path
from typing import Optional

from core.config import config

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AirDeck"


def _get_executable_cmd() -> str:
    """Determine the command line invocation for AirDeck on Windows boot."""
    # If running as a frozen PyInstaller bundle
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'

    # If running from source Python: use pythonw.exe to prevent console window popup
    base_dir = Path(__file__).parent.parent.resolve()
    tray_script = base_dir / "tray_app.py"

    py_exe = Path(sys.executable)
    pyw_exe = py_exe.parent / "pythonw.exe"
    if pyw_exe.exists():
        return f'"{pyw_exe}" "{tray_script}" --minimized'
    return f'"{py_exe}" "{tray_script}" --minimized'


def is_autostart_enabled() -> bool:
    """Check if AirDeck is registered in Windows Startup registry."""
    if sys.platform != "win32":
        return bool(config.get("general.start_with_windows", False))

    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"[AUTOSTART] Error checking registry: {e}")
        return False


def set_autostart(enable: bool) -> bool:
    """Enable or disable AirDeck on Windows boot."""
    config.set("general.start_with_windows", enable)
    config.save()

    if sys.platform != "win32":
        return True

    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                cmd = _get_executable_cmd()
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                print(f"[AUTOSTART] Enabled startup in registry: {cmd}")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    print("[AUTOSTART] Disabled startup in registry.")
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print(f"[AUTOSTART] Error modifying registry: {e}")
        return False
