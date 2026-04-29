from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class FunctionParam:
    name: str
    annotation: str | None = None
    default: str | None = None
    kind: str = "positional_or_keyword"


@dataclass
class BranchCondition:
    expression: str
    variables: list[str] = field(default_factory=list)
    constants: list[Any] = field(default_factory=list)


@dataclass
class FunctionInfo:
    name: str
    qualname: str
    language: str
    file_path: str
    lineno: int
    end_lineno: int
    docstring: str | None = None
    params: list[FunctionParam] = field(default_factory=list)
    return_annotation: str | None = None
    branch_conditions: list[BranchCondition] = field(default_factory=list)
    raised_exceptions: list[str] = field(default_factory=list)
    source: str | None = None
    is_method: bool = False
    receiver: str | None = None


@dataclass
class FileAnalysis:
    path: str
    language: str
    functions: list[FunctionInfo] = field(default_factory=list)


@dataclass
class TestExecutionResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass
class WorkflowResult:
    root_path: str
    output_path: str
    files: list[FileAnalysis] = field(default_factory=list)
    python_tests: list[str] = field(default_factory=list)
    go_tests: list[str] = field(default_factory=list)
    docs: list[str] = field(default_factory=list)
    test_runs: list[TestExecutionResult] = field(default_factory=list)
    repaired: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_path": self.root_path,
            "output_path": self.output_path,
            "files": [asdict(item) for item in self.files],
            "python_tests": self.python_tests,
            "go_tests": self.go_tests,
            "docs": self.docs,
            "test_runs": [asdict(item) for item in self.test_runs],
            "repaired": self.repaired,
        }


def relative_slug(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    return "__".join(relative.with_suffix("").parts)
