# BitGN PAC — Personal & Trustworthy Agent Challenge

Репозиторий двух ИИ-агентов для [BitGN Agent Challenge](https://bitgn.com) — глобального соревнования, где агенты работают с личными данными пользователя в детерминированной виртуальной среде и оцениваются не только по точности, но и по устойчивости к адверсариальным атакам.

**Дата финала:** 11 апреля 2026  
**Формат:** 104 задачи в слепом режиме, детерминированная оценка по side-эффектам  
**Пиковый результат:** 92.5% (Qwen3.6-plus, dev-бенчмарк на 40 задачах)

## Почему этот проект интересен

BitGN PAC — это не обычный coding benchmark. Платформа намеренно внедряет скрытые вредоносные инструкции (prompt injections) в задания и файлы окружения. Агент должен:

- Выполнить задачу точно по инструкции
- Обнаружить и отклонить скрытые атаки (`OUTCOME_DENIED_SECURITY`)
- Не навредить системе в процессе работы

Ложный отказ стоит максимум 1 балл. Послушание инъекции может стоить каскадно дороже. Вся архитектура построена вокруг этой асимметрии.

## Результаты

За 12 дней подготовки проведено 161 полных прогонов бенчмарка на пяти моделях:

| Модель | Бэкенд | Лучший результат | Прогонов |
|--------|--------|-------------------|----------|
| Qwen3.6-plus (free tier) | OpenRouter | **92.5%** (37/40) | 52 |
| Claude Haiku 4.5 | Anthropic API | **84.0%** (21/25) | 5 |
| Qwen3-235B-A22B-Thinking | Nebius AI Studio | **80.7%** (25/31) | 13 |
| Claude Sonnet 4.6 | Anthropic API | **76.0%** (19/25) | 15 |
| Qwen3.5-397B-A17B | Nebius AI Studio | **69.2%** (72/104) | 4 |

Неожиданный результат: Haiku 4.5 (84%) стабильно обходила Sonnet 4.6 (76%) на задачах безопасности. Меньшая модель буквальнее следует правилам, а в контексте threat injection resistance буквальность — преимущество.

**Финальный профиль** на день соревнования: Claude Sonnet 4.6 (primary) + Claude Haiku 4.5 (verifier), параллелизм 4.

## Архитектура

### PCDRED — шесть стадий каждого шага

В отличие от схемы «планирую → делаю», здесь каждый шаг агента проходит полный цикл из шести проверок:

```
Perceive → Classify → Decide → Respond → Evaluate → Defend
```

| Стадия | Что происходит | Модуль |
|--------|---------------|--------|
| **Perceive** | Быстрый regex-скан текста задачи на 40+ паттернов атак. Микросекунды, без LLM | `defend.py` |
| **Classify** | Категоризация в 1 из 7 типов задач, определение threat level и security posture | `classify.py` |
| **Decide** | Сборка промпта: статическая часть (кэшируемая) + динамическая (target hints, tool surface) | `strategy.py` |
| **Respond** | LLM заполняет структурированный бланк (`NextStep` — Pydantic union по полю `tool`) | `llm.py` |
| **Evaluate** | Stagnation detection, write verification, pre-completion gates | `verify.py` |
| **Defend** | Скан tool output на угрозы, 3-уровневые risk gates, cumulative threat counter | `agent_loop.py` |

Каждая стадия может остановить выполнение. Это не линейный конвейер — это цепь, где достаточно одного срабатывания, чтобы перехватить атаку.

### Структурная защита вместо поведенческой

Агент не отвечает свободным текстом. Модель заполняет жёсткий JSON-бланк (Pydantic schema с discriminated union), где набор инструментов и допустимых значений зафиксирован. Вредоносная инструкция может убедить модель *захотеть* выполнить атаку, но структура ответа не позволит ей это *выразить*.

Три бэкенда обеспечивают это по-разному:
- **Nebius AI Studio** — `response_format: json_schema` (OpenAI-compatible)
- **Anthropic API** — `messages.parse()` с `output_format=NextStep` + prompt caching
- **OpenRouter** — `json_schema` с `strict=True`

### Domain Plugin Architecture

Главный цикл (`agent_loop.py`) не знает, что такое «файл», «удалить» или «записать». Он оперирует абстракциями: у каждого действия есть уровень риска (low / medium / high), и по нему цикл выбирает gate.

```python
class DomainProtocol(Protocol):
    tool_registry: dict[str, ToolHandler]  # каждый tool несёт risk_level
    def dispatch(self, client, cmd) -> Any: ...
    def format_result(self, cmd, result) -> str: ...
    # ... ещё 8 методов
```

`domain_fs.py` реализует этот протокол для файловой системы PAC1. Чтобы добавить поддержку календаря или почты — достаточно написать новый плагин. Все защиты (stagnation detection, risk gates, threat counting) наследуются автоматически.

### Четыре стены обороны

1. **Pattern matching** — нормализация текста (Unicode homoglyphs, Base64, hex escape) → скан 40+ regex паттернов по 14 категориям атак
2. **Data sandboxing** — весь tool output оборачивается в `[FILE DATA]`/`[END FILE DATA]` с инъекцией post-read напоминания. Instruction hierarchy: system > task > AGENTS.md > file content
3. **Process discipline** — stagnation detection (exact repeat, A-B-A-B oscillation, semantic stagnation), read-after-write enforcement, pre-completion gates
4. **Risk gates** — stateful HIGH-risk interlock: повторное опасное действие разрешается только если (a) был хотя бы один промежуточный шаг и (b) за это время не появилось новых угроз. Блокирует атаку «двойного удара»

### Second Opinion Verifier

Перед отправкой `report_completion` — независимый вызов Claude Haiku как верификатора. Видит задачу, предложенный outcome, последние 6 tool outputs. Возвращает `agree/disagree` с suggested outcome. При несогласии агент блокируется до предъявления нового evidence.

## Два агента

### pac1-py — основной

Полный PCDRED pipeline, 22 модуля, ~5000 строк Python. Protobuf RPC через ConnectRPC к PCM Runtime. 10 инструментов (tree, find, search, list, read, write, delete, mkdir, move, report_completion). 7 типов задач с индивидуальными стратегиями и step budgets (8–28 шагов).

### sandbox-py — упрощённый

Агент для sandbox/mini среды (симуляция Obsidian-заметок). Без классификации, стратегии и verify-модулей. Фиксированный бюджет 30 шагов. 7 инструментов. Возвращает raw JSON вместо Unix-style форматирования.

## Agent Team — 13 разработческих агентов

Разработка велась соло, но с командой из 13 Claude Code агентов (`.claude/agents/`), организованных вокруг PCDRED цикла:

| Агент | Роль |
|-------|------|
| **Analyst** | Классификация провалов по 6 семействам после каждого прогона |
| **Generalization Analyst** | Кластеризация по failure families, рекомендация одного fix за цикл |
| **Architect** | Минимальный обобщаемый fix (< 30 строк кода за цикл) |
| **Red Team** | 8 категорий адверсариальных атак на свежие изменения |
| **Commander** | Финальный gate: 5 anti-overfit правил (нет task ID в коде, нет hardcoded paths, fix целит в семейство, variance не растёт) |
| **Evaluator** | Benchmark run → COMMIT / REVERT / INVESTIGATE |
| **Optimizer** | Профилирование step budget, tool call efficiency |
| **Variance Reducer** | N идентичных прогонов → baseline mean ± stdev с 95% CI |
| **BenchOps** | 7 health checks после каждого run (детерминированный чеклист) |
| **Run Historian** | Валидация run_history.json, per-task win rates, trigger compile_wiki |
| **Dashboard Updater** | Streamlit dashboard parsers after report format drift |
| **Run Narrator** | Русскоязычный анализ прогона (≤150 строк) |
| **Memory Consolidator** | autoDream-style 4-фазная консолидация памяти |

Агенты общаются через файлы-артефакты в `docs/scratchpad/` с YAML frontmatter (`agent`, `type`, `run_id`, `depends_on`). Получается явный DAG: Analyst → Architect → Red Team → Commander → Evaluator.

Автоматизированный цикл:
```bash
for i in $(seq 1 10); do
  claude --model claude-sonnet-4-6 --permission-mode acceptEdits --max-turns 50 \
    -p "$(cat docs/superpowers/plans/pcdred-cycle-prompt.txt)"
  sleep 30
done
```

## A-Evolve

pac1-py интегрирован с [A-Evolve](https://github.com/synth-agi/agent-evolve) для автоматической эволюции промптов:

```bash
uv run python evolve.py --cycles 5 --batch-size 32
```

A-Evolve мутирует файлы в `workspace/prompts/`, прогоняет benchmark, откатывает если score падает. Evolver model: `claude-opus-4-5` (настраивается через `EVOLVER_MODEL`).

## Knowledge Wiki

`compile_wiki.py` компилирует живую документацию из `run_history.json`, `task_cache.json` и PCDRED-отчётов. Чистый Python, без LLM, < 1 секунды. Выходные файлы:

- `docs/wiki/index.md` — текущий score, health alerts, task summary
- `docs/wiki/tasks/tNN.md` — per-task win rate, failure modes, fix history
- `docs/wiki/scoreboard.md` — score progression и per-model comparison
- `docs/wiki/fix-registry.md` — consolidated DO_NOT_REPEAT из всех циклов
- `docs/wiki/vulnerability-catalog.md` — все находки Red Team

```bash
python3 compile_wiki.py          # полная сборка
python3 compile_wiki.py --check  # только lint
```

## Быстрый старт

```bash
cd pac1-py
make sync                          # uv sync

# Dev-профиль (Nebius + Qwen3)
export NEBIUS_API_KEY=...
make run                           # все задачи
make task TASKS='t01 t03'          # конкретные задачи

# Final-профиль (Anthropic Sonnet + Haiku verifier)
cp .env.final.example .env.final
# добавить ANTHROPIC_API_KEY в .env.final
make run-final PARALLEL=4
```

### Переменные окружения

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `LLM_BACKEND` | `nebius` | `nebius`, `api` (Anthropic), `openrouter` |
| `MODEL_ID` | `Qwen/Qwen3-235B-A22B-Thinking-2507` | Модель для активного бэкенда |
| `RUN_PROFILE` | `dev` | `dev` или `final` |
| `VERIFIER_MODEL` | `claude-haiku-4-5` | Модель second opinion verifier |
| `VERIFIER_POLICY` | `adaptive` | `off`, `always`, `adaptive` |
| `PARALLEL` | `1` (dev) / `4` (final) | Параллелизм запуска задач |
| `BENCHMARK_HOST` | `https://api.bitgn.com` | API endpoint |
| `BENCHMARK_ID` | `bitgn/pac1-dev` | ID бенчмарка |
| `BITGN_API_KEY` | — | Для authenticated endpoints |

## Пять уроков

1. **Меньшая модель обыграла большую.** Haiku 84% vs Sonnet 76%. В задачах на security compliance буквальность — преимущество перед «интерпретацией».

2. **Код бьёт промпты.** На thinking-моделях дописать правило в промпт — почти бесполезно. Та же логика, реализованная как проверка в коде, даёт ~100% попадание.

3. **Защита бьёт по невинным.** Паттерн `\bDAN\b` ловит атаки и... контакт по имени Daniel. Каждый новый threat pattern требует проверки на ложные срабатывания.

4. **Проверяющий код может стать дырой.** Error handler в verifier возвращал `DENIED` при недоступности сервиса. Одно изменение (нейтральный fallback вместо агрессивного) подняло score с 77% до 84%.

5. **Один прогон ничего не доказывает.** Разброс до 10% между идентичными прогонами. Минимум два run перед принятием любого изменения.

## Структура проекта

```
pac1-py/                   Основной агент (PCDRED pipeline)
├── agent_loop.py          Generic PCDRED runtime (597 строк)
├── domain_protocol.py     DomainProtocol interface + ToolHandler
├── domain_fs.py           Filesystem domain plugin (427 строк)
├── classify.py            7 типов задач, regex classification
├── strategy.py            Per-type prompt composition + step budgets
├── defend.py              40+ threat patterns, normalization, scanning
├── verify.py              Stagnation + WriteTracker + pre-completion gates
├── llm.py                 3 LLM backends (Nebius, Anthropic, OpenRouter)
├── second_opinion.py      Haiku verifier (independent Anthropic call)
├── main.py                Entry point, parallel runner, run history
├── evolve.py              A-Evolve integration
└── workspace/prompts/     Prompt fragments (loaded fresh per call)

sandbox-py/                Упрощённый агент для mini-среды
.claude/agents/            13 разработческих агентов
docs/                      Eval reports, analysis, wiki, scratchpad
dashboard/                 Streamlit dashboard
compile_wiki.py            Knowledge wiki compiler
```

## Документация

- `docs/challenge/handbook.md` — правила соревнования (canonical source of truth)
- `docs/final/release-notes.md` — release notes финального профиля
- `docs/articles/linkedin-architecture-2026-04-11.md` — развёрнутая статья об архитектуре
- `docs/wiki/` — автогенерируемая knowledge wiki (scoreboard, per-task cards, fix registry)

## Лицензия

Competition codebase. Оба агента будут доступны как отправная точка для тех, кто строит trustworthy personal agents.
