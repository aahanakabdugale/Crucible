import subprocess
import sys


def run_build_pipeline(dry_run=True):
    """
    Simulates a CI/CD build pipeline execution step.

    BUG: '--outdated-flag' is passed to the Python interpreter itself (before -c),
    which is an unrecognised option — causes exit code 2 and a CalledProcessError.

    Correct command: [sys.executable, "c", "print('Executing build step...')"]
    """
    # BUG: --outdated-flag is not a valid Python interpreter option
    # FIX: Remove the invalid flag and add check=True for robust error handling.
    cmd = [sys.executable, "-c", "print('Executing build step...')"]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True, # Ensure non-zero exit codes raise CalledProcessError
        )
        return {"status": "SUCCESS", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Pipeline step failed (exit {e.returncode}): {e.stderr.strip()}"
        )