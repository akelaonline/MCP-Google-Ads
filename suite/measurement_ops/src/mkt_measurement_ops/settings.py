from __future__ import annotations

import os
from dataclasses import dataclass


_TRUE = {"1", "true", "yes", "on"}


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


@dataclass(frozen=True, slots=True)
class MeasurementSettings:
    gtm_enable_writes: bool = False
    gtm_enable_publish: bool = False

    @classmethod
    def from_env(cls) -> "MeasurementSettings":
        return cls(
            gtm_enable_writes=env_bool("GTM_ENABLE_WRITES", False),
            gtm_enable_publish=env_bool("GTM_ENABLE_PUBLISH", False),
        )
