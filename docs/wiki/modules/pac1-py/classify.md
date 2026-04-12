---
title: classify — классификация задачи (фаза Classify)
sources:
  - pac1-py/classify.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - pcdred
  - classification
---

# classify

> Источник: `pac1-py/classify.py`

## Назначение

Реализует фазу **Classify** рантайм-PCDRED. По тексту задачи и списку уже найденных угроз за микросекунды определяет один из семи классов задачи: `crud`, `search`, `multi_step`, `analysis`, `security_test`, `communication`, `inbox_processing`. От класса зависит стратегия и бюджет шагов, поэтому классификация — важнейшая развилка пайплайна. Код полностью правиловой (regex-основанный) — никаких LLM-вызовов.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `TaskType` | `Literal[...]` | Семь допустимых классов задач |
| `ThreatLevel` | `Literal["none", "low", "high"]` | Уровень угрозы, вычисленный по предупреждениям |
| `TaskClassification` | `@dataclass(frozen=True)` | Результат классификации (`task_type`, `estimated_steps`, `threat_level`, `requires_write`, `requires_delete`, `target_hints`) |
| `classify_task` | `(task_text: str, threat_warnings: list[str]) -> TaskClassification` | Главная точка входа |

## Алгоритм

1. **`_extract_target_hints`** по регулярке `_PATH_HINTS` собирает упоминания путей/имён файлов/известных директорий (`outbox`, `inbox`, `contacts`, `calendar`). Эти подсказки проходят через pre-completion gate в `verify.py` и не дают агенту зарапортовать OK без обращения к конкретному упомянутому файлу.
2. **`_compute_threat_level`** смотрит на категории в `threat_warnings`. Высокая уверенность (`direct_override`, `hierarchy_spoof`, `role_manipulation`, `protected_file`, `context_reset`, `blanket_instruction`, `exfiltration`) — немедленно `high`. Две разные категории — тоже `high`. Иначе `low`. Пустой список — `none`.
3. **Развилки в `classify_task`** (первая подошедшая ветка побеждает):
   - `threat_level == "high"` → `security_test`, 8 шагов.
   - `has_inbox_processing` → `inbox_processing`, 22 шага. Эта ветка обязательно идёт раньше `multi_step`, потому что слово «process» попадает в оба паттерна.
   - `has_read_only_date_lookup and not has_write` → `search`, 15 шагов («next birthday», «coming up next»).
   - `has_multi_step and (has_write or has_search or has_analysis)` → `multi_step`, 20.
   - `has_analysis and not has_write` → `analysis`, 15.
   - `has_search or has_lookup` с лёгким исключением для `questionish_lookup` → `search`, 12.
   - `has_communication` → `communication`, 15.
   - Иначе → `crud`, 10 (или 12, если есть `has_delete`).

## Регулярные паттерны

Паттерны покрывают английский и частично multilingual случаи — немецкий (`wie viel`, `posteingang`), испанский (`bandeja de entrada`, `cuánto`), французский (`combien`, `boite de reception`), CJK (`多少钱`, `受信トレイ`, `收件箱`). Это сделано ради «blind»-устойчивости: финальный бенчмарк может содержать задачи на других языках, и правила не должны срываться на простых морфологических вариантах.

## Зависимости

**Импорты:** только `re`, `dataclasses`, `typing.Literal`.

**Импортируют:** `agent_loop`, `strategy`, `second_opinion`, `synthetic_gauntlet`.

## См. также

- [Task Classification](../../concepts/task-classification.md) — концепция и таблица «класс → бюджет шагов»
- [strategy](strategy.md) — что делает с `TaskClassification` дальше
- [defend](defend.md) — откуда берутся `threat_warnings`
