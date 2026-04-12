---
title: BitGN PAC Handbook
sources:
  - docs/challenge/handbook.md
last_updated: 2026-04-11T14:00:00Z
tags:
  - spec
  - handbook
  - competition
---

# BitGN PAC Handbook

> Источник: `docs/challenge/handbook.md`

## Резюме

Канонический источник правды по правилам соревнования **BitGN PAC (Personal Agent Challenge)** — трастовый персональный агент против детерминированной симуляции. Цель — собрать собственного автономного агента, соединить его через API с simulated environment и решать задачи через tool-use. Оценка по observable-outcomes (tool-call'ы, side-effects, required flags/refs), не по subjective-text grading.

Разработчик: **BitGN by Rinat Abdullin** (Вена, Австрия). Дата соревнования: **11 апреля 2026**, Europe/Vienna.

## Ключевые моменты

### Что вы строите

Участник отвечает за agentic core:

- Planning и control loop
- Tool selection и tool-use safety
- Memory strategy (или осознанное отсутствие памяти)
- Prompt-injection resistance и security posture
- Protocol-compliant outputs в формате задачи

BitGN предоставляет environment, задачи и детерминированную оценку, чтобы не строить собственных test-harness'ов.

### Почему «personal + trustworthy»

Личные агенты работают с поверхностью личных инструментов: файлы/notes, календарь, сообщения, контакты, scheduling. Эта поверхность одновременно — security и safety граница.

BitGN PAC явно про агентов, которые:

- **делают работу** (reliability)
- **не поддаются обману** (prompt injection resistance)
- **не утекают секреты** (security posture)
- **не делают небезопасных действий** (safe tool-use + side-effect discipline)
- **оцениваются с determinism и rigor** (reproducibility, explainability)

### Deterministic simulation, не «judge-by-prose»

BitGN симулирует мир и предоставляет tool API. Агент решает задачу, вызывая эти API и возвращая финальный результат. Grader смотрит на tool-call'ы, side-effects, required flags и references — не на качество prose в completion-message.

### Roll-out фазы

1. **API access smoke test / minimal sandbox** — март 2026.
2. **Full API + limited practice task set** — минимум за две недели до 11 апреля 2026.
3. **Competition task set enabled (blind-scoring window)** — 11 апреля 2026.
4. **Post-event continuation** — challenge остаётся runnable, leaderboard продолжает работать.

### Track record

Предыдущая итерация (Enterprise RAG Challenge 3): 525 зарегистрированных команд, 10,439 completed сессий, 368,679 evaluated agent runs.

## Ссылки из спецификации

В оригинальном `handbook.md` также описаны: секции 6-15 — definitions, practice vs competition mode, fair play, scoring & penalties, leaderboards, trustworthiness rubric, hubs program, code of conduct, open-source roadmap, glossary. Эти разделы не вошли в текущую сводку — для подробностей см. оригинал.

## Связанные компоненты

- [Scoring](../concepts/scoring.md) — как начисляются баллы
- [Overview](../architecture/overview.md) — наш ответ на правила handbook
- [Security Model](../architecture/security-model.md) — как реализуется «trustworthy»
