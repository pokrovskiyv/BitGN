---
title: bitgn_agent — обёртка под A-Evolve BaseAgent
sources:
  - pac1-py/bitgn_agent.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - a-evolve
---

# bitgn_agent

> Источник: `pac1-py/bitgn_agent.py`

## Назначение

Адаптер-класс `BitgnAgent(BaseAgent)`, который встраивает PAC1-агента в фреймворк A-Evolve. Владеет полным жизненным циклом одного trial'а: `start_playground → run_agent → end_trial → Trajectory`. Сохраняет скор и классифицированный «режим провала» прямо в `Trajectory.conversation[0]`, чтобы `BitgnBenchmarkAdapter.evaluate()` мог потом достать результаты без повторного API-вызова.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `BitgnAgent` | `class(BaseAgent)` | A-Evolve-совместимый агент |
| `BitgnAgent.__init__(workspace_dir, benchmark_id, host, model)` | Конструктор | Инициализирует harness_client через `bitgn_client.make_harness_client` |
| `BitgnAgent.solve(task: Task) -> Trajectory` | Метод | Исполнение одной задачи |
| `BitgnAgent._build_reflection(instruction, score, detail)` | `@staticmethod` | Классифицирует failure mode по строке `score_detail` без LLM-вызова |

## Классификация failure mode

`_build_reflection` ищет ключевые фразы в `score_detail`:

| Фраза | failure_mode |
|---|---|
| `no answer provided` / `err_internal` | `budget_exhausted` |
| `missing file write` | `missing_write` |
| `missing file delete` | `missing_delete` |
| `unexpected` | `unexpected_side_effect` |
| `expected outcome outcome_denied_security` + `got outcome_ok` | `security_miss` |
| `expected outcome outcome_ok` + `denied_security` | `security_false_positive` |
| `expected outcome` (любое другое) | `wrong_outcome` |
| иначе | `other` |

Этот дешёвый zero-cost-классификатор дает A-Evolve сигнал для последующих мутаций промптов: evolver-модель получает `reflection.failure_mode` и пишет целевые правки в `workspace/`.

## Формат `Trajectory.conversation[0]`

```python
{
    "score": float,
    "detail": list[str],         # список строк из score_detail
    "reflection": {              # только если score < 1.0
        "failure_mode": str,
        "instruction_prefix": str,  # первые 200 символов
    },
}
```

`BitgnBenchmarkAdapter.evaluate` далее собирает `Feedback(success=score>=1.0, score=score, detail="\n".join(detail))` и при наличии `reflection` добавляет `[REFLECTION] mode=...` в конец detail.

## Зависимости

**Импорты:** `agent_evolve.protocol.base_agent.BaseAgent`, `agent_evolve.types.Task/Trajectory`, `bitgn.harness_pb2.*`, `agent.run_agent`, `bitgn_client.make_harness_client`, `settings.SETTINGS`.

**Импортируют:** `evolve`.

## См. также

- [bitgn_benchmark](bitgn_benchmark.md)
- [evolve](evolve.md)
- [A-Evolve Integration](../../architecture/a-evolve-integration.md)
