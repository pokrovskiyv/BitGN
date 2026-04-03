"""Generic agent loop, parameterized by DomainProtocol."""

import time
from dataclasses import dataclass

from connectrpc.errors import ConnectError

from classify import classify_task
from criteria import check_criteria, extract_criteria
from defend import scan_content
from domain_protocol import DomainProtocol
from environment import extract_environment
from hints import folder_format_hint
from llm import call_llm
from second_opinion import get_second_opinion, needs_second_opinion
from strategy import decide_strategy
from verify import (
    BUDGET_WARNING,
    StagnationDetector,
    WriteTracker,
    action_gate_message,
    merge_grounding_refs,
    outcome_evidence_message,
    pre_completion_gate,
    report_budget_exhaustion,
)


@dataclass(frozen=True)
class AgentResult:
    """Per-task metrics returned from the agent loop."""

    outcome: str | None
    total_time_ms: int
    step_count: int
    tool_call_count: int
    steps_detail: list  # [{step, tool, args, plan, planning_ms, dispatch_ms}]


CLI_RED, CLI_GREEN, CLI_BLUE, CLI_YELLOW, CLI_CLR = (
    "\x1b[31m",
    "\x1b[32m",
    "\x1b[34m",
    "\x1b[33m",
    "\x1b[0m",
)

_FMT_CORRECTION = (
    "JSON PARSE ERROR: Your previous response was not valid JSON. "
    'You MUST respond with EXACTLY this structure (action goes INSIDE "function", '
    "not at the top level):\n"
    '{\n  "current_state": "<one sentence>",\n'
    '  "plan_remaining_steps_brief": ["<step1>", "<step2>"],\n'
    '  "task_completed": false,\n'
    '  "function": { <your action object with tool field here> }\n}\n'
    "No markdown code fences. No explanation. Only the raw JSON object."
)


