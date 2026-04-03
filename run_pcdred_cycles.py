"""Automated PCDRED optimization cycles via Claude Agent SDK.

Runs the PCDRED cycle prompt N times with a cooldown between cycles.
No human interaction required. Uses acceptEdits permission mode +
project-level allowed Bash patterns (see .claude/settings.json).

Usage:
    uv run python run_pcdred_cycles.py              # 3 cycles, 60s cooldown
    uv run python run_pcdred_cycles.py --cycles 5   # 5 cycles
    uv run python run_pcdred_cycles.py --cooldown 120  # 2 min between cycles
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)

PCDRED_PROMPT_PATH = (
    Path(__file__).parent / "docs" / "superpowers" / "plans" / "pcdred-cycle-prompt.txt"
)


def _load_cycle_prompt() -> str:
    """Load the canonical PCDRED cycle prompt from file."""
    return PCDRED_PROMPT_PATH.read_text()


async def run_cycle(cycle_num: int, total: int) -> dict:
    """Run one PCDRED cycle. Returns summary dict."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'=' * 60}")
    print(f"PCDRED Cycle {cycle_num}/{total} — {timestamp}")
    print(f"{'=' * 60}\n")

    result_text = ""
    session_id = None

    async for message in query(
        prompt=_load_cycle_prompt(),
        options=ClaudeAgentOptions(
            cwd=str(Path(__file__).parent),
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            permission_mode="acceptEdits",
            max_turns=50,
            setting_sources=["project"],
        ),
    ):
        if isinstance(message, ResultMessage):
            result_text = message.result
            print(f"\n--- Cycle {cycle_num} result ---")
            print(result_text[:500])
            if len(result_text) > 500:
                print(f"... ({len(result_text)} chars total)")
        elif isinstance(message, SystemMessage) and message.subtype == "init":
            session_id = message.data.get("session_id")

    return {
        "cycle": cycle_num,
        "timestamp": timestamp,
        "session_id": session_id,
        "result_length": len(result_text),
    }


async def main(cycles: int, cooldown: int) -> None:
    print(f"Starting {cycles} PCDRED cycles with {cooldown}s cooldown")
    print(f"Working directory: {Path(__file__).parent}")
    print(f"Permission mode: acceptEdits")
    print(f"Allowed tools configured in: .claude/settings.json\n")

    results = []
    for i in range(1, cycles + 1):
        summary = await run_cycle(i, cycles)
        results.append(summary)

        if i < cycles:
            print(f"\nCooldown: {cooldown}s before next cycle...")
            await asyncio.sleep(cooldown)

    print(f"\n{'=' * 60}")
    print(f"All {cycles} cycles complete")
    print(f"{'=' * 60}")
    for r in results:
        print(f"  Cycle {r['cycle']}: {r['timestamp']} (session: {r['session_id']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PCDRED optimization cycles")
    parser.add_argument("--cycles", type=int, default=3, help="Number of cycles (default: 3)")
    parser.add_argument(
        "--cooldown", type=int, default=60, help="Seconds between cycles (default: 60)"
    )
    args = parser.parse_args()

    asyncio.run(main(args.cycles, args.cooldown))
