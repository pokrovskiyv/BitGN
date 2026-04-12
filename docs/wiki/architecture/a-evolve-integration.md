---
title: Интеграция A-Evolve
sources:
  - pac1-py/evolve.py
  - pac1-py/bitgn_agent.py
  - pac1-py/bitgn_benchmark.py
  - pac1-py/agent.py
  - pac1-py/strategy.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - architecture
  - a-evolve
---

# Интеграция A-Evolve

A-Evolve — внешний фреймворк автоматической эволюции агентов. В pac1-py он используется для циклической мутации файлов `workspace/prompts/` и `workspace/skills/` под управлением evolver-модели (по умолчанию `claude-opus-4-5`). Этот документ описывает, как именно pac1-py встроен в A-Evolve и какие инварианты поддерживаются.

## Компоненты

| Модуль | Что делает |
|---|---|
| [evolve](../modules/pac1-py/evolve.md) | CLI: `uv run python evolve.py --cycles N --batch-size K` |
| [bitgn_agent](../modules/pac1-py/bitgn_agent.md) | `BitgnAgent(BaseAgent)` — жизненный цикл одного трайла (`start_playground → run_agent → end_trial`) |
| [bitgn_benchmark](../modules/pac1-py/bitgn_benchmark.md) | `BitgnBenchmarkAdapter(BenchmarkAdapter)` — `get_tasks` и `evaluate` |
| [agent](../modules/pac1-py/agent.md) | Preserved-сигнатура `run_agent(model, harness_url, task_text)` |

## Жизненный цикл одного цикла

```
AdaptiveEvolveEngine.run_cycle(agent, benchmark, config):
    tasks = benchmark.get_tasks(split="train", limit=batch_size)
    for task in tasks:
        trajectory = agent.solve(task)            # start_playground + run_agent + end_trial
        feedback = benchmark.evaluate(task, trajectory)  # извлекает кешированный score
        accumulate(feedback)
    mutations = evolver_model.propose_changes(accumulated_feedback, workspace)
    apply(mutations)                                 # правки в workspace/
    rerun on holdout (split="holdout"):              # валидация
        if score drops → rollback
```

`AdaptiveEvolveEngine` — адаптивный цикл с откатом. Любое падение скора ведёт к rollback, что критично для финала: эволюция не может ухудшить агент.

## Поток данных

```
evolve.py
   │
   ├── BitgnAgent(workspace_dir=WORKSPACE, benchmark_id, host, model)
   │        │
   │        └── solve(task) ─► start_playground(benchmark_id, task_id)
   │                           │
   │                           ▼
   │                        run_agent(model, harness_url, instruction)
   │                           │
   │                           ▼
   │                        end_trial(trial_id) ─► score + detail
   │                           │
   │                           ▼
   │                        Trajectory(task_id, output, conversation=[{"score", "detail", "reflection"}])
   │
   ├── BitgnBenchmarkAdapter(benchmark_id, host)
   │        │
   │        ├── get_tasks(split="train|holdout", limit) — 80/20 split
   │        └── evaluate(task, trajectory) — извлекает score из conversation[0]
   │
   └── AdaptiveEvolveEngine(config=EvolveConfig(batch_size, max_cycles, evolver_model))
            │
            └── evolver_model правит workspace/prompts/ и workspace/skills/
```

## EvolveConfig

```python
EvolveConfig(
    batch_size=32,             # полный train-split PAC1
    max_cycles=N,
    holdout_ratio=0.2,
    evolve_prompts=True,       # мутируем workspace/prompts/
    evolve_skills=True,        # мутируем workspace/skills/
    evolve_memory=False,       # episodic memory не имеет смысла — VM изолированы
    evolver_model=os.getenv("EVOLVER_MODEL", "claude-opus-4-5"),
)
```

## Инварианты совместимости

1. **`run_agent(model, harness_url, task_text)`**. `agent.py` — тонкая обёртка (~15 строк), которая преобразует этот вызов в `run_agent_loop(..., domain=FilesystemDomain())`. Никакая часть Domain Plugin Architecture не сломала внешнюю сигнатуру.

2. **`workspace/` на исходном пути**. Эволюция ожидает `pac1-py/workspace/` — ровно там, где он и лежит. Никаких packaging manipulations.

3. **Hot-reload промптов**. `strategy.decide_strategy` вызывает `_load(rel)` на каждый свой вызов — без кэша и синглтонов. Это ключевой инвариант: A-Evolve меняет файл → следующая задача уже видит новый промпт.

4. **`Trajectory.conversation[0]` schema**. Строго `{"score": float, "detail": list[str], "reflection"?: {"failure_mode": str, "instruction_prefix": str}}`. Любое расширение — в дополнительных ключах, без ломки старых.

5. **Flat project (`package = false`)**. Все новые файлы добавляются в корень `pac1-py/`, без вложенных пакетов.

## Failure-reflection

`BitgnAgent._build_reflection` генерирует reflection **без LLM-вызова** — чистая классификация по ключевым фразам в `score_detail`. Результат попадает в `trajectory.conversation[0]["reflection"]` и далее используется evolver-моделью при выборе мутаций: если failure_mode == `missing_write`, evolver будет трогать промпты и verify; если `security_miss` — `defend.py` и `security.md`.

## Dry-run

Безопасная проверка конфигурации без единого API-запроса агентом:

```bash
uv run python evolve.py --dry-run
```

Выводит:

- `train split = N tasks, holdout split = M tasks`
- `--batch-size` эффект на ротацию
- Оценка wall-clock (30s/задача × batch × cycles)
- `Agent workspace` path
- `System prompt length` в символах
- Список `skills`
- `Evolver model` и `ANTHROPIC_API_KEY` presence

## Пересечение с обычным пробегом через `main.py`

`main.py` и `evolve.py` — два **независимых** энтрипойнта. Оба используют `run_agent(...)`, но через разные обвесы:

- `main.py` → `StartRun` + `StartTrial` + `EndTrial` + `SubmitRun` (через `make_harness_client`).
- `evolve.py` → `BitgnAgent.solve(task)` → `start_playground + end_trial` (без `StartRun` — playground-режим).

Скоры `main.py` попадают в `docs/run_history.json` и в `compile_wiki.py`; скоры `evolve.py` живут во внутреннем состоянии A-Evolve и не пишутся в `run_history.json`.

## См. также

- [evolve](../modules/pac1-py/evolve.md)
- [bitgn_agent](../modules/pac1-py/bitgn_agent.md)
- [bitgn_benchmark](../modules/pac1-py/bitgn_benchmark.md)
- [strategy](../modules/pac1-py/strategy.md)
