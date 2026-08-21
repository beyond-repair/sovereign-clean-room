#!/usr/bin/env python3
"""Integration tests for CleanRoomGodotBridge (Unix socket, offline)."""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_godot_bridge import (  # noqa: E402
    BridgeClient,
    BridgeConfig,
    CleanRoomGodotBridge,
    default_socket_path,
)
from skill_crypto import generate_keypair, sign_package  # noqa: E402


def _pkg() -> dict:
    return {
        "manifest": {
            "skill_id": "cold_boot_ping",
            "version": "1.0.0",
            "signature": "UNSIGNED_DEV_PLACEHOLDER",
            "author": "beyond-repair",
        },
        "sovereignty": {
            "network_access": False,
            "file_system_access": "none",
            "execution_mode": "sandboxed_python",
        },
        "vsa_bindings": {
            "dimension": 8192,
            "binding_threshold": 0.92,
            "sparsity_k": 256,
            "codebook_atoms": [
                "SELF",
                "ENVIRONMENT",
                "EPISODIC",
                "SEMANTIC",
                "SUCCESS",
                "FAILURE",
            ],
        },
        "interface": {"inputs": {}, "outputs": {}},
    }


def test_socket_must_be_under_workspace() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        ws.mkdir()
        outside = Path(tmp) / "evil.sock"
        try:
            CleanRoomGodotBridge(
                BridgeConfig(workspace=ws, socket_path=outside)
            )
            raise AssertionError("expected PermissionError")
        except PermissionError:
            pass
        print("[OK] socket path isolation")


def test_ping_memory_ledger_skill() -> None:
    sk, vk = generate_keypair()
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        sock = default_socket_path(ws)
        bridge = CleanRoomGodotBridge(
            BridgeConfig(
                workspace=ws,
                socket_path=sock,
                trusted_verify_keys=[vk],
                require_skill_signature=True,
            )
        )
        bridge.start(blocking=False)
        time.sleep(0.2)
        try:
            client = BridgeClient(sock)

            pong = client.request("ping")
            assert pong["ok"] is True
            assert pong["network_access"] is False
            assert pong["dim"] == 8192

            # Game-state telemetry → memory + ledger
            r = client.request(
                "memory_remember",
                content="cold boot player entered sector-7",
                meta={"scene": "sector-7", "tick": 42},
            )
            assert r["ok"] is True
            eid = r["episode_id"]

            hits = client.request(
                "memory_recall", query="cold boot player entered sector-7", top_k=3
            )
            assert hits["ok"] is True
            assert any(h["episode_id"] == eid for h in hits["hits"])

            # SHACL on good package shape
            sh = client.request("shacl_check", data=_pkg())
            assert sh["ok"] is True and sh["conforms"] is True

            bad = _pkg()
            bad["sovereignty"]["network_access"] = True
            sh2 = client.request("shacl_check", data=bad)
            assert sh2["ok"] is True and sh2["conforms"] is False

            # Signed skill run
            signed = sign_package(_pkg(), sk)
            run = client.request("skill_run", package=signed, payload={"tick": 42})
            assert run["ok"] is True, run

            # Unsigned rejected
            run2 = client.request("skill_run", package=_pkg())
            assert run2["ok"] is False

            # Ledger chain
            ver = client.request("ledger_verify")
            assert ver["ok"] is True
            assert ver.get("entries", 0) >= 1

            tel = client.request("telemetry")
            assert tel["ok"] is True
            assert tel["engine"]["jump_start_ok"] is True

            print("[OK] ping / memory / shacl / skill / ledger via Unix IPC")
        finally:
            bridge.stop()


def test_ledger_append_game_telemetry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        sock = default_socket_path(ws)
        bridge = CleanRoomGodotBridge(
            BridgeConfig(
                workspace=ws,
                socket_path=sock,
                require_skill_signature=False,
            )
        )
        bridge.start(blocking=False)
        time.sleep(0.15)
        try:
            client = BridgeClient(sock)
            r = client.request(
                "ledger_append",
                event_type="cold_boot_frame",
                payload={"fps": 60, "nodes": 12},
            )
            assert r["ok"] is True
            assert "entry_hash" in r
            ver = client.request("ledger_verify")
            assert ver["ok"] is True
            print("[OK] game telemetry on append-only ledger")
        finally:
            bridge.stop()


if __name__ == "__main__":
    test_socket_must_be_under_workspace()
    test_ping_memory_ledger_skill()
    test_ledger_append_game_telemetry()
    print("--- GODOT BRIDGE TESTS PASSED ---")
