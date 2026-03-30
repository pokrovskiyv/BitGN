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
import os
from pathlib import Path

from bitgn.harness_connect import HarnessServiceClientSync
from bitgn.harness_pb2 import EndTrialRequest, StartPlaygroundRequest
from agent_evolve.protocol.base_agent import BaseAgent
from agent_evolve.types import Task, Trajectory

from agent import run_agent


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
        self._benchmark_id = benchmark_id or os.getenv("BENCHMARK_ID", "bitgn/pac1-dev")
        self._host = host or os.getenv("BENCHMARK_HOST", "https://api.bitgn.com")
        self._model = model or os.getenv("MODEL_ID", "claude-sonnet-4-6")
        self._harness_client = HarnessServiceClientSync(self._host)

    def solve(self, task: Task) -> Trajectory:
        """Run the agent on a single task and return trajectory with cached score."""
        trial = self._harness_client.start_playground(
            StartPlaygroundRequest(
                benchmark_id=self._benchmark_id,
                task_id=task.id,
            )
        )

        try:
            run_agent(self._model, trial.harness_url, trial.instruction)
        except Exception as exc:
            logging.error("run_agent error on task %s: %s", task.id, exc)

        result = self._harness_client.end_trial(EndTrialRequest(trial_id=trial.trial_id))

        return Trajectory(
            task_id=task.id,
            output=f"score={result.score:.2f}",
            conversation=[{
                "score": float(result.score),
                "detail": list(result.score_detail),
            }],
        )
