from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
from datasets import load_dataset


ROOT_DIR = Path(__file__).resolve().parents[2]
EVALS_DIR = ROOT_DIR / "evals"
PROMPTS_DIR = EVALS_DIR / "prompts"
RESULTS_DIR = ROOT_DIR / "results"
RUNS_DIR = RESULTS_DIR / "runs"
REPORTS_DIR = RESULTS_DIR / "reports"
MAPPINGS_DIR = ROOT_DIR / "mappings" / "topobench_mappings"
SUBMODULES_DIR = ROOT_DIR / "submodules"

DATASET_REPOS = {
    "plain": "topobench/topobench",
    "intformat": "topobench/topobench_intformat",
    "intformat_json": "topobench/topobench_intformat_json",
}


@dataclass(frozen=True)
class PuzzleSpec:
    key: str
    dataset_name: str
    prompt_stem: str
    verifier_type: str
    default_args: str

    def prompt_path(self, variant: str) -> Path:
        suffix = {
            "plain": ".txt",
            "intformat": "_intformat.txt",
            "intformat_json": "_intformat_json.txt",
        }[variant]
        return PROMPTS_DIR / f"{self.prompt_stem}{suffix}"


PUZZLES: dict[str, PuzzleSpec] = {
    "bridges": PuzzleSpec(
        key="bridges",
        dataset_name="bridges",
        prompt_stem="bridges",
        verifier_type="bridges",
        default_args="5x5deL",
    ),
    "flow_free": PuzzleSpec(
        key="flow_free",
        dataset_name="flow_free",
        prompt_stem="flow_free",
        verifier_type="flow_free",
        default_args="5x5",
    ),
    "galaxies": PuzzleSpec(
        key="galaxies",
        dataset_name="galaxies",
        prompt_stem="galaxies",
        verifier_type="galaxies",
        default_args="4x4",
    ),
    "loopy": PuzzleSpec(
        key="loopy",
        dataset_name="loopy",
        prompt_stem="loopy",
        verifier_type="loopy",
        default_args="5x5t0",
    ),
    "pattern": PuzzleSpec(
        key="pattern",
        dataset_name="pattern",
        prompt_stem="pattern",
        verifier_type="pattern",
        default_args="5x5",
    ),
    "undead": PuzzleSpec(
        key="undead",
        dataset_name="undead",
        prompt_stem="undead",
        verifier_type="undead",
        default_args="4x4",
    ),
}


def get_puzzle(name: str) -> PuzzleSpec:
    try:
        return PUZZLES[name]
    except KeyError as exc:
        valid = ", ".join(sorted(PUZZLES))
        raise ValueError(f"Unknown puzzle '{name}'. Valid values: {valid}") from exc


def list_puzzle_names() -> list[str]:
    return sorted(PUZZLES)


def expand_puzzles(names: Iterable[str]) -> list[PuzzleSpec]:
    items = list(names)
    if not items or items == ["all"]:
        return [PUZZLES[name] for name in list_puzzle_names()]
    return [get_puzzle(name) for name in items]


def load_prompt(puzzle: PuzzleSpec, variant: str) -> str:
    return puzzle.prompt_path(variant).read_text(encoding="utf-8")


def load_dataset_frame(
    puzzle: PuzzleSpec,
    *,
    variant: str,
    difficulty: str,
    limit: int | None,
    split: str = "test",
) -> pd.DataFrame:
    repo_id = DATASET_REPOS[variant]
    frame = load_dataset(repo_id, split=split).to_pandas()
    frame = frame[frame["puzzlename"] == puzzle.dataset_name].copy()

    if "include" in frame.columns:
        frame = frame[frame["include"].fillna(False)]

    if difficulty != "all":
        frame = frame[frame["difficulty"] == difficulty]

    frame = frame.sort_values(["difficulty", "filename"]).reset_index(drop=True)

    if limit is not None:
        frame = frame.head(limit).copy()

    return frame.reset_index(drop=True)


def build_row_lookup(frame: pd.DataFrame) -> dict[str, pd.Series]:
    return {row["filename"]: row for _, row in frame.iterrows()}
