---
title: PCDRED-пайплайн
sources:
  - pac1-py/agent_loop.py
  - pac1-py/classify.py
  - pac1-py/strategy.py
  - pac1-py/defend.py
  - pac1-py/verify.py
  - pac1-py/environment.py
  - docs/superpowers/specs/2026-03-29-pcdred-meta-model-design.md
last_updated: 2026-04-11T14:00:00Z
tags:
  - architecture
  - pcdred
  - pipeline
---

# PCDRED-пайплайн

PCDRED — «Perceive → Classify → Decide → Run → Evaluate → Defend» — шестифазный цикл, применяемый одновременно на двух уровнях: во время разработки (через Agent Team) и во время исполнения каждой задачи (внутри `agent_loop.run_agent_loop`). Эта статья — про runtime-часть.

## Компоненты runtime-фаз

| Фаза | Что делает | Модули |
|---|---|---|
| Perceive | Читает дерево, `AGENTS.md`, `context()`, строит `EnvironmentModel` с sensitive_paths и constraints | [domain_fs.boot_messages](../modules/pac1-py/domain_fs.md), [environment.extract_environment](../modules/pac1-py/environment.md) |
| Classify | Правиловая категоризация задачи в 7 классов + извлечение target_hints | [classify](../modules/pac1-py/classify.md), [defend.scan_content](../modules/pac1-py/defend.md) |
| Decide | Выбирает бюджет шагов, security posture, собирает системный промпт (static + dynamic) | [strategy.decide_strategy](../modules/pac1-py/strategy.md) |
| Run | Цикл шагов: LLM → NextStep → gate → dispatch → scan → stagnation → update history | [agent_loop](../modules/pac1-py/agent_loop.md), [domain_fs.dispatch](../modules/pac1-py/domain_fs.md), [llm.call_llm](../modules/pac1-py/llm.md) |
| Evaluate | Pre-submission verification: unverified writes, target hints, criteria, answer contract, pre_completion_gate, evidence challenge, second_opinion | [verify](../modules/pac1-py/verify.md), [criteria](../modules/pac1-py/criteria.md), [output_contract](../modules/pac1-py/output_contract.md), [second_opinion](../modules/pac1-py/second_opinion.md) |
| Defend | Скан tool-output на каждом шаге + Unicode/encoded-эвристики + кумулятивный счётчик threats | [defend](../modules/pac1-py/defend.md) |

## Поток данных

```
task_text ─► scan_content ─► threat_warnings
               │
               ▼
         classify_task ─► TaskClassification ─► decide_strategy ─► ExecutionStrategy
                                                                       │
                                                                       ▼
domain.boot_messages ─► EnvironmentModel   ┌──► call_llm(system_static, system_dynamic, messages, ...)
            │                              │           │
            ▼                              │           ▼
         messages ─────────────────────────┘        NextStep.function (cmd)
                                                       │
                                                       ▼
                                          ┌── DEFEND: action-gate (low/medium/high + interlock)
                                          │        │
                                          │        ▼
                                          │  PRE-SUBMIT: unverified writes, target hints, criteria,
                                          │              answer_contract, pre_completion_gate,
                                          │              outcome_evidence, second_opinion
                                          │        │
                                          │        ▼
                                          ├── DISPATCH: domain.dispatch → tool result
                                          │        │
                                          │        ▼
                                          ├── TRACK: WriteTracker + StagnationDetector
                                          │        │
                                          │        ▼
                                          └── SCAN: scan_content → warnings → messages history
                                                 │
                                                 ▼
                                          report_completion ─► AgentResult
```

## Подробности каждой фазы

### Perceive

`FilesystemDomain.boot_messages` исполняет три команды подряд: `Req_Tree(level=2)`, `Req_Read("AGENTS.md")`, `Req_Context()`. Результат каждой команды:

1. Скан через `scan_content` — результат boot тоже может содержать инъекции.
2. Обёртка через `wrap_tool_output`.
3. Склейка с SECURITY WARNING'ами, если найдены.
4. Добавление в `messages` как user-сообщение.

После boot'а `extract_environment(agents_md_text)` превращает `AGENTS.md` в `EnvironmentModel` с `sensitive_paths` (включает как минимум `AGENTS.md`) и `constraints` (до 10 ключевых правил).

### Classify

`classify_task(task_text, task_warnings)` — синхронный regex-классификатор, работает за микросекунды. Возвращает `TaskClassification`:

