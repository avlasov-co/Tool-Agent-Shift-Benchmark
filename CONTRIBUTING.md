# Contributing

Contributions should preserve the safety boundary: no real APIs, no real credentials, no private data, no exploit code, no operational abuse workflows, and no external side effects.

Useful contributions:

- new synthetic environments with hidden ground truth;
- new deterministic faults;
- better monitors;
- stronger tests;
- clearer failure replay;
- documentation improvements.

Run before submitting:

```bash
python -m compileall -q src tests
pytest -q
bash scripts/run_repro.sh
```
