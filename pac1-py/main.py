import json
import os
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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
from llm import LLM_BACKEND

BITGN_URL = os.getenv("BENCHMARK_HOST") or "https://api.bitgn.com"
BENCHMARK_ID = os.getenv("BENCHMARK_ID") or "bitgn/pac1-dev"
MODEL_ID = os.getenv("MODEL_ID") or "Qwen/Qwen3-235B-A22B-Thinking-2507"

TASK_CACHE_PATH = Path(__file__).parent.parent / "docs" / "task_cache.json"
RUN_HISTORY_PATH = Path(__file__).parent.parent / "docs" / "run_history.json"
PROGRESS_PATH = Path(__file__).parent / ".run_progress.json"

# Pricing per M tokens — Nebius/OpenRouter: (input, output); Anthropic: (in, out, cache_write, cache_read)
_RATES_NEBIUS = {
    "Qwen3-235B": (0.20, 0.80),
    "DeepSeek-R1": (0.80, 2.40),
    "DeepSeek-V3": (0.50, 1.50),
}
_RATES_OPENROUTER = {
    "qwen3.6-plus:free": (0, 0),
    "qwen3.6-plus": (0.30, 1.20),
}
_RATES_ANTHROPIC = {
    "haiku": (1, 5, 1.25, 0.1),
    "sonnet": (3, 15, 3.75, 0.3),
    "opus": (15, 75, 18.75, 1.5),
}

CLI_RED, CLI_GREEN, CLI_BLUE, CLI_CLR = "\x1b[31m", "\x1b[32m", "\x1b[34m", "\x1b[0m"


def _save_task_cache(entry: dict) -> None:
    existing = {}
    if TASK_CACHE_PATH.exists():
        try:
            existing = json.loads(TASK_CACHE_PATH.read_text())
        except Exception:
            pass
    existing.update(entry)
    TASK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TASK_CACHE_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False))


def _save_progress(scores: list, task_data: dict) -> None:
    PROGRESS_PATH.write_text(json.dumps({"scores": scores, "task_data": task_data}))


def _load_progress() -> tuple[list, dict]:
    if PROGRESS_PATH.exists():
        try:
            p = json.loads(PROGRESS_PATH.read_text())
            return p.get("scores", []), p.get("task_data", {})
        except Exception:
            pass
    return [], {}


def _collect_usage() -> dict | None:
    """Collect usage stats from the active LLM backend, return None if no calls made."""
    if LLM_BACKEND == "nebius":
        from llm import get_nebius_usage

        u = get_nebius_usage()
        if not u["calls"]:
            return None
        r_in, r_out = next((v for k, v in _RATES_NEBIUS.items() if k in MODEL_ID), (0.20, 0.80))
        cost = (u["input_tokens"] * r_in + u["output_tokens"] * r_out) / 1_000_000
        return {**u, "cost_usd": round(cost, 4)}
    if LLM_BACKEND == "openrouter":
        from llm import get_openrouter_usage

        u = get_openrouter_usage()
        if not u["calls"]:
            return None
        r_in, r_out = next((v for k, v in _RATES_OPENROUTER.items() if k in MODEL_ID), (0, 0))
        cost = (u["input_tokens"] * r_in + u["output_tokens"] * r_out) / 1_000_000
        return {**u, "cost_usd": round(cost, 4)}
    if LLM_BACKEND == "api":
        from llm import get_api_usage

        u = get_api_usage()
        if not u["calls"]:
            return None
        r = next((v for k, v in _RATES_ANTHROPIC.items() if k in MODEL_ID), (3, 15, 3.75, 0.3))
        cost = (
            u["input_tokens"] * r[0]
            + u["output_tokens"] * r[1]
            + u.get("cache_creation_input_tokens", 0) * r[2]
            + u.get("cache_read_input_tokens", 0) * r[3]
        ) / 1_000_000
        return {**u, "cost_usd": round(cost, 4)}
    return None


