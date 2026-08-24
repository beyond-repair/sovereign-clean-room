#!/usr/bin/env python3
"""
JKillnHide — Active System Defense & State Enforcement Watchdog

Offline host/workspace security adapter for the Sovereign Clean-Room stack.

Capabilities (local only, network_access=false):
  - File integrity hashing over sovereign workspace paths
  - Baseline snapshot + anomaly detection
  - Process snapshot of local host (read-only)
  - Map telemetry into FHRR (dim=8192)
  - SHACL evaluation of security event graphs
  - Append-only ledger trail + optional daemon hooks

Remediation is limited to fail-closed policy decisions inside the workspace
(e.g. refuse skill runs, freeze daemon cycle). This module does not perform
remote actions, privilege escalation, or cross-host interference.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Union

import numpy as np

from clean_room_vsa import CleanRoomVSAEngine
from clean_room_ledger import CleanRoomLedger
from clean_room_shacl import LocalGraph, ShapeEngine, ValidationReport

# Paths watched relative to workspace (constitutional surface)
DEFAULT_WATCH_GLOBS = (
    "twin_state/**/*",
    "keys/*.pub",
    "keys/*.sk",
    "skills/**/*.json",
    "workspace.json",
    # audit/ is self-modifying (ledger appends) — never watch tip.json
    "ipc/**/*",
)

SECURITY_SHAPES: Dict[str, Any] = {
    "shapes": [
        {
            "id": "SecurityEventShape",
            "targetClass": "seem:SecurityEvent",
            "closed": False,
            "properties": [
                {
                    "path": "seem:severity",
                    "minCount": 1,
                    "in": ["INFO", "WARN", "CRIT"],
                },
                {
                    "path": "seem:network_access",
                    "minCount": 1,
                    "hasValue": False,
                },
                {
                    "path": "seem:anomaly",
                    "datatype": "boolean",
                    "minCount": 1,
                },
            ],
        },
        {
            "id": "IntegrityBaselineShape",
            "targetClass": "seem:IntegrityReport",
            "closed": False,
            "properties": [
                {
                    "path": "seem:status",
                    "minCount": 1,
                    "in": ["CLEAN", "DRIFT", "MISSING_BASELINE"],
                },
                {
                    "path": "seem:network_access",
                    "hasValue": False,
                    "minCount": 1,
                },
            ],
        },
    ]
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _expand_watches(workspace: Path, patterns: Sequence[str]) -> List[Path]:
    files: List[Path] = []
    seen: Set[str] = set()
    for pat in patterns:
        for p in workspace.glob(pat):
            if p.is_file():
                key = str(p.resolve())
                if key not in seen:
                    seen.add(key)
                    files.append(p)
    return sorted(files, key=lambda x: str(x))


@dataclass
class IntegrityDelta:
    path: str
    kind: str  # added | removed | modified
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None


@dataclass
class DefenseReport:
    status: str  # CLEAN | DRIFT | MISSING_BASELINE
    anomaly: bool
    severity: str  # INFO | WARN | CRIT
    deltas: List[IntegrityDelta] = field(default_factory=list)
    process_count: int = 0
    fhrr_vector_registered: bool = False
    shacl_conforms: bool = True
    ledger_seq: Optional[int] = None
    network_access: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "anomaly": self.anomaly,
            "severity": self.severity,
            "deltas": [
                {
                    "path": d.path,
                    "kind": d.kind,
                    "old_hash": d.old_hash,
                    "new_hash": d.new_hash,
                }
                for d in self.deltas
            ],
            "process_count": self.process_count,
            "fhrr_vector_registered": self.fhrr_vector_registered,
            "shacl_conforms": self.shacl_conforms,
            "ledger_seq": self.ledger_seq,
            "network_access": False,
        }


class JKillnHideWatchdog:
    """
    Local offline defense watchdog.

    baseline stored at: workspace/defense/baseline.json
    """

    def __init__(
        self,
        workspace: Union[str, Path],
        engine: Optional[CleanRoomVSAEngine] = None,
        ledger: Optional[CleanRoomLedger] = None,
        watch_globs: Optional[Sequence[str]] = None,
        fail_closed_on_drift: bool = True,
    ):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.defense_dir = self.workspace / "defense"
        self.defense_dir.mkdir(exist_ok=True)
        self.baseline_path = self.defense_dir / "baseline.json"
        self.watch_globs = list(watch_globs or DEFAULT_WATCH_GLOBS)
        self.fail_closed_on_drift = fail_closed_on_drift

        self.engine = engine or CleanRoomVSAEngine(dim=8192)
        if self.engine.dim != 8192:
            raise ValueError("JKillnHide requires dim=8192")
        if not self.engine.verify_jump_start_integrity():
            self.engine.jump_start_v01()

        self.ledger = ledger or CleanRoomLedger(self.workspace / "audit")
        self.shapes = ShapeEngine(SECURITY_SHAPES)

        # Defense vocabulary in FHRR space
        for name in (
            "DEFENSE_CLEAN",
            "DEFENSE_DRIFT",
            "DEFENSE_CRIT",
            "JKILLNHIDE",
        ):
            if name not in self.engine.codebook:
                self.engine.register(name, pinned=True)

    def snapshot_file_hashes(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for path in _expand_watches(self.workspace, self.watch_globs):
            try:
                rel = str(path.relative_to(self.workspace))
            except ValueError:
                rel = str(path)
            try:
                result[rel] = _sha256_file(path)
            except OSError:
                continue
        return result

    def snapshot_processes(self, limit: int = 64) -> List[Dict[str, Any]]:
        """Best-effort local process list (Linux /proc; empty if unavailable)."""
        procs: List[Dict[str, Any]] = []
        proc = Path("/proc")
        if not proc.is_dir():
            return procs
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                cmd = (entry / "comm").read_text(encoding="utf-8", errors="ignore").strip()
                procs.append({"pid": int(entry.name), "comm": cmd})
            except (OSError, ValueError):
                continue
            if len(procs) >= limit:
                break
        return procs

    def write_baseline(self) -> Dict[str, str]:
        hashes = self.snapshot_file_hashes()
        payload = {
            "version": "jkillnhide_baseline_v1",
            "created_at": time.time(),
            "network_access": False,
            "files": hashes,
        }
        tmp = self.baseline_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.baseline_path)
        self.ledger.append("defense_baseline", {"file_count": len(hashes)})
        return hashes

    def load_baseline(self) -> Optional[Dict[str, str]]:
        if not self.baseline_path.is_file():
            return None
        data = json.loads(self.baseline_path.read_text(encoding="utf-8"))
        files = data.get("files") or {}
        return {str(k): str(v) for k, v in files.items()}

    def diff_integrity(self) -> tuple[str, List[IntegrityDelta]]:
        baseline = self.load_baseline()
        current = self.snapshot_file_hashes()
        if baseline is None:
            return "MISSING_BASELINE", []

        deltas: List[IntegrityDelta] = []
        base_keys = set(baseline)
        cur_keys = set(current)
        for p in sorted(base_keys - cur_keys):
            deltas.append(IntegrityDelta(path=p, kind="removed", old_hash=baseline[p]))
        for p in sorted(cur_keys - base_keys):
            deltas.append(IntegrityDelta(path=p, kind="added", new_hash=current[p]))
        for p in sorted(base_keys & cur_keys):
            if baseline[p] != current[p]:
                deltas.append(
                    IntegrityDelta(
                        path=p,
                        kind="modified",
                        old_hash=baseline[p],
                        new_hash=current[p],
                    )
                )
        status = "CLEAN" if not deltas else "DRIFT"
        return status, deltas

    def encode_report_vector(self, status: str, severity: str) -> np.ndarray:
        flag = {
            "CLEAN": "DEFENSE_CLEAN",
            "DRIFT": "DEFENSE_DRIFT",
            "MISSING_BASELINE": "DEFENSE_DRIFT",
        }.get(status, "DEFENSE_DRIFT")
        if severity == "CRIT":
            flag = "DEFENSE_CRIT"
        role = self.engine.codebook["JKILLNHIDE"]
        filler = self.engine.codebook[flag]
        return self.engine.bind(role, filler)

    def register_defense_atom(self, status: str, severity: str) -> str:
        """Encode defense status in-memory only.

        Do not register timestamped codebook atoms: that would mutate twin_state
        on every check and false-trigger integrity drift against a baseline.
        """
        _ = self.encode_report_vector(status, severity)
        return f"DEFENSE_EVENT::{int(time.time())}"

    def shacl_security_event(
        self, severity: str, anomaly: bool
    ) -> ValidationReport:
        g = LocalGraph()
        g.add("evt:1", "rdf:type", "seem:SecurityEvent")
        g.add("evt:1", "seem:severity", severity)
        g.add("evt:1", "seem:network_access", False)
        g.add("evt:1", "seem:anomaly", bool(anomaly))
        return self.shapes.validate_graph(g, shape_id="SecurityEventShape")

    def shacl_integrity_report(self, status: str) -> ValidationReport:
        g = LocalGraph()
        g.add("rep:1", "rdf:type", "seem:IntegrityReport")
        g.add("rep:1", "seem:status", status)
        g.add("rep:1", "seem:network_access", False)
        return self.shapes.validate_graph(g, shape_id="IntegrityBaselineShape")

    def scan(self, log: bool = True) -> DefenseReport:
        status, deltas = self.diff_integrity()
        procs = self.snapshot_processes()
        anomaly = status == "DRIFT" or (
            status == "MISSING_BASELINE" and self.fail_closed_on_drift
        )
        if status == "CLEAN":
            severity = "INFO"
        elif status == "MISSING_BASELINE":
            severity = "WARN"
        else:
            crit_paths = any(
                d.path.startswith("keys/") or d.path.startswith("twin_state/")
                for d in deltas
            )
            severity = "CRIT" if crit_paths else "WARN"

        atom = self.register_defense_atom(status, severity)
        se = self.shacl_security_event(severity, anomaly)
        ir = self.shacl_integrity_report(status)
        shacl_ok = se.conforms and ir.conforms

        report = DefenseReport(
            status=status,
            anomaly=anomaly,
            severity=severity,
            deltas=deltas,
            process_count=len(procs),
            fhrr_vector_registered=True,
            shacl_conforms=shacl_ok,
        )

        if log:
            entry = self.ledger.append(
                "jkillnhide_scan",
                {
                    **report.to_dict(),
                    "atom": atom,
                    "process_sample": procs[:8],
                },
            )
            report.ledger_seq = entry.seq

        return report

    def enforce(self, report: Optional[DefenseReport] = None) -> Dict[str, Any]:
        """
        Policy decision for daemon/gate integration.

        Returns:
          allow_execution: bool
          action: CONTINUE | FREEZE | REQUIRE_BASELINE
        """
        report = report or self.scan(log=True)
        if report.status == "MISSING_BASELINE":
            action = "REQUIRE_BASELINE"
            allow = not self.fail_closed_on_drift
        elif report.status == "DRIFT":
            action = "FREEZE" if self.fail_closed_on_drift else "CONTINUE"
            allow = not self.fail_closed_on_drift
        else:
            action = "CONTINUE"
            allow = True

        decision = {
            "allow_execution": allow,
            "action": action,
            "severity": report.severity,
            "status": report.status,
            "network_access": False,
            "report": report.to_dict(),
        }
        self.ledger.append("jkillnhide_enforce", decision)
        return decision


def attach_watchdog_to_daemon(daemon: Any, fail_closed_on_drift: bool = True) -> JKillnHideWatchdog:
    """
    Attach watchdog to CleanRoomDaemon instance.
    Monkey-patches run_task to enforce integrity before cycles.
    """
    wd = JKillnHideWatchdog(
        workspace=daemon.workspace,
        engine=daemon.engine,
        ledger=daemon.ledger,
        fail_closed_on_drift=fail_closed_on_drift,
    )
    daemon.jkillnhide = wd  # type: ignore[attr-defined]

    original = daemon.run_task

    def guarded_run_task(task, resume: bool = True):
        decision = wd.enforce()
        if not decision["allow_execution"]:
            from clean_room_daemon import DaemonRunReport

            return DaemonRunReport(
                task_id=getattr(task, "task_id", "unknown"),
                pipeline_id=getattr(task, "task_id", "unknown"),
                status="FAIL",
                resumed=False,
                steps_executed=0,
                aborted_at=0,
                error=f"JKillnHide FREEZE: {decision['action']} ({decision['status']})",
                ledger_tip=daemon.ledger.tip_hash,
            )
        return original(task, resume=resume)

    daemon.run_task = guarded_run_task  # type: ignore[method-assign]
    return wd
