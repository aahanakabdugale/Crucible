"""
Crucible self-healing loop entry point.

Usage:
    python scripts/run_heal.py --target <path-to-target-repo>

Steps:
    1. TRIAGE  – run pytest on <target>/tests/, capture failure output
    2. PATCH   – invoke Gemini AI to triage + patch the failure
    3. VERIFY  – re-run pytest to confirm the fix
    4. REPORT  – write structured JSON to reports/heal_<timestamp>.json

Exit codes:
    0 – fix applied and verified (or no failures found)
    1 – patch applied but verification still failing
    2 – unexpected error
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure stdout/stderr use UTF-8 on Windows (cp1252 default rejects box-drawing chars)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load .env from project root if present (pip install python-dotenv, or fall back silently)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # python-dotenv not installed; rely on environment variable being set externally


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_pytest(target: Path) -> tuple[bool, str]:
    """
    Run pytest against <target>/tests/.
    Returns (passed: bool, output: str).
    Passes if exit code is 0; any other code means failures or errors.
    """
    tests_dir = target / "tests"
    if not tests_dir.exists():
        # Fall back to running pytest on the target root (discovers tests anywhere)
        tests_dir = target

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests_dir), "-v"],
        capture_output=True,
        text=True,
    )
    combined = result.stdout + result.stderr
    passed = result.returncode == 0
    return passed, combined


def parse_triage_response(ai_output: str) -> dict:
    """
    Extract structured [TRIAGE], [PATCH], [VERIFICATION] sections from the
    AI response text.  Falls back to storing raw text if sections are not found.
    """
    sections = {"triage": {}, "patch": {}, "verification": {}}

    for label, key in (("[TRIAGE]", "triage"), ("[PATCH]", "patch"), ("[VERIFICATION]", "verification")):
        start = ai_output.find(label)
        if start == -1:
            continue
        # Find the next labelled section or end of string
        next_labels = [ai_output.find(l, start + 1)
                       for l in ("[TRIAGE]", "[PATCH]", "[VERIFICATION]")
                       if ai_output.find(l, start + 1) != -1]
        end = min(next_labels) if next_labels else len(ai_output)
        block = ai_output[start + len(label):end].strip()
        sections[key] = {"raw": block}

    return sections


def detect_source_file(pytest_output: str, target: Path) -> Path | None:
    """
    Identify the failing source file from a pytest traceback.

    Handles two traceback formats:
      - Runtime errors:  `demo_sandbox/app/billing.py:7: KeyError`
      - SyntaxErrors:    `File "C:\\...\\billing.py", line 9`

    Skips venv, site-packages, _pytest, importlib, and test_ files.
    Returns the last qualifying candidate inside `target` (deepest frame =
    closest to the actual bug), or None if nothing is found.
    """
    import re

    _SKIP = ("venv/", "site-packages", "_pytest", "importlib")

    def _is_valid(raw: str) -> bool:
        normalised = raw.replace("\\", "/")
        if any(s in normalised for s in _SKIP):
            return False
        name = Path(raw).name
        if name.startswith("test_") or name.endswith("_test.py"):
            return False
        return True

    def _resolve(raw: str) -> Path | None:
        p = Path(raw)
        resolved = p if p.is_absolute() else (Path.cwd() / p).resolve()
        if resolved.exists() and target in resolved.parents:
            return resolved
        return None

    candidates: list[Path] = []

    # Pattern 1 — runtime errors:  path/file.py:N:
    for m in re.finditer(r'([\w/\\.-]+\.py):(\d+):', pytest_output):
        raw = m.group(1)
        if _is_valid(raw):
            r = _resolve(raw)
            if r:
                candidates.append(r)

    # Pattern 2 — SyntaxErrors / collection errors:  File "path/file.py", line N
    for m in re.finditer(r'File "([^"]+\.py)", line \d+', pytest_output):
        raw = m.group(1)
        if _is_valid(raw):
            r = _resolve(raw)
            if r:
                candidates.append(r)

    # Return the last (deepest) unique candidate
    seen: set[Path] = set()
    unique = [c for c in candidates if not (c in seen or seen.add(c))]  # type: ignore[func-returns-value]
    return unique[-1] if unique else None


def extract_triage_summary(pytest_output: str, source_file: Path | None) -> str:
    """
    Extract a crisp 1-line triage summary directly from the pytest traceback.
    Examples:
        billing.py:7 — KeyError: 'tax_rate'
        billing.py:9 — SyntaxError: can't use starred expression here

    Returns "unknown error" if no recognisable error line is found.
    """
    import re

    # Match lines like: "E       KeyError: 'tax_rate'" or "E   SyntaxError: ..."
    err_match = re.search(r'E\s+(\w[\w.]*Error[^:\n]*:[^\n]*)', pytest_output)
    if not err_match:
        # Fallback: any "E   <word>:" line
        err_match = re.search(r'E\s+([A-Z]\w+:[^\n]+)', pytest_output)

    error_text = err_match.group(1).strip() if err_match else "unknown error"

    # Find the line number associated with the source file
    line_no = ""
    if source_file:
        fname = source_file.name
        # Pattern 1: billing.py:7:
        ln = re.search(rf'{re.escape(fname)}:(\d+):', pytest_output)
        if not ln:
            # Pattern 2: File "...billing.py", line 9
            ln = re.search(
                rf'File "[^"]*{re.escape(fname)}", line (\d+)', pytest_output
            )
        if ln:
            line_no = f":{ln.group(1)}"

    file_label = f"{source_file.name}{line_no}" if source_file else "unknown file"
    return f"{file_label} — {error_text}"


def find_test_file(source_file: Path, target: Path) -> str:
    """
    Locate the test file corresponding to source_file and return its content.

    Looks for target/tests/test_<source_stem>.py first, then falls back to
    the first test_*.py found under target/tests/.
    Returns empty string if nothing is found.
    """
    tests_dir = target / "tests"
    if not tests_dir.exists():
        return ""

    # Exact match: test_pipeline.py for pipeline.py
    exact = tests_dir / f"test_{source_file.stem}.py"
    if exact.exists():
        return exact.read_text(encoding="utf-8")

    # Fallback: first test_*.py in tests/
    hits = sorted(tests_dir.glob("test_*.py"))
    return hits[0].read_text(encoding="utf-8") if hits else ""


def invoke_full_spectrum_patcher(
    failure_log: str,
    source_file_path: str,
    test_file_content: str,
) -> dict:
    """
    Full-spectrum Gemini patcher — fixes active failures AND silent logic bugs.

    Sends the failure log, source file, and test file to gemini-2.5-flash in a
    single call. The prompt instructs Gemini to reason across three domains:
      1. Syntax & structural completeness (crashes, syntax errors, missing keywords)
      2. Semantic & silent logic bugs (swallowed errors, wrong return values,
         missing check=True, incorrect operator, silent subprocess failures)
      3. Robustness — ensure implementation strictly satisfies the test contract

    Raises:
        EnvironmentError  – GOOGLE_API_KEY is not set.
        ImportError       – google-genai not installed.
        ConnectionError   – Network or API error.
        RuntimeError      – Response missing required [TRIAGE]/[PATCH]/[VERIFICATION] tags.

    Returns dict with keys: triage, patch, verification (each {"raw": str}),
    and ai_raw_output (full response text).
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. Export it or add it to the .env file."
        )

    source_path = Path(source_file_path)
    source_content = source_path.read_text(encoding="utf-8")

    test_section = (
        f"=== TEST FILE ===\n{test_file_content}\n=== END TEST FILE ==="
        if test_file_content.strip()
        else "=== TEST FILE ===\n(not found)\n=== END TEST FILE ==="
    )

    prompt = (
        "You are Crucible's full-spectrum code-repair engine.\n"
        "Your job is to fix ALL bugs in the source file — both active failures "
        "AND silent logic bugs that may not directly cause a crash.\n\n"

        "HEALING DOMAINS — analyse and fix issues across all three:\n\n"

        "1. SYNTAX & STRUCTURAL COMPLETENESS\n"
        "   - Fix syntax errors, stray/missing tokens, unclosed strings, "
        "mismatched brackets, bad indentation.\n"
        "   - Restore missing keywords (e.g. check=True, return statements, "
        "required arguments).\n\n"

        "2. SEMANTIC & SILENT LOGIC BUGS\n"
        "   - Look beyond the crash. If a subprocess/API call swallows errors "
        "(e.g. missing check=True, unhandled exit codes, masked exceptions "
        "returning false SUCCESS states), identify and fix the silent failure path.\n"
        "   - Fix wrong operators, wrong variable names, wrong CLI flags, "
        "wrong key names that cause incorrect results.\n"
        "   - If the implementation can return a value that satisfies the test "
        "assert by coincidence (even when something is broken), flag and fix it.\n\n"

        "3. ROBUSTNESS — CONTRACT ENFORCEMENT\n"
        "   - Read the test file carefully. Ensure every assert in the test is "
        "genuinely satisfied by the fixed implementation — not by accident.\n"
        "   - Validate inputs/outputs match what the test suite expects.\n\n"

        "STRICT RULES:\n"
        "1. Fix ONLY the source file. Never modify the test file.\n"
        "2. The [PATCH] section must contain the COMPLETE corrected source file — "
        "every single line, nothing omitted, no ellipsis.\n"
        "3. Do NOT use markdown code fences (no ``` or ~~~) anywhere.\n"
        "4. Do NOT add text outside the three required tags.\n"
        "5. Minimal changes — only fix what is wrong.\n\n"

        "Reply in this EXACT format:\n"
        "[TRIAGE]\n"
        "<list ALL issues found: active failures and silent bugs, one per line>\n"
        "[PATCH]\n"
        "<complete corrected source file — every line>\n"
        "[VERIFICATION]\n"
        "<pytest command to verify the fix>\n\n"

        "=== FAILURE LOG ===\n"
        "{failure_log}\n"
        "=== END FAILURE LOG ===\n\n"
        "=== SOURCE FILE: {source_file_path} ===\n"
        "{source_content}\n"
        "=== END SOURCE FILE ===\n\n"
        "{test_section}"
    ).format(
        failure_log=failure_log,
        source_file_path=source_file_path,
        source_content=source_content,
        test_section=test_section,
    )

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = response.text
    except ImportError:
        raise ImportError(
            "google-genai is not installed. Run: pip install google-genai"
        )
    except Exception as exc:
        raise ConnectionError(f"Gemini API call failed: {exc}") from exc

    # Validate all three required tags are present
    for tag in ("[TRIAGE]", "[PATCH]", "[VERIFICATION]"):
        if tag not in raw:
            raise RuntimeError(
                f"Gemini response is missing the '{tag}' tag.\n"
                f"Full response:\n{raw}"
            )

    sections = parse_triage_response(raw)

    # Write patched content back to source file
    patched_content = sections["patch"]["raw"]
    source_path.write_text(patched_content, encoding="utf-8")

    return {
        "triage": sections["triage"],
        "patch": sections["patch"],
        "verification": sections["verification"],
        "ai_raw_output": raw,
    }


