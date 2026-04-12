"""A-Evolve runner for BitGN PAC1.

Usage:
    uv run python evolve.py              # 5 cycles, adaptive_evolve
    uv run python evolve.py --cycles 10  # custom cycle count
    uv run python evolve.py --dry-run    # smoke test: fetch tasks, don't evolve
"""

import argparse
import logging
import os
from pathlib import Path

import agent_evolve as ae
from agent_evolve.algorithms.adaptive_evolve import AdaptiveEvolveEngine
from agent_evolve.config import EvolveConfig
from bitgn_agent import BitgnAgent
from bitgn_benchmark import BitgnBenchmarkAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

WORKSPACE = Path(__file__).parent / "workspace"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evolve PAC1 agent against bitgn/pac1-dev")
    parser.add_argument("--cycles", type=int, default=5, help="Number of evolution cycles")
    parser.add_argument("--dry-run", action="store_true", help="Fetch tasks only, skip evolution")
    # batch_size = tasks per cycle. Library (engine/loop.py:82) always calls
    # benchmark.get_tasks(split="train", limit=batch_size) starting from index 0,
    # so a small batch_size causes the evolver to overfit the FIRST N train tasks
    # instead of rotating. Default 32 = full pac1-dev train split (40 tasks × 0.8).
    # Cost warning: 32 × cycles sequential runs. At ~30s/task this is ~16min/cycle.
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Tasks per cycle (default 32 = full train split)",
    )
    args = parser.parse_args()

    benchmark = BitgnBenchmarkAdapter()
    agent = BitgnAgent(workspace_dir=WORKSPACE)

    if args.dry_run:
        tasks = benchmark.get_tasks(split="train", limit=10_000)
        holdout = benchmark.get_tasks(split="holdout", limit=10_000)
        print(f"Dry run: train split = {len(tasks)} tasks, holdout split = {len(holdout)} tasks")
        print(
            f"Dry run: --batch-size={args.batch_size} → engine sees first "
            f"{min(args.batch_size, len(tasks))} train tasks each cycle"
        )
        print(
            f"Dry run: --cycles={args.cycles} → estimated wall-clock "
            f"{min(args.batch_size, len(tasks)) * args.cycles * 30 // 60} min "
            f"(sequential, ~30s/task)"
        )
        print("Agent workspace:", WORKSPACE)
        print("System prompt length:", len(agent.system_prompt), "chars")
        print("Skills loaded:", [s.name for s in agent.skills])
        print(f"Evolver model: {os.getenv('EVOLVER_MODEL', 'claude-opus-4-5')}")
        print(f"ANTHROPIC_API_KEY set: {bool(os.getenv('ANTHROPIC_API_KEY'))}")
        return

    config = EvolveConfig(
        batch_size=args.batch_size,
        max_cycles=args.cycles,
        holdout_ratio=0.2,
        evolve_prompts=True,
        evolve_skills=True,
        evolve_memory=False,  # no episodic memory for per-task isolated VMs
        evolver_model=os.getenv("EVOLVER_MODEL", "claude-opus-4-5"),
    )

    engine = AdaptiveEvolveEngine(config=config)

    evolver = ae.Evolver(
        agent=agent,
        benchmark=benchmark,
        engine=engine,
        config=config,
    )

    result = evolver.run(cycles=args.cycles)
    print(f"\nEvolution complete: {args.cycles} cycles")
    print(f"Final score: {getattr(result, 'final_score', 'N/A')}")


if __name__ == "__main__":
    main()
