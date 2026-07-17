# Golden suites and performance budgets

The packaged `suite-contract-v1` manifests are the public v0.4.0 evaluation
matrix. Their plan counts are deterministic and validated at load time.

| Suite | Config | Split | Episodes | Intended use |
|---|---|---:|---:|---|
| smoke | `small` | development | 28 | install and lifecycle smoke |
| standard | `suite_standard_v0_4` | validation | 240 | regression and release evidence |
| research | `suite_research_v0_4` | validation | 3,375 | full monitor/oversight factorial research |
| challenge | `suite_challenge_v0_4` | challenge | 120 | held-out evaluation; outcomes sealed from development |

Run and validate a suite with:

```bash
tasb suite plan standard
tasb suite run standard --run-name standard-v040
tasb analyze --run runs/standard-v040
tasb plot --run runs/standard-v040
tasb report --run runs/standard-v040 --html
tasb suite validate standard --run runs/standard-v040
tasb verify-run --strict runs/standard-v040
```

Golden validation checks plan/completion counts, semantic identity stability,
scenario split integrity, clean competence, fault activation, trace-length
bounds, retry-agent execution, plugin descriptors/isolation, artifact
verification, and broad `[0, 1]` rate ranges. These checks avoid exact floating
snapshots so intended metric improvements do not masquerade as regressions.

## Budgets

The suite manifests carry absolute ceilings for runtime, process peak RSS,
artifact size, and the two-worker/one-worker runtime ratio. The smoke ceilings
are 30 seconds, 512 MiB, 25 MiB, and 2.0 respectively. Standard ceilings are
300 seconds, 1,024 MiB, 250 MiB, and 1.5. Research and challenge have larger
declared ceilings in their packaged manifests. Cross-build regression alerts
use 20% as the maximum runtime increase and require the same suite version,
Python minor version, OS, and CPU class.

Generate machine-readable evidence with:

```bash
tasb performance --suite smoke --output performance-evidence.json
```

Runtime uses `time.perf_counter`; memory records process peak RSS and Python
allocation peak; artifact size sums finalized bundle files. Worker scaling is
the two-worker duration divided by the one-worker duration, so lower is better.

The Checkpoint 50 macOS/Python 3.14.6 baseline measured smoke at 3.00/2.95
seconds (one/two workers), 63.3 MiB RSS, and 9.08 MiB artifacts. Standard
measured 26.64/28.15 seconds, 221.7 MiB RSS, and 77.12 MiB artifacts. Ratios
were 0.985 and 1.057. These are regression baselines for comparable machines,
not cross-platform performance claims; installed-sdist rehearsals retain their
own evidence JSON.
