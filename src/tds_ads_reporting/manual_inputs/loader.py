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
    revenue: float | None = None
    organic: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def _normalize_budget(raw: dict[str, Any]) -> dict[str, Any]:
    """Merge the `budget` and `spend` YAML sections into one budget dict.

    Supports both shapes:
      budget: {amount, currency, revenue}
      spend:  {amount, vat, remaining}
    """
    budget = dict(raw.get("budget") or {})
    spend = dict(raw.get("spend") or {})
    amount = float(budget.get("amount") or 0.0)
    spent = float(spend.get("amount") or budget.get("spent") or 0.0)
    vat = float(spend.get("vat") or budget.get("vat") or 0.0)
    remaining = float(spend.get("remaining") or budget.get("remaining") or max(0.0, amount - spent))
    revenue = raw.get("revenue", budget.get("revenue"))
    return {
        "amount": amount,
        "spent": spent,
        "vat": vat,
        "remaining": remaining,
        "revenue": float(revenue) if revenue is not None else None,
        "currency": budget.get("currency", ""),
    }


def load_manual_inputs(client_id: str, month: str) -> ManualInputs:
    path = INPUT_DIR / f"{client_id}_{month}.yaml"
    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text()) or {}
    budget = _normalize_budget(raw)
    return ManualInputs(
        client_id=client_id,
        month=month,
        budget=budget,
        scope_prose=raw.get("scope_prose", ""),
        scope_notes=raw.get("scope_notes", ""),
        insights=raw.get("insights", []),
        recommendations=raw.get("recommendations", []),
        revenue=budget.get("revenue"),
        organic=raw.get("organic") or {},
        raw=raw,
    )