def run_agent_loop(
    model: str, harness_url: str, task_text: str, domain: DomainProtocol
) -> str | None:
    client = domain.create_client(harness_url)

    messages = domain.boot_messages(client)
    agents_md_text = messages[1]["content"] if len(messages) > 1 else ""
    env_model = extract_environment(agents_md_text)

    task_warnings = scan_content(task_text)
    classification = classify_task(task_text, task_warnings)
    strategy = decide_strategy(classification)

    print(
        f"{CLI_BLUE}CLASSIFY{CLI_CLR}: {classification.task_type} "
        f"threat={classification.threat_level} steps={strategy.max_steps}"
    )

    messages.append({"role": "user", "content": task_text})

    tracker = WriteTracker()
    stagnation = StagnationDetector()
    nextstep_type = domain.nextstep_type

    task_criteria = extract_criteria(task_text)  # ISC-style verifiable criteria
    cumulative_threats = 0  # T4: Crescendo defense
    outcome_challenged = False  # T1: one-shot evidence challenge
    second_opinion_done = False  # one-shot independent verifier
    completion_gate_count = 0  # pre_completion_gate attempt cap
    high_risk_gated: set[str] = set()  # paths already challenged at HIGH risk

    tool_call_count = 0
    steps_detail: list[dict] = []
    loop_started = time.time()

    for i in range(strategy.max_steps):
        if i == strategy.max_steps - 4 and not tracker._writes:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "URGENT: 4 steps remain and you have NOT written any output file. "
                        "STOP reading. Write your primary output file NOW, then report_completion."
                    ),
                }
            )
        if i == strategy.max_steps - 2:  # T6: force completion before exhaustion
            messages.append({"role": "user", "content": BUDGET_WARNING})
        print(f"Next step_{i + 1}... ", end="")
        started = time.time()

        job = None
        for attempt in range(3):
            try:
                retry_msgs = messages
                if attempt > 0:
                    retry_msgs = messages + [{"role": "user", "content": _FMT_CORRECTION}]
                job = call_llm(strategy.system_prompt, "", retry_msgs, model, nextstep_type)
                break
            except Exception as exc:
                print(f"LLM parse error (attempt {attempt + 1}/3): {exc}")
                if attempt == 2:
                    print(f"{CLI_RED}LLM FAILURE after 3 attempts{CLI_CLR}")
        if job is None:
            break
        elapsed_ms = int((time.time() - started) * 1000)
        print(job.plan_remaining_steps_brief[0], f"({elapsed_ms} ms)\n  {job.function}")

        messages.append({"role": "assistant", "content": job.model_dump_json()})
        cmd = job.function

        # ── DEFEND: action-gate destructive or sensitive ops ────────
        tool_name = getattr(cmd, "tool", "")
        handler = domain.tool_registry.get(tool_name)
        cmd_path = getattr(cmd, "path", getattr(cmd, "from_name", ""))
        is_sensitive = tool_name == "write" and any(
            cmd_path.rstrip("/").endswith(s) for s in env_model.sensitive_paths
        )
        effective_risk = handler.risk_level if handler else "low"
        if is_sensitive:
            effective_risk = "high"
        # Authorized deletes: downgrade from HIGH (blocks dispatch) to MEDIUM (warn only)
        if effective_risk == "high" and tool_name == "delete" and classification.requires_delete:
            effective_risk = "medium"
        if effective_risk != "low" and not domain.is_completion(cmd):
            gate_msg = action_gate_message(tool_name, cmd_path, risk_level=effective_risk)
            # Enrich write gates with contextual hints (format, stem)
            if tool_name == "write":
                hint = folder_format_hint(client, domain, cmd_path, tracker)
                if hint:
                    gate_msg += f"\n{hint}"
            print(f"{CLI_YELLOW}GATE{CLI_CLR}: {gate_msg}")
            messages.append({"role": "user", "content": gate_msg})
            if effective_risk == "high" and cmd_path not in high_risk_gated:
                high_risk_gated.add(cmd_path)
                continue

        # ── PRE-SUBMIT VERIFICATION (before dispatch) ────────────
        if domain.is_completion(cmd):
            unverified = tracker.unverified_writes()
            if strategy.pre_submit_verification and unverified:
                hold = f"HOLD: You wrote to [{', '.join(sorted(unverified))}] but never re-read. Verify first."
                print(f"{CLI_YELLOW}HOLD{CLI_CLR}: {hold}")
                messages.append({"role": "user", "content": hold})
                continue
            outcome = domain.completion_outcome(cmd)
            # Criteria gate: check task-extracted write/delete targets
            if task_criteria and outcome == "OUTCOME_OK":
                unmet = check_criteria(task_criteria, tracker)
                if unmet:
                    hold = f"HOLD: Unmet criteria: {'; '.join(unmet)}. Complete these before reporting OK."
                    print(f"{CLI_YELLOW}CRITERIA{CLI_CLR}: {hold}")
                    messages.append({"role": "user", "content": hold})
                    continue
            # Pre-completion gate (early-completion, inbox reads, threat count)
            if completion_gate_count < 2:
                gate_rejection = pre_completion_gate(
                    outcome,
                    tool_call_count,
                    classification.task_type,
                    tracker,
                    cumulative_threats,
                )
                if gate_rejection:
                    completion_gate_count += 1
                    print(f"{CLI_YELLOW}GATE{CLI_CLR}: {gate_rejection}")
                    messages.append({"role": "user", "content": gate_rejection})
                    continue
            # Evidence challenge for non-OK outcomes (once)
            deleted = tracker.deleted_paths()
            if outcome != "OUTCOME_OK" and not outcome_challenged:
                outcome_challenged = True
                messages.append(
                    {
                        "role": "user",
                        "content": outcome_evidence_message(
                            outcome, deleted, classification.task_type
                        ),
                    }
                )
                print(f"{CLI_YELLOW}CHALLENGE{CLI_CLR}: evidence required for {outcome}")
                continue
            # Second opinion: independent verifier for judgment-heavy outcomes
            if not second_opinion_done and needs_second_opinion(classification, outcome):
                recent_evidence = [
                    m["content"]
                    for m in messages[-8:]
                    if m["role"] == "user" and "[FILE DATA" in m.get("content", "")
                ]
                verdict = get_second_opinion(
                    task_text, outcome, cmd.message, recent_evidence, model
                )
                second_opinion_done = True
                print(
                    f"{CLI_YELLOW}VERIFIER{CLI_CLR}: {'AGREE' if verdict.agree else 'DISAGREE'} — {verdict.reasoning[:80]}"
                )
                if not verdict.agree and verdict.suggested_outcome:
                    override_msg = (
                        f"SECOND OPINION: An independent verifier DISAGREES with {outcome}. "
                        f"Reasoning: {verdict.reasoning} "
                        f"Suggested: {verdict.suggested_outcome}. Reconsider."
                    )
                    messages.append({"role": "user", "content": override_msg})
                    continue
            if deleted:  # T2: side-effect check
                del_msg = f"Note: you deleted [{', '.join(deleted)}]. Confirm required by task."
                messages.append({"role": "user", "content": del_msg})
            cmd = merge_grounding_refs(cmd, tracker)

        # ── DISPATCH ──────────────────────────────────────────────
        dispatch_started = time.time()
        try:
            result = domain.dispatch(client, cmd)
            txt = domain.format_result(cmd, result)
            tool_call_count += 1
            print(f"{CLI_GREEN}OUT{CLI_CLR}: {txt}")
        except ConnectError as exc:
            txt = str(exc.message)
            tool_call_count += 1
            print(f"{CLI_RED}ERR {exc.code}: {exc.message}{CLI_CLR}")
            if "not_found" in txt.lower():
                txt += "\nHint: use 'tree' or 'find' to locate the correct path."
            elif "already_exists" in txt.lower():
                txt += "\nHint: read the existing file first, then decide how to proceed."
        except Exception as exc:
            txt = f"RPC error: {exc}"
            print(f"{CLI_RED}ERR: {txt}{CLI_CLR}")
        dispatch_ms = int((time.time() - dispatch_started) * 1000)
        steps_detail.append(
            {
                "step": i + 1,
                "tool": tool_name,
                "args": str(getattr(cmd, "path", getattr(cmd, "pattern", "")))[:80],
                "plan": (
                    job.plan_remaining_steps_brief[0] if job.plan_remaining_steps_brief else ""
                )[:80],
                "planning_ms": max(0, elapsed_ms - dispatch_ms),
                "dispatch_ms": dispatch_ms,
            }
        )

        # ── COMPLETION (after dispatch) ───────────────────────────
        if domain.is_completion(cmd):
            outcome = domain.completion_outcome(cmd)
            clr = CLI_GREEN if outcome == "OUTCOME_OK" else CLI_YELLOW
            steps_s = " | ".join(cmd.completed_steps_laconic)
            refs = ", ".join(cmd.grounding_refs or [])
            print(f"{clr}{outcome}{CLI_CLR}: {cmd.message}\n  [{steps_s}]\n  refs: {refs}")
            return AgentResult(
                outcome=outcome,
                total_time_ms=int((time.time() - loop_started) * 1000),
                step_count=i + 1,
                tool_call_count=tool_call_count,
                steps_detail=steps_detail,
            )

        # ── TRACKING ──────────────────────────────────────────────
        if hasattr(cmd, "path"):
            if tool_name == "write":
                tracker.record_write(cmd.path)
            elif tool_name == "read":
                tracker.record_read(cmd.path)
            elif tool_name == "delete":  # T2: track deletes
                tracker.record_delete(cmd.path)
            elif tool_name == "list" and result is not None and hasattr(result, "entries"):
                tracker.record_list(cmd.path, [e.name for e in result.entries])
        elif tool_name == "move" and hasattr(cmd, "to_name"):
            tracker.record_write(cmd.to_name)

        if tool_name == "move":
            tool_args = f"{getattr(cmd, 'from_name', '')}->{getattr(cmd, 'to_name', '')}"
        else:
            tool_args = str(getattr(cmd, "path", getattr(cmd, "pattern", "")))
        stagnation.record(tool_name, tool_args)
        if stagnation.is_stagnant() or stagnation.is_oscillating():
            nudge = stagnation.nudge_message()
            print(f"{CLI_YELLOW}STAGNATION{CLI_CLR}: {nudge}")
            txt += f"\n{nudge}"

        # ── DEFEND: scan tool output + T4 cumulative threat ───────
        content_warnings = scan_content(txt)
        if content_warnings:
            cumulative_threats += len(content_warnings)
            warning_text = "SECURITY WARNING: " + "; ".join(content_warnings)
            if cumulative_threats >= 3:
                warning_text += " CUMULATIVE THREAT: multiple warnings across steps."
            print(f"{CLI_YELLOW}DEFEND{CLI_CLR}: {warning_text}")
            txt += f"\n{warning_text}"

        messages.append({"role": "user", "content": domain.wrap_output(txt)})
    report_budget_exhaustion(domain, client, tracker, classification.task_type, cumulative_threats)
    print(f"{CLI_YELLOW}BUDGET EXHAUSTED{CLI_CLR}: smart fallback outcome")
    return AgentResult(
        outcome=None,
        total_time_ms=int((time.time() - loop_started) * 1000),
        step_count=strategy.max_steps,
        tool_call_count=tool_call_count,
        steps_detail=steps_detail,
    )
