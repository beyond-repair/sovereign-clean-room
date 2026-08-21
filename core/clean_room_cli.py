#!/usr/bin/env python3
"""
Unified Sovereign Control CLI & Command Center

Offline-first workspace management for:
  VSA core, skill signing, orchestrator, ledger, checkpoints,
  daemon, episodic memory, SHACL, local model bridge, loopback dashboard,
  JKillnHide integrity watchdog, Ware/SPARC physics bridge.

No external network. network_access: false.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_CORE = Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))


def _die(msg: str, code: int = 1) -> None:
    print(f"[-] {msg}", file=sys.stderr)
    raise SystemExit(code)


def _ok(msg: str) -> None:
    print(f"[+] {msg}")


def _workspace(path: Optional[str]) -> Path:
    return Path(path or "./sovereign_workspace").resolve()


def _read_key_hex(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip().split()[0]


def _load_engine(ws: Path):
    from clean_room_vsa import CleanRoomVSAEngine

    eng = CleanRoomVSAEngine(dim=8192)
    twin = ws / "twin_state"
    if twin.is_dir():
        try:
            eng.load(twin)
            return eng
        except Exception:
            pass
    eng.jump_start_v01()
    return eng


def cmd_init(args: argparse.Namespace) -> int:
    from clean_room_vsa import CleanRoomVSAEngine

    ws = _workspace(args.workspace)
    (ws / "audit").mkdir(parents=True, exist_ok=True)
    (ws / "checkpoints").mkdir(exist_ok=True)
    (ws / "memory").mkdir(exist_ok=True)
    (ws / "skills").mkdir(exist_ok=True)
    (ws / "keys").mkdir(exist_ok=True)
    (ws / "defense").mkdir(exist_ok=True)
    twin = ws / "twin_state"

    engine = CleanRoomVSAEngine(dim=8192)
    engine.jump_start_v01()
    engine.save(twin)

    meta = {
        "version": "sovereign_workspace_v1",
        "dim": 8192,
        "network_access": False,
        "twin_state": str(twin),
    }
    (ws / "workspace.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _ok(f"workspace initialized at {ws}")
    _ok("Jump-Start v0.1 pinned atoms written to twin_state")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from clean_room_vsa import CleanRoomVSAEngine
    from clean_room_ledger import CleanRoomLedger, CheckpointStore

    ws = _workspace(args.workspace)
    report: Dict[str, Any] = {"workspace": str(ws), "network_access": False}

    twin = ws / "twin_state"
    eng = CleanRoomVSAEngine(dim=8192)
    if twin.is_dir():
        try:
            eng.load(twin)
            report["engine"] = {
                "loaded": True,
                "jump_start_ok": eng.verify_jump_start_integrity(),
                "codebook": eng.codebook_stats(),
            }
        except Exception as e:
            report["engine"] = {"loaded": False, "error": str(e)}
    else:
        report["engine"] = {"loaded": False, "error": "no twin_state"}

    audit = ws / "audit"
    if audit.is_dir():
        led = CleanRoomLedger(audit)
        report["ledger"] = led.verify_chain()
    else:
        report["ledger"] = {"ok": True, "entries": 0, "note": "no audit dir"}

    ckpt_dir = ws / "checkpoints"
    ckpts = list(ckpt_dir.glob("ckpt_*.json")) if ckpt_dir.is_dir() else []
    ckpt_ok = 0
    ckpt_bad = 0
    store = CheckpointStore(ckpt_dir) if ckpt_dir.is_dir() else None
    for p in ckpts:
        pid = p.stem.replace("ckpt_", "", 1)
        try:
            if store:
                store.load(pid, verify=True)
            ckpt_ok += 1
        except Exception:
            ckpt_bad += 1
    report["checkpoints"] = {"count": len(ckpts), "valid": ckpt_ok, "invalid": ckpt_bad}

    keys_dir = ws / "keys"
    vk_files = list(keys_dir.glob("*.pub")) if keys_dir.is_dir() else []
    report["trust_roots"] = {
        "verify_key_files": len(vk_files),
        "paths": [str(p) for p in vk_files],
    }

    mem = ws / "memory" / "manifest.json"
    if mem.is_file():
        man = json.loads(mem.read_text(encoding="utf-8"))
        report["memory"] = {
            "episodes": len(man.get("episodes") or {}),
            "bundles": len(man.get("bundles") or {}),
            "tau": man.get("tau"),
        }
    else:
        report["memory"] = {"episodes": 0}

    baseline = ws / "defense" / "baseline.json"
    report["jkillnhide"] = {
        "baseline_present": baseline.is_file(),
        "path": str(baseline) if baseline.is_file() else None,
    }

    print(json.dumps(report, indent=2))
    if args.strict:
        eng_ok = report.get("engine", {}).get("jump_start_ok", False)
        led = report.get("ledger", {})
        led_ok = led.get("ok", False) or led.get("entries", 0) == 0
        if not eng_ok or not led_ok or report["checkpoints"]["invalid"] > 0:
            return 2
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    from skill_crypto import sign_package, generate_keypair, save_keypair

    ws = _workspace(args.workspace)
    pkg_path = Path(args.package)
    if not pkg_path.is_file():
        _die(f"package not found: {pkg_path}")

    package = json.loads(pkg_path.read_text(encoding="utf-8"))
    sk_path = Path(args.signing_key) if args.signing_key else ws / "keys" / "skill_ed25519.sk"

    if not sk_path.is_file():
        if args.generate_keys:
            sk, vk = generate_keypair()
            sk_path.parent.mkdir(parents=True, exist_ok=True)
            paths = save_keypair(sk_path.parent, sk, vk, name="skill_ed25519")
            sk_path = paths["signing_key"]
            _ok(f"generated keypair under {sk_path.parent}")
        else:
            _die(f"signing key not found: {sk_path} (use --generate-keys)")

    sk_hex = _read_key_hex(sk_path)
    signed = sign_package(package, sk_hex)
    out = Path(args.output) if args.output else pkg_path.with_suffix(".signed.json")
    out.write_text(json.dumps(signed, indent=2), encoding="utf-8")
    _ok(f"signed package → {out}")
    return 0


def cmd_ledger_verify(args: argparse.Namespace) -> int:
    from clean_room_ledger import CleanRoomLedger

    ws = _workspace(args.workspace)
    led = CleanRoomLedger(ws / "audit")
    report = led.verify_chain()
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 2


def cmd_memory_recall(args: argparse.Namespace) -> int:
    from clean_room_memory import EpisodicMemoryStore

    ws = _workspace(args.workspace)
    eng = _load_engine(ws)

    store = EpisodicMemoryStore(ws / "memory", engine=eng, tau=float(args.tau))
    if args.remember:
        eid = store.remember(args.query, meta={"source": "cli"})
        _ok(f"stored episode {eid}")
        return 0

    hits = store.recall(args.query, top_k=int(args.top_k))
    out = [
        {"episode_id": h.episode_id, "similarity": h.similarity, "meta": h.meta}
        for h in hits
    ]
    print(json.dumps(out, indent=2))
    return 0


def cmd_shacl_check(args: argparse.Namespace) -> int:
    from clean_room_shacl import ShapeEngine, LocalGraph, CONSTITUTIONAL_SHAPES

    shapes_path = Path(args.shapes) if args.shapes else None
    if shapes_path and shapes_path.is_file():
        engine = ShapeEngine.from_json_file(shapes_path)
    else:
        engine = ShapeEngine(CONSTITUTIONAL_SHAPES)

    data_path = Path(args.data)
    if not data_path.is_file():
        _die(f"data file not found: {data_path}")
    raw = json.loads(data_path.read_text(encoding="utf-8"))

    if "sovereignty" in raw or "vsa_bindings" in raw:
        from clean_room_shacl import skill_package_to_graph

        graph = skill_package_to_graph(raw)
        shape_id = args.shape_id or "SkillPackageSovereigntyShape"
    elif "@graph" in raw or "@id" in raw:
        graph = LocalGraph.from_json_ld_nodes(raw)
        shape_id = args.shape_id
    else:
        graph = LocalGraph.from_mapping(raw)
        shape_id = args.shape_id

    report = engine.validate_graph(graph, shape_id=shape_id)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.conforms else 2


def cmd_run(args: argparse.Namespace) -> int:
    from clean_room_vsa import CleanRoomGate
    from clean_room_model import LocalModelBridge, DeterministicLocalBackend, skill_handler_factory
    from clean_room_orchestrator import CleanRoomOrchestrator, PipelineStep

    ws = _workspace(args.workspace)
    pkg_path = Path(args.package)
    if not pkg_path.is_file():
        _die(f"package not found: {pkg_path}")
    package = json.loads(pkg_path.read_text(encoding="utf-8"))

    eng = _load_engine(ws)

    keys: List[str] = []
    keys_dir = ws / "keys"
    if keys_dir.is_dir():
        for p in keys_dir.glob("*.pub"):
            keys.append(_read_key_hex(p))
    if args.verify_key:
        keys.append(_read_key_hex(Path(args.verify_key)))

    gate = CleanRoomGate(
        eng,
        trusted_verify_keys=keys,
        require_skill_signature=not args.allow_unsigned,
        enable_shacl=not args.no_shacl,
    )

    if args.handler == "model":
        bridge = LocalModelBridge(backend=DeterministicLocalBackend())
        handler = skill_handler_factory(bridge)
    else:

        def handler(engine, gate, state, idx):
            return {"status": "PASS", "echo": state.get("note", "ok")}

    orch = CleanRoomOrchestrator(
        engine=eng,
        gate=gate,
        require_skill_signature=not args.allow_unsigned,
        fail_fast=True,
    )
    result = orch.run(
        [PipelineStep(package=package, handler=handler, name="cli_run")],
        initial_state={"note": args.note or "", "task": args.task or args.note or "cli"},
    )
    print(
        json.dumps(
            {"status": result.status, "error": result.error, "steps": result.steps},
            indent=2,
        )
    )
    twin = ws / "twin_state"
    if twin.parent.exists():
        eng.save(twin)
    return 0 if result.status == "PASS" else 2


def cmd_daemon_start(args: argparse.Namespace) -> int:
    from clean_room_daemon import CleanRoomDaemon, SovereignTask
    from clean_room_orchestrator import PipelineStep
    from clean_room_model import LocalModelBridge, DeterministicLocalBackend, skill_handler_factory

    ws = _workspace(args.workspace)
    keys: List[str] = []
    keys_dir = ws / "keys"
    if keys_dir.is_dir():
        for p in keys_dir.glob("*.pub"):
            keys.append(_read_key_hex(p))

    daemon = CleanRoomDaemon(
        ws,
        trusted_verify_keys=keys,
        require_skill_signature=not args.allow_unsigned,
        enable_memory=True,
    )

    packages: List[Dict[str, Any]] = []
    for p in args.package or []:
        path = Path(p)
        if not path.is_file():
            _die(f"package not found: {path}")
        packages.append(json.loads(path.read_text(encoding="utf-8")))

    if not packages:
        _die("daemon start requires at least one --package")

    bridge = LocalModelBridge(backend=DeterministicLocalBackend())
    handler = skill_handler_factory(bridge)
    steps = [
        PipelineStep(
            package=pkg,
            handler=handler,
            name=pkg.get("manifest", {}).get("skill_id", f"s{i}"),
        )
        for i, pkg in enumerate(packages)
    ]
    task = SovereignTask(
        task_id=args.task_id or "cli-daemon",
        description=args.description or "cli daemon run",
        steps=steps,
        initial_state={
            "task": args.task or "offline daemon cycle",
            "note": args.note or "",
        },
    )
    report = daemon.run_task(task, resume=not args.no_resume)
    print(
        json.dumps(
            {
                "status": report.status,
                "resumed": report.resumed,
                "steps_executed": report.steps_executed,
                "error": report.error,
                "ledger_tip": report.ledger_tip,
                "memory_episode_id": report.memory_episode_id,
            },
            indent=2,
        )
    )
    return 0 if report.status == "PASS" else 2


def cmd_dashboard_start(args: argparse.Namespace) -> int:
    from clean_room_dashboard import LoopbackDashboard, LOOPBACK

    ws = _workspace(args.workspace)
    host = args.host or LOOPBACK
    if host not in (LOOPBACK, "localhost"):
        _die(f"dashboard host must be loopback ({LOOPBACK}), got {host!r}")
    port = int(args.port)
    dash = LoopbackDashboard(ws, host=LOOPBACK, port=port)
    try:
        dash.start(blocking=True)
    except KeyboardInterrupt:
        dash.stop()
        _ok("dashboard stopped")
    return 0


def cmd_jkillnhide(args: argparse.Namespace) -> int:
    """Workspace integrity: baseline / check / enforce."""
    from clean_room_jkillnhide import JKillnHideWatchdog
    from clean_room_ledger import CleanRoomLedger

    ws = _workspace(args.workspace)
    eng = _load_engine(ws)
    ledger = CleanRoomLedger(ws / "audit")
    wd = JKillnHideWatchdog(
        workspace=ws,
        engine=eng,
        ledger=ledger,
        fail_closed_on_drift=not args.allow_drift,
    )

    action = args.jkill_cmd
    if action == "baseline":
        hashes = wd.write_baseline()
        print(
            json.dumps(
                {
                    "action": "baseline",
                    "file_count": len(hashes),
                    "path": str(wd.baseline_path),
                    "network_access": False,
                },
                indent=2,
            )
        )
        twin = ws / "twin_state"
        eng.save(twin)
        _ok(f"integrity baseline written ({len(hashes)} files)")
        return 0

    if action == "check":
        report = wd.scan(log=not args.no_log)
        print(json.dumps(report.to_dict(), indent=2))
        twin = ws / "twin_state"
        eng.save(twin)
        if report.status == "CLEAN":
            return 0
        if report.status == "MISSING_BASELINE":
            return 3
        return 2  # DRIFT

    if action == "enforce":
        decision = wd.enforce()
        print(json.dumps(decision, indent=2))
        twin = ws / "twin_state"
        eng.save(twin)
        return 0 if decision.get("allow_execution") else 2

    _die(f"unknown jkillnhide action: {action}")
    return 1


def cmd_physics(args: argparse.Namespace) -> int:
    """Ware/SPARC phenomenological curve evaluation (offline)."""
    from clean_room_physics import WarePhysicsBridge
    from clean_room_ledger import CleanRoomLedger

    ws = _workspace(args.workspace)
    eng = _load_engine(ws)
    ledger = CleanRoomLedger(ws / "audit")
    bridge = WarePhysicsBridge(workspace=ws, engine=eng, ledger=ledger)

    action = args.physics_cmd
    if action != "eval":
        _die(f"unknown physics action: {action}")

    csv_path = Path(args.csv) if args.csv else None
    if csv_path is not None and not csv_path.is_file():
        _die(f"CSV not found: {csv_path}")

    result = bridge.evaluate(
        galaxy_id=args.galaxy or "SAMPLE_A",
        n=float(args.n),
        kappa=float(args.kappa),
        csv_path=csv_path,
        log=not args.no_log,
    )
    print(json.dumps(result, indent=2))
    twin = ws / "twin_state"
    eng.save(twin)

    status = result.get("status")
    if status == "PASS":
        return 0
    if status == "INCONCLUSIVE":
        return 3
    return 2  # FAIL


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="clean_room_cli",
        description="Sovereign Clean-Room Control CLI (offline-only)",
    )
    p.add_argument(
        "--workspace", "-w", default="./sovereign_workspace", help="workspace root"
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="initialize workspace + jump-start")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("status", help="inspect engine, ledger, checkpoints, trust")
    s.add_argument("--strict", action="store_true", help="exit 2 on integrity failures")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("sign", help="Ed25519-sign a skill package")
    s.add_argument("--package", "-p", required=True)
    s.add_argument("--signing-key", default=None)
    s.add_argument("--output", "-o", default=None)
    s.add_argument("--generate-keys", action="store_true")
    s.set_defaults(func=cmd_sign)

    s = sub.add_parser("ledger", help="ledger operations")
    led = s.add_subparsers(dest="ledger_cmd", required=True)
    v = led.add_parser("verify", help="verify hash chain")
    v.set_defaults(func=cmd_ledger_verify)

    s = sub.add_parser("memory", help="episodic memory")
    s.add_argument("query", help="query text or content to store")
    s.add_argument("--remember", action="store_true", help="store instead of recall")
    s.add_argument("--top-k", type=int, default=5)
    s.add_argument("--tau", type=float, default=0.92)
    s.set_defaults(func=cmd_memory_recall)

    s = sub.add_parser("shacl", help="SHACL check")
    s.add_argument("--data", "-d", required=True, help="JSON package or node map")
    s.add_argument("--shapes", default=None)
    s.add_argument("--shape-id", default=None)
    s.set_defaults(func=cmd_shacl_check)

    s = sub.add_parser("run", help="run one signed skill package")
    s.add_argument("--package", "-p", required=True)
    s.add_argument("--handler", choices=("noop", "model"), default="noop")
    s.add_argument("--note", default="")
    s.add_argument("--task", default="")
    s.add_argument("--verify-key", default=None)
    s.add_argument("--allow-unsigned", action="store_true")
    s.add_argument("--no-shacl", action="store_true")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("daemon", help="daemon operations")
    dsub = s.add_subparsers(dest="daemon_cmd", required=True)
    st = dsub.add_parser("start", help="run offline task cycle")
    st.add_argument("--package", "-p", action="append", default=[])
    st.add_argument("--task-id", default="cli-daemon")
    st.add_argument("--description", default="")
    st.add_argument("--task", default="")
    st.add_argument("--note", default="")
    st.add_argument("--allow-unsigned", action="store_true")
    st.add_argument("--no-resume", action="store_true")
    st.set_defaults(func=cmd_daemon_start)

    s = sub.add_parser("dashboard", help="local loopback web dashboard")
    dash_sub = s.add_subparsers(dest="dashboard_cmd", required=True)
    ds = dash_sub.add_parser("start", help="serve UI on 127.0.0.1 only")
    ds.add_argument("--host", default="127.0.0.1", help="must be 127.0.0.1 or localhost")
    ds.add_argument("--port", type=int, default=8765)
    ds.set_defaults(func=cmd_dashboard_start)

    # --- JKillnHide ---
    s = sub.add_parser(
        "jkillnhide",
        help="workspace integrity watchdog (offline)",
    )
    jk = s.add_subparsers(dest="jkill_cmd", required=True)

    jb = jk.add_parser("baseline", help="write integrity baseline snapshot")
    jb.add_argument(
        "--allow-drift",
        action="store_true",
        help="(unused on baseline; reserved for policy consistency)",
    )
    jb.set_defaults(func=cmd_jkillnhide)

    jc = jk.add_parser("check", help="scan vs baseline (exit 2 on DRIFT)")
    jc.add_argument("--allow-drift", action="store_true")
    jc.add_argument("--no-log", action="store_true", help="skip ledger append")
    jc.set_defaults(func=cmd_jkillnhide)

    je = jk.add_parser("enforce", help="policy decision CONTINUE/FREEZE")
    je.add_argument(
        "--allow-drift",
        action="store_true",
        help="do not fail-closed on DRIFT",
    )
    je.set_defaults(func=cmd_jkillnhide)

    # --- Physics / Ware-SPARC ---
    s = sub.add_parser(
        "physics",
        help="Ware/SPARC phenomenological bridge (offline)",
    )
    ph = s.add_subparsers(dest="physics_cmd", required=True)
    pe = ph.add_parser("eval", help="evaluate sample or local CSV curve")
    pe.add_argument(
        "--galaxy",
        default="SAMPLE_A",
        help="bundled sample id (SAMPLE_A|SAMPLE_B)",
    )
    pe.add_argument("--csv", default=None, help="local SPARC-style CSV path")
    pe.add_argument("--n", type=float, default=3.0, help="recursion depth n")
    pe.add_argument("--kappa", type=float, default=25.0, help="phenomenological kappa")
    pe.add_argument("--no-log", action="store_true", help="skip ledger append")
    pe.set_defaults(func=cmd_physics)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    try:
        return int(args.func(args))
    except SystemExit:
        raise
    except Exception as e:
        _die(f"{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
