"""Central runtime configuration for benchmark and model roles."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_first(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class RuntimeSettings:
    run_profile: str
    benchmark_host: str
    benchmark_id: str
    llm_backend: str
    primary_model: str
    verifier_model: str
    verifier_policy: str
    parallel_workers: int


_RUN_PROFILE = os.getenv("RUN_PROFILE", "dev").strip().lower() or "dev"

_PROFILE_DEFAULTS = {
    "dev": {
        "llm_backend": "nebius",
        "primary_model": "Qwen/Qwen3-235B-A22B-Thinking-2507",
        "verifier_model": "claude-haiku-4-5",
        "verifier_policy": "adaptive",
        "parallel_workers": 1,
    },
    "final": {
        "llm_backend": "api",
        "primary_model": "claude-sonnet-4-6",
        "verifier_model": "claude-haiku-4-5",
        "verifier_policy": "adaptive",
        "parallel_workers": 4,
    },
}
_PROFILE = _PROFILE_DEFAULTS.get(_RUN_PROFILE, _PROFILE_DEFAULTS["dev"])


SETTINGS = RuntimeSettings(
    run_profile=_RUN_PROFILE if _RUN_PROFILE in _PROFILE_DEFAULTS else "dev",
    benchmark_host=_env_first("BENCHMARK_HOST", default="https://api.bitgn.com"),
    benchmark_id=_env_first("BENCHMARK_ID", default="bitgn/pac1-dev"),
    llm_backend=_env_first(
        "PRIMARY_LLM_BACKEND",
        "LLM_BACKEND",
        default=_PROFILE["llm_backend"],
    ),
    primary_model=_env_first(
        "PRIMARY_MODEL_ID",
        "MODEL_ID",
        default=_PROFILE["primary_model"],
    ),
    verifier_model=_env_first(
        "VERIFIER_MODEL_ID",
        "VERIFIER_MODEL",
        default=_PROFILE["verifier_model"],
    ),
    verifier_policy=_env_first("VERIFIER_POLICY", default=_PROFILE["verifier_policy"]).lower(),
    parallel_workers=_env_int("PARALLEL", default=_PROFILE["parallel_workers"]),
)
