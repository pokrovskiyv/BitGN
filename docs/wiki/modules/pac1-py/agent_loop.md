---
title: agent_loop — универсальный PCDRED-цикл
sources:
  - pac1-py/agent_loop.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - pcdred
  - core
---

# agent_loop

> Источник: `pac1-py/agent_loop.py`

## Назначение

Универсальный агентский цикл, параметризованный `DomainProtocol`. Реализует все фазы PCDRED на уровне времени выполнения: восприятие (через `boot_messages` домена и `extract_environment`), классификация (`classify_task`), выбор стратегии (`decide_strategy`), исполнение с гейтами, предсабмитная верификация, оборонительные проверки и корректное завершение. Код файла — самый длинный и самый ответственный модуль pac1-py: здесь склеиваются все подсистемы.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `AgentResult` | `@dataclass(frozen=True)` | Метрики запуска одной задачи: `outcome`, `total_time_ms`, `step_count`, `tool_call_count`, `steps_detail`, `verifier_verdict` |
| `GateState` | `@dataclass` | Снимок состояния в момент срабатывания HIGH-risk-гейта или pre-write inbox-гейта (`step_at_gate`, `threats_at_gate`, `tool_idx_at_gate`) |
| `run_agent_loop` | `(model: str, harness_url: str, task_text: str, domain: DomainProtocol) -> AgentResult` | Главный цикл: boot → task-инъекция → шаги → report_completion |

## Алгоритм

1. **Boot.** Домен создаёт клиента и возвращает стартовые сообщения (`Req_Tree`, `Req_Read AGENTS.md`, `Req_Context`). `extract_environment()` превращает содержимое `AGENTS.md` в структурный `EnvironmentModel` c `sensitive_paths`.
2. **Classify + Strategy.** `scan_content(task_text)` выдаёт список предупреждений, `classify_task` превращает их в `TaskClassification`, `decide_strategy` отдаёт `ExecutionStrategy` (статическая часть системного промпта + динамическая + `max_steps` + `security_posture`).
3. **Цикл по `strategy.max_steps`:**
   - За 4 шага до конца, если ни одного `Req_Write` ещё не было, в историю добавляется `URGENT: 4 steps remain…`.
   - За 2 шага до конца — `BUDGET_WARNING`.
   - LLM-вызов с тремя попытками и `_FMT_CORRECTION` при невалидном JSON.
   - Ответ сериализуется в историю сообщений (`assistant`), разбирается `cmd = job.function`.
4. **DEFEND — Action-gate.** Класс инструмента определяет `effective_risk` (`low | medium | high`). Запись в sensitive-путь поднимается до `high`. Авторизованные `delete` для задач с `requires_delete` опускаются до `medium`. Прочитанный `otp.txt` позволяет `delete otp.txt` пройти как `medium`.
5. **Stateful HIGH-risk interlock.** При первом обращении HIGH-risk инструмент блокируется (`continue`), в историю добавляется `action_gate_message` и снимается `GateState`. При повторе: если `threats_since > 0` — отказ с `OUTCOME_DENIED_SECURITY`-напоминанием; если `intervening == 0` — отказ «без раздумий»; только чистый ретрай проходит на диспатч. Так блокируется «double-tap» атака, описанная в Red Team Attack 2.
6. **Inbox pre-write gate.** Аналогичный interlock для первого `write` в `inbox_processing`-задаче, если путь не `outbox/` или `reminders/`.
7. **Pre-submit verification** (перед `report_completion`): проверка несверенных записей, неиспользованных `target_hints`, `answer_contract`, `pre_completion_gate` (двукратный лимит), evidence-challenge для не-OK исходов, опциональный `second_opinion`, sanity-check удалений (`T2`).
8. **Dispatch.** Домен исполняет команду и форматирует результат. При `ConnectError` добавляются контекстные подсказки (`not_found` → посоветовать `tree/find`; `already_exists` → прочесть перед записью).
9. **Tracking + DEFEND.** `WriteTracker` фиксирует `read/write/delete/list/result_paths`. `StagnationDetector` ловит повторы (2), осцилляции (A-B-A-B) и семантическую стагнацию (3 `not_found`, 3 пустых `search`, 4 шага без новых путей). Вывод домена пропускается через `scan_content`, при `cumulative_threats >= 3` появляется предупреждение о «кумулятивной угрозе» (T4 Crescendo defense).
10. **Report.** Если `cmd` — `ReportTaskCompletion`, перед диспатчем вызывается `merge_grounding_refs`, после диспатча строится и возвращается `AgentResult`. На исчерпании бюджета — `report_budget_exhaustion` с безопасным fallback-исходом.

## Тонкости, которые часто теряют при чтении

- Весь цикл работает на **stateless-воспроизведении**: в историю сообщений на каждом шаге дописываются ровно три вещи (system-промпт идёт отдельной ролью), новых полей состояния нет.
- `completion_gate_count` ограничен двумя срабатываниями — иначе pre_completion_gate может уронить задачу в бесконечный цикл нудежей.
- `outcome_challenged` — одноразовый вызов: не-OK исходы требуют доказательств, но только один раз за задачу, кроме `DENIED_SECURITY` при `cumulative_threats >= 2` (там пропускаем, тк DEFEND уже подтвердил угрозу).
- Логика `verifier_new_evidence_required` блокирует повторный report_completion, пока после несогласия верификатора не появилось новых путей в `tracker._consulted`.

## Зависимости

**Импорты:** `classify_task`, `criteria.*`, `defend.scan_content`, `DomainProtocol`, `environment.extract_environment`, `hints.folder_format_hint`, `llm.call_llm`, `second_opinion.*`, `strategy.decide_strategy`, `verify.*`, `connectrpc.errors.ConnectError`.

**Импортируют:** `agent.py`.

## См. также

- [PCDRED Pipeline](../../architecture/pcdred-pipeline.md) — как фазы связаны между собой
- [Security Model](../../architecture/security-model.md) — взаимодействие гейтов, RiskLevel и DEFEND
- [verify](verify.md) — `WriteTracker`, `StagnationDetector`, `pre_completion_gate`
- [defend](defend.md) — источник предупреждений о угрозах
- [classify](classify.md), [strategy](strategy.md)
