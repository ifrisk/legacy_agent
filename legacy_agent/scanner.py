from __future__ import annotations

from pathlib import Path


IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
}


def _is_ignored_path(path: Path) -> bool:
    for part in path.parts:
        if part in IGNORED_DIRS:
            return True
        if part.startswith("agent_output") or part.startswith("agent_context"):
            return True
    return False


def scan_source_files(root: Path, excluded_roots: set[Path] | None = None) -> dict[str, list[Path]]:
    python_files: list[Path] = []
    go_files: list[Path] = []
    excluded = {path.resolve() for path in (excluded_roots or set())}

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_ignored_path(path):
            continue
        resolved = path.resolve()
        if any(resolved == excluded_root or excluded_root in resolved.parents for excluded_root in excluded):
            continue
        if path.suffix == ".py":
            python_files.append(path)
        elif path.suffix == ".go" and not path.name.endswith("_test.go"):
            go_files.append(path)

    return {"python": sorted(python_files), "go": sorted(go_files)}