def write_report(report: dict, reports_dir: Path) -> Path:
    """Write the structured report JSON to reports/ and return the file path."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = reports_dir / f"heal_{ts}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Structured console output
# ---------------------------------------------------------------------------

def print_section(label: str, content: str) -> None:
    print(f"\n{'='*60}")
    print(label)
    print('='*60)
    print(content)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crucible: autonomous CI failure triage and self-healing loop."
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Path to the target repository to heal (e.g. demo_sandbox).",
    )
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"ERROR: target path does not exist: {target}", file=sys.stderr)
        return 2

    reports_dir = Path(__file__).parent.parent / "reports"

    print(f"Crucible — self-healing loop")
    print(f"Target : {target}")
    print(f"Reports: {reports_dir}")

    # ------------------------------------------------------------------
    # Step 1 — TRIAGE: run pytest, capture failure
    # ------------------------------------------------------------------
    print("\n[TRIAGE] Running pytest on target...")
    passed, pytest_output = run_pytest(target)

    if passed:
        print("\n[OK] No failing tests found. Nothing to heal.")
        report = {
            "target": str(target),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "clean",
            "triage": {"result": "no failures"},
            "patch": {},
            "verification": {"result": "no action taken"},
        }
        out = write_report(report, reports_dir)
        print(f"Report : {out}")
        return 0

    print_section("[TRIAGE] Failure captured", pytest_output)

    # ------------------------------------------------------------------
    # Step 2 — PATCH: detect source file, print triage summary, invoke Gemini
    # ------------------------------------------------------------------

    # Detect the failing source file using both runtime-error and SyntaxError patterns
    source_file = detect_source_file(pytest_output, target)
    if source_file is None:
        # Fallback: first .py file under target/app/
        hits = list((target / "app").rglob("*.py")) if (target / "app").exists() else []
        source_file = Path(hits[0]) if hits else target

    # Print crisp 1-line triage summary extracted directly from traceback (no AI)
    summary = extract_triage_summary(pytest_output, source_file)
    print(f"\n[TRIAGE] {summary}")

    # Load test file content for full-spectrum analysis
    test_content = find_test_file(source_file, target)

    print(f"\n[PATCH] Invoking full-spectrum Gemini patcher on {source_file}...")
    try:
        result = invoke_full_spectrum_patcher(pytest_output, str(source_file), test_content)
    except (EnvironmentError, ImportError, ConnectionError, RuntimeError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        report = {
            "target": str(target),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "unresolved",
            "triage": {"raw": str(exc)},
            "patch": {},
            "verification": {"result": "no action taken"},
            "initial_failure": pytest_output,
        }
        out = write_report(report, reports_dir)
        print(f"\nReport written: {out}")
        return 1

    sections = result
    ai_raw = result.get("ai_raw_output", "")
    print_section("[PATCH] Gemini AI output", ai_raw)

    # ------------------------------------------------------------------
    # Step 3 — VERIFY: re-run pytest
    # ------------------------------------------------------------------
    print("\n[VERIFICATION] Re-running pytest to confirm fix...")
    verify_passed, verify_output = run_pytest(target)

    verify_result = "PASSED" if verify_passed else "FAILED"
    print_section("[VERIFICATION] Result", f"{verify_result}\n\n{verify_output}")

    # ------------------------------------------------------------------
    # Step 4 — Write structured report
    # ------------------------------------------------------------------
    report = {
        "target": str(target),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healed" if verify_passed else "unresolved",
        "triage": sections.get("triage", {}),
        "patch": sections.get("patch", {}),
        "verification": {
            "command": f"pytest {target / 'tests'}",
            "result": verify_result,
            "output": verify_output,
        },
        "ai_raw_output": ai_raw,
        "initial_failure": pytest_output,
    }
    out = write_report(report, reports_dir)
    print(f"\nReport written: {out}")

    if verify_passed:
        print("\n[OK] Crucible healed the target successfully.")
        return 0
    else:
        print("\n[FAIL] Verification still failing after patch attempt.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
