#!/usr/bin/env python3
"""Tests for Unified Sovereign Control CLI."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_cli import main, build_parser  # noqa: E402
from skill_crypto import generate_keypair, sign_package, save_keypair  # noqa: E402


def _pkg() -> dict:
    return {
        "manifest": {
            "skill_id": "cli_demo",
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


def test_parser_subcommands() -> None:
    p = build_parser()
    for cmd in (
        ["init"],
        ["status"],
        ["sign", "--package", "x.json"],
        ["ledger", "verify"],
        ["memory", "hello"],
        ["shacl", "--data", "x.json"],
        ["run", "--package", "x.json"],
        ["daemon", "start", "--package", "x.json"],
    ):
        args = p.parse_args(cmd)
        assert hasattr(args, "func")
    print("[OK] subcommand parsing")


def test_init_and_status() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = str(Path(tmp) / "ws")
        assert main(["--workspace", ws, "init"]) == 0
        assert (Path(ws) / "twin_state").is_dir()
        assert main(["--workspace", ws, "status"]) == 0
        assert main(["--workspace", ws, "status", "--strict"]) == 0
        print("[OK] init + status")


def test_sign_and_run_fail_unsigned() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        assert main(["--workspace", str(ws), "init"]) == 0
        pkg_path = Path(tmp) / "pkg.json"
        pkg_path.write_text(json.dumps(_pkg()), encoding="utf-8")

        rc = main(["--workspace", str(ws), "run", "--package", str(pkg_path)])
        assert rc == 2

        sk, vk = generate_keypair()
        (ws / "keys").mkdir(parents=True, exist_ok=True)
        save_keypair(ws / "keys", sk, vk, name="skill_ed25519")
        signed = sign_package(_pkg(), sk)
        signed_path = Path(tmp) / "pkg.signed.json"
        signed_path.write_text(json.dumps(signed), encoding="utf-8")

        rc = main(
            [
                "--workspace",
                str(ws),
                "run",
                "--package",
                str(signed_path),
                "--handler",
                "noop",
                "--note",
                "hello",
            ]
        )
        assert rc == 0
        print("[OK] unsigned fail-closed; signed run passes")


def test_ledger_verify_empty_ok() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = str(Path(tmp) / "ws")
        assert main(["--workspace", ws, "init"]) == 0
        assert main(["--workspace", ws, "ledger", "verify"]) == 0
        print("[OK] empty ledger verify")


def test_memory_remember_recall() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = str(Path(tmp) / "ws")
        assert main(["--workspace", ws, "init"]) == 0
        text = "cli episodic cedar quartz"
        assert main(["--workspace", ws, "memory", text, "--remember"]) == 0
        assert main(["--workspace", ws, "memory", text, "--top-k", "3"]) == 0
        print("[OK] memory remember/recall")


def test_shacl_check_package() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "good.json"
        good.write_text(json.dumps(_pkg()), encoding="utf-8")
        assert main(["shacl", "--data", str(good)]) == 0

        bad = Path(tmp) / "bad.json"
        bad_pkg = _pkg()
        bad_pkg["sovereignty"]["network_access"] = True
        bad.write_text(json.dumps(bad_pkg), encoding="utf-8")
        assert main(["shacl", "--data", str(bad)]) == 2
        print("[OK] shacl check pass/fail")


def test_missing_package_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = str(Path(tmp) / "ws")
        main(["--workspace", ws, "init"])
        try:
            main(
                [
                    "--workspace",
                    ws,
                    "run",
                    "--package",
                    str(Path(tmp) / "missing.json"),
                ]
            )
            raise AssertionError("expected SystemExit")
        except SystemExit as e:
            assert e.code == 1
        print("[OK] missing package fail-closed")


if __name__ == "__main__":
    test_parser_subcommands()
    test_init_and_status()
    test_sign_and_run_fail_unsigned()
    test_ledger_verify_empty_ok()
    test_memory_remember_recall()
    test_shacl_check_package()
    test_missing_package_fail_closed()
    print("--- CLI TESTS PASSED ---")
