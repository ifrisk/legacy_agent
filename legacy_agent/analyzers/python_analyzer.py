from __future__ import annotations

import ast
from pathlib import Path

from legacy_agent.models import BranchCondition, FileAnalysis, FunctionInfo, FunctionParam


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self, source: str, file_path: Path) -> None:
        self.source = source
        self.file_path = file_path
        self.stack: list[str] = []
        self.functions: list[FunctionInfo] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(self._build_function(node, is_async=False))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.functions.append(self._build_function(node, is_async=True))
        self.generic_visit(node)

    def _build_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
    ) -> FunctionInfo:
        qual_parts = [*self.stack, node.name]
        params = _extract_params(node)
        qualname = ".".join(qual_parts)
        source_segment = ast.get_source_segment(self.source, node)
        branch_conditions = _extract_branch_conditions(node)
        raised = _extract_raised_exceptions(node)
        return FunctionInfo(
            name=node.name,
            qualname=qualname,
            language="python",
            file_path=str(self.file_path),
            lineno=node.lineno,
            end_lineno=getattr(node, "end_lineno", node.lineno),
            docstring=ast.get_docstring(node),
            params=params,
            return_annotation=ast.unparse(node.returns) if node.returns else None,
            branch_conditions=branch_conditions,
            raised_exceptions=raised,
            source=source_segment,
            is_method=bool(self.stack),
            receiver=self.stack[-1] if self.stack else None,
        )


def _extract_params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[FunctionParam]:
    params: list[FunctionParam] = []
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)

    for arg, default in zip(positional, defaults):
        params.append(
            FunctionParam(
                name=arg.arg,
                annotation=ast.unparse(arg.annotation) if arg.annotation else None,
                default=ast.unparse(default) if default is not None else None,
            )
        )

    if args.vararg:
        params.append(
            FunctionParam(
                name=args.vararg.arg,
                annotation=ast.unparse(args.vararg.annotation) if args.vararg.annotation else None,
                kind="vararg",
            )
        )

    kw_defaults = [None if item is None else item for item in args.kw_defaults]
    for arg, default in zip(args.kwonlyargs, kw_defaults):
        params.append(
            FunctionParam(
                name=arg.arg,
                annotation=ast.unparse(arg.annotation) if arg.annotation else None,
                default=ast.unparse(default) if default is not None else None,
                kind="keyword_only",
            )
        )

    if args.kwarg:
        params.append(
            FunctionParam(
                name=args.kwarg.arg,
                annotation=ast.unparse(args.kwarg.annotation) if args.kwarg.annotation else None,
                kind="varkw",
            )
        )
    return params


def _extract_branch_conditions(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[BranchCondition]:
    conditions: list[BranchCondition] = []
    for child in ast.walk(node):
        if isinstance(child, ast.If):
            expression = ast.unparse(child.test)
            variables = sorted({sub.id for sub in ast.walk(child.test) if isinstance(sub, ast.Name)})
            constants: list[object] = []
            for sub in ast.walk(child.test):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, (str, int, float, bool)):
                    constants.append(sub.value)
            conditions.append(
                BranchCondition(
                    expression=expression,
                    variables=variables,
                    constants=constants,
                )
            )
    return conditions


def _extract_raised_exceptions(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    raised: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Raise) and child.exc is not None:
            if isinstance(child.exc, ast.Call):
                raised.add(ast.unparse(child.exc.func))
            else:
                raised.add(ast.unparse(child.exc))
    return sorted(raised)


def analyze_python_file(path: Path) -> FileAnalysis:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    visitor = _FunctionVisitor(source, path)
    visitor.visit(tree)
    return FileAnalysis(path=str(path), language="python", functions=visitor.functions)
