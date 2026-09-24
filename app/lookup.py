"""Serves precomputed scores when the ML stack isn't installed.

`export_lookup.py` runs the real `ModelBundle` over every dataset address
and writes `models/lookup.json.gz`. This module reads that file with the
standard library only, and exposes the same interface `app/main.py` uses
on `ModelBundle`: `metrics`, `thresholds`, `examples()`, `score_address()`.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path

LOOKUP_FILE = Path(__file__).resolve().parent.parent / "models" / "lookup.json.gz"


@dataclass
class LookupBundle:
    scores: dict[str, dict]
    metrics: dict
    thresholds: dict[str, float]
    example_addresses: list[str]
    disclaimer: str

    @classmethod
    def load(cls) -> "LookupBundle | None":
        if not LOOKUP_FILE.exists():
            return None
        with gzip.open(LOOKUP_FILE, "rt", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            data["scores"], data["metrics"], data["thresholds"], data["examples"], data["disclaimer"]
        )

    def examples(self) -> list[str]:
        return self.example_addresses

    def score_address(self, address: str) -> dict | None:
        key = address.lower()
        entry = self.scores.get(key)
        if entry is None:
            return None
        return {"address": key, **entry, "disclaimer": self.disclaimer}
