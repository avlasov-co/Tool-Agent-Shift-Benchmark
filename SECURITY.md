# Security Policy

This repository is intentionally non-operational. It must not include real API calls, credentials, private user data, exploit code, bypass guidance, or external side effects.

Report security issues by opening a private advisory if hosted on GitHub, or by contacting the maintainers listed in the repository metadata.

Do not submit real secrets or private traces as test fixtures. Synthetic data only. Humanity has already invented enough ways to leak credentials.

## Supply-chain and CI expectations

- Keep Python dependencies in `pyproject.toml` and regenerate the reviewed,
  hash-checked lockfiles under `requirements/` together. Keep Node tooling in
  `package-lock.json`; do not add `npx --yes`, floating installers, or mutable
  tool downloads to automation.
- GitHub workflows default to `contents: read`, pin every third-party action to
  an immutable commit SHA, and use no `pull_request_target`, deployment, or
  publishing path. Pull requests from forks therefore receive no repository
  secrets or privileged release capability.
- Dependabot, dependency review, `pip-audit`, CodeQL, and a reproducible
  CycloneDX SBOM provide layered dependency and static-analysis coverage. The
  SBOM is built beside the standard sdist and wheel; no package publication is
  performed by CI.
- Enable GitHub secret scanning and push protection for the hosted repository.
  Treat any detected credential, private trace, or accidental token as a
  security incident: revoke or rotate it, remove it from reachable history as
  appropriate, and report it through the private advisory route above. Do not
  place production secrets in Actions variables, test data, issues, or logs.
