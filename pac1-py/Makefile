.PHONY: sync run resume task narrate run-full

sync:
	uv sync

run:
	uv run python main.py

run-parallel:
	uv run python main.py --parallel=5

resume:
	uv run python main.py --resume

task:
	@if [ -z "$(TASKS)" ]; then echo "usage: make task TASKS='t01 t03'"; exit 1; fi
	uv run python main.py $(TASKS)

narrate:
	cd .. && claude --model claude-sonnet-4-6 --permission-mode acceptEdits --max-turns 15 \
		-p "$$(awk '/^---$$/{n++; next} n>=2' .claude/agents/run-narrator.md)"

# Full pipeline: benchmark → narrative analysis
run-full: run narrate
	@echo "Pipeline complete. Dashboard will auto-refresh."
