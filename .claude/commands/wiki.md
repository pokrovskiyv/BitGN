Invoke the wiki skill at ~/.claude/skills/wiki/SKILL.md.

Wiki state: docs/wiki/.state/config.json
Scanner: python3 ~/.claude/skills/wiki/scanner.py

BitGN notes:
- This repo co-owns `docs/wiki/` with `compile_wiki.py`.
- Python-owned files (never touch from /wiki): `index.md`, `scoreboard.md`, `fix-registry.md`, `vulnerability-catalog.md`, `health.md`, `_meta.json`, `tasks/*.md`.
- LLM-owned subdirs: `modules/`, `architecture/`, `concepts/`, `specs/`, `decisions/`, plus `glossary.md`.
- Wiki prose language is Russian (config.language = "ru"). Keep filenames and code identifiers in English.

Pass the user's argument (init/compile/rebuild/lint/query/status) to determine the subcommand:
- No args or "status": run `scanner.py check` and report freshness
- "init": full initialization (already done — will refuse if state/config.json sections already populated)
- "compile": incremental update — only files in `changed` + `added` get regenerated
- "rebuild": full recompilation — deletes only files in LLM-owned subdirs, then compiles
- "lint": integrity checks (coverage, broken links, orphans, glossary completeness)
- "query <question>": Q&A mode against the wiki
