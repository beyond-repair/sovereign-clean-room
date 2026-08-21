#!/usr/bin/env python3
"""
SHACL Neuro-Symbolic Constraint Engine — offline structural validation.

- Python-native / JSON shape graphs (no network, no external triplestore)
- Optional minimal JSON-LD node maps
- Validation reports mapped into FHRR (dim=8192) for vector-symbolic query
- Hooks for CleanRoomGate / CleanRoomDaemon pre/post checks

This is a sovereign SHACL *subset*: NodeShape + property constraints
(minCount, maxCount, datatype, in, pattern, closed, hasValue).
Full W3C SHACL coverage is not claimed.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from clean_room_vsa import CleanRoomVSAEngine


@dataclass
class ConstraintViolation:
    focus_node: str
    shape_id: str
    path: Optional[str]
    message: str
    severity: str = "Violation"


@dataclass
class ValidationReport:
    conforms: bool
    shape_id: str
    violations: List[ConstraintViolation] = field(default_factory=list)
    focus_nodes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conforms": self.conforms,
            "shape_id": self.shape_id,
            "focus_nodes": self.focus_nodes,
            "violations": [
                {
                    "focus_node": v.focus_node,
                    "shape_id": v.shape_id,
                    "path": v.path,
                    "message": v.message,
                    "severity": v.severity,
                }
                for v in self.violations
            ],
        }


class LocalGraph:
    """Simple property graph: node_id -> {predicate: [values]}."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Dict[str, List[Any]]] = {}

    def add(self, s: str, p: str, o: Any) -> None:
        self.nodes.setdefault(s, {}).setdefault(p, []).append(o)

    def get(self, s: str, p: str) -> List[Any]:
        return list(self.nodes.get(s, {}).get(p, []))

    def subjects(self) -> List[str]:
        return list(self.nodes.keys())

    @classmethod
    def from_mapping(cls, data: Dict[str, Dict[str, Any]]) -> "LocalGraph":
        """
        data = {
          "node1": {"rdf:type": "ex:Skill", "ex:status": "PASS"},
          ...
        }
        Values may be scalars or lists.
        """
        g = cls()
        for s, props in data.items():
            for p, o in props.items():
                if isinstance(o, list):
                    for item in o:
                        g.add(s, p, item)
                else:
                    g.add(s, p, o)
        return g

    @classmethod
    def from_json_ld_nodes(cls, doc: Dict[str, Any]) -> "LocalGraph":
        """Minimal JSON-LD: {"@graph": [{
@id": ..., ...}]} or single node."""
        g = cls()
        nodes = doc.get("@graph")
        if nodes is None:
            nodes = [doc]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            sid = str(node.get("@id") or node.get("id") or f"_:n{len(g.nodes)}")
            for k, v in node.items():
                if k in ("@id", "id"):
                    continue
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and "@id" in item:
                            g.add(sid, k, item["@id"])
                        else:
                            g.add(sid, k, item)
                elif isinstance(v, dict) and "@id" in v:
                    g.add(sid, k, v["@id"])
                else:
                    g.add(sid, k, v)
        return g


def _as_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