def _append_run_history(task_data: dict, scores: list) -> None:
    if not scores:
        return
    tasks_passed = sum(1 for _, s in scores if s >= 1.0)
    tasks_total = len(scores)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "model": MODEL_ID,
        "backend": LLM_BACKEND,
        "score_pct": round(tasks_passed / tasks_total * 100.0, 2),
        "tasks_passed": tasks_passed,
        "tasks_total": tasks_total,
        "tasks": {
            tid: {"score": td["score"], "score_detail": td.get("score_detail", [])}
            for tid, td in task_data.items()
        },
    }
    usage_record = _collect_usage()
    if usage_record:
        record["api_usage"] = usage_record
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


EVAL_DIR = Path(__file__).parent.parent / "docs" / "eval"


def _generate_eval_report(task_data: dict, scores: list) -> None:
    """Auto-generate eval report comparing current run vs previous."""
    if not scores:
        return
    history = []
    if RUN_HISTORY_PATH.exists():
        try:
            history = json.loads(RUN_HISTORY_PATH.read_text())
        except Exception:
            pass
    if len(history) < 2:
        return  # need at least 2 runs to compare

    current = history[-1]
    previous = history[-2]
    cur_tasks = current.get("tasks", {})
    prev_tasks = previous.get("tasks", {})
    all_ids = sorted(set(cur_tasks) | set(prev_tasks))

    wins, losses, stable_pass, stable_fail = [], [], [], []
    # Only compare tasks present in BOTH runs (partial runs skip missing tasks)
    common_ids = sorted(set(cur_tasks) & set(prev_tasks))
    cur_only = sorted(set(cur_tasks) - set(prev_tasks))
    for tid in common_ids:
        cur_s = cur_tasks[tid].get("score", -1)
        prev_s = prev_tasks[tid].get("score", -1)
        if cur_s >= 1 and prev_s < 1:
            wins.append(tid)
        elif cur_s < 1 and prev_s >= 1:
            losses.append(tid)
        elif cur_s >= 1:
            stable_pass.append(tid)
        else:
            stable_fail.append(tid)
    for tid in cur_only:
        (stable_pass if cur_tasks[tid].get("score", 0) >= 1 else stable_fail).append(tid)

    ts = datetime.now(UTC).strftime("%Y-%m-%d-%H")
    usage = current.get("api_usage", {})
    lines = [
        f"# Eval Report — {ts}",
        "",
        f"**Model:** `{current.get('model', '?')}`  ",
        f"**Backend:** `{current.get('backend', '?')}`  ",
        f"**Score:** {current['tasks_passed']}/{current['tasks_total']} "
        f"({current['score_pct']}%)  ",
        f"**Previous:** {previous['tasks_passed']}/{previous['tasks_total']} "
        f"({previous['score_pct']}%)  ",
        f"**Delta:** {current['score_pct'] - previous['score_pct']:+.1f}pp  ",
    ]
    if usage:
        lines.append(
            f"**API:** {usage.get('calls', 0)} calls, "
            f"in={usage.get('input_tokens', 0):,} out={usage.get('output_tokens', 0):,}, "
            f"${usage.get('cost_usd', 0):.2f}  "
        )
    lines += ["", "## Improvements" if wins else "## Improvements: none", ""]
    for tid in wins:
        detail = " | ".join(cur_tasks[tid].get("score_detail", [])[:2])
        lines.append(f"- **{tid}**: 0→1 {detail}")
    lines += ["", "## Regressions" if losses else "## Regressions: none", ""]
    for tid in losses:
        detail = " | ".join(cur_tasks[tid].get("score_detail", [])[:2])
        lines.append(f"- **{tid}**: 1→0 {detail}")
    lines += ["", "## Still Failing", ""]
    for tid in stable_fail:
        detail = " | ".join(cur_tasks.get(tid, {}).get("score_detail", [])[:2])
        lines.append(f"- {tid}: {detail}")
    lines += [
        "",
        "## Passing",
        "",
        ", ".join(stable_pass + wins),
        "",
        "## Per-Task Scores",
        "",
    ]
    for tid in sorted(cur_tasks):
        cur_s = cur_tasks[tid].get("score", -1)
        mark = "PASS" if cur_s >= 1 else "FAIL"
        lines.append(f"| {tid} | {cur_s:.2f} | {mark} |")

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    report_path = EVAL_DIR / f"run-{ts}.md"
    report_path.write_text("\n".join(lines) + "\n")
    print(f"{CLI_GREEN}Eval report: {report_path}{CLI_CLR}")


