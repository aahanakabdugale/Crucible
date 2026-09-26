# AGENTS.md

This file provides comprehensive guidance to AI agents (Bob IDE, Bob Shell, Antigravity, or any LLM-based tool) working in this repository.

---

## Project Purpose

**Crucible** is an autonomous CI/CD failure-triage and self-healing agent. When a test suite or CI/CD pipeline fails, Crucible ingests the pytest failure log, isolates the root cause, generates a minimal surgical patch using Google Gemini AI, re-runs verification, and writes a structured report — entirely without human intervention at any step.

### Core Self-Healing Loop

```
pytest FAILS
    ↓
[TRIAGE]       Extract failing file + error root cause (pure Python regex, no AI overhead)
    ↓
[PATCH]        Send failure log + source + test contract to Gemini 2.5 Flash
               → Gemini reasons across 3 healing domains:
                 1. Syntax & Structural Completeness (SyntaxError, stray tokens, missing keywords)
                 2. Semantic & Silent Logic Bugs (swallowed errors, wrong operators/keys, missing check=True)
                 3. Contract Enforcement (strictly satisfies test assertions)
    ↓
[VERIFICATION] Re-run pytest on patched source file
    ↓
[REPORT]       Write structured report JSON to reports/heal_<timestamp>.json
```

---

## Stack & Dependencies

| Component | Technology | Description |
|---|---|---|
| **Language** | Python 3.12 | Primary execution language |
| **AI Model** | Google Gemini 2.5 Flash | Driven via official `google-genai` SDK |
| **Test Runner** | pytest | Automated test execution & traceback capture |
| **Dashboard** | NiceGUI | Live heal runs, status metrics, and report inspection (`app.py`) |
| **CI/CD** | GitHub Actions | Auto-healing workflow committing to `crucible/auto-fix-<run-number>` |
| **Agent IDE** | IBM Bob 2.0 / Antigravity | AI pair-programming and autonomous agent workflows |

---

## Repository Layout

```
Crucible/
├── scripts/
│   └── run_heal.py            ← CLI entry point: --target flag, triage → patch → verify loop
├── app.py                     ← NiceGUI dashboard (live heal runs + report viewer)
├── demo_sandbox/
│   ├── __init__.py            ← Package root (ensures pytest root imports work)
│   ├── trial_1/               ← E-Commerce billing error (KeyError demo)
│   │   ├── app/billing.py
│   │   └── tests/test_billing.py
│   ├── trial_2/               ← CI/CD pipeline bug (subprocess RuntimeError + missing check=True)
│   │   ├── app/pipeline.py
│   │   └── tests/test_pipeline.py
│   └── trial_3/               ← Deployment config error (unsafe os.environ[] KeyError demo)
│       ├── app/config.py
│       └── tests/test_config.py
├── .github/
│   └── workflows/ci.yml       ← GitHub Actions: auto-heal on push, commit fix to new branch
├── reports/                   ← Runtime scratchpad (gitignored): heal_<timestamp>.json files
├── bob_sessions/              ← Hackathon evidence screenshots
├── .bobrules                  ← Bob agent rules (surgical diffs only, no hardcoded paths)
├── .env                       ← GOOGLE_API_KEY (gitignored — never commit)
├── AGENTS.md                  ← Agent guidance & architecture reference
└── README.md                  ← Project documentation
```

---

## Demo Targets

Three real-world SDLC bug scenarios are included to demonstrate generalization across different failure classes:

| Trial | Domain | Bug Description | Source File | Test File |
|---|---|---|---|---|
| `trial_1` | E-commerce billing | `KeyError` — accessing wrong dict key (`tax_rate` vs `tax_pct`) | `demo_sandbox/trial_1/app/billing.py` | `demo_sandbox/trial_1/tests/test_billing.py` |
| `trial_2` | CI/CD build pipeline | `RuntimeError` — invalid subprocess CLI flag + missing `check=True` / unhandled exit code | `demo_sandbox/trial_2/app/pipeline.py` | `demo_sandbox/trial_2/tests/test_pipeline.py` |
| `trial_3` | Deployment config | `KeyError` — unsafe direct `os.environ[]` access at startup instead of safe default handling | `demo_sandbox/trial_3/app/config.py` | `demo_sandbox/trial_3/tests/test_config.py` |

---

## Commands & Usage

### 1. Setup & Environment
```sh
# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install pytest google-genai python-dotenv nicegui
```

### 2. Run Test Suites
> **IMPORTANT**: Always execute pytest from the **project root** to maintain package import resolution (`demo_sandbox.__init__.py`).
```sh
# Run all demo targets
pytest demo_sandbox/ -v

# Run individual trials
pytest demo_sandbox/trial_1/ -v
pytest demo_sandbox/trial_2/ -v
pytest demo_sandbox/trial_3/ -v
```

### 3. Run the Crucible Healer (CLI)
```sh
# Heal demo targets
python scripts/run_heal.py --target demo_sandbox/trial_1
python scripts/run_heal.py --target demo_sandbox/trial_2
python scripts/run_heal.py --target demo_sandbox/trial_3

# Heal any arbitrary external repository / project
python scripts/run_heal.py --target /path/to/any/python/project
```

### 4. Run the Dashboard
```sh
python app.py
# Web UI served at http://localhost:8080
```

---

## Architecture & Internals (`scripts/run_heal.py`)

### Execution Pipeline

