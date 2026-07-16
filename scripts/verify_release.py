#!/usr/bin/env python3
"""Compatibility launcher for the packaged non-destructive release verifier."""

from tool_agent_shift_benchmark.release_verification import main

if __name__ == "__main__":
    raise SystemExit(main())
