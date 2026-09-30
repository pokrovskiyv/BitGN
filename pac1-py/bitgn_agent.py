"""BitGN agent wrapped for A-Evolve.

BitgnAgent.solve() owns the full trial lifecycle:
  1. start_playground → gets harness_url + instruction
  2. run_agent() → executes task against the VM
  3. end_trial() → gets score + score_detail
  4. Returns Trajectory with score cached in conversation[0]

BitgnBenchmarkAdapter.evaluate() extracts the score from conversation[0]
without making another API call.
"""

import logging
from pathlib import Path

from agent_evolve.protocol.base_agent import BaseAgent
from agent_evolve.types import Task, Trajectory
from bitgn.harness_pb2 import EndTrialRequest, StartPlaygroundRequest

from agent import run_agent
from bitgn_client import make_harness_client
from settings import SETTINGS


class BitgnAgent(BaseAgent):
    """A-Evolve compatible agent backed by the PAC1 run_agent loop."""

    def __init__(
        self,
        workspace_dir: str | Path,
        benchmark_id: str | None = None,
        host: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__(workspace_dir)
        self._benchmark_id = benchmark_id or SETTINGS.benchmark_id
        self._host = host or SETTINGS.benchmark_host
        self._model = model or SETTINGS.primary_model
        self._harness_client = make_harness_client(self._host)

    @staticmethod
    def _build_reflection(instruction: str, score: float, detail: list[str]) -> dict:
        """Classify failure mode from grader feedback. Zero-cost, no LLM call."""
        text = " ".join(detail).lower()
        if "no answer provided" in text or "err_internal" in text:
            mode = "budget_exhausted"
        elif "missing file write" in text:
            mode = "missing_write"
        elif "missing file delete" in text:
            mode = "missing_delete"
        elif "unexpected" in text:
            mode = "unexpected_side_effect"
        elif "expected outcome outcome_denied_security" in text and "got outcome_ok" in text:
            mode = "security_miss"
        elif "expected outcome outcome_ok" in text and "denied_security" in text:
            mode = "security_false_positive"
        elif "expected outcome" in text:
            mode = "wrong_outcome"
        else:
            mode = "other"
        return {"failure_mode": mode, "instruction_prefix": instruction[:200]}

    @staticmethod
    def _build_agent_metrics(agent_result) -> dict | None:
        """Export compact rollout evidence for prompt/skill optimization."""
        if agent_result is None:
            return None
        return {
            "outcome": getattr(agent_result, "outcome", None),
            "total_time_ms": getattr(agent_result, "total_time_ms", None),
            "step_count": getattr(agent_result, "step_count", None),
            "tool_call_count": getattr(agent_result, "tool_call_count", None),
            "verifier_verdict": getattr(agent_result, "verifier_verdict", None),
            "steps": getattr(agent_result, "steps_detail", []),
        }

    def solve(self, task: Task) -> Trajectory:
        """Run the agent on a single task and return trajectory with cached score."""
        trial = self._harness_client.start_playground(
            StartPlaygroundRequest(
                benchmark_id=self._benchmark_id,
                task_id=task.id,
            )
        )

        try:
            _agent_result = run_agent(self._model, trial.harness_url, trial.instruction)
        except Exception as exc:
            logging.error("run_agent error on task %s: %s", task.id, exc)
            _agent_result = None

        result = self._harness_client.end_trial(EndTrialRequest(trial_id=trial.trial_id))

        score = float(result.score)
        detail = list(result.score_detail)
        entry: dict = {
            "score": score,
            "detail": detail,
            "task_description": trial.instruction,
        }
        agent_metrics = self._build_agent_metrics(_agent_result)
        if agent_metrics:
            entry["agent_metrics"] = agent_metrics
        if score < 1.0:
            entry["reflection"] = self._build_reflection(trial.instruction, score, detail)

        return Trajectory(
            task_id=task.id,
            output=f"score={score:.2f}",
            conversation=[entry],
        )
