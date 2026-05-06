#!/usr/bin/env python3
import argparse
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple
import sys

RAW_HEADER_RE = re.compile(r'^\s*#\s*----\s*raw\s*puzzle\s*block', re.IGNORECASE)

def detect_solver_bin_name() -> str:
    return "flowfree.exe" if platform.system().lower().startswith("win") else "flowfree"

def needs_rebuild(src: Path, bin_: Path) -> bool:
    if not bin_.exists():
        return True
    try:
        return src.stat().st_mtime > bin_.stat().st_mtime
    except FileNotFoundError:
        return True

def build_solver(src: Path, bin_: Path) -> None:
    print(f"[build] compiling {src.name} -> {bin_.name}")
    if platform.system().lower().startswith("win"):
        # Prefer gcc from MSYS2/MinGW if available
        cmd = ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-o", str(bin_), str(src)]
    else:
        cmd = ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-o", str(bin_), str(src)]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as e:
        raise SystemExit(
            "Error: C compiler not found (gcc). Install gcc or build the solver manually."
        ) from e
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"Build failed with exit code {e.returncode}")

def extract_puzzle_block(text: str) -> Optional[str]:
    """
    Returns the exact text to feed the solver in solver mode:
        "<colors_n> <cols_n> <rows_n>\n"
        "<pair line 1>\n"
        ...
        "<pair line colors_n>\n"
    """
    lines = text.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        if RAW_HEADER_RE.search(lines[i]):
            i += 1
            # Skip blank lines after the header
            while i < n and not lines[i].strip():
                i += 1
            if i >= n:
                return None
            # Expect "<colors_n> <cols_n> <rows_n>"
            header_match = re.match(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s*$', lines[i])
            if not header_match:
                return None
            colors_n = int(header_match.group(1))
            cols_n = int(header_match.group(2))
            rows_n = int(header_match.group(3))
            i += 1

            # Collect the next colors_n non-empty lines that look like coordinate pairs
            pairs = []
            while i < n and len(pairs) < colors_n:
                line = lines[i].strip()
                if line:
                    # Accept anything that starts with '(' as a pair line
                    if line.startswith("("):
                        pairs.append(line)
                    else:
                        # If we encounter something else before collecting enough pairs, abort
                        return None
                i += 1

            if len(pairs) != colors_n:
                return None

            puzzle = f"{colors_n} {cols_n} {rows_n}\n" + "\n".join(pairs) + "\n"
            return puzzle
        i += 1
    return None

def already_has_solution(text: str) -> bool:
    return "# ---- solution (appended by solve_generated.py) ----" in text

def run_solver(bin_path: Path, puzzle_text: str) -> Tuple[str, str, int]:
    """Return (stdout, stderr, returncode)."""
    try:
        proc = subprocess.run(
            [str(bin_path)],
            input=puzzle_text,
            text=True,
            capture_output=True,
            check=False,
        )
        return proc.stdout, proc.stderr, proc.returncode
    except FileNotFoundError:
        raise SystemExit(f"Solver binary not found: {bin_path}")





def convert_with_freeflow(raw_block: str, converter_path='./convert_freeflow.py') -> str:
    """
    Pipe the raw block to convert_freeflow.py and capture the human-readable grid.
    """
    proc = subprocess.run(
        [sys.executable, converter_path],
        input=raw_block.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        # If conversion fails, include stderr for debugging in the saved file
        pretty = f'"""CONVERSION FAILED (exit {proc.returncode})"""\n{proc.stderr.decode("utf-8", "replace")}'
    else:
        pretty = proc.stdout.decode("utf-8", "replace").strip()
    return pretty


# def process_file(path: Path, solver_bin: Path, dry_run: bool=False) -> str:
#     content = path.read_text(encoding="utf-8")
#     if already_has_solution(content):
#         return f"[skip] {path.name}: solution already appended"

#     puzzle = extract_puzzle_block(content)
#     if not puzzle:
#         return f"[warn] {path.name}: could not find a valid raw puzzle block"

#     out, err, rc = run_solver(solver_bin, puzzle)
#     if rc != 0:
#         return f"[fail] {path.name}: solver exit code {rc}\nstderr:\n{err}"

#     append_block = (
#         "\n# ---- solution (appended by solve_generated.py) ----\n"
#         "## Solver input:\n"
#         + puzzle
#         + "\n## Solver output:\n"
#         + out.strip()
#         + ("\n\n## Solver stderr:\n" + err.strip() if err.strip() else "")
#         + "\n"
#     )

#     print(append_block)  # For visibility in dry-run mode
#     asd

#     if dry_run:
#         return f"[dry-run] {path.name}: would append solution"
#     else:
#         with path.open("a", encoding="utf-8") as f:
#             f.write(append_block)
#         return f"[ok] {path.name}: solution appended"



def process_file(path: Path, solver_bin: Path, converter_path='./convert_freeflow.py', dry_run: bool=False) -> str:
    content = path.read_text(encoding="utf-8")
    if already_has_solution(content):
        return f"[skip] {path.name}: solution already appended"

    puzzle = extract_puzzle_block(content)
    if not puzzle:
        return f"[warn] {path.name}: could not find a valid raw puzzle block"

    out, err, rc = run_solver(solver_bin, puzzle)
    if rc != 0:
        return f"[fail] {path.name}: solver exit code {rc}\nstderr:\n{err}"

    # Make a pretty (human-readable) grid of the solver output
    # Note: we pass solver stdout (the solution paths) to the converter.
    # print('puzzle')
    header = puzzle.splitlines()[0]
    # print(puzzle)
    # print('soln')
    out = header + out
    # print(out)
    # asd
    pretty_solution = convert_with_freeflow(out, str(converter_path))

    append_block = (
        "\n# ---- solution (appended by solve_generated.py) ----\n"
        "## Human-readable solution:\n"
        f"{pretty_solution}\n"
        "\n## Raw solver output:\n"
        f"{out.strip()}\n"
        + (f"\n\n## Solver stderr:\n{err.strip()}\n" if err.strip() else "\n")
        + "## Solver input (raw puzzle block):\n"
        f"{puzzle}"
    )
    # print('append_block')
    # print(append_block)  # For visibility in dry-run mode
    # asd

    if dry_run:
        # Show what we would append (useful for checking formatting)
        print(append_block)
        return f"[dry-run] {path.name}: would append solution"
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(append_block)
        return f"[ok] {path.name}: solution appended"

def main():
    ap = argparse.ArgumentParser(description="Extract raw puzzle blocks, run solver, append solutions to files in generated/")
    ap.add_argument("--generated-dir", default="generated", help="Directory with input files (default: generated)")
    ap.add_argument("--solver-src", default="flowfree.c", help="C source file for the solver (default: flowfree.c)")
    ap.add_argument("--solver-bin", default=None, help="Solver binary name/path (default: auto: flowfree or flowfree.exe)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen without writing")
    args = ap.parse_args()

    gen_dir = Path(args.generated_dir)
    if not gen_dir.is_dir():
        raise SystemExit(f"Directory not found: {gen_dir}")

    solver_src = Path(args.solver_src)
    solver_bin = Path(args.solver_bin) if args.solver_bin else Path(detect_solver_bin_name())

    # # Build solver if needed
    # if solver_src.exists() and needs_rebuild(solver_src, solver_bin):
    #     build_solver(solver_src, solver_bin)
    # elif not solver_bin.exists():
    #     # If no src to build but also no binary, stop
    #     raise SystemExit(f"Solver binary not found: {solver_bin}. Put it next to this script or provide --solver-bin.")

    # Process all regular files in generated/
    results = []
    for p in sorted(gen_dir.iterdir(), reverse=True):
        # temp_path = '/notebooks/multimodal_cot/FlowFree/generated/5x5_3c_1_3b79ecca.txt'
        # p = Path(temp_path)
        if p.is_file():
            try:
                results.append(process_file(p, solver_bin, dry_run=args.dry_run))
            except Exception as e:
                results.append(f"[error] {p.name}: {e}")
        # break

    print("\n".join(results))

if __name__ == "__main__":
    main()
