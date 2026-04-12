---
title: Agent Team — разработческий PCDRED-цикл
sources:
  - .claude/agents/analyst.md
  - .claude/agents/architect.md
  - .claude/agents/red-team.md
  - .claude/agents/optimizer.md
  - .claude/agents/evaluator.md
  - .claude/agents/memory-consolidator.md
  - docs/superpowers/specs/2026-03-29-pcdred-meta-model-design.md
last_updated: 2026-04-11T14:00:00Z
tags:
  - architecture
  - agent-team
  - pcdred
---

# Agent Team

Разработка агента ведётся тем же шестифазным PCDRED-циклом, который применяется в рантайме — только вместо pydantic-структур тут шесть Claude Code-субагентов, перекидывающих друг другу артефакты через `docs/scratchpad/`.

## Состав команды

| Агент | Файл | Роль в PCDRED | Триггер | Выход |
|---|---|---|---|---|
| **Analyst** | `.claude/agents/analyst.md` | Perceive + Classify | После каждого пробега | `docs/analysis/run-YYYY-MM-DD-HH.md` |
| **Architect** | `.claude/agents/architect.md` | Decide + Build | После отчёта Analyst | код-правки в `pac1-py/` |
| **Red Team** | `.claude/agents/red-team.md` | Defend (offensive) | После правок Architect или по запросу | `docs/redteam/cycle-YYYY-MM-DD-HH.md` |
| **Optimizer** | `.claude/agents/optimizer.md` | Tune + Trim | После Evaluator | `docs/optimization/tune-YYYY-MM-DD.md` |
| **Evaluator** | `.claude/agents/evaluator.md` | Run + Measure | После любой правки кода | `docs/eval/run-YYYY-MM-DD-HH.md` |
| **Memory Consolidator** | `.claude/agents/memory-consolidator.md` | autoDream meta | Когда MEMORY.md «устала» | обновлённые memory-файлы |

## Analyst

Читает `docs/wiki/index.md` и `docs/wiki/fix-registry.md` перед выбором целей — чтобы не повторять провалившиеся подходы. Для каждой проваленной задачи выдаёт:

- **Root cause** (ровно одна причина)
- **Evidence** (точная цитата из `score_detail`)
- **Fix** (одна actionable правка: какой файл/функция и как)
- **Generalizability**: `HIGH` / `MEDIUM` / `LOW` (LOW → SKIP)
- **Zone**: `GREEN` (safe) / `AMBER` (требует обоснования)

Категория `model_parse_failure` (`OUTCOME_ERR_INTERNAL`, `no answer provided`, `LLM FAILURE`) — **никогда** не предлагает prompt-правок; только инфраструктура (`llm.py`, `strategy.py`, `agent_loop.py`).

## Architect

Принцип: **«smallest generalizable diff that moves the score»**. Правила:

- GREEN zone: `llm.py`, `verify.py`, `defend.py`, `agent_loop.py`, `strategy.py` (только бюджет и posture), `system.md`, `outcomes.md`, `reasoning.md`, `security.md`.
- AMBER zone: `inbox_processing.md`, `communication.md`, `multi_step.md`, `classify.py`, `criteria.py`, `hints.py` — только с обоснованием от Analyst.
- Запрещено: task-id в коде (t01/t02…), хардкоженные пути/имена, few-shot-примеры с ответами конкретных задач, условная логика «if task contains X, do Y».
- **Diff size limit: 30 строк за цикл.** Больше — разбить на несколько циклов.

## Red Team

Атакует по восьми категориям: direct override, embedded-in-data, context reset, hierarchy spoof, subtle misdirection, schema clone (format-hijack), encoding tricks (base64/Unicode), retry exhaustion. Для каждой атаки:

1. Точный payload.
2. Трасса через код: срабатывает ли `scan_content`? Попадает ли под `wrap_tool_output`? Работают ли правила system-prompt?
3. Рейтинг: **BLOCKED / PARTIAL / BYPASSES**.
4. Для PARTIAL/BYPASSES — минимальный фикс (обычно дополнительные паттерны в `defend.py`).

