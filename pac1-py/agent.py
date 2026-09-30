"""Agent entry point — thin wrapper preserving the run_agent() signature.

Domain-specific logic lives in domain_*.py. The generic agent loop lives in
agent_loop.py. This file keeps `from agent import run_agent` stable for
bitgn_agent.py, main.py, and evolve.py.
"""

import os

from agent_loop import AgentResult, run_agent_loop
from domain_fs import FilesystemDomain


def _select_domain():
    override = os.getenv("BITGN_DOMAIN", "").strip().lower()
    domain_name = override or "filesystem"
    if domain_name == "ecom":
        from domain_ecom import EcomDomain

        return EcomDomain()
    if domain_name != "filesystem":
        raise ValueError(f"Unknown BITGN_DOMAIN: {domain_name!r}")
    return FilesystemDomain()


_domain = _select_domain()


def run_agent(model: str, harness_url: str, task_text: str) -> AgentResult:
    """Preserved signature for bitgn_agent.py / A-Evolve compatibility."""
    return run_agent_loop(model, harness_url, task_text, domain=_domain)
