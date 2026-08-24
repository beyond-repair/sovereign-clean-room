#!/usr/bin/env python3
"""
Provenance helpers for Stage-1 legacy extraction.

Records extraction events for audit (EXTRACTION_LEGACY.md companion).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass(frozen=True)
class ProvenanceRecord:
    date: str
    source_repo: str
    source_file: str
    target_module: str
    pattern: str
    status: str  # PLANNED | EXTRACTED | VERIFIED | ARCHIVED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "source_repo": self.source_repo,
            "source_file": self.source_file,
            "target_module": self.target_module,
            "pattern": self.pattern,
            "status": self.status,
        }


class ProvenanceLog:
    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: List[ProvenanceRecord] = []
        if self.path.is_file():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for r in raw.get("records", []):
                self._records.append(
                    ProvenanceRecord(
                        date=str(r["date"]),
                        source_repo=str(r["source_repo"]),
                        source_file=str(r["source_file"]),
                        target_module=str(r["target_module"]),
                        pattern=str(r["pattern"]),
                        status=str(r["status"]),
                    )
                )

    def add(self, record: ProvenanceRecord) -> None:
        self._records.append(record)
        self._save()

    def _save(self) -> None:
        body = {
            "version": "provenance_v1",
            "updated_at": time.time(),
            "records": [r.to_dict() for r in self._records],
        }
        self.path.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")

    def list_records(self) -> List[ProvenanceRecord]:
        return list(self._records)

    def markdown_table(self) -> str:
        lines = [
            "| Date | Source | Target | Pattern | Status |",
            "|------|--------|--------|---------|--------|",
        ]
        for r in self._records:
            lines.append(
                f"| {r.date} | {r.source_repo}/{r.source_file} | {r.target_module} | {r.pattern} | {r.status} |"
            )
        return "\n".join(lines)
