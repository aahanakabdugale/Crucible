# Crucible — Autonomous CI/CD Self-Healing Agent

> **Triage → Patch → Verify.** Crucible ingests a test failure, isolates the root cause, generates a surgical fix using Gemini AI, and re-runs verification — entirely without human intervention.

---

## What It Does

When a CI/CD pipeline or test suite fails, developers typically:
1. Read the failure log manually
2. Trace the root cause
3. Write a fix
4. Re-run tests to verify

Crucible automates this entire loop. Point it at any Python repository with a `tests/` folder and it handles the rest.

```
pytest FAILS
    ↓
[TRIAGE]   Detect failing file + error type from traceback
    ↓
[PATCH]    Send failure log + source + test to Gemini 2.5 Flash
           → Gemini reasons across 3 domains:
             1. Syntax & structural errors (SyntaxError, missing keywords)
             2. Silent logic bugs (swallowed exceptions, wrong operators, missing check=True)
             3. Contract enforcement (does the fix actually satisfy all test assertions?)
    ↓
[VERIFY]   Re-run pytest on the patched file
    ↓
[REPORT]   Write structured JSON to reports/
```

---

## Demo Targets

Three real-world SDLC bug scenarios are included, each proving generalization:

| Trial | Domain | Bug Type | File |
|---|---|---|---|
| `trial_1` | E-commerce billing | `KeyError` — wrong dict key | `billing.py` |
| `trial_2` | CI/CD build pipeline | `RuntimeError` — invalid subprocess flag + missing `check=True` | `pipeline.py` |
| `trial_3` | Deployment config | `KeyError` — unsafe `os.environ[]` access at startup | `config.py` |

---

## Repository Structure

```
Crucible/
├── scripts/
│   └── run_heal.py            ← Core agent: --target flag, triage → patch → verify loop
├── app.py                     ← NiceGUI dashboard (live heal runs + report viewer)
├── demo_sandbox/
│   ├── __init__.py
│   ├── trial_1/               ← E-Commerce billing error(basic mathematics) KeyError demo
│   │   ├── app/billing.py
│   │   └── tests/test_billing.py
│   ├── trial_2/               ← CI/CD pipeline bug demo
│   │   ├── app/pipeline.py
│   │   └── tests/test_pipeline.py
│   └── trial_3/               ← Env config KeyError demo
│       ├── app/config.py
│       └── tests/test_config.py
├── .github/
│   └── workflows/ci.yml       ← GitHub Actions: auto-heal on push, commit fix to new branch
├── reports/                   ← Runtime scratchpad (gitignored): heal JSON outputs
├── bob_sessions/              ← Hackathon evidence screenshots
├── AGENTS.md                  ← Bob IDE project context
├── PRD.md                     ← Product requirements
└── .bobrules                  ← Bob agent rules (surgical diffs only, no hardcoded paths)
```

---

## Setup

**Prerequisites:** Python 3.12, a Gemini API key

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/Crucible.git
cd Crucible

# 2. Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install pytest google-genai python-dotenv nicegui

# 4. Set your Gemini API key
# Create a .env file in the project root:
echo GOOGLE_API_KEY=your_key_here > .env
```

---

## Usage

### Run the healer from the command line

```bash
# Heal trial_1 (billing KeyError)
python scripts/run_heal.py --target demo_sandbox/trial_1

# Heal trial_2 (CI/CD pipeline bug)
python scripts/run_heal.py --target demo_sandbox/trial_2

# Heal trial_3 (env config KeyError)
python scripts/run_heal.py --target demo_sandbox/trial_3

# Point at any external repo
python scripts/run_heal.py --target /path/to/any/python/project
```

### Run the dashboard

```bash
python app.py
# Opens at http://localhost:8080
```

The dashboard lets you:
- Select and inspect any past report (triage, patch, verification)
- Choose a target and click **Run Heal** to trigger a live heal cycle
- Watch the report list refresh automatically after each run

### Run the test suites manually

```bash
# Run all demo targets from the project root
pytest demo_sandbox/ -v

