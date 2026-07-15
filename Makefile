PYTHON ?= python3

.PHONY: setup lint format format-check typecheck test coverage audit small full plots report repro clean seeds sweep architecture

setup:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check src tests

format:
	$(PYTHON) -m ruff format src tests

format-check:
	$(PYTHON) -m ruff format --check src tests

typecheck:
	$(PYTHON) -m mypy

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m compileall -q src tests
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m pytest -q

coverage:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m coverage run -m pytest -q -p no:cacheprovider
	$(PYTHON) -m coverage report

small:
	$(PYTHON) -m src.run_eval --all-envs --all-agents --config configs/small.yaml --seed 42

full:
	$(PYTHON) -m src.run_eval --all-envs --all-agents --config configs/full.yaml --seed 42

seeds:
	$(PYTHON) -m src.run_seeds --config configs/seeds.yaml --all-envs --all-agents

sweep:
	$(PYTHON) -m src.run_sweep --config configs/ablations.yaml --seed 42

plots:
	$(PYTHON) -m src.plot_results

report:
	$(PYTHON) -m src.generate_report

architecture:
	bash scripts/render_architecture.sh

audit:
	$(PYTHON) -m src.audit

repro:
	bash scripts/run_repro.sh

clean:
	bash scripts/clean_outputs.sh
