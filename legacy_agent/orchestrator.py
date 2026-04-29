from __future__ import annotations

import json
from pathlib import Path

from legacy_agent.agent_pipeline import FileAgentTrace, LegacyCodeAgentPipeline
from legacy_agent.analyzers import analyze_go_file, analyze_python_file
from legacy_agent.generators import generate_go_test_file
from legacy_agent.llm import LLMConfig
from legacy_agent.models import FileAnalysis, WorkflowResult, relative_slug
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


def execute_workflow(root: Path, output_path: Path, max_repair_attempts: int = 2, llm_config: LLMConfig | None = None) -> WorkflowResult:
    output_path.mkdir(parents=True, exist_ok=True)
    excluded_roots = {output_path.resolve()} if output_path.resolve().is_relative_to(root.resolve()) else set()
    analyses = analyze_project(root, excluded_roots=excluded_roots)
    config = llm_config or LLMConfig()
    workflow = WorkflowResult(
        root_path=str(root),
        output_path=str(output_path),
        files=analyses,
        llm_provider=config.provider,
        llm_model=config.model if config.enabled else None,
    )
    pipeline = LegacyCodeAgentPipeline(config)

    tests_python_dir = output_path / "tests" / "python"
    tests_go_dir = output_path / "tests" / "go"
    docs_dir = output_path / "docs"
    agent_context_dir = output_path / "agent_context"
    agent_context_dir.mkdir(parents=True, exist_ok=True)

    for analysis in analyses:
        trace = FileAgentTrace(file_path=analysis.path, language=analysis.language)
        context = pipeline.understand_code(analysis, trace)
        context_path = agent_context_dir / f"{relative_slug(root, Path(analysis.path))}.json"
        context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")

        doc_path = pipeline.generate_docs(root, analysis, docs_dir)
        workflow.docs.append(str(doc_path))
        if analysis.language == "python":
            test_path = pipeline.generate_python_tests(root, analysis, tests_python_dir, context, trace)
            workflow.python_tests.append(str(test_path))
        elif analysis.language == "go":
            test_path = generate_go_test_file(root, analysis, tests_go_dir)
            workflow.go_tests.append(str(test_path))
            trace.stages.append(
                {
                    "stage": "generate_tests",
                    "used_llm": False,
                    "success": True,
                    "detail": "Go generation currently uses static skeleton generation",
                }
            )
        workflow.agent_traces.append(
            {
                "file_path": trace.file_path,
                "language": trace.language,
                "stages": [item if isinstance(item, dict) else item.__dict__ for item in trace.stages],
            }
        )

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
            repaired_by_llm = False
            for analysis in analyses:
                if analysis.language != "python":
                    continue
                test_path = tests_python_dir / f"test_{relative_slug(root, Path(analysis.path))}.py"
                trace_dict = next((item for item in workflow.agent_traces if item["file_path"] == analysis.path), None)
                trace = FileAgentTrace(file_path=analysis.path, language=analysis.language)
                if pipeline.repair_python_test(analysis, test_path, result.stderr, trace):
                    repaired_by_llm = True
                if trace_dict is not None:
                    trace_dict["stages"].extend(item.__dict__ for item in trace.stages)
            if not repaired_by_llm and not attempt_repair(tests_python_dir, result.stderr):
                break
            workflow.repaired = True

    report_path = output_path / "report.json"
    report_path.write_text(json.dumps(workflow.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return workflow
