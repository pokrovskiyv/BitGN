---
title: bitgn_benchmark — бенчмарк-адаптер для A-Evolve
sources:
  - pac1-py/bitgn_benchmark.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - a-evolve
  - benchmark
---

# bitgn_benchmark

> Источник: `pac1-py/bitgn_benchmark.py`

## Назначение

Реализация `BenchmarkAdapter` из фреймворка A-Evolve. Две обязанности:

1. `get_tasks(split, limit)` — забирает список задач из `GetBenchmarkRequest` и режет его на train (первые 80 %) или holdout (последние 20 %). Никаких случайных сэмплов — стабильный детерминированный порядок, чтобы `evolve.py --cycles N` каждый раз видел одинаковый срез.
2. `evaluate(task, trajectory)` — НЕ делает повторного API-вызова: вытаскивает скор из `trajectory.conversation[0]`, который заранее положил `BitgnAgent.solve()`.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `BitgnBenchmarkAdapter(benchmark_id=None, host=None)` | `class(BenchmarkAdapter)` | Адаптер |
| `benchmark_id` | Свойство | Текущий benchmark_id |
| `client` | Свойство | `HarnessServiceClientSync` |
| `get_tasks(split="train", limit=50) -> list[Task]` | Метод | 80/20 split |
| `evaluate(task, trajectory) -> Feedback` | Метод | Извлекает кешированный скор |

## Алгоритм `get_tasks`

```python
res = client.get_benchmark(GetBenchmarkRequest(benchmark_id=benchmark_id))
all_tasks = [Task(id=t.task_id, input=t.task_id) for t in res.tasks]

if split not in ("train", "holdout"):
    raise ValueError
n_holdout = max(1, int(len(all_tasks) * 0.2))
tasks = all_tasks[-n_holdout:] if split == "holdout" else all_tasks[:-n_holdout]
return tasks[:limit]
```

Нулевой ответ (`len(all_tasks) == 0`) сразу кидает `ValueError` — иначе A-Evolve бесконечно крутился бы на пустом батче. Минимум 1 задача в holdout (`max(1, ...)`) — гарантирует, что холд-аут всегда непустой, даже если полный бенчмарк очень маленький.

## Алгоритм `evaluate`

```python
if trajectory.conversation:
    data = trajectory.conversation[0]
    score = float(data.get("score", 0.0))
    detail = "\n".join(data.get("detail") or [])
    if data.get("reflection"):
        detail += f"\n[REFLECTION] mode={reflection['failure_mode']}"
    return Feedback(success=score >= 1.0, score=score, detail=detail)

return Feedback(success=False, score=0.0, detail="no score cached in trajectory")
```

При ошибках парсинга (`TypeError`, `ValueError`) возвращается `success=False` со строкой «score parse error: ...» — A-Evolve трактует это как failure и не останавливает эволюцию.

## Зависимости

**Импорты:** `agent_evolve.benchmarks.base.BenchmarkAdapter`, `agent_evolve.types.{Feedback, Task, Trajectory}`, `bitgn.harness_connect.HarnessServiceClientSync`, `bitgn.harness_pb2.GetBenchmarkRequest`, `bitgn_client.make_harness_client`.

**Импортируют:** `evolve`.

## См. также

- [bitgn_agent](bitgn_agent.md)
- [evolve](evolve.md)
- [A-Evolve Integration](../../architecture/a-evolve-integration.md)
