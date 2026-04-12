---
title: strategy — выбор стратегии исполнения (фаза Decide)
sources:
  - pac1-py/strategy.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - pcdred
  - strategy
---

# strategy

> Источник: `pac1-py/strategy.py`

## Назначение

Реализует фазу **Decide** рантайм-PCDRED. На вход принимает `TaskClassification` из [classify](classify.md) и выдаёт `ExecutionStrategy` — инструкцию, как исполнять задачу: какой системный промпт собрать, сколько шагов разрешить, какую `security_posture` держать, нужна ли предсабмитная верификация. Критически важная особенность: **промпты грузятся свежими на каждый вызов**, чтобы A-Evolve мог мутировать `workspace/prompts/` и изменения сразу вступали в силу без рестарта.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `SecurityPosture` | `Literal["standard", "hardened", "paranoid"]` | Три уровня защитной постуры |
| `ExecutionStrategy` | `@dataclass(frozen=True)` | `system_prompt_static`, `system_prompt_dynamic`, `max_steps`, `security_posture`, `pre_submit_verification`; свойство `system_prompt` склеивает обе части |
| `decide_strategy` | `(classification: TaskClassification, domain=None) -> ExecutionStrategy` | Главная точка входа |

Вспомогательные приватные:

| Функция | Назначение |
|---|---|
| `_load(rel)` | Читает файл из `workspace/` на каждом вызове (без кэша) |
| `_runtime_tool_surface(domain)` | Формирует динамический фрагмент со списком зарегистрированных инструментов домена |

## Таблица стратегий

Хардкод в `_STRATEGY_TABLE` (значения из текущего исходника):

| Ключ | max_steps | security_posture | pre_submit_verify |
|---|---|---|---|
| `security_test` | 12 | `paranoid` | нет |
| `crud` | 15 | `standard` | да |
| `crud_delete` | 22 | `hardened` | да |
| `search` | 30 | `standard` | да |
| `communication` | 25 | `standard` | да |
| `analysis` | 28 | `standard` | да |
| `inbox_processing` | 40 | `hardened` | да |
| `multi_step` | 32 | `standard` | да |

Ключ `crud_delete` используется, когда `classification.task_type == "crud"` и `classification.requires_delete == True` — шаг-бюджет удваивается, потому что удаление требует дополнительной верификации и анти-deletion-гейта.

## Алгоритм

1. Загружается базовый `system.md` и все fragment-файлы под `workspace/prompts/fragments/`.
2. Выбирается ключ стратегии (`security_test` → прямой проброс, `crud_delete` → при наличии удаления, иначе == `task_type`).
3. Из таблицы забираются `max_steps`, `security_posture`, `pre_submit`.
4. **Апгрейд постуры по угрозе:** `threat_level == "high"` повышает постуру до `paranoid`, `threat_level == "low" && posture == "standard"` — до `hardened`.
5. Собирается статическая часть промпта: `base` + task-addon + `outcomes.md` + `reasoning.md` + (security-addon, если не `security_test` и постура не `standard`).
6. Динамическая часть: target-подсказки (`Target references from task: …`) + runtime-tool-surface + `HINT` из переменной окружения.
7. Возвращается `ExecutionStrategy`.

## Почему split на static и dynamic

Такое деление ключевое для prompt caching в Anthropic-бэкенде: `system_prompt_static` получает `cache_control: ephemeral` в `llm._call_api`, динамическая часть идёт без кэша. Nebius-бэкенд просто конкатенирует обе части в одно system-сообщение. См. [LLM Backends](../../architecture/llm-backends.md).

## Зависимости

**Импорты:** `classify.TaskClassification`, стандартные `logging`, `os`, `pathlib.Path`.

**Импортируют:** `agent_loop`.

## См. также

- [outcomes.md](../../concepts/outcome-codes.md) — дерево решений по исходам (always-on фрагмент)
- [reasoning.md](../../concepts/instruction-hierarchy.md) — дисциплина рассуждений (always-on фрагмент)
- [A-Evolve integration](../../architecture/a-evolve-integration.md) — почему промпты перечитываются без рестарта
- [classify](classify.md)
