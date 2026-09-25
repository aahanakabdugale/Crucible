Product Requirements Document: Crucible
1. Problem Statement

When a CI/CD pipeline or test suite fails, developers manually read failure logs, trace the root cause, write a fix, and re-run tests to verify — a repetitive, time-consuming loop. There is no autonomous agent that ingests a failure, isolates the exact cause, generates a minimal correct patch, and verifies the fix without human intervention at each step.

2. Solution

Crucible is an autonomous CI/CD failure-triage and self-healing agent, built on IBM Bob (Bob IDE / Bob Shell). It ingests a build/test failure log, isolates the root cause, generates a minimal surgical patch, re-runs verification, and presents a ready-to-commit fix — without rewriting unrelated code or altering passing logic.

Crucible is designed as a generic agent, not bound to any single codebase. It can be pointed at any target repository via a configurable path (--target flag), and operates only on the target it is explicitly given — proven by demonstrating it against a sample bug and then swapping the target to a different repo with no code changes to the agent itself.

3. Objective

Build and demonstrate a working self-healing loop (failure → triage → patch → verify) within the IBM Bob 2.0 Hackathon timeframe, submit it as a public repository on lablab.ai, and prove — via a live demo — that the agent generalizes beyond the bundled sample bug.

4. Tech Stack
Language: Python 3.x
Agent/IDE: Bob IDE / Bob Shell (IBM Bob 2.0)
Test runner: pytest
Version control: Git, single public GitHub repository
CI simulation (optional): GitHub Actions — push → pipeline runs pytest → failure fed to Bob → patch applied → re-run passes
Environment isolation: Python venv (excluded from version control via .gitignore)
5. Features
Failure triage: ingest a raw test/build failure log and identify file, line, and root cause
Minimal patch generation: produce a surgical diff targeting only the failing statement — no unrelated rewrites or formatting changes to passing code
Verification loop: re-run the target's test suite after patching to confirm the fix
Structured output format: every run outputs
[TRIAGE] — file, line, error root cause
[PATCH] — explanation of the surgical change
[VERIFICATION] — command executed and result
Target-agnostic operation: target repository/path is passed as a parameter (CLI flag), never hardcoded into agent rules or modes — proving Crucible works on any repo, not just the bundled demo
Session evidence: each healing pass captured as a screenshot in bob_sessions/ (hackathon requirement)
6. Project Structure
crucible/
├── AGENTS.md              # Generated via Bob /init — persistent project context
├── .bobrules              # Global rules: minimal diffs, no unrelated rewrites, ignore build artifacts/venv/.git
├── .bob/                  # Bob-native config (modes, mode-specific rules — structure per Bob's own /init output)
├── reports/                # Scratchpad: triage JSON, proposed patch diffs, verification logs
├── scripts/
│   └── run_heal.py        # Entry point: takes --target flag, runs triage → patch → verify loop
├── demo-sandbox/           # Sample target with a seeded bug, used for the hackathon demo
│   ├── app/
│   ├── tests/
│   └── requirements.txt
├── bob_sessions/            # Mandatory task screenshots (evidence of healing passes)
├── .gitignore              # Excludes venv/, __pycache__/, *.pyc, .pytest_cache/
└── README.md
7. Demo Scope (Sample Bug)

A seeded KeyError in an e-commerce billing calculation:

demo-sandbox/app/billing.py — BillingService.calculate_invoice() accesses order_data["tax_rate"] directly, when the real payload key is tax_pct
demo-sandbox/tests/test_billing.py — a standard invoice test that fails against this bug
Used to produce the first, reproducible [TRIAGE] → [PATCH] → [VERIFICATION] pass on camera
8. Scope

In scope:

One agent (Crucible), operable against any target repo via a passed-in path
One bundled demo target (demo-sandbox) with one seeded bug, used to prove the loop works