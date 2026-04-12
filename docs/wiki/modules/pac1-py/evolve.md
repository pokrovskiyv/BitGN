---
title: evolve — CLI для A-Evolve pipeline
sources:
  - pac1-py/evolve.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - a-evolve
  - cli
---

# evolve

> Источник: `pac1-py/evolve.py`

## Назначение

Тонкий CLI-энтрипойнт для запуска A-Evolve-эволюции над pac1-py-агентом. Собирает пары `BitgnAgent` + `BitgnBenchmarkAdapter`, конфигурирует `AdaptiveEvolveEngine` и запускает цикл мутаций workspace-файлов через `Evolver.run(cycles=N)`. Поддерживает `--dry-run` режим для sanity-check'а без единого API-вызова.

## Интерфейс

| Функция | Назначение |
|---|---|
| `main()` | CLI-энтрипойнт |

## CLI-флаги

- `--cycles N` (default 5) — сколько циклов эволюции прогнать.
- `--batch-size N` (default **32** = полный train-split) — сколько задач в одном цикле.
- `--dry-run` — вывести sanity-информацию (train/holdout размеры, workspace path, длину системного промпта, список скиллов, `EVOLVER_MODEL`, `ANTHROPIC_API_KEY` присутствие) и выйти без API-запросов.

## Почему `--batch-size 32`

Библиотека A-Evolve (`engine/loop.py:82`) на каждом цикле вызывает `benchmark.get_tasks(split="train", limit=batch_size)` и всегда начинает с индекса 0. Это означает, что маленький `batch_size` приводит к переобучению на первые N train-задач вместо ротации. Дефолт `32 = 40 × 0.8` перекрывает полный train-split BitGN PAC1 (40 задач), чтобы мутации прогонялись по всему корпусу.

Cost-предупреждение в docstring'е: **32 задачи × cycles** последовательно. При ~30s/задача один цикл ≈ 16 минут.

## `EvolveConfig`

```python
config = EvolveConfig(
    batch_size=args.batch_size,
    max_cycles=args.cycles,
    holdout_ratio=0.2,
    evolve_prompts=True,
    evolve_skills=True,
    evolve_memory=False,  # no episodic memory for per-task isolated VMs
    evolver_model=os.getenv("EVOLVER_MODEL", "claude-opus-4-5"),
)
```

Ключевые решения:

- `evolve_memory=False` — каждая задача исполняется в изолированной VM, episodic-memory не несёт смысла между задачами.
- `evolver_model` управляется через env-переменную; по умолчанию `claude-opus-4-5`, самая «толстая» модель для мутаций.

## Движок

Используется `AdaptiveEvolveEngine` из `agent_evolve.algorithms.adaptive_evolve` — адаптивный цикл с rollback'ом: если скор падает, мутация откатывается. Это критически важно для финала — эволюция не может ухудшить агент.

## Зависимости

**Импорты:** `agent_evolve as ae`, `agent_evolve.algorithms.adaptive_evolve.AdaptiveEvolveEngine`, `agent_evolve.config.EvolveConfig`, `bitgn_agent.BitgnAgent`, `bitgn_benchmark.BitgnBenchmarkAdapter`.

**Импортируют:** используется только как CLI (`uv run python evolve.py`).

## См. также

- [A-Evolve Integration](../../architecture/a-evolve-integration.md)
- [bitgn_agent](bitgn_agent.md)
- [bitgn_benchmark](bitgn_benchmark.md)
