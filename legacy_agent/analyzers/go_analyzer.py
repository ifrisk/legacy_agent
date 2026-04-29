from __future__ import annotations

import re
from pathlib import Path

from legacy_agent.models import BranchCondition, FileAnalysis, FunctionInfo, FunctionParam


FUNC_RE = re.compile(
    r"func\s*(\((?P<receiver>[^)]+)\)\s*)?(?P<name>[A-Za-z_]\w*)\s*"
    r"\((?P<params>[^)]*)\)\s*(?P<returns>\([^)]*\)|[^{\n]+)?\{",
    re.MULTILINE,
)

IF_RE = re.compile(r"^\s*if\s+(?P<expr>.+?)\s*\{", re.MULTILINE)


def _parse_params(raw: str) -> list[FunctionParam]:
    params: list[FunctionParam] = []
    if not raw.strip():
        return params
    for chunk in raw.split(","):
        part = chunk.strip()
        if not part:
            continue
        pieces = part.split()
        if len(pieces) == 1:
            params.append(FunctionParam(name=pieces[0]))
            continue
        annotation = pieces[-1]
        names = pieces[:-1]
        for name in names:
            params.append(FunctionParam(name=name, annotation=annotation))
    return params


def analyze_go_file(path: Path) -> FileAnalysis:
    source = path.read_text(encoding="utf-8")
    functions: list[FunctionInfo] = []
    lines = source.splitlines()

    for match in FUNC_RE.finditer(source):
        receiver = match.group("receiver")
        name = match.group("name")
        params = _parse_params(match.group("params"))
        returns = (match.group("returns") or "").strip() or None
        lineno = source[: match.start()].count("\n") + 1
        branch_conditions: list[BranchCondition] = []
        snippet = "\n".join(lines[lineno - 1 : min(len(lines), lineno + 30)])
        for if_match in IF_RE.finditer(snippet):
            expr = if_match.group("expr").strip()
            branch_conditions.append(BranchCondition(expression=expr))

        qualname = name if receiver is None else f"{receiver}.{name}"
        functions.append(
            FunctionInfo(
                name=name,
                qualname=qualname,
                language="go",
                file_path=str(path),
                lineno=lineno,
                end_lineno=lineno,
                params=params,
                return_annotation=returns,
                branch_conditions=branch_conditions,
                receiver=receiver,
                is_method=receiver is not None,
            )
        )

    return FileAnalysis(path=str(path), language="go", functions=functions)
