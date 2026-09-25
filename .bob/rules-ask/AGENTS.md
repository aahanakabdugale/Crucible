# Project Documentation Context (Non-Obvious Only)

- `demo_sandbox/` is NOT the Crucible agent — it is the *target* repo used to demonstrate the agent. The agent itself lives in `scripts/`.
- `demo_sandbox/app/billing.py` has a deliberate bug (wrong dict key) — this is by design, not a mistake to fix in documentation.
- There is no `setup.py` or `pyproject.toml`; the only dependency declaration for the demo target is `demo_sandbox/requirements.txt` (contains only `pytest`).
- The project root `venv/` holds the active Python environment; it is gitignored and must be activated before running pytest.
- `bob_sessions/` stores screenshot evidence of healing passes — it is a hackathon submission requirement, not general dev tooling.
- `reports/` is a runtime scratchpad directory (currently empty); it is not a documentation folder.
