"""BitGN benchmark adapter for A-Evolve.

get_tasks() fetches the task list from bitgn/pac1-dev.
evaluate() extracts the cached score from Trajectory.conversation[0].
The trial lifecycle (start → run → end) is owned by BitgnAgent.solve().
"""

import os

from bitgn.harness_connect import HarnessServiceClientSync
from bitgn.harness_pb2 import GetBenchmarkRequest
from agent_evolve.benchmarks.base import BenchmarkAdapter
from agent_evolve.types import Feedback, Task, Trajectory


class BitgnBenchmarkAdapter(BenchmarkAdapter):
    """Adapter for the BitGN PAC1 development benchmark."""

    def __init__(
        self,
        benchmark_id: str | None = None,
        host: str | None = None,
    ) -> None:
        self._benchmark_id = benchmark_id or os.getenv("BENCHMARK_ID", "bitgn/pac1-dev")
        self._host = host or os.getenv("BENCHMARK_HOST", "https://api.bitgn.com")
        self._client = HarnessServiceClientSync(self._host)

    @property
    def benchmark_id(self) -> str:
        return self._benchmark_id

    @property
    def client(self) -> HarnessServiceClientSync:
        return self._client

    def get_tasks(self, split: str = "train", limit: int = 50) -> list[Task]:
        """Return task list from the benchmark. train = first 80%, holdout = last 20%."""
        res = self._client.get_benchmark(GetBenchmarkRequest(benchmark_id=self._benchmark_id))
        all_tasks = [Task(id=t.task_id, input=t.task_id) for t in res.tasks]

        if not all_tasks:
            raise ValueError(f"Benchmark {self._benchmark_id!r} returned 0 tasks — check benchmark_id and API access")

        if split not in ("train", "holdout"):
            raise ValueError(f"Unknown split {split!r}; expected 'train' or 'holdout'")

        n_holdout = max(1, int(len(all_tasks) * 0.2))
        if split == "holdout":
            tasks = all_tasks[-n_holdout:]
        else:
            tasks = all_tasks[:-n_holdout]

        return tasks[:limit]

    def evaluate(self, task: Task, trajectory: Trajectory) -> Feedback:
        """Extract cached score from trajectory. Score is stored by BitgnAgent.solve()."""
        if trajectory.conversation:
            try:
                data = trajectory.conversation[0]
                score = float(data.get("score", 0.0))
                detail = "\n".join(data.get("detail") or [])
                return Feedback(success=score >= 1.0, score=score, detail=detail)
            except (TypeError, ValueError) as exc:
                return Feedback(success=False, score=0.0, detail=f"score parse error: {exc}")

        return Feedback(success=False, score=0.0, detail="no score cached in trajectory")
