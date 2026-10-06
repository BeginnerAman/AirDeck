"""
AirDeck Core Telemetry Subsystem
Monitors PC vital performance metrics (CPU, RAM, Battery, Uptime) for real-time mobile display.
"""

import socket
import time
from typing import Any, Dict, Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

_boot_time = time.time()
if HAS_PSUTIL:
    try:
        _boot_time = psutil.boot_time()
    except Exception:
        pass


def get_system_telemetry() -> Dict[str, Any]:
    """Gather real-time PC diagnostic metrics safely."""
    if not HAS_PSUTIL:
        return {
            "available": False,
            "cpu_percent": 0.0,
            "ram_percent": 0.0,
            "ram_used_gb": 0.0,
            "ram_total_gb": 0.0,
            "battery": None,
            "uptime_seconds": int(time.time() - _boot_time),
        }

    try:
        # Non-blocking CPU percent reading
        cpu = psutil.cpu_percent(interval=None)

        mem = psutil.virtual_memory()
        ram_pct = mem.percent
        ram_used = round(mem.used / (1024 ** 3), 1)
        ram_total = round(mem.total / (1024 ** 3), 1)

        battery_info: Optional[Dict[str, Any]] = None
        try:
            batt = psutil.sensors_battery()
            if batt:
                battery_info = {
                    "percent": round(batt.percent),
                    "power_plugged": batt.power_plugged,
                }
        except Exception:
            pass

        uptime = int(time.time() - _boot_time)

        return {
            "available": True,
            "cpu_percent": round(cpu, 1),
            "ram_percent": round(ram_pct, 1),
            "ram_used_gb": ram_used,
            "ram_total_gb": ram_total,
            "battery": battery_info,
            "uptime_seconds": uptime,
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "cpu_percent": 0.0,
            "ram_percent": 0.0,
        }
