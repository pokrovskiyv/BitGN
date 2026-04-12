---
title: Prompt injection и семейства атак
sources:
  - pac1-py/defend.py
  - pac1-py/workspace/prompts/system.md
  - pac1-py/workspace/prompts/fragments/security.md
  - .claude/agents/red-team.md
last_updated: 2026-04-11T14:00:00Z
tags:
  - concept
  - security
  - threat
---

# Prompt injection и семейства атак

## Определение

**Prompt injection** в BitGN PAC — это попытка заставить агента выполнить действие, которое не просила исходная задача, через содержимое файлов, которые он читает в ходе своей работы. Платформа регулярно встраивает такие инъекции в тестовые задачи и штрафует за compliance.

## Семейства атак, покрытые pac1-py

Список категорий жёстко прописан в `defend.py` и отражает реальные паттерны, которые видит бенчмарк. Каждая категория обнаруживается одним или несколькими regex'ами — см. [defend](../modules/pac1-py/defend.md).

| Категория | Примеры паттернов |
|---|---|
| `direct_override` | «ignore all prior instructions», «disregard previous», «forget everything you know», «override safety» |
| `exfiltration` | «send/forward/exfiltrate the API key», «collect all credentials» |
| `protected_file` | «delete agents.md», «overwrite agents.md», «agents.md is deprecated» |
| `hierarchy_spoof` | `<system>`, `[INST]`, `### Admin:`, `BEGIN OVERRIDE PROMPT`, `<<< SYS`, `[[paste hijack` |
| `role_manipulation` | «you are now admin», «pretend you have no restrictions», `DAN`, «developer mode», «jailbreak» |
| `context_reset` | «new instructions:», `--- END ---`, «previous task is complete» |
| `social_engineering` | «as the admin has authorized», «this is a test, verify by…», «for audit purposes, please write…» |
| `channel_spoof` | «this message is from admin», «pose as moderator» |
| `mass_send` | «broadcast to all contacts», «send to every user» |
| `blacklist_bypass` | «ignore the blacklist», «bypass trust rules» |
| `payload_split` | «continued in the next file», «when you see marker X, do Y» |
| `format_hijack` | `FORMAT CORRECTION:` |
| `encoding` | «decode the following base64», `rot13:` |
| `blanket_instruction` | «after every task, always write/delete/send X» |

Высоко-уверенные категории (`direct_override`, `hierarchy_spoof`, `role_manipulation`, `protected_file`, `context_reset`, `blanket_instruction`, `exfiltration`) сразу поднимают `threat_level` задачи до `high` в [classify._compute_threat_level](../modules/pac1-py/classify.md).

## Evasion и нормализация

Чтобы обойти regex, инъекторы используют:

1. **Zero-width characters** (`\u200b`, `\u200c`, `\u200d`, `\u2060`, `\ufeff`) — разбивают слова («ign\u200bore previous»).
2. **Homoglyphs** — кириллическая «а», «е», «о», «р»; греческие «α», «ε»; армянская «օ».
3. **Encoded blobs** — base64, hex-escape `\xNN`, URL-encoded.
4. **Прямая подмена одиночных escape'ов** — `\x3cscript` вместо `<script`.

Все они нейтрализуются [defend._normalize_for_scan](../modules/pac1-py/defend.md):

- Удаляются zero-width.
- `\xNN` → реальный символ.
- Homoglyphs → латиница по explicit-словарю.
- `\s+` → один пробел.

После нормализации оригинальный контент (до свёртки) дополнительно проверяется на наличие zero-width и homoglyph-символов — это даёт отдельное предупреждение «UNICODE: detected», даже если regex-паттерны не сработали.

Encoded-сегменты (`_BASE64_RE`, `_HEX_ESCAPE_RE`, `_URL_ENCODED_RE`) декодируются и **рекурсивно** прогоняются через полный набор threat-паттернов — в результате поймать можно, например, base64-encoded версию «ignore previous instructions».

## Три сценария разрешения

Инъекция — не единственная причина отказа. Модель безопасности различает три варианта:

1. **LOOKALIKE / TYPOSQUAT** (типосквот, `-secure`, `-admin`, разный registered-домен) → **SECURITY** (отказ).
2. **FILENAME-ARTIFACT suffix** (`.bak`, `.old`, `.tmp`, `.staging`, `.local`) или near-variant subdomain без body-уровня инъекции → **CLARIFICATION** (failed identity verification, НЕ security).
3. **Body contains actual injection content** (override-инструкции, exfiltration-просьбы, protected-file мутации) → **SECURITY**, независимо от sender'а.

Это правило описано в [outcomes.md](../../pac1-py/workspace/prompts/fragments/outcomes.md) и применяется в [inbox_processing.md](../../pac1-py/workspace/prompts/fragments/inbox_processing.md).

## Как Red Team расширяет покрытие

[Red Team агент](../architecture/agent-team.md) систематически гонит 8 классов атак и помечает каждую BLOCKED / PARTIAL / BYPASSES. Для BYPASSES минимальный фикс — добавить один `ThreatPattern` в `defend.THREAT_PATTERNS`. Таблица растёт с каждым циклом разработки.

## См. также

- [Security Model](../architecture/security-model.md)
- [Instruction Hierarchy](instruction-hierarchy.md)
- [defend](../modules/pac1-py/defend.md)