class ShapeEngine:
    """
    Offline SHACL-subset validator.

    Shape document (JSON):
    {
      "shapes": [
        {
          "id": "SkillOutputShape",
          "targetClass": "ex:SkillResult",
          "closed": false,
          "properties": [
            {"path": "ex:status", "minCount": 1, "maxCount": 1, "in": ["PASS", "FAIL"]},
            {"path": "ex:invertibility", "datatype": "float", "minCount": 0}
          ]
        }
      ]
    }
    """

    def __init__(self, shapes_doc: Optional[Dict[str, Any]] = None):
        self.shapes: List[Dict[str, Any]] = list((shapes_doc or {}).get("shapes") or [])

    @classmethod
    def from_json_file(cls, path: Union[str, Path]) -> "ShapeEngine":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(doc)

    @classmethod
    def from_python(cls, shapes: Sequence[Dict[str, Any]]) -> "ShapeEngine":
        return cls({"shapes": list(shapes)})

    def add_shape(self, shape: Dict[str, Any]) -> None:
        self.shapes.append(shape)

    def validate_graph(
        self,
        graph: LocalGraph,
        shape_id: Optional[str] = None,
    ) -> ValidationReport:
        shapes = self.shapes
        if shape_id:
            shapes = [s for s in self.shapes if s.get("id") == shape_id]
            if not shapes:
                return ValidationReport(
                    conforms=False,
                    shape_id=shape_id or "",
                    violations=[
                        ConstraintViolation(
                            focus_node="",
                            shape_id=shape_id or "",
                            path=None,
                            message=f"unknown shape_id: {shape_id}",
                        )
                    ],
                )

        all_violations: List[ConstraintViolation] = []
        focus_all: List[str] = []
        used_ids: List[str] = []

        for shape in shapes:
            sid = str(shape.get("id", "anon"))
            used_ids.append(sid)
            targets = self._targets(graph, shape)
            focus_all.extend(targets)
            for node in targets:
                all_violations.extend(self._validate_node(graph, node, shape))

        report_id = shape_id or ",".join(used_ids) or "all"
        return ValidationReport(
            conforms=len(all_violations) == 0,
            shape_id=report_id,
            violations=all_violations,
            focus_nodes=sorted(set(focus_all)),
        )

    def validate_mapping(
        self,
        data: Dict[str, Dict[str, Any]],
        shape_id: Optional[str] = None,
    ) -> ValidationReport:
        return self.validate_graph(LocalGraph.from_mapping(data), shape_id=shape_id)

    def _targets(self, graph: LocalGraph, shape: Dict[str, Any]) -> List[str]:
        if "targetNode" in shape:
            return [str(x) for x in _as_list(shape["targetNode"])]
        tc = shape.get("targetClass")
        if tc:
            out = []
            for s in graph.subjects():
                types = [str(x) for x in graph.get(s, "rdf:type") + graph.get(s, "@type")]
                if str(tc) in types:
                    out.append(s)
            return out
        # default: all subjects
        return graph.subjects()

    def _validate_node(
        self,
        graph: LocalGraph,
        node: str,
        shape: Dict[str, Any],
    ) -> List[ConstraintViolation]:
        violations: List[ConstraintViolation] = []
        sid = str(shape.get("id", "anon"))
        props = shape.get("properties") or []
        declared_paths = {str(p.get("path")) for p in props if p.get("path")}

        if shape.get("closed"):
            for p in graph.nodes.get(node, {}).keys():
                if p in ("rdf:type", "@type"):
                    continue
                if p not in declared_paths and p not in set(shape.get("ignoredProperties") or []):
                    violations.append(
                        ConstraintViolation(
                            node, sid, p, f"closed shape: unexpected property {p}"
                        )
                    )

        for pc in props:
            path = str(pc.get("path", ""))
            values = graph.get(node, path)
            violations.extend(self._property_constraints(node, sid, path, values, pc))
        return violations

    def _property_constraints(
        self,
        node: str,
        sid: str,
        path: str,
        values: List[Any],
        pc: Dict[str, Any],
    ) -> List[ConstraintViolation]:
        vios: List[ConstraintViolation] = []
        n = len(values)

        if "minCount" in pc and n < int(pc["minCount"]):
            vios.append(
                ConstraintViolation(
                    node, sid, path, f"minCount {pc['minCount']} not met (got {n})"
                )
            )
        if "maxCount" in pc and n > int(pc["maxCount"]):
            vios.append(
                ConstraintViolation(
                    node, sid, path, f"maxCount {pc['maxCount']} exceeded (got {n})"
                )
            )
        if "in" in pc:
            allowed = set(pc["in"])
            for val in values:
                if val not in allowed:
                    vios.append(
                        ConstraintViolation(
                            node, sid, path, f"value {val!r} not in {sorted(allowed)!r}"
                        )
                    )
        if "hasValue" in pc:
            if pc["hasValue"] not in values:
                vios.append(
                    ConstraintViolation(
                        node, sid, path, f"missing required hasValue {pc['hasValue']!r}"
                    )
                )
        if "datatype" in pc:
            dt = str(pc["datatype"]).lower()
            for val in values:
                if not self._check_datatype(val, dt):
                    vios.append(
                        ConstraintViolation(
                            node, sid, path, f"datatype {dt} failed for {val!r}"
                        )
                    )
        if "pattern" in pc:
            rx = re.compile(str(pc["pattern"]))
            for val in values:
                if not rx.search(str(val)):
                    vios.append(
                        ConstraintViolation(
                            node, sid, path, f"pattern {pc['pattern']!r} failed for {val!r}"
                        )
                    )
        return vios

    @staticmethod
    def _check_datatype(val: Any, dt: str) -> bool:
        if dt in ("string", "xsd:string"):
            return isinstance(val, str)
        if dt in ("integer", "int", "xsd:integer"):
            return isinstance(val, int) and not isinstance(val, bool)
        if dt in ("float", "double", "number", "xsd:float", "xsd:double"):
            return isinstance(val, (int, float)) and not isinstance(val, bool)
        if dt in ("boolean", "bool", "xsd:boolean"):
            return isinstance(val, bool)
        return True


