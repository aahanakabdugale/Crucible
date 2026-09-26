import pytest
from demo_sandbox.trial_2.app.pipeline import run_build_pipeline


def test_pipeline_execution():
    """
    Verifies the build pipeline step completes successfully.
    Fails if:
      - the subprocess exits non-zero (bad CLI flag, missing check=True)
      - the command produces no output (silent failure swallowed by missing check=True)
    """
    res = run_build_pipeline(dry_run=True)
    assert res["status"] == "SUCCESS", (
        f"Pipeline step reported failure: {res}"
    )
    assert res.get("output", "").strip() != "", (
        "Pipeline step returned empty output — subprocess may have failed silently "
        "(check=True missing or command did not execute)"
    )
