from __future__ import annotations

import importlib.util
import itertools
import json
from pathlib import Path
from typing import Any

from legacy_agent.models import FileAnalysis, FunctionInfo, relative_slug


def _annotation_hint(annotation: str | None) -> str:
    return (annotation or "").lower()


def _default_value_for_annotation(annotation: str | None) -> Any:
    hint = _annotation_hint(annotation)
    if "int" in hint:
        return 0
    if "float" in hint:
        return 0.0
    if "bool" in hint:
        return False
    if "str" in hint:
        return ""
    if "list" in hint or "sequence" in hint or "tuple" in hint:
        return []
    if "dict" in hint or "mapping" in hint:
        return {}
    return None


def _boundary_values(function: FunctionInfo, param_name: str, annotation: str | None) -> list[Any]:
    values: list[Any] = []
    hint = _annotation_hint(annotation)
    if "int" in hint:
        values.extend([-1, 0, 1])
    elif "float" in hint:
        values.extend([-1.0, 0.0, 1.0])
    elif "bool" in hint:
        values.extend([False, True])
    elif "str" in hint:
        values.extend(["", "sample", "x" * 32])
    elif "list" in hint or "sequence" in hint:
        values.extend([[], [1], [1, 2, 3]])
    elif "dict" in hint or "mapping" in hint:
        values.extend([{}, {"key": "value"}])

    for branch in function.branch_conditions:
        if param_name not in branch.variables:
            continue
        for constant in branch.constants:
            if isinstance(constant, bool):
                values.append(constant)
            elif isinstance(constant, int):
                values.extend([constant - 1, constant, constant + 1])
            elif isinstance(constant, float):
                values.extend([constant - 0.1, constant, constant + 0.1])
            elif isinstance(constant, str):
                values.extend(["", constant])

    if not values:
        values.append(_default_value_for_annotation(annotation))

    unique: list[Any] = []
    seen: set[str] = set()
    for value in values:
        marker = json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(value)
    return unique[:4]


def _build_cases(function: FunctionInfo) -> list[dict[str, Any]]:
    callable_params = [
        param
        for param in function.params
        if param.name != "self" and param.kind == "positional_or_keyword"
    ]
    if not callable_params:
        return [{"label": "default", "kwargs": {}}]

    base = {
        param.name: _default_value_for_annotation(param.annotation)
        for param in callable_params
    }
    cases = [{"label": "default", "kwargs": dict(base)}]

    for param in callable_params:
        for index, boundary in enumerate(_boundary_values(function, param.name, param.annotation)):
            kwargs = dict(base)
            kwargs[param.name] = boundary
            cases.append({"label": f"{param.name}_{index}", "kwargs": kwargs})

    unique_cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for case in cases:
        marker = json.dumps(case["kwargs"], ensure_ascii=True, sort_keys=True, default=str)
        if marker in seen:
            continue
        seen.add(marker)
        unique_cases.append(case)
    return unique_cases[:8]


def _load_module(file_path: Path) -> tuple[Any | None, str | None]:
    module_name = f"legacy_agent_dynamic_{file_path.stem}_{abs(hash(file_path))}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        return None, "Could not create import spec"
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - generator should stay resilient
        return None, f"{type(exc).__name__}: {exc}"
    return module, None


def _materialize_observations(function: FunctionInfo) -> list[dict[str, Any]]:
    if function.is_method:
        return []

    module, error = _load_module(Path(function.file_path))
    if error is not None or module is None:
        return [{"label": "import_failure", "kind": "import_error", "error": error}]

    target = getattr(module, function.name, None)
    if target is None or not callable(target):
        return [{"label": "missing_callable", "kind": "import_error", "error": "Callable not found"}]

    observations: list[dict[str, Any]] = []
    for case in _build_cases(function):
        kwargs = case["kwargs"]
        try:
            result = target(**kwargs)
            observations.append(
                {
                    "label": case["label"],
                    "kind": "return",
                    "kwargs": kwargs,
                    "expected": repr(result),
                }
            )
        except Exception as exc:  # pragma: no cover - characterization of current failures
            observations.append(
                {
                    "label": case["label"],
                    "kind": "raises",
                    "kwargs": kwargs,
                    "exception": type(exc).__name__,
                }
            )
    return observations


def _test_method_name(function_name: str, label: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in f"{function_name}_{label}")
    return f"test_{safe}".lower()


def _render_observation(function: FunctionInfo, observation: dict[str, Any]) -> str:
    kwargs_literal = repr(observation.get("kwargs", {}))
    method_name = _test_method_name(function.name, observation["label"])

    if observation["kind"] == "import_error":
        error = observation["error"]
        return f"""    def {method_name}(self):
        self.fail("Unable to import target module/function during generation: {error!r}")
"""

    if observation["kind"] == "raises":
        return f"""    def {method_name}(self):
        with self.assertRaises({observation["exception"]}):
            self.module.{function.name}(**{kwargs_literal})
"""

    expected_literal = observation["expected"]
    return f"""    def {method_name}(self):
        result = self.module.{function.name}(**{kwargs_literal})
        self.assertEqual(repr(result), {expected_literal!r})
"""


def generate_python_test_file(root: Path, analysis: FileAnalysis, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = Path(analysis.path)
    file_slug = relative_slug(root, source_path)
    output_path = output_dir / f"test_{file_slug}.py"

    classes: list[str] = []
    for function in analysis.functions:
        if function.is_method:
            continue
        observations = _materialize_observations(function)
        if not observations:
            continue
        class_name = "".join(ch if ch.isalnum() else "_" for ch in function.name.title())
        methods = "".join(_render_observation(function, item) for item in observations)
        classes.append(
            f"""
class Test{class_name}(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_target_module(TARGET_FILE)
{methods}
"""
        )

    if not classes:
        classes.append(
            """
class TestNoTopLevelFunctions(unittest.TestCase):
    def test_placeholder(self):
        self.skipTest("No top-level Python functions were found for characterization.")
"""
        )

    content = f"""import importlib.util
from pathlib import Path
import unittest


TARGET_FILE = Path(r\"{str(source_path)}\")


def _load_target_module(file_path: Path):
    spec = importlib.util.spec_from_file_location("legacy_target_module", file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {{file_path}}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
{''.join(classes)}


if __name__ == "__main__":
    unittest.main()
"""
    output_path.write_text(content, encoding="utf-8")
    return output_path