- `task_type`: `security_test | crud | search | multi_step | analysis | communication | inbox_processing`
- `estimated_steps`
- `threat_level`: `none | low | high`
- `requires_write`, `requires_delete`
- `target_hints`: упомянутые в задаче пути/файлы/директории

См. [Task Classification](../concepts/task-classification.md).

### Decide

`decide_strategy(classification, domain)`:

1. Перечитывает `workspace/prompts/system.md` + все fragment-файлы (без кэша — A-Evolve может поменять их между вызовами).
2. Выбирает ключ из `_STRATEGY_TABLE` (`security_test`, `crud`, `crud_delete`, `search`, `communication`, `analysis`, `inbox_processing`, `multi_step`).
3. Апгрейдит security_posture: `high threat → paranoid`, `low threat + standard → hardened`.
4. Собирает статическую часть промпта: base + task-type addon + outcomes + reasoning + security.
5. Собирает динамическую часть: target_hints + runtime tool surface + HINT env.
6. Возвращает `ExecutionStrategy`.

### Run

Основной цикл в `agent_loop.run_agent_loop`. Ключевые инварианты:

- На каждом шаге ровно один LLM-вызов и (обычно) ровно один dispatch.
- Если парс JSON фейлится — до 3 ретраев с `_FMT_CORRECTION`.
- За 4 шага до конца без единого write — urgent-нудж.
- За 2 шага до конца — `BUDGET_WARNING`.
- После исчерпания `max_steps` — `report_budget_exhaustion` с evidence-based fallback-исходом.

### Evaluate

Перед отправкой `report_completion`:

1. `unverified_writes()` — все ли записи сверены читаниями (read-after-write).
2. `task_criteria` + `check_criteria` — покрыты ли явно упомянутые пути.
3. `pre_completion_gate` — двухкратный лимит, общие эвристики (target_hints, answer_contract, inbox-чтения, OTP-deletion, counting).
4. `outcome_evidence_message` — для не-OK исходов, одноразовый evidence-challenge.
5. `second_opinion` — при необходимости (verifier policy).
6. `merge_grounding_refs` — добивает refs всеми consulted-путями.

### Defend

Advisory-слой, никогда не блокирует напрямую:

- `scan_content` прогоняет текст через ~50 regex-паттернов (14 категорий).
- Homoglyph-защита: кириллица/греч/армянский → латиница.
- Encoded-scan: base64/hex/URL-escape сегменты декодируются и проверяются рекурсивно.
- `wrap_tool_output` добавляет делимитеры и напоминание.

Блокировки происходят в `agent_loop`, который смотрит на `cumulative_threats` и вычисляет `effective_risk` с учётом sensitive_paths.

## Stateful HIGH-risk interlock

Ключевая защита от «double-tap»-атак (Red Team Attack 2):

```
Первый HIGH-risk вызов ── отказ, GateState записан.
                         │
                         ▼
Retry ── проверка:
          │
          ├── threats_since > 0 → отказ «new threats detected»
          ├── intervening == 0 → отказ «no deliberation»
          └── clean retry      → пропустить
```

`high_risk_gates: dict[str, GateState]` держит снимок `(step_at_gate, threats_at_gate, tool_idx_at_gate)`. Это делает невозможным сценарий, когда инъекция заставляет агента немедленно повторить тот же запрос.

## Отличия dev-time PCDRED

Разработка агента тоже организована как PCDRED-цикл, но с другими исполнителями и артефактами:

| Фаза | Runtime | Dev-time |
|---|---|---|
| Perceive | boot_messages + scan | [Analyst](agent-team.md) анализирует `docs/eval/` и `docs/analysis/` |
| Classify | classify_task | Analyst маркирует failure_mode (wrong_outcome, security_miss, ...) |
| Decide | decide_strategy | [Architect](agent-team.md) выбирает минимальный фикс |
| Run | agent_loop | Architect правит код/промпты + [Evaluator](agent-team.md) запускает бенчмарк |
| Evaluate | pre_completion_gate + second_opinion | Evaluator сравнивает с предыдущим пробегом |
| Defend | scan_content + gate interlock | [Red Team](agent-team.md) генерирует новые атаки |

См. [Agent Team](agent-team.md).

## См. также

- [PCDRED Concept](../concepts/pcdred.md)
- [Security Model](security-model.md)
- [Agent Team](agent-team.md)
- [PCDRED Meta-Model Spec](../specs/pcdred-meta-model.md)
