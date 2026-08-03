from __future__ import annotations

import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOG = ROOT / "logs" / "tds-report.log"


def setup_logging(log_path: Path = DEFAULT_LOG, level: int = logging.INFO) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    handlers.append(logging.FileHandler(log_path))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
    )
