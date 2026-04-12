.PHONY: sync run run-final run-parallel run-train run-holdout run-final-train run-final-holdout resume resume-final task task-final gauntlet gauntlet-strict narrate wiki run-full

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

# Train/test split runs — prevents overfitting to pac1-dev.
# Use run-train for iterative development; run-holdout ONLY for final
# validation to avoid leaking the held-out set into training.
# Split = first 80% train / last 20% holdout, mirrors BitgnBenchmarkAdapter.
run-train:
	uv run python main.py --parallel=$(PARALLEL) --split=train

run-holdout:
	uv run python main.py --parallel=$(PARALLEL) --split=holdout

run-final-train:
	RUN_PROFILE=final VERIFIER_POLICY=adaptive PARALLEL=$(PARALLEL) \
		uv run python main.py --parallel=$(PARALLEL) --split=train

run-final-holdout:
	RUN_PROFILE=final VERIFIER_POLICY=adaptive PARALLEL=$(PARALLEL) \
		uv run python main.py --parallel=$(PARALLEL) --split=holdout

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

gauntlet:
	UV_CACHE_DIR=$(CURDIR)/../.uv-cache uv run python synthetic_gauntlet.py

gauntlet-strict:
	UV_CACHE_DIR=$(CURDIR)/../.uv-cache uv run python synthetic_gauntlet.py --strict

narrate:
	cd .. && claude --model claude-sonnet-4-6 --permission-mode acceptEdits --max-turns 15 \
		-p "$$(awk '/^---$$/{n++; next} n>=2' .claude/agents/run-narrator.md)"

wiki:
	cd .. && python3 compile_wiki.py

# Full pipeline: benchmark → narrative analysis → wiki
run-full: run narrate wiki
	@echo "Pipeline complete. Wiki updated. Dashboard will auto-refresh."
