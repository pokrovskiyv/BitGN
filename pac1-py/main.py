import json
import os
import textwrap
from datetime import UTC, datetime
from pathlib import Path

from bitgn.harness_connect import HarnessServiceClientSync
from bitgn.harness_pb2 import (
    EndTrialRequest,
    EvalPolicy,
    GetBenchmarkRequest,
    StartPlaygroundRequest,
    StatusRequest,
)
from connectrpc.errors import ConnectError

from agent import run_agent

BITGN_URL = os.getenv("BENCHMARK_HOST") or "https://api.bitgn.com"
BENCHMARK_ID = os.getenv("BENCHMARK_ID") or "bitgn/pac1-dev"
MODEL_ID = os.getenv("MODEL_ID") or "claude-sonnet-4-6"

TASK_CACHE_PATH = Path(__file__).parent.parent / "docs" / "task_cache.json"
RUN_HISTORY_PATH = Path(__file__).parent.parent / "docs" / "run_history.json"

CLI_RED = "\x1b[31m"
CLI_GREEN = "\x1b[32m"
CLI_CLR = "\x1b[0m"
CLI_BLUE = "\x1b[34m"


def _save_task_cache(task_data: dict) -> None:
    """Persist task instructions and score details to docs/task_cache.json."""
    existing = {}
    if TASK_CACHE_PATH.exists():
        try:
            existing = json.loads(TASK_CACHE_PATH.read_text())
        except Exception:
            pass
    existing.update(task_data)
    TASK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TASK_CACHE_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False))


def _append_run_history(task_data: dict, scores: list) -> None:
    """Append a complete run record to docs/run_history.json (never overwrites)."""
    if not scores:
        return

    tasks_passed = sum(1 for _, s in scores if s >= 1.0)
    tasks_total = len(scores)
    score_pct = round(tasks_passed / tasks_total * 100.0, 2) if tasks_total else 0.0

    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "model": MODEL_ID,
        "score_pct": score_pct,
        "tasks_passed": tasks_passed,
        "tasks_total": tasks_total,
        "tasks": {
            task_id: {
                "score": td["score"],
                "score_detail": td.get("score_detail", []),
            }
            for task_id, td in task_data.items()
        },
    }

    history = []
    if RUN_HISTORY_PATH.exists():
        try:
            history = json.loads(RUN_HISTORY_PATH.read_text())
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []

    history.append(record)
    RUN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUN_HISTORY_PATH.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    print(f"Run history: {len(history)} records in docs/run_history.json")


def main() -> None:
    task_filter = os.sys.argv[1:]

    scores = []
    task_data: dict = {}
    try:
        client = HarnessServiceClientSync(BITGN_URL)
        print("Connecting to BitGN", client.status(StatusRequest()))
        res = client.get_benchmark(GetBenchmarkRequest(benchmark_id=BENCHMARK_ID))
        print(
            f"{EvalPolicy.Name(res.policy)} benchmark: {res.benchmark_id} "
            f"with {len(res.tasks)} tasks.\n{CLI_GREEN}{res.description}{CLI_CLR}"
        )

        for task in res.tasks:
            if task_filter and task.task_id not in task_filter:
                continue

            print(f"{'=' * 30} Starting task: {task.task_id} {'=' * 30}")
            trial = client.start_playground(
                StartPlaygroundRequest(
                    benchmark_id=BENCHMARK_ID,
                    task_id=task.task_id,
                )
            )

            print(f"{CLI_BLUE}{trial.instruction}{CLI_CLR}\n{'-' * 80}")

            try:
                run_agent(MODEL_ID, trial.harness_url, trial.instruction)
            except Exception as exc:
                print(exc)

            result = client.end_trial(EndTrialRequest(trial_id=trial.trial_id))
            if result.score >= 0:
                scores.append((task.task_id, result.score))
                task_data[task.task_id] = {
                    "instruction": trial.instruction,
                    "score": result.score,
                    "score_detail": list(result.score_detail),
                    "model": MODEL_ID,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                style = CLI_GREEN if result.score == 1 else CLI_RED
                explain = textwrap.indent("\n".join(result.score_detail), "  ")
                print(f"\n{style}Score: {result.score:0.2f}\n{explain}\n{CLI_CLR}")

    except ConnectError as exc:
        print(f"{exc.code}: {exc.message}")
    except KeyboardInterrupt:
        print(f"{CLI_RED}Interrupted{CLI_CLR}")

    if task_data:
        _save_task_cache(task_data)
        _append_run_history(task_data, scores)

    if scores:
        for task_id, score in scores:
            style = CLI_GREEN if score == 1 else CLI_RED
            print(f"{task_id}: {style}{score:0.2f}{CLI_CLR}")

        total = sum(score for _, score in scores) / len(scores) * 100.0
        print(f"FINAL: {total:0.2f}%")


if __name__ == "__main__":
    main()
