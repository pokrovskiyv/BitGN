---
title: Классификация задач
sources:
  - pac1-py/classify.py
  - pac1-py/strategy.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - concept
  - classification
---

# Классификация задач

## Определение

Классификация задач — это rule-based фаза **Classify** рантайм-PCDRED, превращающая свободный текст инструкции бенчмарка в один из семи жёстко определённых классов. Класс задаёт бюджет шагов, security posture и набор промптовых фрагментов. Классификация происходит **до первого LLM-вызова** и занимает микросекунды — никакого сетевого обращения или тяжёлых моделей здесь нет.

## Семь классов

| Класс | Бюджет | Security posture | Prompt fragment | Когда |
|---|---|---|---|---|
| `security_test` | 12 | `paranoid` | `security.md` | `threat_level == "high"` (перебивает всё остальное) |
| `inbox_processing` | 40 | `hardened` | `inbox_processing.md` | «process inbox», «handle the next message», multilingual варианты |
| `search` | 30 | `standard` | `search.md` | «find», «locate», «who is», «what is», «return only the email» |
| `analysis` | 28 | `standard` | `analysis.md` | «analyze», «summarize», «count», «how many», «total», multilingual monetary |
| `multi_step` | 32 | `standard` | `multi_step.md` | «then», «after that», «also», «finally», explicit sequencing |
| `communication` | 25 | `standard` | `communication.md` | «send email», «reply to», «ping», «forward», «outbox», «channel» |
| `crud` | 15 (22 если `requires_delete`) | `standard` (если delete → `hardened`) | `crud.md` | default |

## Порядок проверки

Первый match побеждает. `classify_task` проверяет ветки в таком порядке (важном):

1. `threat_level == "high"` → `security_test` (высокая угроза перебивает всё)
2. `has_inbox_processing` → `inbox_processing` (это **раньше** multi_step, потому что слово «process» попадает в оба паттерна, а inbox-специализация должна победить)
3. `has_read_only_date_lookup and not has_write` → `search` (для «next birthday» / «coming up next» — это lookup, не процедурный)
4. `has_multi_step and (has_write or has_search or has_analysis)` → `multi_step`
5. `has_analysis and not has_write` → `analysis` (не счётная задача с записями)
6. `has_search or has_lookup` → `search` (с исключением для questionish-lookup'ов)
7. `has_communication` → `communication`
8. default → `crud`

## Target hints

Параллельно с классификацией, `classify._extract_target_hints` ищет упоминания путей/имён файлов/известных директорий (`outbox`, `inbox`, `contacts`, `calendar`). Пример: для инструкции «Update accounts/acct_009.json with the new status» хинты будут `("accounts/acct_009.json", "accounts")`.

Эти хинты потом используются в [pre_completion_gate](../modules/pac1-py/verify.md): если `OUTCOME_OK` и какой-то из хинтов не оказался в `tracker.all_consulted_paths()`, гейт блокирует отправку.

## Compute threat level

`_compute_threat_level(threat_warnings)` превращает список предупреждений [defend.scan_content](../modules/pac1-py/defend.md) в `ThreatLevel`:

- Пусто → `none`
- Хотя бы одна высоко-уверенная категория (`direct_override`, `hierarchy_spoof`, `role_manipulation`, `protected_file`, `context_reset`, `blanket_instruction`, `exfiltration`) → `high`
- Две и более разных категорий → `high`
- Иначе → `low`

## Multilingual coverage

Регулярки покрывают не только английский: немецкий (`wie viel`, `Posteingang`, `Einnahmen`), испанский (`bandeja de entrada`, `cuánto`), французский (`combien`, `boite de reception`), CJK (`受信トレイ`, `次の受信`, `多少钱`, `收件箱`). Это сделано ради blind-устойчивости — финальные задачи могут содержать multilingual формулировки, и классификация не должна срываться на простых переводах.

## Отличие от LLM-классификации

Исходная идея в SoTA-анализе — возможно fallback на LLM-классификатор для спорных случаев. В текущей реализации это не нужно: правиловый классификатор справляется с 7 классами стабильно, а ошибочная классификация — дешёвая (неправильный бюджет, не неправильный ответ). Никаких LLM-вызовов в `classify.py` нет.

## См. также

- [classify](../modules/pac1-py/classify.md)
- [strategy](../modules/pac1-py/strategy.md)
- [Scoring](scoring.md)
- [PCDRED Pipeline](../architecture/pcdred-pipeline.md)
