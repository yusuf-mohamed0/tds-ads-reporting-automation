from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


class MissingCredentialError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingCredentialError(
            f"{name} is not set. Add it to {ROOT / '.env'}."
        )
    return value


class Credentials:
    def __init__(self) -> None:
        self.meta_access_token = _require("META_SYSTEM_USER_TOKEN")
        self.meta_api_version = os.environ.get("META_API_VERSION", "v26.0")
        self.google_ads_yaml = os.environ.get("GOOGLE_ADS_YAML", str(ROOT / "google-ads.yaml"))


def init_credentials() -> Credentials:
    return Credentials()
