from __future__ import annotations

import argparse
import json
from pathlib import Path

from legacy_agent.llm import LLMConfig
from legacy_agent.orchestrator import analyze_project, execute_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legacy-agent",
        description="Generate legacy-code tests and documentation from Python/Go codebases.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Run static analysis only.")
    analyze_parser.add_argument("--path", required=True, help="Source project root.")
    analyze_parser.add_argument("--out", required=True, help="Artifact output directory.")

    run_parser = subparsers.add_parser("run", help="Run full generation workflow.")
    run_parser.add_argument("--path", required=True, help="Source project root.")
    run_parser.add_argument("--out", required=True, help="Artifact output directory.")
    run_parser.add_argument(
        "--max-repair-attempts",
        type=int,
        default=2,
        help="Maximum number of repair attempts after a failed generated-test run.",
    )
    run_parser.add_argument(
        "--llm-provider",
        default="none",
        choices=["none", "openai"],
        help="LLM provider used for code understanding, test generation, and repair.",
    )
    run_parser.add_argument(
        "--llm-model",
        default="gpt-5",
        help="Model name for the configured LLM provider.",
    )
    run_parser.add_argument(
        "--llm-api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable name that stores the LLM API key.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.path).resolve()
    out = Path(args.out).resolve()

    if args.command == "analyze":
        out.mkdir(parents=True, exist_ok=True)
        excluded_roots = {out.resolve()} if out.resolve().is_relative_to(root.resolve()) else set()
        analyses = analyze_project(root, excluded_roots=excluded_roots)
        payload = [item.__dict__ for item in analyses]
        result_path = out / "analysis.json"
        result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=lambda x: x.__dict__), encoding="utf-8")
        print(f"Analysis written to {result_path}")
        return 0

    if args.command == "run":
        llm_config = LLMConfig(
            provider=args.llm_provider,
            model=args.llm_model,
            api_key_env=args.llm_api_key_env,
        )
        result = execute_workflow(root, out, max_repair_attempts=args.max_repair_attempts, llm_config=llm_config)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1