# Run a specific trial
pytest demo_sandbox/trial_1/ -v
pytest demo_sandbox/trial_2/ -v
pytest demo_sandbox/trial_3/ -v
```

---

## How the Healer Works

### `scripts/run_heal.py`

| Function | Role |
|---|---|
| `run_pytest(target)` | Runs `pytest` via subprocess, captures full output |
| `detect_source_file(output, target)` | Dual-pattern traceback parser: handles `file.py:N:` (runtime) and `File "...", line N` (SyntaxError) format. Skips `venv/`, `_pytest`, `test_*` files |
| `extract_triage_summary(output, file)` | Extracts a crisp 1-line summary from the traceback — no AI call |
| `find_test_file(source, target)` | Locates `test_<stem>.py` so Gemini can reason against the test contract |
| `invoke_full_spectrum_patcher(log, src, test)` | Single Gemini call: failure log + source + test file → structured `[TRIAGE]` / `[PATCH]` / `[VERIFICATION]` response |
| `write_report(report, dir)` | Writes timestamped JSON to `reports/` |

### Gemini Prompt — Three Healing Domains

The prompt instructs Gemini to reason across all three simultaneously:

1. **Syntax & Structural** — SyntaxErrors, stray tokens, missing keywords (`check=True`, `return`)
2. **Semantic & Silent Logic** — Swallowed subprocess failures, wrong operators, wrong dict keys, false SUCCESS states
3. **Contract Enforcement** — Every `assert` in the test must be genuinely satisfied, not by coincidence

### Output Format

Every heal run prints:

```
[TRIAGE]  billing.py:7 — KeyError: 'tax_rate'
[PATCH]   Gemini AI output (full corrected file written back to disk)
[VERIFICATION]  PASSED — 1 passed in 0.01s
[OK] Crucible healed the target successfully.
```

And writes a structured report to `reports/heal_<timestamp>.json`.

---

## GitHub Actions CI

The workflow at [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push:

1. Runs `pytest demo_sandbox/`
2. If tests **pass** → reports success
3. If tests **fail** → runs `scripts/run_heal.py` against the failing target
4. If the patch **passes verification**:
   - Creates a branch `crucible/auto-fix-<run-number>`
   - Commits the patched file with message: `Crucible auto-fix: <triage summary>`
   - Pushes the branch — **never commits to `main` or the triggering branch**
5. If the patch **fails verification** → logs triage output and fails the job

### Setup required

Add your Gemini key as a GitHub secret:
```
Repository → Settings → Secrets and variables → Actions → New repository secret
Name:   GEMINI_API_KEY
Value:  <your Gemini API key>
```

---

## Report JSON Schema

Each file in `reports/` follows this schema:

```json
{
  "target": "absolute/path/to/target",
  "timestamp": "2026-09-26T09:07:03+00:00",
  "status": "healed | clean | unresolved",
  "triage": { "raw": "billing.py, line 7 — KeyError: 'tax_rate'" },
  "patch":  { "raw": "<full corrected source file>" },
  "verification": {
    "command": "pytest .../tests",
    "result": "PASSED",
    "output": "1 passed in 0.01s"
  },
  "ai_raw_output": "<full Gemini response>",
  "initial_failure": "<full pytest output before patch>"
}
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | Gemini API key — read from `.env` or environment |
| `APP_ENV` | No | Deployment environment name (used in trial_3 demo) |

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12 |
| AI model | Google Gemini 2.5 Flash (`google-genai` SDK) |
| Test runner | pytest |
| Dashboard | NiceGUI |
| CI/CD | GitHub Actions |
| Agent IDE | IBM Bob 2.0 |

---

## Key Design Principles

- **`--target` flag only** — the target repo path is never hardcoded anywhere
- **Surgical patches** — Gemini is instructed to change only what is broken, leave all other lines untouched
- **Full-spectrum healing** — one Gemini call covers crashes, silent bugs, and contract violations simultaneously
- **No external DB** — reports are plain JSON files on disk
- **Offline-capable** — dashboard reads from `reports/` directly, no network needed to view past results
