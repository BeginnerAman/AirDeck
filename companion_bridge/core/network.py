"""
AirDeck Core Network Subsystem
Provides robust LAN IP detection across multi-NIC / virtual adapters and dynamic port allocation.
"""

import ipaddress
import socket
from typing import List, Optional


def is_virtual_or_link_local(ip_str: str) -> bool:
    """Detect if an IP is link-local, loopback, or likely a virtual adapter (WSL/Docker)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
        return False
    except ValueError:
        return True


def get_all_lan_ips() -> List[str]:
    """Retrieve all valid non-virtual IPv4 addresses on the host system."""
    candidates = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not is_virtual_or_link_local(ip):
                candidates.append(ip)
    except Exception:
        pass

    # Sort candidates prioritizing common home/office Wi-Fi ranges (192.168.x.x, 10.x.x.x)
    def ip_priority(ip: str) -> int:
        if ip.startswith("192.168."):
            return 1
        if ip.startswith("10."):
            return 2
        if ip.startswith("172."):
            return 3
        return 4

    candidates.sort(key=ip_priority)
    return candidates


def get_primary_lan_ip() -> str:
    """
    Detect the active LAN / Hotspot IP address reachable by mobile devices.
    Uses multi-stage discovery:
      1. Socket UDP probe towards external or gateway IP.
      2. Interface scan with virtual adapter filtering.
      3. Fallback to loopback 127.0.0.1.
    """
    # Stage 1: UDP Probe (fastest and most accurate for selecting the active default route)
    for probe_target in [("8.8.8.8", 80), ("1.1.1.1", 80), ("223.5.5.5", 80)]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(probe_target)
            ip = s.getsockname()[0]
            s.close()
            if not is_virtual_or_link_local(ip):
                return ip
        except Exception:
            continue

    # Stage 2: Filtered candidate list from hostname interfaces
    valid_ips = get_all_lan_ips()
    if valid_ips:
        return valid_ips[0]

    return "127.0.0.1"


def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a TCP port is currently occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def allocate_server_port(start_port: int = 8765, max_attempts: int = 10, auto_fallback: bool = True) -> int:
    """
    Find a free port starting from start_port.
    Returns start_port if free; otherwise attempts subsequent ports if auto_fallback is True.
    """
    if not is_port_in_use(start_port):
        return start_port

    if not auto_fallback:
        raise OSError(f"Port {start_port} is already in use and auto_fallback is disabled.")

    print(f"[NETWORK] Port {start_port} is in use. Searching for an alternative port...")
    for offset in range(1, max_attempts + 1):
        test_port = start_port + offset
        if not is_port_in_use(test_port):
            print(f"[NETWORK] Found free port: {test_port}")
            return test_port

    raise OSError(f"Could not find an available port in range {start_port}-{start_port + max_attempts}.")
