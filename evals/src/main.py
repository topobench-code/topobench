from __future__ import annotations

import argparse
from pathlib import Path

from clients import parse_request_args
from evals import run_benchmarks
from puzzles import RUNS_DIR, list_puzzle_names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run TopoBench benchmark evaluations and verify them locally."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one or more puzzle benchmarks.")
    add_run_arguments(run_parser)

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify a completed run using the copied submodule verifiers.",
    )
    verify_parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Run directory under results/runs/ or an absolute path.",
    )

    combined_parser = subparsers.add_parser(
        "run-and-verify",
        help="Run the benchmark and immediately verify it.",
    )
    add_run_arguments(combined_parser)

    return parser


def add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        required=True,
        choices=["openai", "openrouter", "deepseek", "anthropic", "google"],
        help="Which API provider client to use.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Provider-specific model id.",
    )
    parser.add_argument(
        "--variant",
        default="plain",
        choices=["plain", "intformat", "intformat_json"],
        help="Which published dataset/prompt variant to use.",
    )
    parser.add_argument(
        "--difficulty",
        default="all",
        choices=["all", "easy", "medium", "hard"],
        help="Filter benchmark rows by difficulty.",
    )
    parser.add_argument(
        "--puzzle",
        action="append",
        choices=["all", *list_puzzle_names()],
        help="Puzzle(s) to run. Repeat the flag to select several. Defaults to all.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of rows per selected puzzle after filtering.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=8192,
        help="Provider output token limit.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Optional sampling temperature.",
    )
    parser.add_argument(
        "--request-arg",
        action="append",
        default=[],
        help="Extra provider request arg in KEY=VALUE form. VALUE may be JSON.",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Optional custom run directory name.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing run directory of the same name.",
    )


def resolve_run_dir(path: Path) -> Path:
    if path.is_absolute():
        return path
    return RUNS_DIR / path


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "verify":
        from evals_verifier import verify_run

        verify_run(resolve_run_dir(args.run_dir))
        return

    request_args = parse_request_args(args.request_arg)
    run_dir = run_benchmarks(
        provider=args.provider,
        model=args.model,
        variant=args.variant,
        difficulty=args.difficulty,
        puzzle_names=args.puzzle or ["all"],
        limit=args.limit,
        max_output_tokens=args.max_output_tokens,
        temperature=args.temperature,
        request_args=request_args,
        run_name=args.run_name,
        overwrite=args.overwrite,
    )
    print(f"Run saved to: {run_dir}")

    if args.command == "run-and-verify":
        from evals_verifier import verify_run

        verify_run(run_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Interrupted.")
    except Exception as exc:
        raise SystemExit(str(exc))
