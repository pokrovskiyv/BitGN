"""Generic agent loop, parameterized by DomainProtocol.

Extracted from agent.py to decouple the LLM call + step loop from any
specific domain (filesystem, messenger, etc.). All domain-specific
behaviour is injected via the DomainProtocol interface.
"""

import time

from connectrpc.errors import ConnectError

from classify import classify_task
from defend import scan_content
from domain_protocol import DomainProtocol
from environment import EnvironmentModel, extract_environment
from llm import call_llm
from strategy import decide_strategy
from verify import StagnationDetector, WriteTracker, action_gate_message

CLI_RED = "\x1b[31m"
CLI_GREEN = "\x1b[32m"
CLI_CLR = "\x1b[0m"
CLI_BLUE = "\x1b[34m"
CLI_YELLOW = "\x1b[33m"


# ── Generic agent loop ────────────────────────────────────────────────────


def run_agent_loop(
    model: str, harness_url: str, task_text: str, domain: DomainProtocol
) -> str | None:
    client = domain.create_client(harness_url)

    # ── PERCEIVE ──────────────────────────────────────────────────
    messages = domain.boot_messages(client)

    # Extract environment model from AGENTS.md (second boot message)
    agents_md_text = messages[1]["content"] if len(messages) > 1 else ""
    env_model = extract_environment(agents_md_text)

    # ── CLASSIFY + DECIDE ─────────────────────────────────────────
    task_warnings = scan_content(task_text)
    classification = classify_task(task_text, task_warnings)
    strategy = decide_strategy(classification)

    print(
        f"{CLI_BLUE}CLASSIFY{CLI_CLR}: {classification.task_type} "
        f"threat={classification.threat_level} "
        f"max_steps={strategy.max_steps} "
        f"posture={strategy.security_posture}"
    )

    messages.append({"role": "user", "content": task_text})

    # ── RUN ────────────────────────────────────────────────────────
    tracker = WriteTracker()
    stagnation = StagnationDetector()
    nextstep_type = domain.nextstep_type

    for i in range(strategy.max_steps):
        print(f"Next step_{i + 1}... ", end="")
        started = time.time()

        job = None
        for attempt in range(3):
            try:
                retry_msgs = messages
                if attempt > 0:
                    retry_msgs = messages + [
                        {
                            "role": "user",
                            "content": (
                                "FORMAT CORRECTION: Your previous response was not valid JSON. "
                                'You MUST respond with EXACTLY this structure (action goes INSIDE "function", '
                                "not at the top level):\n"
                                '{\n  "current_state": "<one sentence>",\n'
                                '  "plan_remaining_steps_brief": ["<next step>"],\n'
                                '  "task_completed": false,\n'
                                '  "function": { <your action object with tool field here> }\n}\n'
                                "No markdown code fences. No explanation. Only the raw JSON object."
                            ),
                        }
                    ]
                job = call_llm(strategy.system_prompt, retry_msgs, model, nextstep_type)
                break
            except Exception as exc:
                print(f"LLM parse error (attempt {attempt + 1}/3): {exc}")
                if attempt == 2:
                    raise
        elapsed_ms = int((time.time() - started) * 1000)
        print(job.plan_remaining_steps_brief[0], f"({elapsed_ms} ms)\n  {job.function}")

        messages.append({"role": "assistant", "content": job.model_dump_json()})
        cmd = job.function

        # ── DEFEND: action-gate destructive or sensitive ops ────────
        tool_name = getattr(cmd, "tool", "")
        handler = domain.tool_registry.get(tool_name)
        cmd_path = getattr(cmd, "path", getattr(cmd, "from_name", ""))
        is_sensitive_write = tool_name == "write" and any(
            cmd_path.rstrip("/").endswith(s) for s in env_model.sensitive_paths
        )
        if ((handler and handler.destructive) or is_sensitive_write) and not domain.is_completion(
            cmd
        ):
            gate_msg = action_gate_message(tool_name, cmd_path)
            print(f"{CLI_YELLOW}GATE{CLI_CLR}: {gate_msg}")
            messages.append({"role": "user", "content": gate_msg})

        # ── PRE-SUBMIT VERIFICATION (before dispatch) ────────────
        if domain.is_completion(cmd):
            unverified = tracker.unverified_writes()
            if strategy.pre_submit_verification and unverified:
                paths_str = ", ".join(sorted(unverified))
                print(f"{CLI_YELLOW}HOLD{CLI_CLR}: unverified writes: {paths_str}")
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"HOLD: You wrote to [{paths_str}] but never re-read to verify. "
                            f"Read each file to confirm writes succeeded before completing."
                        ),
                    }
                )
                continue  # skip dispatch, force re-read first

            # Auto-merge consulted paths into grounding_refs before submission
            all_paths = tracker.all_consulted_paths()
            merged = list(cmd.grounding_refs or [])
            for p in sorted(all_paths):
                if p not in merged:
                    merged.append(p)
            cmd = cmd.model_copy(update={"grounding_refs": merged})

        # ── DISPATCH ──────────────────────────────────────────────
        try:
            result = domain.dispatch(client, cmd)
            txt = domain.format_result(cmd, result)
            print(f"{CLI_GREEN}OUT{CLI_CLR}: {txt}")
        except ConnectError as exc:
            txt = str(exc.message)
            print(f"{CLI_RED}ERR {exc.code}: {exc.message}{CLI_CLR}")
            if "not_found" in txt.lower():
                txt += "\nHint: use 'tree' or 'find' to locate the correct path."
            elif "already_exists" in txt.lower():
                txt += "\nHint: read the existing file first, then decide how to proceed."

        # ── COMPLETION (after dispatch) ───────────────────────────
        if domain.is_completion(cmd):
            outcome = domain.completion_outcome(cmd)
            status = CLI_GREEN if outcome == "OUTCOME_OK" else CLI_YELLOW
            print(f"{status}agent {outcome}{CLI_CLR}. Summary:")
            for item in cmd.completed_steps_laconic:
                print(f"- {item}")
            print(f"\n{CLI_BLUE}AGENT SUMMARY: {cmd.message}{CLI_CLR}")
            if cmd.grounding_refs:
                for ref in cmd.grounding_refs:
                    print(f"- {CLI_BLUE}{ref}{CLI_CLR}")
            return outcome

        # ── TRACKING ──────────────────────────────────────────────
        if hasattr(cmd, "path"):
            if tool_name == "write":
                tracker.record_write(cmd.path)
            elif tool_name == "read":
                tracker.record_read(cmd.path)

        tool_args = str(getattr(cmd, "path", getattr(cmd, "pattern", "")))
        stagnation.record(tool_name, tool_args)
        if stagnation.is_stagnant() or stagnation.is_oscillating():
            nudge = stagnation.nudge_message()
            print(f"{CLI_YELLOW}STAGNATION{CLI_CLR}: {nudge}")
            txt += f"\n{nudge}"

        # ── DEFEND: scan tool output ──────────────────────────────
        content_warnings = scan_content(txt)
        if content_warnings:
            warning_text = "SECURITY WARNING: " + "; ".join(content_warnings)
            print(f"{CLI_YELLOW}DEFEND{CLI_CLR}: {warning_text}")
            txt += f"\n{warning_text}"

        messages.append({"role": "user", "content": domain.wrap_output(txt)})

    return None
