---
title: Variance-Reducer + Phantom-Agent Review
sources:
  - docs/superpowers/specs/2026-04-09-variance-reducer-phantom-review-design.md
last_updated: 2026-04-11T14:00:00Z
tags:
  - spec
  - variance
  - finals
---

# Variance-Reducer Agent + Phantom-Agent Manual Review

> Источник: `docs/superpowers/specs/2026-04-09-variance-reducer-phantom-review-design.md`

## Резюме

Спецификация решает две проблемы за два дня до соревнования:

1. **Неизмеренный шум-floor**: последнее известное значение variance — около 8pp на прогон. Без измеренного baseline mean ± CI любой delta неотличим от случайного сэмплинга, и финальные решения принимаются на глаз вместо evidence.
2. **Непроверенный внешний источник**: репозиторий `vakovalskii/phantom-agent` — конкурирующий BitGN PAC1 агент. Содержит ли он generalization-safe паттерны, которых нет у нас, или тратить время на разбор — бессмысленно?

Цель: решить обе проблемы без правки core `pac1-py/`, соблюдая anti-overfit правила `commander.md`, в двухдневный бюджет.

## Ключевые решения

### ADR-1: Variance measurement поверх внешнего pattern extraction

**Решение**: приоритет variance-reducer'у, не phantom-extractor'у.
**Обоснование**: извлекаемая польза phantom-agent'а — 1-2 generalization-safe паттерна после фильтрации. Их defend-аналог архитектурно слабее нашего. Их «unresolved cases» — GPT-OSS Harmony-format артефакты, не применимые к Claude/Qwen-бэкендам. Вложение в variance-measurement даёт больший ROI, потому что меняет уверенность в **каждом** последующем решении.

### ADR-2: Thin orchestrator поверх полноценного аналиста

**Решение**: `variance-reducer` триггерит пробеги и агрегирует сырую статистику; интерпретацию передаёт `generalization-analyst`.
**Обоснование**: `generalization-analyst.md` уже считает mean/stdev/flipped-tasks — дублирование бессмысленно, к тому же создаёт риск дрифта.

### ADR-3: Sequential runs поверх параллельных

**Решение**: variance-reducer гонит N циклов последовательно.
**Обоснование**: квоты BitGN API, verifier cost spike risk, write-race prevention в `run_history.json`. Sequential проще и детерминированнее. Trade-off: ~75 min wall-time для N=5, приемлемо.

### ADR-4: Ручной phantom-review вместо нового extractor-агента

**Решение**: один проход глазами (≤60 мин) с отчётом в `docs/analysis/phantom-agent-extraction-2026-04-09.md`.
**Обоснование**: строить отдельного агента для одного разового обзора — overkill.

## Scope и non-goals

**В scope:**
- Создать `variance-reducer.md` — один новый dev-time агент.
- Обновить `docs/scratchpad/README.md` (две строки).
- Провести ≤60 мин manual phantom-agent review + отчёт.
- Условно: если phantom-review находит generalization-safe паттерн, пройдённый через commander — применить ≤10-строчный diff в GREEN-зоне.

**Non-goals (anti-scope-creep):**
- Variance-reducer НЕ исполняется в этой сессии (это отдельный вызов ~75 мин + API бюджет).
- НЕТ правок в core `pac1-py/` кроме условного ≤10-строчного diff'а.
- НЕТ новых LLM-бэкендов, task types, tools.
- НЕТ правок в AMBER-зоне.
- НЕТ fix evaluation (это роль `evaluator.md`).
- НЕТ family analysis внутри variance-reducer'а (это `generalization-analyst.md`).
- НЕТ коммитов в этой сессии.

## Статус

- Variance-reducer агент создан (`.claude/agents/variance-reducer.md`).
- Phantom-agent review проведён, отчёт в `docs/analysis/phantom-agent-extraction-2026-04-09.md`.
- Defend.py сравнение подтвердило структурное превосходство BitGN над phantom-agent.

## Связанные компоненты

- [Agent Team](../architecture/agent-team.md) — как variance-reducer встраивается в существующую команду
- `.claude/agents/commander.md`, `.claude/agents/generalization-analyst.md`, `.claude/agents/bench-ops.md` — реюзаные агенты
- [defend](../modules/pac1-py/defend.md) — то, что сравнивали с phantom-agent
