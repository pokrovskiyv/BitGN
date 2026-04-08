.PHONY: sync run run-final run-parallel resume resume-final task task-final narrate wiki run-full

PARALLEL ?= 4

sync:
	uv sync

run:
	uv run python main.py

run-final:
	RUN_PROFILE=final VERIFIER_POLICY=adaptive PARALLEL=$(PARALLEL) \
		uv run python main.py

run-parallel:
	uv run python main.py --parallel=5

resume:
	uv run python main.py --resume

resume-final:
	RUN_PROFILE=final VERIFIER_POLICY=adaptive PARALLEL=$(PARALLEL) \
		uv run python main.py --resume

task:
	@if [ -z "$(TASKS)" ]; then echo "usage: make task TASKS='t01 t03'"; exit 1; fi
	uv run python main.py $(TASKS)

task-final:
	@if [ -z "$(TASKS)" ]; then echo "usage: make task-final TASKS='t01 t03'"; exit 1; fi
	RUN_PROFILE=final VERIFIER_POLICY=adaptive PARALLEL=$(PARALLEL) \
		uv run python main.py $(TASKS)

narrate:
	cd .. && claude --model claude-sonnet-4-6 --permission-mode acceptEdits --max-turns 15 \
		-p "$$(awk '/^---$$/{n++; next} n>=2' .claude/agents/run-narrator.md)"

wiki:
	cd .. && python3 compile_wiki.py

# Full pipeline: benchmark → narrative analysis → wiki
run-full: run narrate wiki
	@echo "Pipeline complete. Wiki updated. Dashboard will auto-refresh."
