.PHONY: setup test small full plots report repro clean seeds sweep

setup:
	python -m pip install -r requirements.txt

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m compileall -q src tests
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q

small:
	python -m src.run_eval --all-envs --all-agents --config configs/small.yaml --seed 42

full:
	python -m src.run_eval --all-envs --all-agents --config configs/full.yaml --seed 42

seeds:
	python -m src.run_seeds --config configs/seeds.yaml --all-envs --all-agents

sweep:
	python -m src.run_sweep --config configs/ablations.yaml --seed 42

plots:
	python -m src.plot_results

report:
	python -m src.generate_report

repro:
	bash scripts/run_repro.sh

clean:
	bash scripts/clean_outputs.sh
