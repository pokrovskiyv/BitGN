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

PCDRED_CYCLE_PROMPT = """## Task: PCDRED Optimization Cycle

You are running one PCDRED iteration cycle to improve the BitGN PAC
competition agent score.

### Before you start

1. Read the LATEST evaluation report — find the most recent file in:
```bash
ls -t docs/eval/run-*.md | head -1
```

2. Read these for context:
   - `docs/superpowers/plans/03-plan-cycles.md` — cycle process
   - `docs/sota-analysis.md` — P2 changes backlog (Section 2)
   - `CLAUDE.md` — Key Design Principles

3. Note the current score from the latest eval report. This is your
   baseline for THIS cycle.

### The Cycle (Meta-Model Section 3.6, steps 1-9)

**1. ANALYST** (follow `agents/analyst.md`):
- Read the latest eval report
- Identify the task with the highest point loss that is NOT yet fixed
- Check previous analysis reports in `docs/analysis/` to avoid repeating
  already-attempted fixes
- Classify the root cause: SECURITY / SIDE_EFFECT / PROTOCOL /
  STAGNATION / TOOL_ERROR / EDGE_CASE
- Write a SHORT report (one failure only) to
  `docs/analysis/cycle-YYYY-MM-DD-HH.md`

**2. ARCHITECT** (follow `agents/architect.md`):
- Read the Analyst report
- Read `docs/sota-analysis.md` to check if a known SoTA fix applies
- Read the relevant source code
- Implement the MINIMAL fix
- If the fix touches `strategy.py` prompts, verify the prompt still
  contains "CRITICAL SECURITY RULES"
- If the fix touches `defend.py`, verify pattern count hasn't decreased
- Commit:
```bash
git commit -m "fix: [one-line description of what and why]"
```

**3. RED TEAM + OPTIMIZER** (parallel — do both):

RED TEAM (follow `agents/redteam.md`):
- Read the Architect's diff: `git diff HEAD~1`
- Generate 3 attack scenarios targeting the change
- Rate: BLOCKED / PARTIAL / BYPASSES
- Write to `docs/redteam/cycle-YYYY-MM-DD-HH.md`

OPTIMIZER (follow `agents/optimizer.md`):
- Read the latest benchmark output
- Check for waste: redundant reads, empty searches, stagnation events
- If a tuning recommendation has high confidence, note it
- Write to `docs/optimization/cycle-YYYY-MM-DD-HH.md`

**4. ARCHITECT** (if needed):
- If Red Team found BYPASSES: patch and commit
- If Optimizer has a high-confidence tuning: apply and commit
- Skip if nothing to fix

**5. EVALUATOR** (follow `agents/evaluator.md`):
```bash
cd pac1-py && make run 2>&1 | tee /tmp/cycle-run.log
```
- Compare against the baseline noted in step 0
- Write to `docs/eval/run-YYYY-MM-DD-HH.md`
- Verdict: IMPROVED / IMPROVED_WITH_REGRESSION / NEUTRAL / REGRESSED

**6. DECISION GATE**:
- IMPROVED (zero regressions) → done, changes stay
- IMPROVED_WITH_REGRESSION → changes stay, note the regression task ID
  in the eval report for the next cycle's Analyst
- NEUTRAL → revert Architect changes: `git revert HEAD --no-edit`
- REGRESSED → revert: `git revert HEAD --no-edit`

**7. P2 BACKLOG CHECK** (only if score is plateauing):
If the last 2+ cycles were NEUTRAL, check `docs/sota-analysis.md`
Section 2 for P2 changes not yet implemented:
- P2.1: Constraint extraction → add to `verify.py`
- P2.2: Tree-diff side-effect check → add to `verify.py`
- P2.3: Cross-run reflections → add to `main.py` + `strategy.py`
- P2.4: Few-shot examples → add to `strategy.py`
Pick one, implement it as the Architect fix, then continue the cycle
from step 3.

### Critical rules

- ONE fix per cycle. Do not bundle multiple fixes
- The Analyst must check `docs/analysis/` for previously attempted fixes
  to avoid repeating failed approaches
- If score REGRESSED, revert immediately — do not try to fix forward
- All timestamps in filenames use UTC: YYYY-MM-DD-HH
- Commit after each agent step
"""


async def run_cycle(cycle_num: int, total: int) -> dict:
    """Run one PCDRED cycle. Returns summary dict."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*60}")
    print(f"PCDRED Cycle {cycle_num}/{total} — {timestamp}")
    print(f"{'='*60}\n")

    result_text = ""
    session_id = None

    async for message in query(
        prompt=PCDRED_CYCLE_PROMPT,
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

    print(f"\n{'='*60}")
    print(f"All {cycles} cycles complete")
    print(f"{'='*60}")
    for r in results:
        print(f"  Cycle {r['cycle']}: {r['timestamp']} (session: {r['session_id']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PCDRED optimization cycles")
    parser.add_argument("--cycles", type=int, default=3, help="Number of cycles (default: 3)")
    parser.add_argument("--cooldown", type=int, default=60, help="Seconds between cycles (default: 60)")
    args = parser.parse_args()

    asyncio.run(main(args.cycles, args.cooldown))
