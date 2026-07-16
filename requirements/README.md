# Python dependency constraints

`pyproject.toml` is the sole source of dependency intent. This directory holds
the generated, hash-checked runtime and development resolutions used by CI and
release checks.

Regenerate it only in a reviewed dependency-update change, using the supported
Python baseline and the exact tool pinned in the result:

```bash
python -m pip install pip-tools==7.5.3
python -m piptools compile --strip-extras --generate-hashes --output-file requirements/runtime.txt pyproject.toml
python -m piptools compile --all-extras --strip-extras --generate-hashes --output-file requirements/development.txt pyproject.toml
```

The `docs` extra currently supplies `mdformat` for Markdown validation. Run the
supported-Python CI matrix and `pip check` after regeneration. Node
Mermaid/browser tooling is locked independently in `package-lock.json`; install
it only with `npm ci --ignore-scripts`.

`make setup` installs `development.txt` with `--require-hashes`, then installs
the local project with `--no-deps`; the locked graph therefore remains the only
dependency resolver input. Installed-artifact checks install `runtime.txt`
first and then install the wheel with `--no-deps`. Runtime-only consumers can
instead install the published distribution normally, receiving only its
`PyYAML` dependency.