Перед атакой читает `docs/wiki/vulnerability-catalog.md`, чтобы сфокусироваться на не проверенных категориях.

## Optimizer

Метрики:

- **Steps per task** vs `max_steps` — какие задачи используют > 80% бюджета?
- **Tool call distribution** — сколько tree/read/search/write/delete на задачу.
- **Wasted reads** — чтения, не попавшие в `grounding_refs`.
- **Redundant calls** — повторное чтение того же пути без записи между.
- **Context window pressure** — задачи с > 8 ходов до первого write.

Выдаёт таблицу «task_type → current_budget → recommended → reasoning». **Никогда** не рекомендует правки в security-critical путях и не предлагает компрессию промптов без доказательств проблемы.

## Evaluator

Запускает бенчмарк (`cd pac1-py && make run` или `make task TASKS='...'`), сравнивает task-by-task c последним eval-отчётом того же split'а, выдаёт verdict:

- `new_mean > old_mean && 0 regressions` → **COMMIT**
- `new_mean > old_mean && 1 regression` → **COMMIT** + флаг регрессии для Analyst
- `new_mean == old_mean` → **NEUTRAL**
- `new_mean < old_mean` → **REVERT**

## Memory Consolidator

Четырёхфазный autoDream-цикл (Orient → Gather Signal → Consolidate → Prune & Index) над `.claude/projects/*/memory/`. Правило: **«When in doubt, keep the memory»**. Устаревшие, дублирующиеся, drift'ящие записи мягко объединяются; относительные даты заменяются на абсолютные; orphan-файлы удаляются, только если они не ссылаются ни на одну actual-запись в MEMORY.md.

## Scratchpad-протокол

Артефакты публикуются в `docs/scratchpad/` с YAML frontmatter:

```yaml
agent: analyst | architect | red-team | optimizer | evaluator
type: analysis | fix | attack | optimization | eval
run_id: YYYY-MM-DD-HH
status: draft | final
depends_on: [file1.md, file2.md]
produces: [modified_file1.py, ...]
priority_fix: "Top priority from analyst"
```

Именование: `{run_id}--{agent}--{type}.md`. Протокол создаёт явный DAG зависимостей: **Analyst → Architect → Red Team → Evaluator**.

## Анти-оверфит: GREEN и AMBER зоны

Главный риск в финальной фазе — не security, а **overfitting к dev-бенчмарку**. Поэтому:

- Analyst помечает каждый fix по шкале generalizability. `LOW` → SKIP.
- Architect физически **не имеет права** редактировать AMBER-файлы без явного обоснования, включённого в scratchpad.
- Commander-агент (`.claude/agents/commander.md`) — gate поверх любого diff'а в AMBER-зоне.
- `synthetic_gauntlet.py` локально проверяет перефразы (RouteCase R01–R12) и portability-токены в классификаторах — это отдельный слой защиты от лексической «застревания».

## Автоматический запуск

Один полный цикл из 10 PCDRED-итераций запускается так:

```bash
cd ~/Projects/BitGN && mkdir -p /tmp/pcdred-cycles && \
for i in $(seq 1 10); do
  claude --model claude-sonnet-4-6 --permission-mode acceptEdits --max-turns 50 \
    -p "$(cat docs/superpowers/plans/pcdred-cycle-prompt.txt)" 2>&1 | \
  tee "/tmp/pcdred-cycles/cycle-$i-$(date -u +%Y%m%d-%H%M).log" && sleep 30
done
```

Каждый цикл фиксирует свои артефакты в `docs/analysis/`, `docs/eval/`, `docs/redteam/`, `docs/optimization/`. Prompt оркестратора живёт в `docs/superpowers/plans/pcdred-cycle-prompt.txt`.

## См. также

- [PCDRED Pipeline](pcdred-pipeline.md) — runtime-версия того же цикла
- [PCDRED Meta-Model Spec](../specs/pcdred-meta-model.md)
- [Security Model](security-model.md)
