import json
import os
import re
import sys
import textwrap
import uuid
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

# Layered .env loading: base .env first, then .env.final (or
# .env.final.example as fallback) overrides when RUN_PROFILE=final. Without
# this layering, dev values in .env (e.g. LLM_BACKEND=nebius, MODEL_ID=Qwen3)
# would silently override the final profile defaults in settings.py and the
# Sonnet+Haiku scaffold would be bypassed at runtime.
_EXTERNAL_ENV = dict(os.environ)
load_dotenv()
if os.getenv("RUN_PROFILE", "").strip().lower() == "final":
    _here = Path(__file__).parent
    _final_env = _here / ".env.final"
    if not _final_env.exists():
        _final_env = _here / ".env.final.example"
    if _final_env.exists():
        load_dotenv(_final_env, override=True)
        os.environ.update(_EXTERNAL_ENV)
        print(f"[final-profile] loaded {_final_env.name} (overrides applied)")
    else:
        print("[final-profile] WARNING: no .env.final or .env.final.example found")

from bitgn.harness_pb2 import (
    EndTrialRequest,
    EvalPolicy,
    GetBenchmarkRequest,
    RunState,
    StartRunRequest,
    StartTrialRequest,
    StatusRequest,
    SubmitRunRequest,
)
from connectrpc.errors import ConnectError

from agent import run_agent
from bitgn_client import BITGN_API_KEY, make_harness_client
from llm import LLM_BACKEND
from second_opinion import VERIFIER_BACKEND, VERIFIER_MODEL, get_verifier_usage
from settings import SETTINGS

BITGN_URL = SETTINGS.benchmark_host
BENCHMARK_ID = SETTINGS.benchmark_id
MODEL_ID = SETTINGS.primary_model

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


def _task_sort_key(task_id: str) -> tuple[int, str]:
    m = re.search(r"(\d+)$", task_id)
    return (int(m.group(1)), task_id) if m else (10**9, task_id)


def _apply_split(tasks: list, split: str) -> list:
    """Apply train/holdout split — mirror of BitgnBenchmarkAdapter.get_tasks.

    Preserves server-returned task order for consistency with evolve.py.
    train = first 80%, holdout = last 20% (at least 1 task). "all" = no split.
    Kept inline (not reused from bitgn_benchmark.py) because that adapter
    returns agent_evolve Task objects, while main.py works with Protobuf tasks.
    """
    if split == "all":
        return list(tasks)
    if split not in ("train", "holdout"):
        raise ValueError(f"Unknown split {split!r}; expected 'all', 'train', or 'holdout'")
    if not tasks:
        return []
    n_holdout = max(1, int(len(tasks) * 0.2))
    return list(tasks[-n_holdout:]) if split == "holdout" else list(tasks[:-n_holdout])


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
    if LLM_BACKEND == "codex_cli":
        from llm import get_codex_cli_usage

        u = get_codex_cli_usage()
        if not u["calls"]:
            return None
        return {**u, "cost_usd": 0}
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


def _collect_verifier_usage() -> dict | None:
    usage = get_verifier_usage()
    if not usage["calls"]:
        return None
    if VERIFIER_BACKEND == "codex_cli":
        return {**usage, "cost_usd": 0}
    r_in, r_out, _, _ = next(
        (v for k, v in _RATES_ANTHROPIC.items() if k in VERIFIER_MODEL),
        (1, 5, 1.25, 0.1),
    )
    cost = (usage["input_tokens"] * r_in + usage["output_tokens"] * r_out) / 1_000_000
    return {**usage, "cost_usd": round(cost, 4)}


