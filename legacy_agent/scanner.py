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


def scan_source_files(root: Path, excluded_roots: set[Path] | None = None) -> dict[str, list[Path]]:
    python_files: list[Path] = []
    go_files: list[Path] = []
    excluded = {path.resolve() for path in (excluded_roots or set())}

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        resolved = path.resolve()
        if any(resolved == excluded_root or excluded_root in resolved.parents for excluded_root in excluded):
            continue
        if path.suffix == ".py":
            python_files.append(path)
        elif path.suffix == ".go" and not path.name.endswith("_test.go"):
            go_files.append(path)

    return {"python": sorted(python_files), "go": sorted(go_files)}
