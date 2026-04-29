from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legacy_agent.generators.docs import generate_docs
from legacy_agent.generators.python_tests import generate_python_test_file
from legacy_agent.llm import LLMConfig, LLMError, NullLLMProvider, build_llm_provider
from legacy_agent.models import FileAnalysis, FunctionInfo, relative_slug


@dataclass
class AgentStageRecord:
    stage: str
    used_llm: bool
    success: bool
    detail: str


@dataclass
class FileAgentTrace:
    file_path: str
    language: str
    stages: list[AgentStageRecord] = field(default_factory=list)


class LegacyCodeAgentPipeline:
    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self.provider_error: str | None = None
        try:
            self.provider = build_llm_provider(self.config)
        except LLMError as exc:
            self.provider = NullLLMProvider()
            self.provider_error = str(exc)

    def _record(self, trace: FileAgentTrace, stage: str, used_llm: bool, success: bool, detail: str) -> None:
        trace.stages.append(
            AgentStageRecord(
                stage=stage,
                used_llm=used_llm,
                success=success,
                detail=detail,
            )
        )

    def _function_payload(self, function: FunctionInfo) -> dict[str, Any]:
        return {
            "name": function.name,
            "qualname": function.qualname,
            "params": [param.__dict__ for param in function.params],
            "return_annotation": function.return_annotation,
            "branch_conditions": [branch.__dict__ for branch in function.branch_conditions],
            "raised_exceptions": function.raised_exceptions,
            "source": function.source,
        }

    def understand_code(self, analysis: FileAnalysis, trace: FileAgentTrace) -> dict[str, Any]:
        fallback = {
            "file_path": analysis.path,
            "language": analysis.language,
            "functions": [self._function_payload(function) for function in analysis.functions],
        }
        if not self.config.enabled:
            self._record(trace, "understand_code", used_llm=False, success=True, detail=f"Static summary for {len(analysis.functions)} functions")
            return fallback
        if self.provider_error:
            self._record(trace, "understand_code", used_llm=True, success=False, detail=self.provider_error)
            return fallback

        prompt = json.dumps(
            {
                "task": "Summarize the legacy source file for automated test generation.",
                "file_path": analysis.path,
                "language": analysis.language,
                "functions": fallback["functions"],
            },
            ensure_ascii=False,
            indent=2,
        )
        instructions = (
            "You are a senior software testing agent. "
            "Return JSON only with keys summary, risks, candidate_boundaries, and test_strategy. "
            "Keep each field concise and grounded in the provided source."
        )
        try:
            result = self.provider.generate_json(instructions=instructions, prompt=prompt)
            self._record(trace, "understand_code", used_llm=True, success=True, detail="LLM code understanding completed")
            return result
        except LLMError as exc:
            self._record(trace, "understand_code", used_llm=True, success=False, detail=str(exc))
            return fallback

    def generate_python_tests(
        self,
        root: Path,
        analysis: FileAnalysis,
        output_dir: Path,
        context: dict[str, Any],
        trace: FileAgentTrace,
    ) -> Path:
        if self.config.enabled and not self.provider_error and any(not function.is_method for function in analysis.functions):
            source_path = Path(analysis.path)
            prompt = json.dumps(
                {
                    "task": "Generate a complete Python unittest file for the target legacy module.",
                    "target_file": str(source_path),
                    "analysis": context,
                    "requirements": [
                        "Return JSON only",
                        "Include a single field named test_code",
                        "Use only Python standard library unittest",
                        "Load the target module from TARGET_FILE using importlib.util",
                        "Generate multiple characterization tests for boundary conditions",
                        "Do not use markdown fences",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            instructions = (
                "You are an automated test-generation agent for legacy Python systems. "
                "Produce a complete executable unittest file that preserves current behavior. "
                "Prefer deterministic assertions and exception checks."
            )
            try:
                result = self.provider.generate_json(instructions=instructions, prompt=prompt)
                test_code = result.get("test_code", "")
                if "unittest" in test_code and "TARGET_FILE" in test_code:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    output_path = output_dir / f"test_{relative_slug(root, source_path)}.py"
                    output_path.write_text(test_code, encoding="utf-8")
                    self._record(trace, "generate_tests", used_llm=True, success=True, detail="LLM-generated Python tests were written")
                    return output_path
                raise LLMError("LLM test output did not contain the expected test file structure")
            except LLMError as exc:
                self._record(trace, "generate_tests", used_llm=True, success=False, detail=str(exc))
        elif self.provider_error and self.config.enabled:
            self._record(trace, "generate_tests", used_llm=True, success=False, detail=self.provider_error)

        output_path = generate_python_test_file(root, analysis, output_dir)
        self._record(trace, "generate_tests", used_llm=False, success=True, detail="Fell back to static Python test generation")
        return output_path

    def repair_python_test(self, analysis: FileAnalysis, test_path: Path, stderr: str, trace: FileAgentTrace) -> bool:
        if not self.config.enabled or not test_path.exists():
            self._record(trace, "repair_tests", used_llm=False, success=False, detail="LLM repair disabled or test file missing")
            return False
        if self.provider_error:
            self._record(trace, "repair_tests", used_llm=True, success=False, detail=self.provider_error)
            return False

        prompt = json.dumps(
            {
                "task": "Repair the generated Python unittest file so it passes without changing the target source module.",
                "target_file": analysis.path,
                "test_file": str(test_path),
                "test_code": test_path.read_text(encoding="utf-8"),
                "analysis": {
                    "file_path": analysis.path,
                    "functions": [self._function_payload(function) for function in analysis.functions],
                },
                "test_error": stderr,
                "requirements": [
                    "Return JSON only",
                    "Include keys repaired and test_code",
                    "If no safe fix exists, return repaired=false and keep test_code unchanged",
                    "Do not use markdown fences",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        instructions = (
            "You are a test-repair agent. "
            "Fix only the generated unittest file. "
            "Do not change the production source behavior or invent unsupported imports."
        )
        try:
            result = self.provider.generate_json(instructions=instructions, prompt=prompt)
            repaired = bool(result.get("repaired"))
            repaired_code = result.get("test_code", "")
            if repaired and repaired_code:
                test_path.write_text(repaired_code, encoding="utf-8")
                self._record(trace, "repair_tests", used_llm=True, success=True, detail="LLM repaired the generated Python tests")
                return True
            self._record(trace, "repair_tests", used_llm=True, success=False, detail="LLM declined repair")
            return False
        except LLMError as exc:
            self._record(trace, "repair_tests", used_llm=True, success=False, detail=str(exc))
            return False

    def generate_docs(self, root: Path, analysis: FileAnalysis, output_dir: Path) -> Path:
        return generate_docs(root, analysis, output_dir)
