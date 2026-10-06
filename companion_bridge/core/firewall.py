"""
AirDeck Windows Defender Firewall Integration Subsystem
Provides automated checking, rule creation, and UAC elevation helpers
to ensure mobile devices can connect smoothly across the local Wi-Fi network.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

RULE_NAME = "AirDeck Pro"


def check_firewall_rule(rule_name: str = RULE_NAME) -> bool:
    """Check if an inbound Windows Firewall rule exists for AirDeck."""
    if sys.platform != "win32":
        return True

    try:
        res = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            text=True,
        )
        return res.returncode == 0 and "AirDeck" in res.stdout
    except Exception as e:
        print(f"[FIREWALL] Error querying rule: {e}")
        return False


def get_firewall_command(port: int = 8765, port_range: Optional[str] = "8765-8775") -> str:
    """Generate the exact netsh command required for inbound TCP traffic."""
    ports = port_range if port_range else str(port)
    return f'netsh advfirewall firewall add rule name="{RULE_NAME}" dir=in action=allow protocol=TCP localport={ports} profile=any'


def generate_firewall_script(output_path: Optional[Path] = None, port_range: str = "8765-8775") -> Path:
    """Generate a 1-click batch script to configure Windows Firewall with Admin rights."""
    if output_path is None:
        base_dir = Path(__file__).parent.parent.resolve()
        output_path = base_dir / "allow_firewall.bat"

    cmd = get_firewall_command(port_range=port_range)
    script_content = f"""@echo off
:: AirDeck Pro — Automated Windows Firewall Rule Installer
:: Requires Administrator privileges.
echo ============================================================
echo   AirDeck Pro - Windows Firewall Configuration
echo ============================================================
echo.
echo Adding inbound firewall rule for ports {port_range} (TCP)...

{cmd}

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] AirDeck Pro firewall rule added successfully!
    echo Your mobile phone can now connect to AirDeck on this Wi-Fi.
) else (
    echo.
    echo [ERROR] Failed to add firewall rule. Please right-click this script
    echo and choose 'Run as administrator'.
)
echo.
pause
"""
    output_path.write_text(script_content, encoding="utf-8")
    return output_path


def add_firewall_rule_elevated(port_range: str = "8765-8775") -> bool:
    """Request UAC elevation to automatically execute netsh firewall rule."""
    if sys.platform != "win32":
        return True

    cmd = get_firewall_command(port_range=port_range)
    ps_cmd = f"Start-Process cmd -ArgumentList '/c {cmd}' -Verb RunAs"

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return res.returncode == 0
    except Exception as e:
        print(f"[FIREWALL] Failed to request elevation: {e}")
        return False
