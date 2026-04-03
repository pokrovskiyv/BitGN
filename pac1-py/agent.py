"""Agent entry point — thin wrapper preserving the run_agent() signature.

All domain-specific logic lives in domain_fs.py. The generic agent loop
lives in agent_loop.py. This file exists solely to maintain backward
compatibility with bitgn_agent.py, main.py, and evolve.py which all
import `from agent import run_agent`.
"""

from agent_loop import AgentResult, run_agent_loop
from domain_fs import FilesystemDomain

_domain = FilesystemDomain()


def run_agent(model: str, harness_url: str, task_text: str) -> AgentResult:
    """Preserved signature for bitgn_agent.py / A-Evolve compatibility."""
    return run_agent_loop(model, harness_url, task_text, domain=_domain)
