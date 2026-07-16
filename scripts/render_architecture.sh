#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PUPPETEER_CACHE_DIR="${PUPPETEER_CACHE_DIR:-$HOME/.cache/puppeteer}"
MERMAID_CLI="${MERMAID_CLI:-$ROOT/node_modules/.bin/mmdc}"

render_one() {
  local extension="$1"
  local output="$ROOT/docs/architecture.$extension"
  local temporary
  temporary="$(mktemp "$ROOT/docs/.architecture.$extension.XXXXXX.$extension")"
  if [[ -x "$MERMAID_CLI" ]]; then
    if ! "$MERMAID_CLI" -i "$ROOT/docs/architecture.mmd" -o "$temporary" -b transparent; then
      rm -f "$temporary"
      return 1
    fi
  else
    return 1
  fi
  mv "$temporary" "$output"
}

if ! render_one svg; then
  if [[ "${TASB_REQUIRE_MERMAID:-0}" == "1" ]]; then
    echo "Mermaid renderer is required in this environment" >&2
    exit 1
  fi
  test -s "$ROOT/docs/architecture.svg" && test -s "$ROOT/docs/architecture.png" || {
    echo "Mermaid renderer unavailable and checked-in renders are missing" >&2
    exit 1
  }
  echo "Mermaid renderer unavailable; retaining checked-in renders (CI performs strict regeneration)." >&2
  exit 0
fi

if ! render_one png; then
  if [[ "${TASB_REQUIRE_MERMAID:-0}" == "1" ]]; then
    echo "Mermaid PNG renderer is required in this environment" >&2
    exit 1
  fi
  test -s "$ROOT/docs/architecture.png" || {
    echo "Mermaid PNG renderer failed and checked-in PNG is missing" >&2
    exit 1
  }
  echo "Mermaid PNG renderer unavailable; retaining checked-in PNG (CI performs strict regeneration)." >&2
fi
