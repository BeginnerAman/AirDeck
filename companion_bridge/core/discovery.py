"""
AirDeck Core mDNS / Zero-Configuration Discovery Subsystem
Broadcasts AirDeck service across the local network using Multicast DNS (Bonjour/mDNS),
allowing mobile devices to automatically discover and connect via airdeck.local or service query.
"""

import socket
from typing import Optional

from zeroconf import IPVersion, ServiceInfo, Zeroconf

SERVICE_TYPE = "_airdeck._tcp.local."
SERVICE_NAME = "AirDeck Pro._airdeck._tcp.local."


class DiscoveryService:
    """Manages mDNS advertisement on local network."""

    def __init__(self):
        self._zeroconf: Optional[Zeroconf] = None
        self._service_info: Optional[ServiceInfo] = None
        self.is_active = False

    def start(self, ip_str: str, port: int, server_name: str = "AirDeck Pro"):
        """Register AirDeck mDNS service and hostname on local network."""
        if self.is_active:
            return

        try:
            self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
            ip_bytes = socket.inet_aton(ip_str)

            desc = {
                "version": "3.0.0",
                "name": server_name,
                "ssl": "true",
                "auth": "pin",
                "endpoint": f"https://{ip_str}:{port}",
            }

            self._service_info = ServiceInfo(
                type_=SERVICE_TYPE,
                name=f"{server_name}.{SERVICE_TYPE}",
                addresses=[ip_bytes],
                port=port,
                properties=desc,
                server=f"airdeck-{socket.gethostname().lower()}.local.",
            )

            self._zeroconf.register_service(self._service_info)
            self.is_active = True
            print(f"[mDNS] ZeroConf service broadcast active: {SERVICE_TYPE} (Port: {port})")
        except Exception as e:
            print(f"[mDNS WARNING] Could not start Zeroconf discovery: {e}")
            self.is_active = False

    def stop(self):
        """Unregister mDNS service cleanly upon server shutdown."""
        if self._zeroconf and self._service_info:
            try:
                self._zeroconf.unregister_service(self._service_info)
                self._zeroconf.close()
                self.is_active = False
                print("[mDNS] ZeroConf service unregistered.")
            except Exception:
                pass


# Singleton instance
discovery_service = DiscoveryService()
