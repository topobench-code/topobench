from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from json_repair import repair_json

from evals import load_json, load_jsonl, write_json
from puzzles import MAPPINGS_DIR, REPORTS_DIR, SUBMODULES_DIR, PUZZLES, build_row_lookup, load_dataset_frame


RLP_PATH = SUBMODULES_DIR / "rlp"
FLOWFREE_PATH = SUBMODULES_DIR / "flowfree"
sys.path.insert(0, str(RLP_PATH))

from rlp.ascii_parser import (  # type: ignore
    check_bridges_structural_validity,
    check_galaxies_structural_validity,
    check_undead_structural_validity,
)
from rlp.puzzle import Puzzle as RLPPuzzle  # type: ignore
from verifier import verify_ascii_state  # type: ignore


MAPPING_FILES = {
    "bridges": "bridges.json",
    "flow_free": "flow_free.json",
    "galaxies": "galaxies.json",
    "loopy": "loopy.json",
    "pattern": "pattern.json",
    "undead": "undead.json",
}

_mapping_cache: dict[str, dict[str, str]] = {}
_puzzle_cache: dict[tuple[str, str], RLPPuzzle] = {}


def _flowfree_verifier_module():
    spec = importlib.util.spec_from_file_location(
        "flowfree_verifier",
        str(FLOWFREE_PATH / "verifier.py"),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load FlowFree verifier module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_mapping(puzzle_type: str) -> dict[str, str]:
    if puzzle_type not in _mapping_cache:
        payload = json.loads(
            (MAPPINGS_DIR / MAPPING_FILES[puzzle_type]).read_text(encoding="utf-8")
        )
        _mapping_cache[puzzle_type] = payload["char_map"]
    return _mapping_cache[puzzle_type]


def decode_intformat_board(encoded_board: str, puzzle_type: str) -> str:
    reverse_map = {value: key for key, value in load_mapping(puzzle_type).items()}
    rows = []
    for line in encoded_board.strip().splitlines():
        cells = [cell.strip() for cell in line.split(",")]
        rows.append("".join(reverse_map.get(cell, "?") for cell in cells))
    return "\n".join(rows)


def decode_intformat_json_board(encoded_board: str, puzzle_type: str) -> str:
    reverse_map = {value: key for key, value in load_mapping(puzzle_type).items()}
    try:
        grid = json.loads(encoded_board)
    except json.JSONDecodeError:
        try:
            grid = ast.literal_eval(encoded_board)
        except (SyntaxError, ValueError):
            return encoded_board
    if not isinstance(grid, list):
        return encoded_board
    rows = []
    for row in grid:
        if not isinstance(row, list):
            return encoded_board
        rows.append("".join(reverse_map.get(str(cell), "?") for cell in row))
    return "\n".join(rows)


def extract_board(response_text: str) -> str | None:
    if not response_text:
        return None

    candidates: list[str] = []

    stripped = response_text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        candidates.append(stripped)

    fenced = re.findall(r"```(?:json)?\s*(.*?)\s*```", response_text, re.DOTALL)
    candidates.extend(fenced)

    object_matches = re.findall(r"(\{.*?\})", response_text, re.DOTALL)
    candidates.extend(object_matches)

    for candidate in reversed(candidates):
        try:
            fixed = repair_json(candidate)
            parsed = json.loads(fixed)
        except Exception:
            continue

        if isinstance(parsed, dict) and "response" in parsed:
            value = parsed["response"]
            return value if isinstance(value, str) else json.dumps(value)
        if isinstance(parsed, list):
            return json.dumps(parsed)

    return None


def verify_flow_free(problem_ascii: str, extracted_board: str) -> dict[str, Any]:
    verifier = _flowfree_verifier_module()
    solver_src = str(FLOWFREE_PATH / "flowfree_all_solutions.c")
    solver_bin = str(FLOWFREE_PATH / "flowfree_all_solutions")
    result = {
        "board_exists": bool(extracted_board),
        "board_valid": False,
        "board_modified": False,
        "correct": False,
    }
    if not extracted_board:
        return result

    is_valid, _ = verifier.verify_solution(
        problem_ascii,
        extracted_board,
        solver_src=solver_src,
        solver_bin=solver_bin,
        print_solutions=False,
    )
    result["correct"] = bool(is_valid)

    problem_lines = [line for line in problem_ascii.strip().splitlines() if line]
    solution_lines = [line for line in extracted_board.strip().splitlines() if line]
    if len(problem_lines) == len(solution_lines) and problem_lines:
        result["board_valid"] = all(
            len(problem_row) == len(solution_row)
            for problem_row, solution_row in zip(problem_lines, solution_lines)
        )
        modified = False
        for problem_row, solution_row in zip(problem_lines, solution_lines):
            for start_cell, end_cell in zip(problem_row, solution_row):
                if start_cell != "." and start_cell != end_cell:
                    modified = True
                    break
            if modified:
                break
        result["board_modified"] = modified
    return result


def get_or_create_rlp_puzzle(puzzle_type: str, args: str) -> RLPPuzzle:
    cache_key = (puzzle_type, args)
    if cache_key not in _puzzle_cache:
        try:
            puzzle = RLPPuzzle(puzzle_type, arg=args, headless=True)
        except OSError as exc:
            raise RuntimeError(
                "RLP verifier libraries are not built yet. "
                "Run 'bash scripts/install.sh' first."
            ) from exc
        puzzle.new_game()
        _puzzle_cache[cache_key] = puzzle
    return _puzzle_cache[cache_key]


def verify_with_rlp(
    *,
    puzzle_type: str,
    problem_ascii: str,
    extracted_board: str,
    args: str,
) -> dict[str, Any]:
    result = {
        "board_exists": bool(extracted_board),
        "board_valid": False,
        "board_modified": False,
        "correct": False,
    }
    if not extracted_board:
        return result

    if puzzle_type == "bridges":
        result["board_valid"] = bool(
            check_bridges_structural_validity(extracted_board, problem_ascii)
        )
    elif puzzle_type == "galaxies":
        result["board_valid"] = bool(
            check_galaxies_structural_validity(extracted_board, problem_ascii)
        )
    elif puzzle_type == "undead":
        result["board_valid"] = bool(check_undead_structural_validity(extracted_board))
    else:
        result["board_valid"] = True

    if not result["board_valid"]:
        result["board_modified"] = True
        return result

    puzzle = get_or_create_rlp_puzzle(puzzle_type, args)
    result["correct"] = (
        verify_ascii_state(
            puzzle,
            extracted_board,
            problem_ascii=problem_ascii,
        )
        == "SOLVED"
    )
    return result


def decode_board_for_variant(board: str | None, variant: str, puzzle_type: str) -> str | None:
    if board is None:
        return None
    if variant == "plain":
        return board
    if variant == "intformat":
        return decode_intformat_board(board, puzzle_type)
    if variant == "intformat_json":
        return decode_intformat_json_board(board, puzzle_type)
    raise ValueError(f"Unknown variant '{variant}'")


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    summary = (
        frame.groupby(["provider", "model", "variant", "puzzlename", "difficulty"], dropna=False)
        .agg(
            total=("filename", "count"),
            board_exists=("board_exists", "sum"),
            board_valid=("board_valid", "sum"),
            correct=("correct", "sum"),
            avg_output_tokens=("output_tokens", "mean"),
            avg_total_tokens=("total_tokens", "mean"),
        )
        .reset_index()
    )
    summary["accuracy"] = summary["correct"] / summary["total"]
    return summary.sort_values(
        ["puzzlename", "difficulty", "provider", "model"]
    ).reset_index(drop=True)


def verify_run(run_dir: Path) -> dict[str, Path]:
    manifest = load_json(run_dir / "manifest.json")
    records = load_jsonl(run_dir / "responses.jsonl")
    variant = manifest["variant"]

    puzzle_frames = {
        key: load_dataset_frame(
            spec,
            variant=variant,
            difficulty="all",
            limit=None,
        )
        for key, spec in PUZZLES.items()
    }
    row_lookups = {
        key: build_row_lookup(frame)
        for key, frame in puzzle_frames.items()
    }

    detail_rows: list[dict[str, Any]] = []
    for record in records:
        puzzlename = record["puzzlename"]
        spec = PUZZLES[puzzlename]
        row = row_lookups[puzzlename][record["filename"]]
        extracted_board = extract_board(record.get("response_text", ""))
        decoded_problem = decode_board_for_variant(
            row["problem"],
            variant,
            spec.verifier_type,
        )
        decoded_board = decode_board_for_variant(
            extracted_board,
            variant,
            spec.verifier_type,
        )
        args = row.get("args") or record.get("args") or spec.default_args

        if spec.verifier_type == "flow_free":
            verification = verify_flow_free(decoded_problem or "", decoded_board or "")
        else:
            verification = verify_with_rlp(
                puzzle_type=spec.verifier_type,
                problem_ascii=decoded_problem or "",
                extracted_board=decoded_board or "",
                args=args,
            )

        detail_rows.append(
            {
                "filename": record["filename"],
                "puzzlename": puzzlename,
                "difficulty": row["difficulty"],
                "provider": record["provider"],
                "model": record["model"],
                "variant": variant,
                "args": args,
                "prompt_file": record["prompt_file"],
                "board_exists": verification["board_exists"],
                "board_valid": verification["board_valid"],
                "board_modified": verification["board_modified"],
                "correct": verification["correct"],
                "input_tokens": record.get("input_tokens"),
                "output_tokens": record.get("output_tokens"),
                "total_tokens": record.get("total_tokens"),
                "response_text": record.get("response_text", ""),
                "decoded_problem": decoded_problem,
                "decoded_board": decoded_board,
            }
        )

    detail_frame = pd.DataFrame(detail_rows)
    summary_frame = summarize(detail_frame)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    detail_csv = REPORTS_DIR / f"{run_dir.name}_details.csv"
    summary_csv = REPORTS_DIR / f"{run_dir.name}_summary.csv"
    detail_frame.to_csv(detail_csv, index=False)
    summary_frame.to_csv(summary_csv, index=False)
    write_json(
        REPORTS_DIR / f"{run_dir.name}_summary.json",
        {
            "run_dir": str(run_dir),
            "rows": len(detail_frame),
            "summary_rows": len(summary_frame),
        },
    )

    print(summary_frame.to_string(index=False))
    print(f"\nDetailed CSV: {detail_csv}")
    print(f"Summary CSV:  {summary_csv}")

    return {"detail_csv": detail_csv, "summary_csv": summary_csv}
