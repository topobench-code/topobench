from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqdm import tqdm

from clients import ModelClient
from puzzles import DATASET_REPOS, RUNS_DIR, PuzzleSpec, expand_puzzles, load_dataset_frame, load_prompt


def slugify(value: str) -> str:
    cleaned = []
    for ch in value:
        if ch.isalnum():
            cleaned.append(ch.lower())
        elif ch in {"-", "_", "."}:
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    return slug or "run"


def timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def build_run_name(
    *,
    model: str,
    variant: str,
    difficulty: str,
    puzzles: list[PuzzleSpec],
) -> str:
    puzzle_part = "all" if len(puzzles) == 6 else "-".join(p.key for p in puzzles)
    return f"{timestamp_slug()}-{slugify(model)}-{variant}-{difficulty}-{puzzle_part}"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def create_run_manifest(
    *,
    run_name: str,
    provider: str,
    model: str,
    variant: str,
    difficulty: str,
    limit: int | None,
    max_output_tokens: int,
    temperature: float | None,
    request_args: dict[str, Any],
    puzzles: list[PuzzleSpec],
) -> dict[str, Any]:
    return {
        "run_name": run_name,
        "created_at": datetime.now(UTC).isoformat(),
        "provider": provider,
        "model": model,
        "variant": variant,
        "dataset_repo": DATASET_REPOS[variant],
        "difficulty": difficulty,
        "limit": limit,
        "max_output_tokens": max_output_tokens,
        "temperature": temperature,
        "request_args": request_args,
        "puzzles": [asdict(puzzle) for puzzle in puzzles],
    }


def run_benchmarks(
    *,
    provider: str,
    model: str,
    variant: str,
    difficulty: str,
    puzzle_names: list[str],
    limit: int | None,
    max_output_tokens: int,
    temperature: float | None,
    request_args: dict[str, Any],
    run_name: str | None,
    overwrite: bool,
) -> Path:
    puzzles = expand_puzzles(puzzle_names)
    resolved_run_name = run_name or build_run_name(
        model=model,
        variant=variant,
        difficulty=difficulty,
        puzzles=puzzles,
    )
    run_dir = RUNS_DIR / resolved_run_name
    responses_path = run_dir / "responses.jsonl"
    manifest_path = run_dir / "manifest.json"

    if run_dir.exists() and not overwrite:
        raise FileExistsError(
            f"Run directory already exists: {run_dir}. "
            "Pass --overwrite or choose --run-name."
        )
    if overwrite and run_dir.exists():
        for path in run_dir.glob("*"):
            if path.is_file():
                path.unlink()
            else:
                raise RuntimeError(
                    f"Refusing to overwrite unexpected directory inside {run_dir}: {path}"
                )

    client = ModelClient()
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = create_run_manifest(
        run_name=resolved_run_name,
        provider=provider,
        model=model,
        variant=variant,
        difficulty=difficulty,
        limit=limit,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        request_args=request_args,
        puzzles=puzzles,
    )
    write_json(manifest_path, manifest)

    for puzzle in puzzles:
        dataset = load_dataset_frame(
            puzzle,
            variant=variant,
            difficulty=difficulty,
            limit=limit,
        )
        prompt = load_prompt(puzzle, variant)
        progress = tqdm(
            dataset.itertuples(index=False),
            total=len(dataset),
            desc=f"{puzzle.key}:{difficulty}",
        )

        for row in progress:
            prompt_text = f"{prompt.rstrip()}\n\n{row.problem}"
            generation = client.generate(
                provider=provider,
                model=model,
                prompt=prompt_text,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                extra_args=request_args,
            )
            record = {
                "filename": row.filename,
                "puzzlename": row.puzzlename,
                "difficulty": row.difficulty,
                "args": getattr(row, "args", None),
                "variant": variant,
                "provider": provider,
                "model": model,
                "prompt_file": puzzle.prompt_path(variant).name,
                "dataset_repo": DATASET_REPOS[variant],
                "response_text": generation.text,
                "input_tokens": generation.input_tokens,
                "output_tokens": generation.output_tokens,
                "total_tokens": generation.total_tokens,
                "created_at": datetime.now(UTC).isoformat(),
            }
            append_jsonl(responses_path, record)

    return run_dir