class NeuroSymbolicBridge:
    """
    Map validation outcomes into FHRR space for vector-symbolic compliance queries.
    """

    def __init__(self, engine: CleanRoomVSAEngine):
        self.engine = engine
        if engine.dim != 8192:
            raise ValueError("NeuroSymbolicBridge requires dim=8192")
        # Stable atoms for compliance vocabulary
        for name in ("SHACL_CONFORMS", "SHACL_VIOLATION", "SHACL_SHAPE"):
            if name not in engine.codebook:
                engine.register(name, pinned=True)

    def _shape_atom(self, shape_id: str) -> np.ndarray:
        key = f"SHAPE::{shape_id}"
        if key not in self.engine.codebook:
            digest = hashlib.sha256(shape_id.encode("utf-8")).digest()
            seed = int.from_bytes(digest[:8], "big") % (2**32 - 1)
            rng = np.random.default_rng(seed)
            self.engine.register(key, self.engine.random_symbol(rng=rng), pinned=False)
        return self.engine.codebook[key]

    def encode_report(self, report: ValidationReport) -> np.ndarray:
        shape_v = self._shape_atom(report.shape_id)
        flag = (
            self.engine.codebook["SHACL_CONFORMS"]
            if report.conforms
            else self.engine.codebook["SHACL_VIOLATION"]
        )
        return self.engine.bind(shape_v, flag)

    def compliance_similarity(
        self,
        report: ValidationReport,
        expect_conforms: bool = True,
    ) -> float:
        encoded = self.encode_report(report)
        shape_v = self._shape_atom(report.shape_id)
        flag = (
            self.engine.codebook["SHACL_CONFORMS"]
            if expect_conforms
            else self.engine.codebook["SHACL_VIOLATION"]
        )
        probe = self.engine.bind(shape_v, flag)
        return self.engine.similarity(encoded, probe)

    def query_conforms(self, report: ValidationReport, tau: float = 0.92) -> bool:
        return self.compliance_similarity(report, expect_conforms=True) >= tau


# ---------------------------------------------------------------------------
# Constitutional default shapes for skill / daemon pipeline artifacts
# ---------------------------------------------------------------------------

CONSTITUTIONAL_SHAPES: Dict[str, Any] = {
    "shapes": [
        {
            "id": "SkillGateResultShape",
            "targetClass": "seem:SkillGateResult",
            "closed": False,
            "properties": [
                {
                    "path": "seem:status",
                    "minCount": 1,
                    "maxCount": 1,
                    "in": ["PASS", "FAIL"],
                },
                {
                    "path": "seem:network_access",
                    "minCount": 0,
                    "maxCount": 1,
                    "in": [False],
                },
            ],
        },
        {
            "id": "PipelineStateShape",
            "targetClass": "seem:PipelineState",
            "closed": False,
            "properties": [
                {"path": "seem:has_inputs", "datatype": "boolean", "minCount": 0},
                {"path": "seem:status", "in": ["PASS", "FAIL", "RUNNING"], "minCount": 0},
            ],
        },
        {
            "id": "SkillPackageSovereigntyShape",
            "targetClass": "seem:SkillPackage",
            "closed": False,
            "properties": [
                {
                    "path": "seem:network_access",
                    "minCount": 1,
                    "maxCount": 1,
                    "hasValue": False,
                },
                {
                    "path": "seem:dimension",
                    "minCount": 1,
                    "hasValue": 8192,
                },
            ],
        },
    ]
}


def skill_package_to_graph(package: Dict[str, Any]) -> LocalGraph:
    g = LocalGraph()
    g.add("pkg:self", "rdf:type", "seem:SkillPackage")
    sov = package.get("sovereignty") or {}
    g.add("pkg:self", "seem:network_access", bool(sov.get("network_access", True)))
    vb = package.get("vsa_bindings") or {}
    if "dimension" in vb:
        g.add("pkg:self", "seem:dimension", int(vb["dimension"]))
    return g


def gate_result_to_graph(result: Dict[str, Any]) -> LocalGraph:
    g = LocalGraph()
    g.add("res:self", "rdf:type", "seem:SkillGateResult")
    g.add("res:self", "seem:status", str(result.get("status", "")))
    return g


class ConstitutionalValidator:
    """Facade used by Gate/Daemon."""

    def __init__(
        self,
        engine: Optional[CleanRoomVSAEngine] = None,
        shapes_doc: Optional[Dict[str, Any]] = None,
        tau: float = 0.92,
    ):
        self.shapes = ShapeEngine(shapes_doc or CONSTITUTIONAL_SHAPES)
        self.engine = engine or CleanRoomVSAEngine(dim=8192)
        if not self.engine.verify_jump_start_integrity():
            # lightweight: ensure SHACL atoms can register even without full jump-start
            pass
        self.bridge = NeuroSymbolicBridge(self.engine)
        self.tau = tau

    def validate_skill_package(self, package: Dict[str, Any]) -> ValidationReport:
        report = self.shapes.validate_graph(
            skill_package_to_graph(package),
            shape_id="SkillPackageSovereigntyShape",
        )
        return report

    def validate_gate_result(self, result: Dict[str, Any]) -> ValidationReport:
        return self.shapes.validate_graph(
            gate_result_to_graph(result),
            shape_id="SkillGateResultShape",
        )

    def neuro_conforms(self, report: ValidationReport) -> bool:
        return self.bridge.query_conforms(report, tau=self.tau)
