from __future__ import annotations

from pathlib import Path

from hook_utils import REPO_ROOT, emit_context, extract_file_path, read_event


CRITICAL_FILES = {
    "pac1-py/main.py",
    "pac1-py/llm.py",
    "pac1-py/second_opinion.py",
    "pac1-py/agent_loop.py",
    "pac1-py/verify.py",
    "pac1-py/strategy.py",
    "pac1-py/bitgn_benchmark.py",
    "pac1-py/evolve.py",
}


def main() -> None:
    event = read_event()
    raw_path = extract_file_path(event)
    if not raw_path:
        return

    try:
        path = Path(raw_path).resolve().relative_to(REPO_ROOT)
    except Exception:
        path = Path(raw_path)

    path_str = path.as_posix()
    if path_str not in CRITICAL_FILES and not path_str.startswith("pac1-py/workspace/prompts/"):
        return

    emit_context(
        "\n".join(
            [
                f"Critical benchmark file changed: {path_str}.",
                "Before the next full run, prefer a small regression check and then a full benchmark run.",
                "If task count or task mix changed, use `triage-benchmark-update` before a broad PCDRED cycle.",
            ]
        ),
        event_name="PostToolUse",
    )


if __name__ == "__main__":
    main()