def _run_single_task(client, benchmark_id: str, task) -> tuple[str, dict] | None:
    """Run one task end-to-end. Returns (task_id, data_dict) or None on error."""
    tid = task.task_id
    print(f"{'=' * 30} Starting task: {tid} {'=' * 30}")
    trial = client.start_playground(StartPlaygroundRequest(benchmark_id=benchmark_id, task_id=tid))
    print(f"{CLI_BLUE}{trial.instruction}{CLI_CLR}\n{'-' * 80}")
    try:
        run_agent(MODEL_ID, trial.harness_url, trial.instruction)
    except Exception as exc:
        print(exc)
    result = client.end_trial(EndTrialRequest(trial_id=trial.trial_id))
    if result.score >= 0:
        data = {
            "instruction": trial.instruction,
            "score": result.score,
            "score_detail": list(result.score_detail),
            "model": MODEL_ID,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        style = CLI_GREEN if result.score == 1 else CLI_RED
        explain = textwrap.indent("\n".join(result.score_detail), "  ")
        print(f"\n{style}Score: {result.score:0.2f}\n{explain}\n{CLI_CLR}")
        return tid, data
    return None


def main() -> None:
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    args = sys.argv[1:]
    resume = "--resume" in args
    parallel = 1
    task_filter = []
    for a in args:
        if a.startswith("--parallel"):
            parallel = int(a.split("=")[1]) if "=" in a else int(args[args.index(a) + 1])
        elif not a.startswith("--"):
            task_filter.append(a)

    if resume:
        scores, task_data = _load_progress()
        completed = {tid for tid, _ in scores}
        print(f"Resuming: {len(completed)} tasks done")
    else:
        scores, task_data, completed = [], {}, set()
        PROGRESS_PATH.unlink(missing_ok=True)

    lock = threading.Lock()

    try:
        client = HarnessServiceClientSync(BITGN_URL)
        print("Connecting to BitGN", client.status(StatusRequest()))
        res = client.get_benchmark(GetBenchmarkRequest(benchmark_id=BENCHMARK_ID))
        print(
            f"{EvalPolicy.Name(res.policy)} benchmark: {res.benchmark_id} "
            f"with {len(res.tasks)} tasks.\n{CLI_GREEN}{res.description}{CLI_CLR}"
        )

        pending = [
            t
            for t in res.tasks
            if t.task_id not in completed and (not task_filter or t.task_id in task_filter)
        ]

        if parallel <= 1:
            for task in pending:
                out = _run_single_task(client, BENCHMARK_ID, task)
                if out:
                    tid, data = out
                    scores.append((tid, data["score"]))
                    task_data[tid] = data
                    _save_task_cache({tid: data})
                    _save_progress(scores, task_data)
        else:
            print(f"{CLI_BLUE}Parallel mode: {parallel} workers{CLI_CLR}")
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                futures = {
                    pool.submit(_run_single_task, client, BENCHMARK_ID, task): task
                    for task in pending
                }
                for future in as_completed(futures):
                    out = future.result()
                    if out:
                        tid, data = out
                        with lock:
                            scores.append((tid, data["score"]))
                            task_data[tid] = data
                            _save_task_cache({tid: data})
                            _save_progress(scores, task_data)

    except ConnectError as exc:
        print(f"{exc.code}: {exc.message}")
    except KeyboardInterrupt:
        print(f"{CLI_RED}Interrupted — progress saved, use --resume to continue{CLI_CLR}")

    if task_data:
        _append_run_history(task_data, scores)
        _generate_eval_report(task_data, scores)
        PROGRESS_PATH.unlink(missing_ok=True)

    if scores:
        for task_id, score in sorted(scores):
            style = CLI_GREEN if score == 1 else CLI_RED
            print(f"{task_id}: {style}{score:0.2f}{CLI_CLR}")
        total = sum(s for _, s in scores) / len(scores) * 100.0
        print(f"FINAL: {total:0.2f}%")

    u = _collect_usage()
    if u:
        print(
            f"API: {u['calls']} calls | in={u['input_tokens']:,} out={u['output_tokens']:,} | ${u['cost_usd']:.2f}"
        )


if __name__ == "__main__":
    main()
