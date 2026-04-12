"""BitGN client factories + API key loader.

The BitGN Run API takes ``api_key`` as a **field on ``StartRunRequest``**
(not an HTTP header). So this module does two small things:

1. :data:`BITGN_API_KEY` — module-level constant, loaded once from the env var
   of the same name. Empty string if unset. ``main.py`` passes this directly
   to ``StartRunRequest(api_key=...)``.
2. :func:`make_harness_client` / :func:`make_vm_client` — thin factories for
   ``HarnessServiceClientSync`` / ``PcmRuntimeClientSync``. They are plain
   wrappers today (no auth interceptor, no custom headers) — they exist so
   callers have a single import point in case auth ever needs to move back
   to the transport layer.

The VM client (``PcmRuntimeClientSync``) is constructed with a scoped
``harness_url`` returned by ``StartTrial``; that URL is already authenticated
server-side, so no additional auth is attached.
"""

from __future__ import annotations

import os

from bitgn.harness_connect import HarnessServiceClientSync
from bitgn.vm.pcm_connect import PcmRuntimeClientSync

_ENV_VAR = "BITGN_API_KEY"

#: API key for the BitGN platform. Read once at import time from the env var
#: ``BITGN_API_KEY``. Empty string if unset. Callers should pass this to
#: ``StartRunRequest(api_key=BITGN_API_KEY)``.
BITGN_API_KEY: str = os.getenv(_ENV_VAR, "").strip()

_announced = False


def _announce_once() -> None:
    global _announced
    if _announced:
        return
    _announced = True
    if BITGN_API_KEY:
        print(
            f"[bitgn-auth] {_ENV_VAR} loaded (len={len(BITGN_API_KEY)}, passed via StartRunRequest)"
        )
    else:
        profile = os.getenv("RUN_PROFILE", "").strip().lower()
        if profile == "final":
            print(
                f"[bitgn-auth] WARNING: {_ENV_VAR} not set but RUN_PROFILE=final — "
                "StartRun will fail on authenticated benchmarks"
            )
        else:
            print(f"[bitgn-auth] {_ENV_VAR} not set (dev mode)")


def make_harness_client(host: str) -> HarnessServiceClientSync:
    """Build a plain ``HarnessServiceClientSync``. Auth is carried in the
    ``api_key`` field of ``StartRunRequest``, not HTTP headers."""
    _announce_once()
    return HarnessServiceClientSync(host)


def make_vm_client(harness_url: str) -> PcmRuntimeClientSync:
    """Build a plain ``PcmRuntimeClientSync``. The ``harness_url`` is scoped
    to a specific trial by the server, so no extra auth is needed."""
    return PcmRuntimeClientSync(harness_url)
