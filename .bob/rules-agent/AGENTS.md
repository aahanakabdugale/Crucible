# Project Coding Rules (Non-Obvious Only)

- The healing agent entry point (`scripts/run_heal.py`) does not yet exist — create it there when scaffolding.
- `--target` flag is the ONLY way to pass a repo path; never reference a path from `.bobrules` or any rule/mode file.
- Patches must be minimal diffs — never refactor, reformat, or touch lines unrelated to the failure.
- Tests import as `from demo_sandbox.app.<module> import ...` — always run `pytest` from the **project root**, not from inside `demo_sandbox/`.
- `demo_sandbox/app/billing.py` contains an **intentional seeded bug** (`order_data["tax_rate"]` should be `order_data["tax_pct"]`). Do not fix it unless explicitly running a healing-demo pass.
- Verification output must use the exact labels `[TRIAGE]`, `[PATCH]`, `[VERIFICATION]` — these are required by the structured output spec.
- Session screenshots go in `bob_sessions/` — this is a hackathon evidence requirement, not optional.
- `reports/` is a runtime scratchpad; write triage JSON and patch diffs there, never commit them.
