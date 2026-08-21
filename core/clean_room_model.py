#!/usr/bin/env python3
"""
Sovereign Local Model Bridge & Inference Router — offline-only.

- Talks only to local runtimes (in-process mock, llama.cpp CLI, or 127.0.0.1 HTTP)
- Builds structured prompts from EpisodicMemory hits + SHACL reports
- Validates model outputs against constitutional shapes before returning
- network_access: false — non-loopback hosts are rejected
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Union
from urllib.parse import urlparse

from clean_room_shacl import (
    ConstitutionalValidator,
    LocalGraph,
    ShapeEngine,
    ValidationReport,
)


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def assert_loopback_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in LOOPBACK_HOSTS:
        raise PermissionError(
            f"non-local model endpoint forbidden (host={host!r}); network_access=false"
        )
    if parsed.scheme not in ("http", "https"):
        raise PermissionError(f"unsupported scheme: {parsed.scheme}")


@dataclass
class InferenceRequest:
    prompt: str
    system: str = ""
    max_tokens: int = 256
    temperature: float = 0.0
    stop: Optional[List[str]] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InferenceResult:
    text: str
    backend: str
    offline: bool = True
    raw: Optional[Dict[str, Any]] = None


class LocalInferenceBackend(Protocol):
    name: str

    def generate(self, request: InferenceRequest) -> InferenceResult:
        ...


class DeterministicLocalBackend:
    """
    Fully offline, no subprocess/socket — used for tests and dry-runs.
    Echoes a structured completion derived from the prompt.
    """

    name = "deterministic_local"

    def generate(self, request: InferenceRequest) -> InferenceResult:
        # Extract last user line for a stable echo
        lines = [ln.strip() for ln in request.prompt.splitlines() if ln.strip()]
        seed = lines[-1] if lines else ""
        text = (
            "STATUS: PASS\n"
            f"SUMMARY: local-offline completion for: {seed[:180]}\n"
            "CONSTRAINT: network_access=false\n"
        )
        return InferenceResult(text=text, backend=self.name, offline=True, raw={"echo": seed})


class LlamaCppCliBackend:
    """
    Offline llama.cpp-style CLI invocation.
    Example: ./llama-cli -m model.gguf -p PROMPT -n N
    """

    name = "llama_cpp_cli"

    def __init__(
        self,
        binary: Union[str, Path],
        model_path: Union[str, Path],
        extra_args: Optional[Sequence[str]] = None,
    ):
        self.binary = Path(binary)
        self.model_path = Path(model_path)
        self.extra_args = list(extra_args or [])
        if not self.binary.exists():
            raise FileNotFoundError(f"llama binary not found: {self.binary}")
        if not self.model_path.exists():
            raise FileNotFoundError(f"model weights not found: {self.model_path}")

    def generate(self, request: InferenceRequest) -> InferenceResult:
        cmd = [
            str(self.binary),
            "-m",
            str(self.model_path),
            "-p",
            request.prompt,
            "-n",
            str(int(request.max_tokens)),
            "--temp",
            str(float(request.temperature)),
        ] + self.extra_args
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"llama.cpp CLI failed ({proc.returncode}): {proc.stderr[:500]}"
            )
        return InferenceResult(
            text=proc.stdout.strip(),
            backend=self.name,
            offline=True,
            raw={"returncode": proc.returncode},
        )


class LocalHttpBackend:
    """
    HTTP to a *loopback-only* OpenAI-compatible or llama.cpp server.
    Rejects any non-127.0.0.1 / localhost host.
    """

    name = "local_http"

    def __init__(self, base_url: str = "http://127.0.0.1:8080", path: str = "/completion"):
        assert_loopback_url(base_url)
        self.base_url = base_url.rstrip("/")
        self.path = path if path.startswith("/") else f"/{path}"

    def generate(self, request: InferenceRequest) -> InferenceResult:
        url = f"{self.base_url}{self.path}"
        assert_loopback_url(url)
        body = {
            "prompt": request.prompt,
            "n_predict": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stop:
            body["stop"] = request.stop
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(f"local model endpoint unreachable: {e}") from e

        text = (
            payload.get("content")
            or payload.get("completion")
            or (payload.get("choices") or [{}])[0].get("text")
            or ""
        )
        return InferenceResult(
            text=str(text).strip(),
            backend=self.name,
            offline=True,
            raw=payload if isinstance(payload, dict) else None,
        )


class ContextInjector:
    """Translate memory hits + SHACL reports into structured prompt context."""

    SYSTEM_DEFAULT = (
        "You are a sovereign offline assistant. "
        "Never request network access. "
        "Obey SHACL constraint summaries. "
        "Respond with STATUS: PASS or STATUS: FAIL on the first line."
    )

    def build(
        self,
        user_task: str,
        memory_hits: Optional[Sequence[Dict[str, Any]]] = None,
        shacl_report: Optional[Union[ValidationReport, Dict[str, Any]]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> InferenceRequest:
        sections: List[str] = []
        sections.append("## Task")
        sections.append(user_task.strip())

        sections.append("\n## Episodic Memory Hits")
        if memory_hits:
            for i, hit in enumerate(memory_hits):
                sections.append(
                    f"- [{i}] id={hit.get('episode_id')} "
                    f"sim={hit.get('similarity', 0):.4f} "
                    f"meta={json.dumps(hit.get('meta') or {}, sort_keys=True)}"
                )
        else:
            sections.append("- (none)")

        sections.append("\n## SHACL Validation")
        if shacl_report is None:
            sections.append("- (none)")
        else:
            rep = (
                shacl_report.to_dict()
                if isinstance(shacl_report, ValidationReport)
                else dict(shacl_report)
            )
            sections.append(f"- conforms: {rep.get('conforms')}")
            sections.append(f"- shape_id: {rep.get('shape_id')}")
            for v in rep.get("violations") or []:
                sections.append(
                    f"  - violation path={v.get('path')} msg={v.get('message')}"
                )

        if extra:
            sections.append("\n## Extra")
            sections.append(json.dumps(extra, sort_keys=True, indent=2))

        sections.append("\n## Response Contract")
        sections.append("First line: STATUS: PASS|FAIL")
        sections.append("Then a short SUMMARY line.")

        prompt = "\n".join(sections)
        return InferenceRequest(
            prompt=prompt,
            system=self.SYSTEM_DEFAULT,
            max_tokens=256,
            temperature=0.0,
            meta={"offline": True, "network_access": False},
        )


# Output shape: model response envelope
MODEL_OUTPUT_SHAPES = {
    "shapes": [
        {
            "id": "LocalModelOutputShape",
            "targetClass": "seem:LocalModelOutput",
            "closed": False,
            "properties": [
                {
                    "path": "seem:status",
                    "minCount": 1,
                    "maxCount": 1,
                    "in": ["PASS", "FAIL"],
                },
                {"path": "seem:backend", "minCount": 1, "datatype": "string"},
                {
                    "path": "seem:network_access",
                    "minCount": 1,
                    "hasValue": False,
                },
            ],
        }
    ]
}


def parse_status_line(text: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^\s*STATUS:\s*(PASS|FAIL)\s*$", line.strip(), re.I)
        if m:
            return m.group(1).upper()
    # soft fallback: presence of PASS/FAIL tokens
    if re.search(r"\bFAIL\b", text, re.I):
        return "FAIL"
    if re.search(r"\bPASS\b", text, re.I):
        return "PASS"
    return "FAIL"  # fail closed


def model_output_graph(status: str, backend: str) -> LocalGraph:
    g = LocalGraph()
    g.add("out:self", "rdf:type", "seem:LocalModelOutput")
    g.add("out:self", "seem:status", status)
    g.add("out:self", "seem:backend", backend)
    g.add("out:self", "seem:network_access", False)
    return g


class LocalModelBridge:
    """
    Routes local inference with memory/SHACL context and output constraints.
    """

    def __init__(
        self,
        backend: Optional[LocalInferenceBackend] = None,
        injector: Optional[ContextInjector] = None,
        validate_outputs: bool = True,
    ):
        self.backend: LocalInferenceBackend = backend or DeterministicLocalBackend()
        self.injector = injector or ContextInjector()
        self.validate_outputs = validate_outputs
        self.output_shapes = ShapeEngine(MODEL_OUTPUT_SHAPES)

    def reason(
        self,
        user_task: str,
        memory_hits: Optional[Sequence[Dict[str, Any]]] = None,
        shacl_report: Optional[Union[ValidationReport, Dict[str, Any]]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        req = self.injector.build(
            user_task=user_task,
            memory_hits=memory_hits,
            shacl_report=shacl_report,
            extra=extra,
        )
        # Prepend system into prompt for backends without a separate system channel
        full = f"System:\n{req.system}\n\n{req.prompt}"
        req.prompt = full

        result = self.backend.generate(req)
        if not result.offline:
            raise PermissionError("backend reported non-offline inference")

        status = parse_status_line(result.text)
        envelope = {
            "status": status,
            "text": result.text,
            "backend": result.backend,
            "network_access": False,
            "offline": True,
        }

        if self.validate_outputs:
            report = self.output_shapes.validate_graph(
                model_output_graph(status, result.backend),
                shape_id="LocalModelOutputShape",
            )
            envelope["shacl_conforms"] = report.conforms
            if not report.conforms:
                envelope["status"] = "FAIL"
                envelope["shacl_violations"] = [v.message for v in report.violations]
        return envelope


def skill_handler_factory(bridge: LocalModelBridge):
    """
    Build an orchestrator handler that uses LocalModelBridge.
    Reads state memory_hits / shacl_report / inputs.task.
    """

    def handler(engine, gate, state, idx):
        task = (
            state.get("task")
            or (state.get("inputs") or {}).get("task")
            or state.get("note")
            or "offline reason"
        )
        hits = state.get("memory_hits") or []
        shacl = state.get("shacl_report")
        out = bridge.reason(str(task), memory_hits=hits, shacl_report=shacl)
        state.setdefault("telemetry", {})["model_status"] = out.get("status")
        state["telemetry"]["model_backend"] = out.get("backend")
        return out

    return handler
