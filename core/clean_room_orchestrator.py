#!/usr/bin/env python3
"""
CleanRoomOrchestrator — multi-skill pipeline over a shared FHRR core.

Each step:
  1) Independent Ed25519 + sovereignty verification via CleanRoomGate
  2) Sandboxed execution
  3) Telemetry / state handoff to the next step (offline only)

Abort on first signature failure, network_access violation, or skill FAIL
when fail_fast=True (default).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from clean_room_vsa import CleanRoomGate, CleanRoomVSAEngine


@dataclass
class PipelineStep:
    """One gated skill in the pipeline."""

    package: Dict[str, Any]
    handler: Callable[..., Dict[str, Any]]
    """
    handler(engine, gate, pipeline_state, step_index) -> dict
    Must return a dict (skill output). May read/write pipeline_state.
    """
    name: Optional[str] = None


@dataclass
class PipelineResult:
    status: str  # PASS | FAIL
    steps: List[Dict[str, Any]] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    aborted_at: Optional[int] = None
    error: Optional[str] = None


class CleanRoomOrchestrator:
    """
    Sequences signed skill packages against one CleanRoomVSAEngine instance.

    Continuity: same engine (dim, codebook, Jump-Start atoms) across steps.
    Isolation: each skill still enters only through CleanRoomGate verification.
    """

    def __init__(
        self,
        engine: Optional[CleanRoomVSAEngine] = None,
        gate: Optional[CleanRoomGate] = None,
        trusted_verify_keys: Optional[Sequence[str]] = None,
        require_skill_signature: bool = True,
        fail_fast: bool = True,
        ensure_jump_start: bool = True,
        jump_start_seed: Optional[int] = 0x5345454D,
    ):
        self.engine = engine or CleanRoomVSAEngine(dim=8192)
        if self.engine.dim != 8192:
            raise ValueError("Orchestrator requires constitutional dim=8192")

        if gate is not None:
            self.gate = gate
            if trusted_verify_keys:
                for k in trusted_verify_keys:
                    self.gate.add_trusted_verify_key(k)
        else:
            self.gate = CleanRoomGate(
                self.engine,
                trusted_verify_keys=list(trusted_verify_keys or []),
                require_skill_signature=require_skill_signature,
            )

        self.fail_fast = fail_fast
        self.ensure_jump_start = ensure_jump_start
        self.jump_start_seed = jump_start_seed

    def _prepare_core(self) -> None:
        if self.ensure_jump_start and not self.engine.verify_jump_start_integrity():
            self.engine.jump_start_v01(seed=self.jump_start_seed)

    @staticmethod
    def load_package(path: Union[str, Path]) -> Dict[str, Any]:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def run(
        self,
        steps: Sequence[PipelineStep],
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Execute steps in order. pipeline_state is a shared offline dict:

          {
            "inputs": {...},          # caller-provided
            "last_output": {...},     # previous skill output
            "history": [ ... ],       # per-step summaries
            "telemetry": {...},       # free-form skill annotations
          }
        """
        self._prepare_core()
        state: Dict[str, Any] = {
            "inputs": dict(initial_state or {}),
            "last_output": None,
            "history": [],
            "telemetry": {},
        }
        # Allow caller to seed nested keys
        if initial_state:
            for k, v in initial_state.items():
                if k not in ("inputs", "last_output", "history", "telemetry"):
                    state[k] = v
            if "telemetry" in initial_state and isinstance(initial_state["telemetry"], dict):
                state["telemetry"] = dict(initial_state["telemetry"])

        results: List[Dict[str, Any]] = []

        for idx, step in enumerate(steps):
            skill_id = (
                step.name
                or step.package.get("manifest", {}).get("skill_id")
                or f"step_{idx}"
            )

            def _handler(
                _engine=self.engine,
                _gate=self.gate,
                _state=state,
                _idx=idx,
                _step=step,
            ):
                return _step.handler(_engine, _gate, _state, _idx)

            gate_result = self.gate.execute_skill_package(
                step.package,
                _handler,
            )

            step_record = {
                "index": idx,
                "skill_id": skill_id,
                "gate_status": gate_result["status"],
                "error": gate_result.get("error"),
                "output": gate_result.get("output"),
                "banel_evidence": gate_result.get("banel_evidence", 0.0),
            }
            results.append(step_record)
            state["history"].append({
                "index": idx,
                "skill_id": skill_id,
                "status": gate_result["status"],
            })

            if gate_result["status"] != "PASS":
                state["last_output"] = None
                if self.fail_fast:
                    return PipelineResult(
                        status="FAIL",
                        steps=results,
                        state=state,
                        aborted_at=idx,
                        error=gate_result.get("error") or f"step {idx} ({skill_id}) failed",
                    )
                continue

            # Secure local handoff: only the sanitized gate output enters state
            out = gate_result.get("output")
            if not isinstance(out, dict):
                out = {"data": out}
            state["last_output"] = out
            # Skills may also write to state["telemetry"] inside handler

        return PipelineResult(
            status="PASS",
            steps=results,
            state=state,
            aborted_at=None,
            error=None,
        )
