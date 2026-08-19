from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"
DEFAULT_CONFIG = CONFIG_DIR / "clients.yaml"


@dataclass
class MetaConfig:
    ad_accounts: list[str] = field(default_factory=list)
    conversion_actions: dict[str, list[str]] = field(default_factory=dict)
    page_id: str | None = None
    instagram_id: str | None = None


@dataclass
class Client:
    id: str
    name: str
    report_recipient: str
    language: str = "en"
    currency: str = "EGP"
    timezone: str = "Africa/Cairo"
    monthly_budget: float | None = None
    goals: dict[str, Any] = field(default_factory=dict)
    meta: MetaConfig = field(default_factory=MetaConfig)
    report: dict[str, Any] = field(default_factory=dict)

    def platforms(self) -> list[str]:
        out = []
        if self.meta.ad_accounts:
            out.append("meta")
        return out


@dataclass
class AppConfig:
    raw: dict[str, Any]
    clients: list[Client] = field(default_factory=list)

    def client(self, client_id: str) -> Client:
        for c in self.clients:
            if c.id == client_id:
                return c
        raise KeyError(client_id)

    def active_clients(self) -> list[Client]:
        return [c for c in self.clients if c.platforms()]


def _parse_meta(entry: dict[str, Any]) -> MetaConfig:
    meta = entry.get("meta") or {}
    ad_accounts = [a["id"] for a in meta.get("ad_accounts", [])]
    return MetaConfig(
        ad_accounts=ad_accounts,
        conversion_actions=meta.get("conversion_actions") or {},
        page_id=meta.get("page_id"),
        instagram_id=meta.get("instagram_id"),
    )


def load_config(path: Path = DEFAULT_CONFIG) -> AppConfig:
    if not path.exists():
        path = CONFIG_DIR / "clients.example.yaml"
    raw = yaml.safe_load(path.read_text()) or {}
    cfg = AppConfig(raw=raw)
    for entry in raw.get("clients", []):
        data = dict(entry)
        data["meta"] = _parse_meta(entry)
        cfg.clients.append(Client(**data))
    return cfg
