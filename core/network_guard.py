#!/usr/bin/env python3
"""Fail-closed network boundary. network_access stays false.

An attempted open is recorded and refused before any socket is used.
"""

from __future__ import annotations

from typing import Any, Dict, List


class NetworkDenied(PermissionError):
    pass


class OfflineBoundary:
    def __init__(self) -> None:
        self.network_access = False
        self.attempts: List[Dict[str, Any]] = []

    def attempt_connection(self, host: str, port: int, socket_module: Any = None) -> None:
        """Refuse a connection. socket_module is accepted only so tests can
        prove it is not called. It is never invoked.
        """
        self.attempts.append({"host": host, "port": int(port), "opened": False})
        if self.network_access is not False:
            # Flag corruption is still fail-closed: do not open.
            self.network_access = False
            raise NetworkDenied("network_access flag corrupted; forced false and refused")
        if socket_module is not None:
            # Presence of a socket implementation must not be used.
            pass
        raise NetworkDenied("network_access=false; connection refused by policy")
