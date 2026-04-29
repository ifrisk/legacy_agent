from __future__ import annotations

from pathlib import Path

from legacy_agent.models import FileAnalysis, FunctionInfo, relative_slug


def _render_function(function: FunctionInfo) -> str:
    params = "\n".join(
        f"- `{param.name}`: type=`{param.annotation or 'unknown'}`, default=`{param.default or 'None'}`"
        for param in function.params
    ) or "- None"
    branches = "\n".join(
        f"- `{branch.expression}`"
        for branch in function.branch_conditions
    ) or "- None detected"
    exceptions = "\n".join(f"- `{item}`" for item in function.raised_exceptions) or "- None detected"
    docstring = function.docstring or "No inline docstring was found."
    return_annotation = function.return_annotation or "unknown"

    return f"""## `{function.qualname}`

- Language: `{function.language}`
- Location: `{function.file_path}:{function.lineno}`
- Returns: `{return_annotation}`

### Summary

{docstring}

### Parameters

{params}

### Branches

{branches}

### Raised Exceptions

{exceptions}
"""


def generate_docs(root: Path, analysis: FileAnalysis, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = Path(analysis.path)
    output_path = output_dir / f"{relative_slug(root, source_path)}.md"

    functions = "\n".join(_render_function(function) for function in analysis.functions)
    if not functions:
        functions = "No functions were detected in this file."

    content = f"""# API Document

- Source File: `{analysis.path}`
- Language: `{analysis.language}`
- Function Count: `{len(analysis.functions)}`

{functions}
"""
    output_path.write_text(content, encoding="utf-8")
    return output_path
