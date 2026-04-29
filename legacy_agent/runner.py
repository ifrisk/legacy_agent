from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from legacy_agent.models import TestExecutionResult


def run_generated_python_tests(test_dir: Path) -> TestExecutionResult:
    command = [sys.executable, "-m", "unittest", "discover", "-s", str(test_dir), "-p", "test_*.py"]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=str(test_dir.parent.parent),
    )
    return TestExecutionResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
