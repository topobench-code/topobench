#!/usr/bin/env python3
"""
generate_puzzles.py

Generate FlowFree puzzles by calling the C generator (./flowfree),
keep only those with exactly one solution, and save them to ./generated/.

Each saved file contains:
1) a human-readable grid from convert_freeflow.py
2) the raw generator block (header + endpoint pairs)

Defaults:
- k x k boards for k in [5..14]
- colors in [3..7] but not exceeding k
- 3 puzzles per (k, colors)

Usage examples:
  python generate_puzzles.py
  python generate_puzzles.py --per-size 5 --colors 3-8 --progress 1000
  python generate_puzzles.py --exe ./flowfree --mindist 2 --forbid 0

Requirements in the same directory:
- ./flowfree  (compiled C generator)
- ./convert_freeflow.py  (your converter script that reads stdin and prints the quoted grid)
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple, List

# --------- Parsing helpers (match the generator's output) ---------
HEADER_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s*$")
PAIR_RE   = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)")
SOLUTIONS_RE = re.compile(r"^\s*Solutions\s+(\d+)\s*$", re.IGNORECASE)

def extract_first_puzzle_block(output: str) -> Optional[Tuple[str, int]]:
    """
    From the program's stdout, find the first complete puzzle block and the
    'Solutions N' line. Return (raw_block_text, solutions_count) or None.
    """
    lines = output.splitlines()
    raw_block_lines: List[str] = []
    ncolors = ncols = nrows = None
    pairs_found = 0
    solutions_found: Optional[int] = None

    i = 0
    while i < len(lines):
        m = HEADER_RE.match(lines[i])
        if m:
            # start of a potential block
            try:
                ncolors = int(m.group(1)); ncols = int(m.group(2)); nrows = int(m.group(3))
            except ValueError:
                i += 1
                continue
            raw_block_lines = [lines[i]]
            pairs_found = 0
            i += 1
            # collect exactly ncolors endpoint lines (skip noise until we have them)
            while i < len(lines) and pairs_found < ncolors:
                pm = PAIR_RE.search(lines[i])
                if pm:
                    raw_block_lines.append(lines[i])
                    pairs_found += 1
                i += 1

            if pairs_found == ncolors:
                # After a complete block, scan forward for "Solutions N"
                j = i
                while j < len(lines):
                    sm = SOLUTIONS_RE.match(lines[j])
                    if sm:
                        try:
                            solutions_found = int(sm.group(1))
                        except ValueError:
                            solutions_found = None
                        break
                    j += 1

                if solutions_found is not None:
                    return ("\n".join(raw_block_lines) + "\n", solutions_found)
                # If no Solutions line found, still return the block (solutions_count=None)
                return ("\n".join(raw_block_lines) + "\n", -1)

        else:
            i += 1

    return None

# --------- Core runner ---------
def run_generator_once(exe: str, params_line: str) -> str:
    """
    Invoke ./flowfree once, supplying the params via stdin.
    Return stdout as text.
    """
    proc = subprocess.run(
        [exe],
        input=(params_line + "\n").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return proc.stdout.decode("utf-8", errors="replace")

def convert_with_freeflow(raw_block: str, converter_path: str) -> str:
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

def ensure_dir(d: Path):
    d.mkdir(parents=True, exist_ok=True)

def parse_colors_arg(arg: str, k: int) -> List[int]:
    """
    Parse --colors argument. Accepts:
      - a range like "3-7"
      - a comma list like "3,4,5"
      - a single int like "6"
    Caps values at k (cannot have more colors than grid size realistically).
    """
    arg = arg.strip()
    vals: List[int] = []
    if "-" in arg:
        a, b = arg.split("-", 1)
        lo, hi = int(a), int(b)
        vals = list(range(lo, hi + 1))
    elif "," in arg:
        vals = [int(x) for x in arg.split(",")]
    else:
        vals = [int(arg)]
    # cap at k and filter invalid
    vals = [c for c in vals if 1 <= c <= max(1, k)]
    # unique & sorted
    return sorted(set(vals))


recommended_flows_per_grid = {
    5:  [3, 5],
    6:  [4, 6],
    7:  [5, 7],
    8:  [6, 8],
    9:  [7, 9],
    10: [9, 11],
    11: [10, 12],
    12: [11, 13],
    13: [12, 14],
    14: [13, 15],
    15: [14, 16]
}

def main():
    ap = argparse.ArgumentParser(description="Generate FlowFree puzzles with unique solutions.")
    ap.add_argument("--exe", default="./flowfree", help="Path to the C generator executable (default: ./flowfree)")
    ap.add_argument("--converter", default="./convert_freeflow.py", help="Path to convert_freeflow.py")
    ap.add_argument("--outdir", default="generated", help="Folder to save puzzles (default: generated)")
    ap.add_argument("--kmin", type=int, default=5, help="Min board size k for kxk (default: 5)")
    ap.add_argument("--kmax", type=int, default=12, help="Max board size k for kxk (default: 14)")
    ap.add_argument("--colors", default="3-7", help="Colors to try per k (range like 3-7, list like 3,4,5, or single int)")
    ap.add_argument("--per-size", type=int, default=10, help="Number of puzzles to save per (k, colors) combo (default: 3)")
    ap.add_argument("--forbid", type=int, default=0, help="Forbid self-touching? (0 or 1) (default: 0)") # here 0 means we forbid self-touching
    ap.add_argument("--mindist", type=int, default=2, help="Minimum endpoint distance (default: 2)")
    ap.add_argument("--progress", type=int, default=1000000, help="Progress print interval (default: 1000)")
    ap.add_argument("--max-tries", type=int, default=100000, help="Hard cap on generator invocations per (k, colors) (default: 100000)")
    args = ap.parse_args()

    exe = args.exe
    converter = args.converter
    outdir = Path(args.outdir)
    ensure_dir(outdir)

    # sanity checks
    if not Path(exe).exists():
        print(f"ERROR: generator executable not found: {exe}", file=sys.stderr)
        sys.exit(1)
    if not Path(converter).exists():
        print(f"WARNING: converter not found: {converter} — files will be saved without pretty grids.", file=sys.stderr)

    for k in range(args.kmin, args.kmax + 1):
        # colors_list = parse_colors_arg(args.colors, k)
        colors_range = recommended_flows_per_grid[k]
        colors_list = list(range(colors_range[0], colors_range[1]+1))
        print(f"\n=== Board size: {k}x{k}, colors to try: {colors_list} ===")
        if not colors_list:
            print(f"Skipping k={k} as no recommended colors are defined for it.", file=sys.stderr)
            continue
        for ncolors in colors_list:
            target_count = args.per_size
            saved = 0
            tries = 0
            print(f"\n=== Generating k={k} ({k}x{k}), colors={ncolors} ===")
            while saved < target_count and tries < args.max_tries:
                tries += 1
                # params: <colors> <cols> <rows> <forbid> <mindist> <maxSolutions=1> <progress>
                params_line = f"{ncolors} {k} {k} {args.forbid} {args.mindist} 1 {args.progress}"
                print(f"Try {tries}: params: {params_line}")
                out = run_generator_once(exe, params_line)

                found = extract_first_puzzle_block(out)
                if not found:
                    # keep going
                    continue

                raw_block, sol = found
                if sol != 1:
                    # ignore anything that's not unique
                    continue

                # Convert to human-readable
                if Path(converter).exists():
                    pretty = convert_with_freeflow(raw_block, converter)
                    
                else:
                    pretty = '"""(converter missing)"""'


                print(pretty)

                print(f"Solutions: {sol}")
                asd

                # Create a stable-ish suffix to avoid overwrites when saving multiple puzzles
                # Use a short hash of the raw_block.
                import hashlib
                h = hashlib.sha1(raw_block.encode("utf-8")).hexdigest()[:8]
                filename = outdir / f"{k}x{k}_{ncolors}c_{saved+1}_{h}.txt"

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(pretty.strip() + "\n\n")
                    f.write("# ---- raw puzzle block (for reproducibility) ----\n")
                    f.write(raw_block)
                    f.write("\n param line: " + params_line + "\n")

                saved += 1
                print(f"Saved: {filename}")

            if saved < target_count:
                print(f"Note: only saved {saved}/{target_count} for k={k}, colors={ncolors} (after {tries} tries)")
            # asd
    print("\nDone.")

if __name__ == "__main__":
    main()
