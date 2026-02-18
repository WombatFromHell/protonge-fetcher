# AGENTS.md

## Overview

Actionable tool usage guidelines for agentic tools when working with the ProtonFetcher codebase.

## Development Commands

- `nix develop` - Enter the reproducible build environment (recommended)
- `make test` - Run test suite
- `make radon` - Check code complexity
- `make quality` - Run code quality checks
- `make all` - Clean, build, and install locally to `~/.local/bin/protonfetcher`
- `make build` - Build the deterministic zipapp to `dist/protonfetcher.pyz`
- `uv run pytest -xvs` - Manually run test suite (outside Nix shell)

## Reproducible Builds

For **bitwise deterministic builds**, always use `nix develop` before running `make` targets.

See [REPRODUCIBLE_BUILDS.md](REPRODUCIBLE_BUILDS.md) for details.
