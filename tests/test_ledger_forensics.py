"""Ledger forensic reconstruction and anomaly classes."""

from __future__ import annotations

import json

from clean_room_ledger import CleanRoomLedger


def test_forensic_fields_and_anomalies(tmp_path):
    led = CleanRoomLedger(tmp_path / "audit")
    led.append(
        "selection",
        {
            "what": "select route",
            "why": "highest weight",
            "evidence": {"fail_count": 1},
            "skill_id": "route-2",
            "constraints": {"network_access": False},
            "failed": False,
            "changed": {"weight": 0.5},
        },
    )
    led.append("selection", {"what": "select route", "skill_id": "route-3", "gate_status": "FAIL"})
    view = led.forensic_reconstruction()
    assert view[0]["why"] == "highest weight"
    assert view[0]["evidence"]["fail_count"] == 1
    assert view[0]["skill_selected"] == "route-2"
    assert view[0]["constraints"]["network_access"] is False
    assert view[1]["failed"] is True
    assert led.anomaly_report()["ok"] is True

    lines = led.ledger_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["payload"]["why"] = "rewritten"
    lines[0] = json.dumps(tampered)
    led.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = led.anomaly_report()
    assert report["ok"] is False
    assert any("tamper" in item or "corruption" in item for item in report["anomalies"])


def test_missing_duplicate_and_order(tmp_path):
    led = CleanRoomLedger(tmp_path / "audit")
    led.append("a", {"what": "one"})
    led.append("b", {"what": "two"})
    led.append("c", {"what": "three"})
    lines = led.ledger_path.read_text(encoding="utf-8").splitlines()
    # drop the middle record
    led.ledger_path.write_text(lines[0] + "\n" + lines[2] + "\n", encoding="utf-8")
    missing = led.anomaly_report()
    assert missing["ok"] is False

    led2 = CleanRoomLedger(tmp_path / "audit2")
    led2.append("a", {"what": "one"})
    led2.append("b", {"what": "two"})
    dup_lines = led2.ledger_path.read_text(encoding="utf-8").splitlines()
    led2.ledger_path.write_text("\n".join(dup_lines + [dup_lines[0]]) + "\n", encoding="utf-8")
    dup = led2.anomaly_report()
    assert dup["ok"] is False

    led3 = CleanRoomLedger(tmp_path / "audit3")
    led3.append("a", {"what": "one"})
    led3.append("b", {"what": "two"})
    ordered = led3.ledger_path.read_text(encoding="utf-8").splitlines()
    led3.ledger_path.write_text("\n".join(reversed(ordered)) + "\n", encoding="utf-8")
    disordered = led3.anomaly_report()
    assert disordered["ok"] is False
