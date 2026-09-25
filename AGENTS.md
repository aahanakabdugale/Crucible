# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Purpose

Crucible is an autonomous CI/CD failure-triage and self-healing agent built on IBM Bob. It ingests a test failure log, isolates the root cause, generates a minimal surgical patch, re-runs verification, and presents a ready-to-commit fix.

## Stack

- Language: Python 3.x
- Test runner: pytest (installed in `venv/`)
- Agent runtime: IBM Bob IDE / Bob Shell
- No `setup.py`, `pyproject.toml`, or `setup.cfg` — dependency for demo target is only `pytest` (in `demo_sandbox/requirements.txt`)

## Commands

```sh
# Run the full demo-sandbox test suite (from project root, with venv active)
pytest demo_sandbox/

# Run a single test
pytest demo_sandbox/tests/test_billing.py::test_calculate_invoice_standard

# Run the healing agent (entry point does not yet exist — scaffold to scripts/run_heal.py)
python scripts/run_heal.py --target <path-to-target-repo>
```

## Architecture

```
scripts/run_heal.py   ← CLI entry point; --target flag sets the target repo (never hardcoded)
  └─ triage          → reads failure log, identifies file/line/root cause
  └─ patch           → generates minimal surgical diff
  └─ verify          → re-runs pytest on target, confirms fix
reports/              ← scratchpad: triage JSON, diffs, verification logs (not committed)
bob_sessions/         ← mandatory screenshots of each healing pass (hackathon evidence)
demo_sandbox/         ← seeded demo target (billing KeyError bug)
  app/billing.py      ← BillingService.calculate_invoice() — uses "tax_rate" but payload has "tax_pct"
  tests/test_billing.py
```

## Critical Rules (from .bobrules)

- **Surgical diffs only** — target only the failing statement; never rewrite whole files or alter passing logic.
- **Never hardcode the target path** — always pass via `--target` CLI flag to `scripts/run_heal.py`.
- Ignore `venv/`, `.git/`, `__pycache__/`, `.pytest_cache/` in all operations.
- Every output must follow the structured format:
  - `[TRIAGE]` — file, line, error root cause
  - `[PATCH]` — explanation of the surgical change
  - `[VERIFICATION]` — command executed and result

## Code Style

- Pure Python; no formatter config detected — follow PEP 8.
- Tests import from `demo_sandbox.app.<module>` (package-relative imports from project root).
- `demo_sandbox/__init__.py` exists — run `pytest` from the **project root**, not from inside `demo_sandbox/`.
