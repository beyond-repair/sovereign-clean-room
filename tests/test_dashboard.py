#!/usr/bin/env python3
"""Tests for Local Loopback Web Dashboard."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_cli import main, build_parser  # noqa: E402
from clean_room_dashboard import (  # noqa: E402
    LoopbackDashboard,
    collect_telemetry,
    LOOPBACK,
)


def test_parser_dashboard_start() -> None:
    p = build_parser()
    args = p.parse_args(["dashboard", "start", "--port", "8765"])
    assert hasattr(args, "func")
    print("[OK] dashboard start subcommand parses")


def test_reject_non_loopback_host() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        try:
            LoopbackDashboard(Path(tmp), host="0.0.0.0", port=8765)
            raise AssertionError("should reject 0.0.0.0")
        except PermissionError:
            pass
        try:
            LoopbackDashboard(Path(tmp), host="192.168.1.1", port=8765)
            raise AssertionError("should reject LAN bind")
        except PermissionError:
            pass
        print("[OK] non-loopback host rejected")


def test_http_health_and_telemetry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        assert main(["--workspace", str(ws), "init"]) == 0

        # free port: use 0 via temporary approach — pick high port
        port = 18765
        dash = LoopbackDashboard(ws, host=LOOPBACK, port=port)
        host, p = dash.start(blocking=False)
        assert host == LOOPBACK
        try:
            time.sleep(0.3)
            with urllib.request.urlopen(f"http://127.0.0.1:{p}/api/health", timeout=2) as resp:
                assert resp.status == 200
                health = json.loads(resp.read().decode("utf-8"))
            assert health.get("network_access") is False
            assert health.get("bind") == LOOPBACK

            with urllib.request.urlopen(f"http://127.0.0.1:{p}/api/telemetry", timeout=5) as resp:
                assert resp.status == 200
                tel = json.loads(resp.read().decode("utf-8"))
            assert tel.get("network_access") is False
            assert tel.get("engine", {}).get("jump_start_ok") is True
            assert "ledger" in tel and "memory" in tel and "shacl" in tel

            with urllib.request.urlopen(f"http://127.0.0.1:{p}/", timeout=2) as resp:
                assert resp.status == 200
                html = resp.read().decode("utf-8")
            assert "SEEM Sovereign Dashboard" in html
            assert "network_access" in html

            print("[OK] health + telemetry + HTML on loopback")
        finally:
            dash.stop()
            time.sleep(0.1)


def test_collect_telemetry_offline() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        main(["--workspace", str(ws), "init"])
        tel = collect_telemetry(ws)
        assert tel["network_access"] is False
        assert tel["engine"]["jump_start_ok"] is True
        print("[OK] collect_telemetry without server")


if __name__ == "__main__":
    test_parser_dashboard_start()
    test_reject_non_loopback_host()
    test_collect_telemetry_offline()
    test_http_health_and_telemetry()
    print("--- DASHBOARD TESTS PASSED ---")
