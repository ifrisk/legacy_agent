from __future__ import annotations

from pathlib import Path

from legacy_agent.models import FileAnalysis, FunctionInfo, relative_slug


def _detect_package_name(source_path: Path) -> str:
    for line in source_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("package "):
            return stripped.split()[1]
    return "main"


def _render_case_comment(function: FunctionInfo) -> str:
    if not function.branch_conditions:
        return "// TODO: Add boundary-focused test cases for this legacy function."
    lines = ["// Candidate branches discovered during static analysis:"]
    for branch in function.branch_conditions[:5]:
        lines.append(f"// - {branch.expression}")
    return "\n".join(lines)


def generate_go_test_file(root: Path, analysis: FileAnalysis, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = Path(analysis.path)
    output_path = output_dir / f"{relative_slug(root, source_path)}_test.go"
    package_name = _detect_package_name(source_path)

    test_functions: list[str] = []
    for function in analysis.functions:
        test_name = f"Test{function.name}"
        test_functions.append(
            f"""
func {test_name}(t *testing.T) {{
    {_render_case_comment(function)}
    t.Skip("Generated skeleton: fill expected values before enabling in CI")
}}
"""
        )

    if not test_functions:
        test_functions.append(
            """
func TestPlaceholder(t *testing.T) {
    t.Skip("No Go functions found for test generation")
}
"""
        )

    content = f"""package {package_name}

import "testing"
{''.join(test_functions)}
"""
    output_path.write_text(content, encoding="utf-8")
    return output_path
