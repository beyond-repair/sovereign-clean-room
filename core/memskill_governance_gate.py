#!/usr/bin/env python3
"""MemSkill dual-gate orchestrator.

Landed name: memskill_governance_gate.py
Source name in the 2026-09-30 update: clean_room_shacl.py

core/clean_room_shacl.py remains the offline SHACL-subset engine. This module is
the promotion orchestrator (Turtle SHACL, then Z3, then Ed25519). It does not
replace that engine.

Fail-closed deviations from the supplied draft:
- Missing pyshacl/rdflib is GATE_1_SHACL_ERROR, not a pass.
- Missing signer or signing key is GATE_3_CRYPTO_UNAVAILABLE, not a mock signature.
- A mock Ed25519 stamp is rejected by the protocol's governance-bypass falsifier.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from clean_room_z3 import MemSkillZ3Verifier


def _load_signer():
    try:
        from skill_crypto import sign_package
    except ImportError:
        try:
            from core.skill_crypto import sign_package
        except ImportError:
            return None
    return sign_package


class MemSkillGovernanceGate:
    def __init__(self, ttl_shape_path: str, max_resource_capacity: int = 100):
        self.ttl_shape_path = ttl_shape_path
        self.shape_graph = None
        self.z3_verifier = MemSkillZ3Verifier(max_resource_capacity=max_resource_capacity)
        self._shape_error = None
        try:
            import rdflib

            self.shape_graph = rdflib.Graph()
            self.shape_graph.parse(ttl_shape_path, format="turtle")
        except ImportError:
            self._shape_error = "rdflib is not installed"
        except Exception as exc:  # parse or IO
            self._shape_error = str(exc)

    def _json_to_rdf(self, candidate_data: Dict[str, Any]):
        import rdflib

        g = rdflib.Graph()
        seem = rdflib.Namespace("http://adl-seem.org/core/ontology#")
        skill_uri = rdflib.URIRef(
            f"http://adl-seem.org/skills/{candidate_data.get('skillId')}"
        )
        g.add((skill_uri, rdflib.RDF.type, seem.MemSkill))
        g.add(
            (
                skill_uri,
                seem.skillId,
                rdflib.Literal(candidate_data.get("skillId", ""), datatype=rdflib.XSD.string),
            )
        )
        g.add(
            (
                skill_uri,
                seem.invertibilityScore,
                rdflib.Literal(
                    float(candidate_data.get("invertibilityScore", 0.0)),
                    datatype=rdflib.XSD.float,
                ),
            )
        )
        g.add(
            (
                skill_uri,
                seem.maxExecutionMs,
                rdflib.Literal(
                    int(candidate_data.get("maxExecutionMs", 0)),
                    datatype=rdflib.XSD.integer,
                ),
            )
        )
        g.add(
            (
                skill_uri,
                seem.networkAccessPermitted,
                rdflib.Literal(
                    bool(candidate_data.get("networkAccessPermitted", False)),
                    datatype=rdflib.XSD.boolean,
                ),
            )
        )
        g.add(
            (
                skill_uri,
                seem.verificationHash,
                rdflib.Literal(
                    candidate_data.get("verificationHash", ""),
                    datatype=rdflib.XSD.string,
                ),
            )
        )
        for step in candidate_data.get("transitions", []):
            step_uri = rdflib.BNode()
            g.add((step_uri, rdflib.RDF.type, seem.TransitionStep))
            g.add(
                (
                    step_uri,
                    seem.stepIndex,
                    rdflib.Literal(int(step.get("stepIndex", 0)), datatype=rdflib.XSD.integer),
                )
            )
            g.add(
                (
                    step_uri,
                    seem.operatorSymbol,
                    rdflib.Literal(step.get("operatorSymbol", ""), datatype=rdflib.XSD.string),
                )
            )
            g.add(
                (
                    step_uri,
                    seem.resourceCost,
                    rdflib.Literal(int(step.get("resourceCost", 0)), datatype=rdflib.XSD.integer),
                )
            )
            g.add((skill_uri, seem.hasTransitionStep, step_uri))
        return g

    def evaluate_and_sign(
        self, candidate_data: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any], str]:
        """SHACL, then Z3, then Ed25519. Any failure returns passed=False."""
        if self.shape_graph is None:
            return False, {}, f"GATE_1_SHACL_ERROR: {self._shape_error}"

        try:
            from pyshacl import validate
        except ImportError:
            return False, {}, "GATE_1_SHACL_ERROR: pyshacl is not installed."

        try:
            data_graph = self._json_to_rdf(candidate_data)
            conforms, _results_graph, results_text = validate(
                data_graph,
                shacl_graph=self.shape_graph,
                inference="rdfs",
                debug=False,
            )
            if not conforms:
                return False, {}, f"GATE_1_SHACL_FAIL: Structural violation.\n{results_text}"
        except Exception as exc:
            return False, {}, f"GATE_1_SHACL_ERROR: RDF conversion or parsing failed: {exc}"

        z3_passed, z3_msg = self.z3_verifier.verify_memskill(candidate_data)
        if not z3_passed:
            return False, {}, f"GATE_2_Z3_FAIL: {z3_msg}"

        sign_package = _load_signer()
        signing_key = os.environ.get("SEEM_SKILL_SIGNING_KEY_HEX", "").strip()
        if sign_package is None or not signing_key:
            return (
                False,
                {},
                "GATE_3_CRYPTO_UNAVAILABLE: Ed25519 signer or SEEM_SKILL_SIGNING_KEY_HEX missing. Mock signature rejected.",
            )
        manifest = candidate_data.get("manifest")
        if not isinstance(manifest, dict):
            return (
                False,
                {},
                "GATE_3_CRYPTO_UNAVAILABLE: candidate.manifest required for skill_crypto.sign_package.",
            )
        try:
            signed_package = sign_package(candidate_data, signing_key)
        except Exception as exc:
            return False, {}, f"GATE_3_CRYPTO_FAIL: {exc}"
        return True, signed_package, f"GOVERNANCE_PASS: SHACL and Z3 gates satisfied. {z3_msg}"
