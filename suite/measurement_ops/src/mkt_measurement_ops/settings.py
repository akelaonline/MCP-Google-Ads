from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass


_TRUE = {"1", "true", "yes", "on"}


def measurement_db_path() -> Path:
    configured = os.getenv("MEASUREMENT_OPS_DB")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".mkt-measurement-ops" / "measurement_ops.db"


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


@dataclass(frozen=True, slots=True)
class MeasurementSettings:
    gtm_enable_preview: bool = False
    gtm_enable_writes: bool = False
    gtm_enable_publish: bool = False

    @classmethod
    def from_env(cls) -> "MeasurementSettings":
        return cls(
            gtm_enable_preview=env_bool("GTM_ENABLE_PREVIEW", False),
            gtm_enable_writes=env_bool("GTM_ENABLE_WRITES", False),
            gtm_enable_publish=env_bool("GTM_ENABLE_PUBLISH", False),
        )
