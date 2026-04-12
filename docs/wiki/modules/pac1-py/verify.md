---
title: verify — трекер записей, pre-completion gate и fallback
sources:
  - pac1-py/verify.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - pcdred
  - verification
---

# verify

> Источник: `pac1-py/verify.py`

## Назначение

Реализует фазу **Evaluate** рантайм-PCDRED: до того как агент зарапортует `report_completion`, модуль проверяет, что все необходимые действия действительно произошли, следы действий зафиксированы, нет несверенных записей, покрыты упомянутые в задаче цели (target hints), соблюдён answer contract и не накопилось критическое число угроз. Также модуль отвечает за fallback-исход при исчерпании бюджета.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `WriteTracker` | `@dataclass` | Трекер всех действий одной задачи (чтения, записи, удаления, списки, search-hits) с пошаговыми счётчиками |
| `StagnationDetector` | `@dataclass` | Ловушка повторов, осцилляций и семантической стагнации |
| `pre_completion_gate(...)` | Функция | Возвращает строку-отказ, если report_completion нужно отклонить, иначе `None` |
| `action_gate_message(tool_name, path, risk_level)` | Функция | Собирает message для гейта (MEDIUM/HIGH) с sanitized-полями |
| `outcome_evidence_message(outcome, deleted, task_type)` | Функция | Evidence-challenge для не-OK исходов (inbox-специализированный) |
| `merge_grounding_refs(cmd, tracker)` | Функция | Добивает `grounding_refs` всеми консультированными путями перед отправкой |
| `report_budget_exhaustion(domain, client, tracker, ...)` | Функция | Отправляет fallback-completion, если исчерпан шаг-бюджет |
| `BUDGET_WARNING` | Константа | Текст предупреждения за 2 шага до конца бюджета |

Приватные утилиты: `_safe_format`, `_join_path`, `_extract_result_paths`, `_looks_inbox_like`, `_looks_contact_lookup_like`, `_unconsulted_target_hints`, `_fallback_outcome`, `_threat_threshold`.

## `WriteTracker`

Основные поля:

- `_writes: dict[path, step]` — путь → номер шага записи
- `_reads: dict[path, step]` — путь → номер шага чтения
- `_deletes: list[path]`
- `_lists: dict[dir, list[names]]`
- `_consulted: dict[path, step]` — любой «увиденный» путь (read/write/delete/list/search/find hit)
- `_count_only_searches: int`

Ключевое свойство — **пошаговые счётчики**: чтение, произошедшее ДО записи, НЕ считается верификацией. Поэтому `unverified_writes()` возвращает только те пути, для которых `reads[p] < writes[p]`. Это ключ к дисциплине read-after-write.

Метод `all_consulted_paths()` собирает итоговый список для `grounding_refs` — объединение `_consulted`, `_reads`, `_writes` в сохранённом порядке.

## `StagnationDetector`

Три класса сигналов:

1. **Exact repeat.** `is_stagnant()` — последние два элемента `history` совпадают. Порог 2, а не 3.
2. **Oscillation.** `is_oscillating()` — последние 4 элемента образуют ABAB паттерн.
3. **Semantic.** `record_result(tool_name, success, is_empty, new_path_count)` отслеживает:
   - `consecutive_not_found` ≥ 3 → сигнал «стоп гадать пути, пользуйся `tree/list`».
   - `zero_match_streak` ≥ 3 (подряд по search/find) → сигнал «переключайся на list/tree».
   - `sum(recent_new_paths) == 0` в окне 4 → «ты зациклился на уже прочитанных данных».

Семантические сигналы одноразовые — каждый класс срабатывает максимум один раз за задачу через `fired_signals: set[str]`. Это спасает от спама одинаковыми советами.

## `pre_completion_gate`

Сложная функция — единый чек-поинт перед отправкой `report_completion`. Условия отказа (в порядке проверки):

1. `OUTCOME_OK` после < 2 шагов → отказ (агент не мог ничего реального сделать).
2. `OUTCOME_OK` и есть `target_hints`, которые выглядят как конкретные пути (содержат `/` или `.`) и не были консультированы → отказ с перечислением «missing targets».
3. `OUTCOME_OK` и `check_answer_contract` нашёл проблемы (пустое сообщение, лишний префикс, не-число для `expect_number`, не-email для `expect_email`, не-ISO-дата и т. п.) → отказ с конкретным списком нарушений.
4. Inbox-like задача и ни одного чтения из `inbox/` → отказ «прочти inbox сначала».
5. Inbox-like задача и список файлов inbox был получен, но не все файлы прочитаны → отказ с перечислением непрочитанных.
6. Inbox-like `OUTCOME_OK` без единой записи в `outbox/` или `reminders/` и без удалений → отказ «ты не выполнил действие».
7. Analysis/search + не-OK исход + ноль чтений → отказ «сначала прочти файлы».
8. Contact-lookup-like + CLARIFICATION без поиска в `contacts/` → отказ «поищи в contacts/».
9. `OUTCOME_OK` и `otp.txt` прочитан, но не удалён → отказ «SYSTEM REQUIREMENT: удали OTP».
10. `OUTCOME_OK` на counting-задаче без `count_only`-search → отказ «используй count_only=True».
11. `cumulative_threats >= threshold(posture)` и исход не `DENIED_SECURITY` → отказ «репортуй DENIED_SECURITY».

Threat-пороги зависят от постуры: `paranoid=1`, `hardened=2`, `standard=3`.

## `_fallback_outcome` — выбор исхода при исчерпании бюджета

Evidence-based решение без привязки к task_type:

- `threats >= threshold` → `OUTCOME_DENIED_SECURITY`
- есть `writes` или `deletes` → `OUTCOME_OK`
- есть `reads`, но без записей → `OUTCOME_NONE_CLARIFICATION`
- вообще ничего → `OUTCOME_NONE_CLARIFICATION` (всегда лучше, чем `ERR_INTERNAL`)

## `action_gate_message`

Два варианта сообщения: HIGH и MEDIUM. HIGH-версия намеренно **не** содержит фразы «RE-ISSUE this exact command» — именно эта формулировка когда-то научила LLM способу обхода «double-tap», обнаруженному Red Team. Новая версия требует перечитать оригинальную задачу и `AGENTS.md`, а interlock в `agent_loop` принудительно требует хотя бы одно промежуточное действие.

Оба поля (`tool_name`, `path`) санитизируются через `_safe_format` перед интерполяцией в user-message — это блокирует Attack 3 (gate-message injection amplifier), где вражеский path с кавычками/переводами строк мог вырваться за шаблон.

## Зависимости

**Импорты:** `re`, `dataclasses`, `output_contract.{extract_answer_contract,check_answer_contract}`.

**Импортируют:** `agent_loop`, `criteria`, `synthetic_gauntlet`.

## См. также

- [Stagnation Detection](../../concepts/stagnation-detection.md)
- [Read-after-write](../../concepts/read-after-write.md)
- [Outcome Codes](../../concepts/outcome-codes.md)
- [output_contract](output_contract.md)
