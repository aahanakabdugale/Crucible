# Project Architecture Rules (Non-Obvious Only)

- Crucible is target-agnostic by design — any architectural decision that couples the agent to `demo_sandbox/` violates a core requirement. The `--target` flag is the sole coupling point.
- The healing loop is sequential and non-parallel: triage → patch → verify. Each step's output feeds the next; do not design concurrent execution.
- `scripts/run_heal.py` is the only planned CLI entry point — do not add secondary scripts or module entry points without updating this file.
- `reports/` is the designated scratchpad for intermediate artifacts (triage JSON, proposed diffs, logs). Design the loop to write here, not to stdout, for auditability.
- `bob_sessions/` screenshots are a hard deliverable for the hackathon submission — plan any demo flow to produce at least one screenshot per healing pass.
- No CI runner is set up yet (GitHub Actions is optional per PRD) — do not assume automated pipeline execution exists.
- The demo bug (`billing.py` `tax_rate` → `tax_pct`) is a `KeyError`, not a logic error. Any patch plan must stay as a single-line key substitution — expanding it is out of scope.
