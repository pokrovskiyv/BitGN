---
title: synthetic_gauntlet — локальный пре-финальный прогон
sources:
  - pac1-py/synthetic_gauntlet.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - tests
  - cli
---

# synthetic_gauntlet

> Источник: `pac1-py/synthetic_gauntlet.py`

## Назначение

Полностью **offline-бенчмарк готовности**: без RPC, без LLM, без сети. Гоняет внутренние компоненты pac1-py (classify, output_contract, pre_completion_gate, second_opinion-trigger и config-audit) против ручной батареи кейсов. Нужен для ловли «лексического оверфита» и операционных ошибок до того, как агент начнёт тратить попытки на реальном бенчмарке.

## Интерфейс

Всё, что показано ниже, — это `@dataclass(frozen=True)` описания кейсов плюс пять runner-функций.

| Датакласс | Поля |
|---|---|
| `RouteCase` | `case_id`, `prompt`, `expected_types`, `why` |
| `ContractCase` | `case_id`, `task_text`, `expected_flags`, `valid_answer`, `invalid_answer` |
| `GateCase` | `case_id`, `title`, `task_type`, `task_text`, `outcome`, `completion_message`, `step`, `tracker_builder`, `expected_substring`, `target_hints` |
| `VerifierCase` | `case_id`, `prompt`, `outcome`, `expected` |
| `AuditCase` | `case_id`, `title`, `path`, `predicate`, `failure` |
| `CaseResult` | `bucket`, `case_id`, `passed`, `summary`, `details` |

Runners: `run_route_cases`, `run_contract_cases`, `run_gate_cases`, `run_verifier_cases`, `run_audit_cases`.

## Группы кейсов

- **ROUTE_CASES (R01–R12)** — 12 перефразов, которые должны правильно классифицироваться (inbox-задачи с layout shift, communication, search).
- **CONTRACT_CASES (C01–C07)** — 7 форматных контрактов с позитивным и негативным примерами ответа.
- **GATE_CASES (G01–G08)** — 8 сценариев `pre_completion_gate`: inbox без чтения, список inbox не дочитан, OK без side-effects, OTP без delete, counting без count_only, OTP с count_only (негативный — gate не должен сработать), contact-lookup clarification без contacts, target-hint не consulted.
- **VERIFIER_CASES (V01–V03)** — три сценария `needs_second_opinion`: inbox (ожидается True), простой email lookup + OK (ожидается False), тот же lookup + CLARIFICATION (ожидается True).
- **AUDIT_CASES (A01–A03)** — проверка `.env.final` / `.env.final.example`: не нацелен ли на `bitgn/pac1-dev`, не содержит ли литерального `sk-ant-` ключа, не дефолтится ли example на dev-бенчмарк.

## Portability audit

Отдельный проход по четырём файлам (`classify.py`, `verify.py`, `communication.md`, `inbox_processing.md`) считает, сколько раз встречаются «жёсткие» токены пути (`inbox/`, `contacts/`, `accounts/`, `outbox/`, `reminders/`, `docs/channels/otp.txt`). Это эвристика переносимости: высокая концентрация таких токенов в логике == хрупкость на blind-задачах с другим layout'ом.

## Вердикт

READY требует, чтобы **routing, contracts, gates и config** полностью прошли. `verifier` bucket только информативный.

## Flags

- `--out path.md` — куда писать markdown-отчёт (по умолчанию `docs/final/synthetic-gauntlet-latest.md`).
- `--strict` — exit code 1 при NOT READY.

## Зависимости

**Импорты:** `classify.classify_task`, `output_contract.{extract_answer_contract,check_answer_contract}`, `second_opinion.needs_second_opinion`, `verify.{WriteTracker, pre_completion_gate}`.

**Импортируют:** используется только как CLI.

## См. также

- [classify](classify.md) / [verify](verify.md) / [output_contract](output_contract.md) / [second_opinion](second_opinion.md)
- [Task Classification](../../concepts/task-classification.md)
