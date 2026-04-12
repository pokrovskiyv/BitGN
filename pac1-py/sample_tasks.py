"""Benchmark reconnaissance — list tasks and (optionally) fetch full instructions.

Designed for final-day pre-run recon: preview the blind task set without
running the agent loop or burning LLM tokens.

Usage (from pac1-py/):

    uv run python sample_tasks.py
        # Lists task IDs from get_benchmark(). No trials created.

    uv run python sample_tasks.py --out /tmp/tasks.md
        # Same as above, but writes the listing to a file.

    uv run python sample_tasks.py --live
        # Also calls start_playground + end_trial for each task to capture
        # the full trial.instruction text. NO LLM calls, but each start_playground
        # creates a trial on the benchmark server.

    uv run python sample_tasks.py --live --limit 5
        # Only the first 5 tasks in --live mode (safer sample).

    uv run python sample_tasks.py --live --out /tmp/final-tasks.md
        # Full recon to file — the recommended final-day warmup.

SAFETY: --live creates real trials via start_playground/end_trial. No agent
loop runs and no LLM calls are made, but some benchmark implementations may
count each start_playground as an attempt. BEFORE using --live on the final
blind benchmark, verify that one-attempt-per-task is NOT enforced (i.e. the
benchmark allows repeated runs). On the practice benchmark (bitgn/pac1-dev)
it is safe to use freely.

Environment:
    Uses the same layered .env loading as main.py — `.env` first, then
    `.env.final` (or `.env.final.example` fallback) when RUN_PROFILE=final.
    Set BENCHMARK_HOST and BENCHMARK_ID to target a specific benchmark.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

# Layered .env loading (mirrors main.py semantics)
load_dotenv()
if os.getenv("RUN_PROFILE", "").strip().lower() == "final":
    _here = Path(__file__).parent
    _final_env = _here / ".env.final"
    if not _final_env.exists():
        _final_env = _here / ".env.final.example"
    if _final_env.exists():
        load_dotenv(_final_env, override=True)

from bitgn.harness_pb2 import (  # noqa: E402
    EndTrialRequest,
    GetBenchmarkRequest,
    StartPlaygroundRequest,
)
from connectrpc.errors import ConnectError  # noqa: E402

from bitgn_client import make_harness_client  # noqa: E402
from settings import SETTINGS  # noqa: E402


def _render_quick(tasks) -> list[str]:
    """Render task list with whatever metadata the benchmark response exposes."""
    lines: list[str] = []
    for t in tasks:
        tid = getattr(t, "task_id", "<unknown>")
        lines.append(f"## {tid}")
        # Best-effort: dump any string-like fields we can find on the proto
        for field_name in ("instruction", "description", "category", "tags"):
            val = getattr(t, field_name, None)
            if val:
                val_str = str(val).strip()
                if val_str:
                    lines.append(f"{field_name}: {val_str}")
        lines.append("")
    return lines


def _render_live(tasks, host: str, benchmark_id: str, limit: int) -> list[str]:
    """For each task, start a trial to capture trial.instruction, then end it."""
    lines: list[str] = []
    sliced = list(tasks)[:limit] if limit > 0 else list(tasks)
    total = len(sliced)
    for idx, t in enumerate(sliced, 1):
        tid = getattr(t, "task_id", f"<unknown-{idx}>")
        try:
            task_client = make_harness_client(host)
            trial = task_client.start_playground(
                StartPlaygroundRequest(benchmark_id=benchmark_id, task_id=tid)
            )
            trial_short = (trial.trial_id[:8] + "…") if len(trial.trial_id) > 8 else trial.trial_id
            instruction = (trial.instruction or "").rstrip()
            harness_url = getattr(trial, "harness_url", "")
            lines.append(f"## {tid}  (trial {trial_short})")
            if harness_url:
                lines.append(f"harness: {harness_url}")
            lines.append("")
            lines.append(instruction if instruction else "<empty instruction>")
            lines.append("")
            # Always end the trial to avoid leaking harness resources
            try:
                task_client.end_trial(EndTrialRequest(trial_id=trial.trial_id))
            except Exception as exc:
                lines.append(f"(end_trial warning: {exc})")
                lines.append("")
            print(f"[{idx}/{total}] {tid} OK", file=sys.stderr)
        except ConnectError as exc:
            lines.append(f"## {tid}  ERROR {exc.code}: {exc.message}")
            lines.append("")
            print(f"[{idx}/{total}] {tid} FAIL: {exc.code}", file=sys.stderr)
        except Exception as exc:
            lines.append(f"## {tid}  ERROR: {exc}")
            lines.append("")
            print(f"[{idx}/{total}] {tid} FAIL: {exc}", file=sys.stderr)
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dump benchmark task instructions without running the agent loop.",
        epilog="No LLM calls. Safe to run on practice benchmarks freely.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call start_playground/end_trial for each task to capture full instruction "
        "(WARNING: may count as an attempt on some benchmarks)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max tasks to fetch in --live mode (0 = all)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args()

    header: list[str] = [
        f"# Benchmark reconnaissance — {datetime.now(UTC).isoformat()}",
        f"# Host: {SETTINGS.benchmark_host}",
        f"# Benchmark: {SETTINGS.benchmark_id}",
        f"# Profile: {SETTINGS.run_profile}",
        f"# Mode: {'live (trials created)' if args.live else 'quick (metadata only)'}",
        "",
    ]

    try:
        client = make_harness_client(SETTINGS.benchmark_host)
        res = client.get_benchmark(GetBenchmarkRequest(benchmark_id=SETTINGS.benchmark_id))
    except ConnectError as exc:
        print(f"ERROR: get_benchmark failed: {exc.code} {exc.message}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: could not connect to {SETTINGS.benchmark_host}: {exc}", file=sys.stderr)
        return 1

    header.append(f"# Benchmark ID: {res.benchmark_id}")
    header.append(f"# Task count: {len(res.tasks)}")
    description = (getattr(res, "description", "") or "").strip()
    if description:
        header.append(f"# Description: {description}")
    header.append("")

    if args.live:
        body = _render_live(res.tasks, SETTINGS.benchmark_host, SETTINGS.benchmark_id, args.limit)
    else:
        body = _render_quick(res.tasks)

    output = "\n".join(header + body)
    if args.out:
        Path(args.out).write_text(output)
        print(f"Wrote {len(header) + len(body)} lines to {args.out}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
