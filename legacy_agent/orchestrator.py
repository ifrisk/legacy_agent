from __future__ import annotations

import json
from pathlib import Path

from legacy_agent.analyzers import analyze_go_file, analyze_python_file
from legacy_agent.generators import generate_docs, generate_go_test_file, generate_python_test_file
from legacy_agent.models import FileAnalysis, WorkflowResult
from legacy_agent.repair import attempt_repair
from legacy_agent.runner import run_generated_python_tests
from legacy_agent.scanner import scan_source_files


def analyze_project(root: Path, excluded_roots: set[Path] | None = None) -> list[FileAnalysis]:
    scanned = scan_source_files(root, excluded_roots=excluded_roots)
    results: list[FileAnalysis] = []
    for path in scanned["python"]:
        results.append(analyze_python_file(path))
    for path in scanned["go"]:
        results.append(analyze_go_file(path))
    return results


def execute_workflow(root: Path, output_path: Path, max_repair_attempts: int = 2) -> WorkflowResult:
    output_path.mkdir(parents=True, exist_ok=True)
    excluded_roots = {output_path.resolve()} if output_path.resolve().is_relative_to(root.resolve()) else set()
    analyses = analyze_project(root, excluded_roots=excluded_roots)
    workflow = WorkflowResult(root_path=str(root), output_path=str(output_path), files=analyses)

    tests_python_dir = output_path / "tests" / "python"
    tests_go_dir = output_path / "tests" / "go"
    docs_dir = output_path / "docs"

    for analysis in analyses:
        doc_path = generate_docs(root, analysis, docs_dir)
        workflow.docs.append(str(doc_path))
        if analysis.language == "python":
            test_path = generate_python_test_file(root, analysis, tests_python_dir)
            workflow.python_tests.append(str(test_path))
        elif analysis.language == "go":
            test_path = generate_go_test_file(root, analysis, tests_go_dir)
            workflow.go_tests.append(str(test_path))

    analysis_path = output_path / "analysis.json"
    analysis_path.write_text(
        json.dumps([item.__dict__ for item in analyses], ensure_ascii=False, indent=2, default=lambda x: x.__dict__),
        encoding="utf-8",
    )

    if tests_python_dir.exists():
        for _ in range(max_repair_attempts + 1):
            result = run_generated_python_tests(tests_python_dir)
            workflow.test_runs.append(result)
            if result.returncode == 0:
                break
            if not attempt_repair(tests_python_dir, result.stderr):
                break
            workflow.repaired = True

    report_path = output_path / "report.json"
    report_path.write_text(json.dumps(workflow.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return workflow
