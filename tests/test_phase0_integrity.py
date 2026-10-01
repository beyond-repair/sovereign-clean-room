"""Phase 0 laboratory integrity. Real gates, not mocked passes."""

from __future__ import annotations

import json
from pathlib import Path

import copy
import os

import numpy as np
import pytest

from banel_protocol import RouteSession
from fhrr_protocol import run_cell, sample_codebook
from memskill_governance_gate import MemSkillGovernanceGate
from memskill_ir import canonicalize, canonical_sha256
from clean_room_ledger import CleanRoomLedger
from network_guard import NetworkDenied, OfflineBoundary
from skill_crypto import generate_keypair, sign_package, verify_package
import socket


def _candidate():
    return {
        "skillId": "11111111-1111-4111-8111-111111111111",
        "invertibilityScore": 0.97,
        "maxExecutionMs": 50,
        "networkAccessPermitted": False,
        "verificationHash": "ab" * 32,
        "transitions": [
            {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 5},
            {"stepIndex": 1, "operatorSymbol": "VERIFY_INTEGRITY", "resourceCost": 5},
            {"stepIndex": 2, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 5},
        ],
    }


def test_d1_deterministic_replay():
    a = sample_codebook(8, 32, 123)
    b = sample_codebook(8, 32, 123)
    assert np.array_equal(a, b)
    left = run_cell(
        d=32, k=2, gamma=0.0, n_trials=2, codebook_seed=5, trial_seed=9,
        m=8, bootstrap_resamples=20, git_sha="d1",
    )
    right = run_cell(
        d=32, k=2, gamma=0.0, n_trials=2, codebook_seed=5, trial_seed=9,
        m=8, bootstrap_resamples=20, git_sha="d1",
    )
    assert left["trials"] == right["trials"]
    assert left["seed_record"]["config_sha256"] == right["seed_record"]["config_sha256"]
    ir = canonicalize(_candidate())
    assert canonical_sha256(ir) == canonical_sha256(canonicalize(_candidate()))
    s1 = RouteSession(n_routes=4, failing=[0], group="C", seed=3)
    s2 = RouteSession(n_routes=4, failing=[0], group="C", seed=3)
    s1.run(6)
    s2.run(6)
    assert s1.selections == s2.selections


def test_d3_network_access_false_fail_closed(monkeypatch):
    called = {"n": 0}

    def boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("socket must not be used")

    monkeypatch.setattr(socket, "create_connection", boom)
    boundary = OfflineBoundary()
    with pytest.raises(NetworkDenied):
        boundary.attempt_connection("203.0.113.5", 9, socket_module=socket)
    assert called["n"] == 0
    assert boundary.network_access is False
    assert boundary.attempts[0]["opened"] is False


def test_d4_signature_tamper_payload_ir_transition_metadata():
    sk, vk = generate_keypair()
    ir = canonicalize(_candidate())
    package = {"manifest": {"signature": "", "version": "1.0.0"}, "ir": ir}
    signed = sign_package(package, sk)
    assert verify_package(signed, [vk]) is True
    mutations = []
    payload = copy.deepcopy(signed)
    payload["manifest"]["version"] = "9.9.9"
    mutations.append(payload)
    ir_mut = copy.deepcopy(signed)
    ir_mut["ir"]["invertibilityScore"] = 0.99
    mutations.append(ir_mut)
    step_mut = copy.deepcopy(signed)
    step_mut["ir"]["transitions"][0]["resourceCost"] = 9
    mutations.append(step_mut)
    meta = copy.deepcopy(signed)
    meta["manifest"]["author"] = "tamper"
    mutations.append(meta)
    sig = copy.deepcopy(signed)
    sig["manifest"]["signature"] = "00" * 64
    mutations.append(sig)
    for bad in mutations:
        with pytest.raises(Exception):
            verify_package(bad, [vk])


def test_d5_missing_signer_is_gate_3(tmp_path, monkeypatch):
    pytest.importorskip("z3")
    pytest.importorskip("pyshacl")
    monkeypatch.delenv("SEEM_SKILL_SIGNING_KEY_HEX", raising=False)
    shape = Path(__file__).resolve().parents[1] / "shapes" / "mem_skill_shape.ttl"
    gate = MemSkillGovernanceGate(str(shape))
    passed, package, message = gate.evaluate_and_sign(_candidate())
    assert passed is False
    assert package == {}
    assert "GATE_3_CRYPTO_UNAVAILABLE" in message
    assert "ED25519_MOCK_SIGNATURE_PASS" not in message


def test_d2_ledger_tamper_detected(tmp_path):
    led = CleanRoomLedger(tmp_path / "led")
    led.append("l0", {"what": "original"})
    led.append("l0", {"what": "next"})
    lines = led.ledger_path.read_text(encoding="utf-8").splitlines()
    body = json.loads(lines[0])
    body["payload"]["what"] = "mutated historical record"
    lines[0] = json.dumps(body)
    led.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = led.verify_chain()
    assert report["ok"] is False