```
--target <path>
  │
  ├─ 1. run_pytest(target)
  │    → subprocess: [sys.executable, -m, pytest, <target/tests>, -v]
  │    → returns (passed: bool, output: str)
  │    → if passed: writes clean report & exits 0
  │
  ├─ 2. detect_source_file(pytest_output, target)
  │    → Dual-pattern traceback parser:
  │        • Pattern 1 (runtime errors): file.py:N:
  │        • Pattern 2 (SyntaxErrors / collection): File "...", line N
  │    → Ignores: venv/, site-packages, _pytest, importlib, test_* files
  │    → returns: deepest app source file Path inside target
  │
  ├─ 3. extract_triage_summary(pytest_output, source_file)
  │    → Pure Python regex extraction directly from pytest output (no LLM call)
  │    → returns: e.g. "billing.py:7 — KeyError: 'tax_rate'"
  │
  ├─ 4. find_test_file(source_file, target)
  │    → Matches test_<source_stem>.py or falls back to first test_*.py in target/tests/
  │    → returns: test file content string (passed as contract context)
  │
  ├─ 5. invoke_full_spectrum_patcher(failure_log, source_file_path, test_file_content)
  │    → Single Gemini call (gemini-2.5-flash)
  │    → Validates required sections: [TRIAGE], [PATCH], [VERIFICATION]
  │    → Overwrites source_file with generated patch
  │    → returns: dict(triage, patch, verification, ai_raw_output)
  │
  ├─ 6. re-run run_pytest(target) [VERIFICATION]
  │    → Confirms whether the patch resolved all test failures
  │
  └─ 7. write_report(report, reports_dir)
       → Persists structured report to reports/heal_<timestamp>.json
```

### Exit Codes

- `0` — Target clean or fix successfully applied and verified.
- `1` — Patch applied but verification still failing, or API/triage error.
- `2` — Invalid target path or unexpected CLI error.

---

## Full-Spectrum Prompt Reasoning

The prompt supplied to `gemini-2.5-flash` enforces simultaneous reasoning across 3 domains:

1. **Syntax & Structural Completeness**:
   - Fixes `SyntaxError`, missing keywords (`return`, `check=True`), unclosed strings, indentation errors.
2. **Semantic & Silent Logic Bugs**:
   - Fixes swallowed exceptions in subprocesses, wrong exit code checks, incorrect mathematical operators, incorrect dict keys, and false SUCCESS returns.
3. **Contract Enforcement & Robustness**:
   - Checks the test assertions to ensure the fix genuinely satisfies the test contract rather than passing by coincidence.

---

## Report JSON Schema

Every run produces a report in `reports/heal_<timestamp>.json` following this schema:

```json
{
  "target": "/absolute/path/to/target",
  "timestamp": "2026-09-26T09:07:03+00:00",
  "status": "healed | clean | unresolved",
  "triage": {
    "raw": "billing.py:7 — KeyError: 'tax_rate'"
  },
  "patch": {
    "raw": "<full corrected source file content>"
  },
  "verification": {
    "command": "pytest .../tests",
    "result": "PASSED | FAILED",
    "output": "<pytest stdout and stderr>"
  },
  "ai_raw_output": "<full raw response from Gemini>",
  "initial_failure": "<pytest failure traceback before patch>"
}
```

---

## GitHub Actions CI Workflow (`.github/workflows/ci.yml`)

The automated self-healing CI workflow operates as follows:

1. **Trigger**: Runs on every `push` to any branch and `workflow_dispatch`.
2. **Test Run**: Executes `pytest demo_sandbox/ -v`.
3. **Condition - Pass**: If all tests pass, workflow completes with success.
4. **Condition - Failure**:
   - Iterates through target trials (`trial_1`, `trial_2`, `trial_3`) to find failing target.
   - Executes `python scripts/run_heal.py --target "$TARGET"`.
5. **Auto-Fix Branch & Push**:
   - If verification passes (`exit code 0`):
     - Creates isolated branch `crucible/auto-fix-<run-number>`.
     - Commits only the modified source file(s) with message `Crucible auto-fix: <triage summary>`.
     - Pushes the branch to remote (**never pushes directly to `main` or triggering branch**).
   - If verification fails (`exit code != 0`):
     - Logs triage and patch output and fails the job.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | **Yes** | Google Gemini API key — loaded from `.env` or system environment. |
| `GEMINI_API_KEY` | **CI Only** | GitHub Secret name mapped to `GOOGLE_API_KEY` in GitHub Actions. |
| `APP_ENV` | Optional | Deployment environment name (used in `trial_3` config demo). |

---

## Critical Execution Rules for AI Agents

- **`--target` flag only**: Never hardcode repository or trial paths in scripts, tests, or rules. The target path must always be passed dynamically.
- **Surgical diffs only**: Gemini is instructed to change only the broken statements. Never reformat, rewrite passing functions, or alter unaffected code.
- **Never modify test files**: The test suite defines the immutable contract. Only source files under `app/` are patched.
- **Run pytest from project root**: Tests rely on relative package resolution from the workspace root.
- **Ignore noise directories**: Always exclude `venv/`, `.git/`, `__pycache__/`, `.pytest_cache/`, `reports/`, and `node_modules` during analysis and file crawling.
- **Strict Output Format**: Every heal operation must cleanly emit `[TRIAGE]`, `[PATCH]`, and `[VERIFICATION]` sections.