def _append_run_history(
    task_data: dict,
    scores: list,
    *,
    benchmark_id: str,
    benchmark_task_count: int,
    is_partial_run: bool,
    split: str,
    split_task_count: int,
) -> None:
    if not scores:
        return
    tasks_passed = sum(1 for _, s in scores if s >= 1.0)
    tasks_total = len(scores)
    record = {
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "benchmark_id": benchmark_id,
        "benchmark_task_count": benchmark_task_count,
        "split": split,
        "split_task_count": split_task_count,
        "is_partial_run": is_partial_run,
        "model": MODEL_ID,
        "verifier_model": VERIFIER_MODEL,
        "backend": LLM_BACKEND,
        "score_pct": round(tasks_passed / tasks_total * 100.0, 2),
        "tasks_passed": tasks_passed,
        "tasks_total": tasks_total,
        "tasks": {
            tid: {
                "score": td["score"],
                "score_detail": td.get("score_detail", []),
                "metrics": td.get("metrics", {}),
            }
            for tid, td in task_data.items()
        },
    }
    usage_record = _collect_usage()
    if usage_record:
        record["api_usage"] = usage_record
    verifier_usage = _collect_verifier_usage()
    if verifier_usage:
        record["verifier_usage"] = verifier_usage
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

    # Auto-recompile knowledge wiki after each run
    wiki_script = Path(__file__).parent.parent / "compile_wiki.py"
    if wiki_script.exists():
        import subprocess

        subprocess.run(
            [sys.executable, str(wiki_script)],
            cwd=str(wiki_script.parent),
            capture_output=True,
            timeout=10,
        )


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
    current_split = current.get("split", "all")
    current_partial = bool(current.get("is_partial_run", False))
    # Compare against the most recent previous run with the SAME split.
    # Otherwise a train-split run would diff against a full run and produce
    # a misleading -20pp delta from tasks that simply aren't in the split.
    previous = None
    for record in reversed(history[:-1]):
        if (
            record.get("split", "all") == current_split
            and bool(record.get("is_partial_run", False)) == current_partial
        ):
            previous = record
            break
    if previous is None:
        return  # no comparable previous run for this split
    cur_tasks = current.get("tasks", {})
    prev_tasks = previous.get("tasks", {})
    wins, losses, stable_pass, stable_fail = [], [], [], []
    # Only compare tasks present in BOTH runs (partial runs skip missing tasks)
    common_ids = sorted(set(cur_tasks) & set(prev_tasks), key=_task_sort_key)
    cur_only = sorted(set(cur_tasks) - set(prev_tasks), key=_task_sort_key)
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
        f"**Split:** `{current_split}` "
        f"({current.get('split_task_count', current['tasks_total'])} tasks)  ",
        f"**Model:** `{current.get('model', '?')}`  ",
        f"**Verifier:** `{current.get('verifier_model', '?')}`  ",
        f"**Backend:** `{current.get('backend', '?')}`  ",
        f"**Score:** {current['tasks_passed']}/{current['tasks_total']} "
        f"({current['score_pct']}%)  ",
        f"**Previous:** {previous['tasks_passed']}/{previous['tasks_total']} "
        f"({previous['score_pct']}%) "
        f"[split=`{previous.get('split', 'all')}`]  ",
        f"**Delta:** {current['score_pct'] - previous['score_pct']:+.1f}pp  ",
    ]
    if usage:
        lines.append(
            f"**API:** {usage.get('calls', 0)} calls, "
            f"in={usage.get('input_tokens', 0):,} out={usage.get('output_tokens', 0):,}, "
            f"${usage.get('cost_usd', 0):.2f}  "
        )
    verifier_usage = current.get("verifier_usage", {})
    if verifier_usage:
        lines.append(
            f"**Verifier API:** {verifier_usage.get('calls', 0)} calls, "
            f"in={verifier_usage.get('input_tokens', 0):,} "
            f"out={verifier_usage.get('output_tokens', 0):,}, "
            f"${verifier_usage.get('cost_usd', 0):.2f}  "
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
    for tid in sorted(cur_tasks, key=_task_sort_key):
        cur_s = cur_tasks[tid].get("score", -1)
        mark = "PASS" if cur_s >= 1 else "FAIL"
        lines.append(f"| {tid} | {cur_s:.2f} | {mark} |")

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    report_path = EVAL_DIR / f"run-{ts}.md"
    report_path.write_text("\n".join(lines) + "\n")
    print(f"{CLI_GREEN}Eval report: {report_path}{CLI_CLR}")


def _run_single_task(
    client,
    trial_id: str,
    allowed_task_ids: set[str] | None,
    completed: set[str],
) -> tuple[str, dict] | None:
    """Start one trial, run the agent, end the trial.

    Skips (returns ``None`` without executing the agent) if the trial's
    ``task_id`` is not in ``allowed_task_ids`` or is already in ``completed``.
    Skipped trials are left in RUNNING state — ``SubmitRun(force=True)`` will
    handle them at the end of the run.
    """
    from llm import get_usage_snapshot

    trial = client.start_trial(StartTrialRequest(trial_id=trial_id))
    tid = trial.task_id

    if allowed_task_ids is not None and tid not in allowed_task_ids:
        return None  # not in split/filter — skip
    if tid in completed:
        return None  # --resume skip

    print(f"{'=' * 30} Starting task: {tid} {'=' * 30}")
    print(f"{CLI_BLUE}{trial.instruction}{CLI_CLR}\n{'-' * 80}")
    usage_before = get_usage_snapshot()
    agent_result = None
    try:
        agent_result = run_agent(MODEL_ID, trial.harness_url, trial.instruction)
    except Exception as exc:
        print(exc)
    usage_after = get_usage_snapshot()
    result = client.end_trial(EndTrialRequest(trial_id=trial.trial_id))
    if result.score >= 0:
        prompt_tok = usage_after.get("input_tokens", 0) - usage_before.get("input_tokens", 0)
        compl_tok = usage_after.get("output_tokens", 0) - usage_before.get("output_tokens", 0)
        metrics = {
            "total_time_ms": agent_result.total_time_ms if agent_result else 0,
            "step_count": agent_result.step_count if agent_result else 0,
            "tool_call_count": agent_result.tool_call_count if agent_result else 0,
            "prompt_tokens": prompt_tok,
            "completion_tokens": compl_tok,
            "steps": agent_result.steps_detail if agent_result else [],
            "verifier_verdict": agent_result.verifier_verdict if agent_result else None,
        }
        data = {
            "instruction": trial.instruction,
            "score": result.score,
            "score_detail": list(result.score_detail),
            "model": MODEL_ID,
            "verifier_model": VERIFIER_MODEL,
            "timestamp": datetime.now(UTC).isoformat(),
            "metrics": metrics,
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
    parallel = SETTINGS.parallel_workers
    split = "all"
    task_filter = []
    for a in args:
        if a.startswith("--parallel"):
            parallel = int(a.split("=")[1]) if "=" in a else int(args[args.index(a) + 1])
        elif a.startswith("--split"):
            split = a.split("=")[1] if "=" in a else args[args.index(a) + 1]
        elif not a.startswith("--"):
            task_filter.append(a)
    if split not in ("all", "train", "holdout"):
        print(f"{CLI_RED}Unknown --split={split!r}; expected all|train|holdout{CLI_CLR}")
        sys.exit(2)

    if resume:
        scores, task_data = _load_progress()
        completed = {tid for tid, _ in scores}
        print(f"Resuming: {len(completed)} tasks done")
    else:
        scores, task_data, completed = [], {}, set()
        PROGRESS_PATH.unlink(missing_ok=True)

    lock = threading.Lock()
    run = None
    benchmark_task_count = 0
    split_task_count = 0
    is_partial_run = False

    try:
        client = make_harness_client(BITGN_URL)
        print("Connecting to BitGN", client.status(StatusRequest()))
        res = client.get_benchmark(GetBenchmarkRequest(benchmark_id=BENCHMARK_ID))
        print(
            f"{EvalPolicy.Name(res.policy)} benchmark: {res.benchmark_id} "
            f"with {len(res.tasks)} tasks.\n{CLI_GREEN}{res.description}{CLI_CLR}"
        )

        benchmark_task_count = len(res.tasks)
        split_tasks = _apply_split(list(res.tasks), split)
        split_task_count = len(split_tasks)
        if split != "all":
            split_ids = sorted((t.task_id for t in split_tasks), key=_task_sort_key)
            print(
                f"{CLI_BLUE}Split: {split!r} — "
                f"{split_task_count}/{benchmark_task_count} tasks "
                f"[{', '.join(split_ids)}]{CLI_CLR}"
            )
        if task_filter:
            split_id_set = {t.task_id for t in split_tasks}
            unknown_in_split = [tf for tf in task_filter if tf not in split_id_set]
            if unknown_in_split:
                print(
                    f"{CLI_RED}WARNING: task filter contains ids not in "
                    f"{split!r} split: {unknown_in_split}{CLI_CLR}"
                )

        # Build allowed_task_ids (intersection of split + task_filter).
        # None means "allow everything" — the competition / full-run case.
        if split == "all" and not task_filter:
            allowed_task_ids: set[str] | None = None
        else:
            split_id_set = {t.task_id for t in split_tasks}
            if task_filter:
                allowed_task_ids = split_id_set & set(task_filter)
            else:
                allowed_task_ids = split_id_set

        is_partial_run = (
            allowed_task_ids is not None and len(allowed_task_ids) < benchmark_task_count
        )

        # StartRun creates the competition session. Works for both open
        # (pac1-dev) and blind (pac1-prod) benchmarks — upstream unified flow.
        # api_key goes in the request body, not an HTTP header.
        run_name = f"pac1-py-{SETTINGS.run_profile}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
        run = client.start_run(
            StartRunRequest(
                benchmark_id=BENCHMARK_ID,
                name=run_name,
                api_key=BITGN_API_KEY,
            )
        )
        print(
            f"{CLI_BLUE}Run started: run_id={run.run_id} "
            f"trials={len(run.trial_ids)} name={run_name!r}{CLI_CLR}"
        )

        try:
            if parallel <= 1:
                for trial_id in run.trial_ids:
                    try:
                        out = _run_single_task(client, trial_id, allowed_task_ids, completed)
                    except Exception as exc:
                        print(f"{CLI_RED}Task worker failed: {exc}{CLI_CLR}")
                        continue
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
                        pool.submit(
                            _run_single_task, client, trial_id, allowed_task_ids, completed
                        ): trial_id
                        for trial_id in run.trial_ids
                    }
                    for future in as_completed(futures):
                        try:
                            out = future.result()
                        except Exception as exc:
                            print(f"{CLI_RED}Task worker failed: {exc}{CLI_CLR}")
                            continue
                        if out:
                            tid, data = out
                            with lock:
                                scores.append((tid, data["score"]))
                                task_data[tid] = data
                                _save_task_cache({tid: data})
                                _save_progress(scores, task_data)
        finally:
            # Always submit the run — even on partial execution or interrupt.
            # force=True tells the server to accept whatever trials have ended;
            # skipped / still-RUNNING trials get scored as 0 or errored.
            if run is not None:
                print(f"{CLI_BLUE}Submitting run {run.run_id}...{CLI_CLR}")
                try:
                    submit_res = client.submit_run(SubmitRunRequest(run_id=run.run_id, force=True))
                    print(
                        f"{CLI_GREEN}Submitted: run_id={run.run_id} "
                        f"state={RunState.Name(submit_res.state)}{CLI_CLR}"
                    )
                except Exception as exc:
                    print(f"{CLI_RED}submit_run failed: {exc}{CLI_CLR}")

    except ConnectError as exc:
        print(f"{exc.code}: {exc.message}")
    except KeyboardInterrupt:
        run_info = f" (run_id={run.run_id})" if run is not None else ""
        print(f"{CLI_RED}Interrupted{run_info} — use --resume to continue{CLI_CLR}")

    if task_data:
        _append_run_history(
            task_data,
            scores,
            benchmark_id=BENCHMARK_ID,
            benchmark_task_count=benchmark_task_count,
            is_partial_run=is_partial_run,
            split=split,
            split_task_count=split_task_count or len(task_data),
        )
        _generate_eval_report(task_data, scores)
        PROGRESS_PATH.unlink(missing_ok=True)

    if scores:
        for task_id, score in sorted(scores, key=lambda item: _task_sort_key(item[0])):
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
