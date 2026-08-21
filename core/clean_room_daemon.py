#!/usr/bin/env python3
"""
Sovereign Agent Daemon — offline-first autonomous task loops.

Coordinates:
  CleanRoomOrchestrator  → multi-skill execution
  CleanRoomLedger        → hash-chained audit
  CheckpointStore        → crash-safe resume
  EpisodicMemoryStore    → long-term FHRR recall (optional)

On startup:
  1) verify ledger chain
  2) load latest valid checkpoint (if any)
  3) resume remaining steps or start fresh

Never opens network connections. Skills with network_access!=false are rejected
by the gate before execution.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from clean_room_vsa import CleanRoomVSAEngine, CleanRoomGate
from clean_room_orchestrator import CleanRoomOrchestrator, PipelineStep, PipelineResult
from clean_room_ledger import (
    CleanRoomLedger,
    CheckpointStore,
    PipelineCheckpoint,
)
from clean_room_memory import EpisodicMemoryStore


Handler = Callable[..., Dict[str, Any]]


@dataclass
class SovereignTask:
    """A multi-step offline task definition."""

    task_id: str
    steps: List[PipelineStep]
    initial_state: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    remember_on_pass: bool = True
    """If True, append a short episodic memory after successful completion."""


@dataclass
class DaemonRunReport:
    task_id: str
    pipeline_id: str
    status: str
    resumed: bool
    steps_executed: int
    aborted_at: Optional[int]
    error: Optional[str]
    ledger_tip: str
    checkpoint_path: Optional[str] = None
    memory_episode_id: Optional[str] = None


class CleanRoomDaemon:
    """
    Local autonomous agent loop.

    workspace/
      audit/       → CleanRoomLedger
      checkpoints/
      twin_state/  → optional engine persistence
      memory/      → EpisodicMemoryStore
    """

    def __init__(
        self,
        workspace: Union[str, Path],
        trusted_verify_keys: Optional[Sequence[str]] = None,
        engine: Optional[CleanRoomVSAEngine] = None,
        require_skill_signature: bool = True,
        persist_engine: bool = True,
        enable_memory: bool = True,
        memory_tau: float = 0.92,
    ):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.audit_dir = self.workspace / "audit"
        self.ckpt_dir = self.workspace / "checkpoints"
        self.twin_dir = self.workspace / "twin_state"
        self.memory_dir = self.workspace / "memory"

        self.ledger = CleanRoomLedger(self.audit_dir)
        self.checkpoints = CheckpointStore(self.ckpt_dir)

        self.engine = engine or CleanRoomVSAEngine(dim=8192)
        if self.engine.dim != 8192:
            raise ValueError("Daemon requires dim=8192")

        self.gate = CleanRoomGate(
            self.engine,
            trusted_verify_keys=list(trusted_verify_keys or []),
            require_skill_signature=require_skill_signature,
        )
        self.orchestrator = CleanRoomOrchestrator(
            engine=self.engine,
            gate=self.gate,
            require_skill_signature=require_skill_signature,
            fail_fast=True,
        )
        self.persist_engine = persist_engine
        self.require_skill_signature = require_skill_signature

        self.memory: Optional[EpisodicMemoryStore] = None
        if enable_memory:
            self.memory = EpisodicMemoryStore(
                self.memory_dir,
                engine=self.engine,
                tau=memory_tau,
            )

    def verify_audit_integrity(self) -> Dict[str, Any]:
        return self.ledger.verify_chain()

    def _engine_bootstrap(self) -> None:
        if self.persist_engine and self.twin_dir.exists():
            try:
                self.engine.load(self.twin_dir)
            except Exception:
                pass
        if not self.engine.verify_jump_start_integrity():
            self.engine.jump_start_v01()

    def _persist_engine(self) -> None:
        if self.persist_engine:
            self.engine.save(self.twin_dir)

    def _pipeline_id(self, task_id: str) -> str:
        return f"{task_id}"

    def _save_checkpoint(
        self,
        pipeline_id: str,
        next_index: int,
        status: str,
        state: Dict[str, Any],
        completed: List[Dict[str, Any]],
    ) -> Path:
        ckpt = PipelineCheckpoint(
            pipeline_id=pipeline_id,
            next_index=next_index,
            status=status,
            state=state,
            completed_steps=completed,
            ledger_tip=self.ledger.tip_hash,
            engine_state_dir=str(self.twin_dir) if self.persist_engine else None,
        )
        return self.checkpoints.save(ckpt)

    def _inject_memory_context(self, state: Dict[str, Any]) -> None:
        """Expose memory API handle + optional recall of task note into state."""
        if self.memory is None:
            return
        state["_memory_stats"] = self.memory.stats()
        note = None
        inputs = state.get("inputs") if isinstance(state.get("inputs"), dict) else {}
        note = state.get("note") or (inputs or {}).get("note")
        if isinstance(note, str) and note.strip():
            hits = self.memory.recall(note.strip(), top_k=3)
            state["memory_hits"] = [
                {
                    "episode_id": h.episode_id,
                    "similarity": h.similarity,
                    "meta": h.meta,
                }
                for h in hits
            ]

    def _remember_task(
        self,
        task: SovereignTask,
        result: PipelineResult,
    ) -> Optional[str]:
        if self.memory is None or not task.remember_on_pass:
            return None
        if result.status != "PASS":
            return None
        summary = (
            f"task={task.task_id}|desc={task.description}|"
            f"telemetry={result.state.get('telemetry', {})}"
        )
        eid = self.memory.remember(
            summary,
            meta={
                "task_id": task.task_id,
                "status": result.status,
            },
        )
        self.ledger.append(
            "memory_append",
            {"task_id": task.task_id, "episode_id": eid},
        )
        return eid

    def run_task(
        self,
        task: SovereignTask,
        resume: bool = True,
    ) -> DaemonRunReport:
        """
        Execute or resume a sovereign task offline.

        Skills may read state['memory_hits'] for historical context and the
        daemon may append episodic memory on PASS.
        """
        chain = self.verify_audit_integrity()
        if not chain["ok"] and chain["entries"] > 0:
            raise RuntimeError(f"ledger integrity failure: {chain['error']}")

        self._engine_bootstrap()
        pipeline_id = self._pipeline_id(task.task_id)
        resumed = False
        start_index = 0
        state: Dict[str, Any] = dict(task.initial_state or {})
        completed: List[Dict[str, Any]] = []

        if resume and self.checkpoints.exists(pipeline_id):
            try:
                ckpt = self.checkpoints.load(pipeline_id, verify=True)
                if ckpt.status in ("PASS", "COMPLETED"):
                    return DaemonRunReport(
                        task_id=task.task_id,
                        pipeline_id=pipeline_id,
                        status=ckpt.status,
                        resumed=True,
                        steps_executed=0,
                        aborted_at=None,
                        error=None,
                        ledger_tip=self.ledger.tip_hash,
                        checkpoint_path=str(self.checkpoints._path(pipeline_id)),
                    )
                if ckpt.status in ("RUNNING", "FAIL", "ABORTED") and ckpt.next_index < len(
                    task.steps
                ):
                    if ckpt.status == "RUNNING" or (
                        ckpt.status == "FAIL" and ckpt.next_index > 0
                    ):
                        start_index = ckpt.next_index
                        state = dict(ckpt.state or {})
                        completed = list(ckpt.completed_steps or [])
                        resumed = True
            except ValueError as e:
                self.ledger.append(
                    "checkpoint_reject",
                    {"pipeline_id": pipeline_id, "error": str(e)},
                )
                raise RuntimeError(f"checkpoint integrity failure: {e}") from e

        remaining = list(task.steps[start_index:])
        if not remaining and completed:
            return DaemonRunReport(
                task_id=task.task_id,
                pipeline_id=pipeline_id,
                status="PASS",
                resumed=resumed,
                steps_executed=0,
                aborted_at=None,
                error=None,
                ledger_tip=self.ledger.tip_hash,
            )

        self._inject_memory_context(state)

        if not resumed:
            self.ledger.record_pipeline_start(
                pipeline_id,
                step_count=len(task.steps),
                meta={"task_id": task.task_id, "description": task.description},
            )
            self._save_checkpoint(pipeline_id, 0, "RUNNING", state, completed)

        self.ledger.append(
            "daemon_cycle",
            {
                "pipeline_id": pipeline_id,
                "resumed": resumed,
                "start_index": start_index,
                "remaining": len(remaining),
                "memory_hits": len(state.get("memory_hits") or []),
            },
        )

        result: PipelineResult = self.orchestrator.run(remaining, initial_state=state)

        abs_steps: List[Dict[str, Any]] = []
        for rec in result.steps:
            abs_rec = dict(rec)
            abs_rec["index"] = start_index + int(rec["index"])
            abs_steps.append(abs_rec)
            sig_ok = rec["gate_status"] == "PASS"
            self.ledger.record_step(
                pipeline_id,
                abs_rec["index"],
                rec["skill_id"],
                rec["gate_status"],
                signature_ok=sig_ok,
                error=rec.get("error"),
                output_summary={
                    "keys": list(rec["output"].keys())
                    if isinstance(rec.get("output"), dict)
                    else {}
                },
                telemetry_snapshot=dict(result.state.get("telemetry") or {}),
            )

        completed.extend(abs_steps)
        merged_state = result.state
        mem_id: Optional[str] = None

        if result.status == "PASS":
            mem_id = self._remember_task(task, result)
            self.ledger.record_pipeline_end(pipeline_id, "PASS")
            path = self._save_checkpoint(
                pipeline_id, len(task.steps), "PASS", merged_state, completed
            )
            self._persist_engine()
            return DaemonRunReport(
                task_id=task.task_id,
                pipeline_id=pipeline_id,
                status="PASS",
                resumed=resumed,
                steps_executed=len(result.steps),
                aborted_at=None,
                error=None,
                ledger_tip=self.ledger.tip_hash,
                checkpoint_path=str(path),
                memory_episode_id=mem_id,
            )

        abs_abort = (
            start_index + result.aborted_at
            if result.aborted_at is not None
            else start_index
        )
        self.ledger.record_pipeline_end(
            pipeline_id, "FAIL", aborted_at=abs_abort, error=result.error
        )
        path = self._save_checkpoint(
            pipeline_id,
            abs_abort,
            "FAIL",
            merged_state,
            completed,
        )
        self._persist_engine()
        return DaemonRunReport(
            task_id=task.task_id,
            pipeline_id=pipeline_id,
            status="FAIL",
            resumed=resumed,
            steps_executed=len(result.steps),
            aborted_at=abs_abort,
            error=result.error,
            ledger_tip=self.ledger.tip_hash,
            checkpoint_path=str(path),
            memory_episode_id=None,
        )

    def run_forever(
        self,
        tasks: Sequence[SovereignTask],
        idle_sleep_s: float = 0.0,
        max_cycles: Optional[int] = 1,
    ) -> List[DaemonRunReport]:
        reports: List[DaemonRunReport] = []
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            for task in tasks:
                reports.append(self.run_task(task, resume=True))
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            if idle_sleep_s > 0:
                time.sleep(idle_sleep_s)
        return reports
