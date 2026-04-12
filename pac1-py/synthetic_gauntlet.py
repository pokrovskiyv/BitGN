"""Local synthetic pre-final gauntlet for unseen-task readiness.

Runs a blind-style battery against routing, answer-contract extraction,
pre-completion gates, verifier triggers, and final-profile config.

This script is intentionally local-only: no benchmark RPCs, no LLM calls,
no network. It is meant to catch lexical overfitting and operational footguns
before spending real blind attempts.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from classify import classify_task
from output_contract import check_answer_contract, extract_answer_contract
from second_opinion import needs_second_opinion
from verify import WriteTracker, pre_completion_gate

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DEFAULT_REPORT_PATH = REPO_ROOT / "docs" / "final" / "synthetic-gauntlet-latest.md"


@dataclass(frozen=True)
class RouteCase:
    case_id: str
    prompt: str
    expected_types: tuple[str, ...]
    why: str


@dataclass(frozen=True)
class ContractCase:
    case_id: str
    task_text: str
    expected_flags: tuple[str, ...]
    valid_answer: str
    invalid_answer: str


@dataclass(frozen=True)
class GateCase:
    case_id: str
    title: str
    task_type: str
    task_text: str
    outcome: str
    completion_message: str
    step: int
    tracker_builder: Callable[[], WriteTracker]
    expected_substring: str | None
    target_hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifierCase:
    case_id: str
    prompt: str
    outcome: str
    expected: bool


@dataclass(frozen=True)
class AuditCase:
    case_id: str
    title: str
    path: Path
    predicate: Callable[[dict[str, str]], bool]
    failure: str


@dataclass(frozen=True)
class CaseResult:
    bucket: str
    case_id: str
    passed: bool
    summary: str
    details: str = ""


def _tracker_with(*ops: tuple[str, str] | tuple[str, str, list[str]]) -> WriteTracker:
    tracker = WriteTracker()
    for op in ops:
        if op[0] == "read":
            tracker.record_read(op[1])
        elif op[0] == "write":
            tracker.record_write(op[1])
        elif op[0] == "delete":
            tracker.record_delete(op[1])
        elif op[0] == "count_only":
            tracker.record_count_only_search()
        elif op[0] == "list":
            tracker.record_list(op[1], op[2])  # type: ignore[index]
        else:
            raise ValueError(f"Unknown tracker op: {op}")
    return tracker


ROUTE_CASES: tuple[RouteCase, ...] = (
    RouteCase(
        "R01",
        "Please clear the message backlog.",
        ("inbox_processing",),
        "mailbox/backlog phrasing should still route to inbox workflow",
    ),
    RouteCase(
        "R02",
        "Triage the waiting messages in my mailbox.",
        ("inbox_processing",),
        "mailbox synonym should not collapse to crud",
    ),
    RouteCase(
        "R03",
        "Go through the newly arrived requests and handle what is appropriate.",
        ("inbox_processing",),
        "queue-like phrasing without the word inbox should still route correctly",
    ),
    RouteCase(
        "R04",
        "Handle the next unread request from the queue.",
        ("inbox_processing",),
        "queue phrasing should trigger inbox routing",
    ),
    RouteCase(
        "R05",
        "Ping Sam with a short update.",
        ("communication",),
        "casual send phrasing should map to communication",
    ),
    RouteCase(
        "R06",
        "Reach out to Alex Meyer about next steps.",
        ("communication",),
        "reach out phrasing should not fall back to crud",
    ),
    RouteCase(
        "R07",
        "What's the legal entity behind the Dutch warehouse ops account?",
        ("search",),
        "entity lookup should map to search",
    ),
    RouteCase(
        "R08",
        "Who runs the German Acme manufacturing account? Return only the email.",
        ("search",),
        "owner/manager lookup should map to search",
    ),
    RouteCase(
        "R09",
        "Which article did I capture 36 days back?",
        ("search", "analysis"),
        "capture-history lookup should not route to crud",
    ),
    RouteCase(
        "R10",
        "Process whatever is waiting in messages/ and remove only the completed item if needed.",
        ("inbox_processing",),
        "layout shift from inbox/ to messages/ should keep the workflow family",
    ),
    RouteCase(
        "R11",
        "Find the email for Braun Markus in people/ and return just the address.",
        ("search",),
        "layout shift from contacts/ to people/ should still look like a lookup task",
    ),
    RouteCase(
        "R12",
        "Which client in clients/ owns the warehouse ops account?",
        ("search",),
        "layout shift from accounts/ to clients/ should still route as search",
    ),
)


CONTRACT_CASES: tuple[ContractCase, ...] = (
    ContractCase(
        "C01",
        "Reply with just the name.",
        ("raw_only",),
        "Acme Logistics",
        "The name is Acme Logistics",
    ),
    ContractCase(
        "C02",
        "Digits only.",
        ("expect_number",),
        "42",
        "42 users",
    ),
    ContractCase(
        "C03",
        "Return just the address.",
        ("expect_email",),
        "miriam.fuchs@example.com",
        "Miriam Fuchs <miriam.fuchs@example.com>",
    ),
    ContractCase(
        "C04",
        "Return the names only, each on its own line.",
        ("one_per_line",),
        "Acme Logistics\nAperture AI Labs\nSilverline Retail",
        "Acme Logistics, Aperture AI Labs, Silverline Retail",
    ),
    ContractCase(
        "C05",
        "Return the names only, each on its own line, in alphabetical order.",
        ("one_per_line", "sorted_alphabetically"),
        "Acme Logistics\nAperture AI Labs\nSilverline Retail",
        "Silverline Retail\nAcme Logistics\nAperture AI Labs",
    ),
    ContractCase(
        "C06",
        "Respond in ISO 8601 date format.",
        ("expect_date_iso",),
        "2026-04-10",
        "April 10, 2026",
    ),
    ContractCase(
        "C07",
        "Return the exact count as an integer.",
        ("expect_number", "requires_exact_count"),
        "7",
        "seven",
    ),
)


GATE_CASES: tuple[GateCase, ...] = (
    GateCase(
        "G01",
        "inbox task with no inbox reads",
        "inbox_processing",
        "Please clear the message backlog.",
        "OUTCOME_OK",
        "done",
        3,
        lambda: _tracker_with(),
        "never read any file from inbox/",
    ),
    GateCase(
        "G02",
        "inbox list not fully read",
        "inbox_processing",
        "Work through the message queue.",
        "OUTCOME_NONE_CLARIFICATION",
        "need clarification",
        3,
        lambda: _tracker_with(("list", "inbox", ["a.md", "b.md"]), ("read", "inbox/a.md")),
        "remaining: b.md",
    ),
    GateCase(
        "G03",
        "inbox ok with no side effects",
        "inbox_processing",
        "Work through the incoming queue.",
        "OUTCOME_OK",
        "processed",
        3,
        lambda: _tracker_with(("list", "inbox", ["a.md"]), ("read", "inbox/a.md")),
        "performed no writes or deletes",
    ),
    GateCase(
        "G04",
        "otp read without delete",
        "communication",
        "Send a reply after verifying the sender identity.",
        "OUTCOME_OK",
        "queued",
        4,
        lambda: _tracker_with(
            ("read", "docs/channels/otp.txt"),
            ("write", "outbox/84500.json"),
            ("read", "outbox/84500.json"),
        ),
        "delete on docs/channels/otp.txt",
    ),
    GateCase(
        "G05",
        "count task without count_only search",
        "analysis",
        "How many accounts are blacklisted? Return the exact count as an integer.",
        "OUTCOME_OK",
        "7",
        3,
        lambda: _tracker_with(("read", "accounts/acct_001.json")),
        "requires an exact count",
    ),
    GateCase(
        "G06",
        "count task with count_only search",
        "analysis",
        "How many accounts are blacklisted? Return the exact count as an integer.",
        "OUTCOME_OK",
        "7",
        3,
        lambda: _tracker_with(("read", "accounts/acct_001.json"), ("count_only", "")),
        None,
    ),
    GateCase(
        "G07",
        "contact lookup clarification without contacts search",
        "search",
        "What is the email address of the account manager for the German Acme manufacturing account?",
        "OUTCOME_NONE_CLARIFICATION",
        "not sure",
        3,
        lambda: _tracker_with(("read", "accounts/acct_009.json")),
        "without searching contacts/",
    ),
    GateCase(
        "G08",
        "target hint mentioned but never consulted",
        "search",
        "Please verify account file accounts/acct_009.json and answer.",
        "OUTCOME_OK",
        "verified",
        3,
        lambda: _tracker_with(("read", "contacts/cont_009.json")),
        "consulted them: accounts/acct_009.json",
        ("accounts/acct_009.json",),
    ),
)


VERIFIER_CASES: tuple[VerifierCase, ...] = (
    VerifierCase(
        "V01",
        "work through the incoming queue",
        "OUTCOME_OK",
        True,
    ),
    VerifierCase(
        "V02",
        "What is the email address of Kuhn Jorg? Return only the email.",
        "OUTCOME_OK",
        False,
    ),
    VerifierCase(
        "V03",
        "What is the email address of Kuhn Jorg? Return only the email.",
        "OUTCOME_NONE_CLARIFICATION",
        True,
    ),
)


AUDIT_CASES: tuple[AuditCase, ...] = (
    AuditCase(
        "A01",
        "final env should not target the dev benchmark",
        HERE / ".env.final",
        lambda env: env.get("BENCHMARK_ID", "").strip() not in {"", "bitgn/pac1-dev"},
        "BENCHMARK_ID still points at bitgn/pac1-dev",
    ),
    AuditCase(
        "A02",
        "final env should not contain a literal Anthropic API key",
        HERE / ".env.final",
        lambda env: not re.match(r"sk-ant-", env.get("ANTHROPIC_API_KEY", "").strip()),
        "ANTHROPIC_API_KEY is stored directly in .env.final",
    ),
    AuditCase(
        "A03",
        "final env example should not default to the dev benchmark",
        HERE / ".env.final.example",
        lambda env: env.get("BENCHMARK_ID", "").strip() not in {"", "bitgn/pac1-dev"},
        "example final profile still defaults to bitgn/pac1-dev",
    ),
)


PORTABILITY_AUDIT_FILES: tuple[Path, ...] = (
    HERE / "classify.py",
    HERE / "verify.py",
    HERE / "workspace" / "prompts" / "fragments" / "communication.md",
    HERE / "workspace" / "prompts" / "fragments" / "inbox_processing.md",
)

PORTABILITY_TOKENS: tuple[str, ...] = (
    "inbox/",
    "contacts/",
    "accounts/",
    "outbox/",
    "reminders/",
    "docs/channels/otp.txt",
)


def _parse_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def run_route_cases() -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in ROUTE_CASES:
        classification = classify_task(case.prompt, [])
        passed = classification.task_type in case.expected_types
        expected = " | ".join(case.expected_types)
        results.append(
            CaseResult(
                bucket="routing",
                case_id=case.case_id,
                passed=passed,
                summary=f"expected {expected}, got {classification.task_type}",
                details=case.prompt,
            )
        )
    return results


def run_contract_cases() -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in CONTRACT_CASES:
        contract = extract_answer_contract(case.task_text)
        missing_flags = [flag for flag in case.expected_flags if not getattr(contract, flag)]
        valid_errors = check_answer_contract(case.task_text, case.valid_answer)
        invalid_errors = check_answer_contract(case.task_text, case.invalid_answer)
        passed = not missing_flags and not valid_errors and bool(invalid_errors)
        detail_parts: list[str] = []
        if missing_flags:
            detail_parts.append(f"missing flags: {', '.join(missing_flags)}")
        if valid_errors:
            detail_parts.append(f"valid answer flagged: {'; '.join(valid_errors)}")
        if not invalid_errors:
            detail_parts.append("invalid answer was accepted")
        results.append(
            CaseResult(
                bucket="contracts",
                case_id=case.case_id,
                passed=passed,
                summary=case.task_text,
                details=" | ".join(detail_parts) if detail_parts else "ok",
            )
        )
    return results


def run_gate_cases() -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in GATE_CASES:
        tracker = case.tracker_builder()
        gate_message = pre_completion_gate(
            outcome=case.outcome,
            step=case.step,
            task_type=case.task_type,
            task_text=case.task_text,
            completion_message=case.completion_message,
            tracker=tracker,
            target_hints=case.target_hints,
        )
        if case.expected_substring is None:
            passed = gate_message is None
            details = gate_message or "ok"
        else:
            passed = bool(gate_message and case.expected_substring in gate_message)
            details = gate_message or "gate did not fire"
        results.append(
            CaseResult(
                bucket="gates",
                case_id=case.case_id,
                passed=passed,
                summary=case.title,
                details=details,
            )
        )
    return results


def run_verifier_cases() -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in VERIFIER_CASES:
        classification = classify_task(case.prompt, [])
        observed = needs_second_opinion(classification, case.outcome, case.prompt)
        passed = observed is case.expected
        results.append(
            CaseResult(
                bucket="verifier",
                case_id=case.case_id,
                passed=passed,
                summary=f"expected {case.expected}, got {observed}",
                details=case.prompt,
            )
        )
    return results


def run_audit_cases() -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in AUDIT_CASES:
        env = _parse_env(case.path)
        passed = case.predicate(env)
        results.append(
            CaseResult(
                bucket="config",
                case_id=case.case_id,
                passed=passed,
                summary=case.title,
                details="ok" if passed else case.failure,
            )
        )
    return results


def run_portability_audit() -> list[str]:
    findings: list[str] = []
    for path in PORTABILITY_AUDIT_FILES:
        if not path.exists():
            continue
        text = path.read_text()
        counts = {token: text.count(token) for token in PORTABILITY_TOKENS if token in text}
        if not counts:
            continue
        pieces = ", ".join(f"{token} x{count}" for token, count in sorted(counts.items()))
        findings.append(f"{path.relative_to(REPO_ROOT)} -> {pieces}")
    return findings


def _bucket_summary(results: list[CaseResult], bucket: str) -> tuple[int, int]:
    subset = [r for r in results if r.bucket == bucket]
    passed = sum(1 for r in subset if r.passed)
    return passed, len(subset)


def _render_result_table(results: list[CaseResult]) -> list[str]:
    lines = ["| Case | Status | Summary | Details |", "|---|---|---|---|"]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        summary = result.summary.replace("|", "/")
        details = result.details.replace("|", "/")
        lines.append(f"| {result.case_id} | {status} | {summary} | {details} |")
    return lines


def render_report(
    all_results: list[CaseResult],
    portability_findings: list[str],
    report_path: Path,
) -> str:
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    routing_passed, routing_total = _bucket_summary(all_results, "routing")
    contracts_passed, contracts_total = _bucket_summary(all_results, "contracts")
    gates_passed, gates_total = _bucket_summary(all_results, "gates")
    verifier_passed, verifier_total = _bucket_summary(all_results, "verifier")
    config_passed, config_total = _bucket_summary(all_results, "config")

    p0_ok = (
        routing_passed == routing_total
        and contracts_passed == contracts_total
        and gates_passed == gates_total
        and config_passed == config_total
    )
    verdict = "READY" if p0_ok else "NOT READY"

    lines: list[str] = [
        "# Synthetic Gauntlet Report",
        "",
        f"**Generated:** {generated_at}",
        f"**Verdict:** {verdict}",
        f"**Report Path:** `{report_path}`",
        "",
        "## Scoreboard",
        "",
        f"- routing: {routing_passed}/{routing_total}",
        f"- contracts: {contracts_passed}/{contracts_total}",
        f"- gates: {gates_passed}/{gates_total}",
        f"- verifier: {verifier_passed}/{verifier_total}",
        f"- config: {config_passed}/{config_total}",
        "",
        "## Routing",
        "",
        *_render_result_table([r for r in all_results if r.bucket == "routing"]),
        "",
        "## Contracts",
        "",
        *_render_result_table([r for r in all_results if r.bucket == "contracts"]),
        "",
        "## Gates",
        "",
        *_render_result_table([r for r in all_results if r.bucket == "gates"]),
        "",
        "## Verifier",
        "",
        *_render_result_table([r for r in all_results if r.bucket == "verifier"]),
        "",
        "## Config Audit",
        "",
        *_render_result_table([r for r in all_results if r.bucket == "config"]),
        "",
        "## Portability Warnings",
        "",
    ]
    if portability_findings:
        lines.extend(f"- {finding}" for finding in portability_findings)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Readiness Rule",
            "",
            "- Verdict is READY only if routing, contracts, gates, and config buckets all pass completely.",
            "- Verifier bucket is informative; it does not block READY on its own.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=f"Path to write the markdown report (default: {DEFAULT_REPORT_PATH})",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 when the gauntlet verdict is NOT READY.",
    )
    args = parser.parse_args()

    all_results = (
        run_route_cases()
        + run_contract_cases()
        + run_gate_cases()
        + run_verifier_cases()
        + run_audit_cases()
    )
    portability_findings = run_portability_audit()
    report = render_report(all_results, portability_findings, args.out)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report)

    routing_passed, routing_total = _bucket_summary(all_results, "routing")
    contracts_passed, contracts_total = _bucket_summary(all_results, "contracts")
    gates_passed, gates_total = _bucket_summary(all_results, "gates")
    verifier_passed, verifier_total = _bucket_summary(all_results, "verifier")
    config_passed, config_total = _bucket_summary(all_results, "config")
    p0_ok = (
        routing_passed == routing_total
        and contracts_passed == contracts_total
        and gates_passed == gates_total
        and config_passed == config_total
    )
    verdict = "READY" if p0_ok else "NOT READY"

    print(f"Synthetic gauntlet verdict: {verdict}")
    print(
        "Buckets: "
        f"routing {routing_passed}/{routing_total}, "
        f"contracts {contracts_passed}/{contracts_total}, "
        f"gates {gates_passed}/{gates_total}, "
        f"verifier {verifier_passed}/{verifier_total}, "
        f"config {config_passed}/{config_total}"
    )
    print(f"Report written to: {args.out}")

    if args.strict and not p0_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
