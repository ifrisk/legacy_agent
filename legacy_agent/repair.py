from __future__ import annotations

from pathlib import Path


def attempt_repair(test_dir: Path, stderr: str) -> bool:
    repaired = False
    for path in test_dir.glob("test_*.py"):
        content = path.read_text(encoding="utf-8")
        updated = content

        if "NameError: name 'Path' is not defined" in stderr and "from pathlib import Path" not in updated:
            updated = updated.replace("import importlib.util\n", "import importlib.util\nfrom pathlib import Path\n")

        if "SyntaxError" in stderr:
            updated = updated.replace("\r\n", "\n")

        if updated != content:
            path.write_text(updated, encoding="utf-8")
            repaired = True
    return repaired
