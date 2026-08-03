from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
INPUT_DIR = ROOT / "manual_inputs"


@dataclass
class ManualInputs:
    client_id: str
    month: str
    budget: dict[str, Any] = field(default_factory=dict)
    scope_prose: str = ""
    scope_notes: str = ""
    insights: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def load_manual_inputs(client_id: str, month: str) -> ManualInputs:
    path = INPUT_DIR / f"{client_id}_{month}.yaml"
    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text()) or {}
    return ManualInputs(
        client_id=client_id,
        month=month,
        budget=raw.get("budget", {}),
        scope_prose=raw.get("scope_prose", ""),
        scope_notes=raw.get("scope_notes", ""),
        insights=raw.get("insights", []),
        recommendations=raw.get("recommendations", []),
        raw=raw,
    )
