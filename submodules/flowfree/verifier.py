#!/usr/bin/env python3
"""
verifier.py

Verify if a given ASCII board state is a valid solution to a FlowFree puzzle.
Uses the modified solver (flowfree_all_solutions.c) to find all solutions and
compares the given solution against them.
"""

import argparse
import platform
import re
import subprocess
import sys
from collections import defaultdict
from itertools import chain
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Reuse patterns from convert_freeflow.py
HEADER_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s*$")
COORD_RE = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")
SOLUTIONS_RE = re.compile(r"^\s*Solutions\s+(\d+)\s*$", re.IGNORECASE)


def letter_labels(n):
    """Generate letter labels for colors (A, B, C, ..., Z, a, b, ..., z, AA, AB, ...)."""
    base = [chr(i) for i in range(ord('A'), ord('Z')+1)]
    extra = [chr(i) for i in range(ord('a'), ord('z')+1)]
    if n <= len(base) + len(extra):
        return list(chain(base, extra))[:n]
    labels = list(chain(base, extra))
    i = 0
    while len(labels) < n:
        for ch in base:
            labels.append(base[i % len(base)] + ch)
            if len(labels) == n:
                break
        i += 1
    return labels


def build_all_solutions_solver(src: Path, bin_: Path) -> None:
    """Compile the modified solver that outputs all solutions."""
    print(f"[build] compiling {src.name} -> {bin_.name}")
    if platform.system().lower().startswith("win"):
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


def parse_ascii_board(ascii_str: str) -> Tuple[List[List[str]], int, int]:
    """
    Parse ASCII board string to 2D grid.
    Returns: (grid as 2D list, cols, rows)
    """
    lines = ascii_str.strip().split('\n')
    grid = []
    for line in lines:
        line = line.strip()
        if line:
            grid.append(list(line))
    
    if not grid:
        raise ValueError("Empty board")
    
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0
    
    # Validate all rows have same length
    for i, row in enumerate(grid):
        if len(row) != cols:
            raise ValueError(f"Row {i} has length {len(row)}, expected {cols}")
    
    return grid, cols, rows


def extract_endpoints(grid: List[List[str]], cols: int, rows: int) -> Dict[str, List[Tuple[int, int]]]:
    """
    Find all endpoint pairs for each color.
    Endpoints are cells that appear exactly once or twice per color (the two endpoints).
    Returns: dict mapping color labels to list of (x, y) coordinates (col, row, zero-based).
    """
    color_positions = defaultdict(list)
    
    # Find all positions for each color
    for y in range(rows):
        for x in range(cols):
            cell = grid[y][x]
            if cell != '.' and cell.strip():
                color_positions[cell].append((x, y))
    
    endpoints = {}
    for color, positions in color_positions.items():
        if len(positions) == 2:
            # Exactly 2 cells - these are the endpoints
            endpoints[color] = positions
        elif len(positions) == 1:
            # Only one cell found - might be a single endpoint visible
            # In problem boards, we expect exactly 2 endpoints per color
            endpoints[color] = positions
        else:
            # More than 2 cells - this is a solution board, not a problem board
            # For problem boards, we should only have endpoints
            raise ValueError(f"Color '{color}' appears {len(positions)} times, expected 2 for problem board")
    
    return endpoints


def convert_to_solver_input(endpoints: Dict[str, List[Tuple[int, int]]], cols: int, rows: int) -> str:
    """
    Convert endpoints to solver input format.
    Format:
        <num_colors> <cols> <rows>
        (x1, y1) (x2, y2)
        ...
    """
    # Sort colors to ensure consistent ordering
    sorted_colors = sorted(endpoints.keys())
    num_colors = len(sorted_colors)
    
    lines = [f"{num_colors} {cols} {rows}"]
    for color in sorted_colors:
        positions = endpoints[color]
        if len(positions) == 2:
            (x1, y1), (x2, y2) = positions
            lines.append(f"({x1}, {y1}) ({x2}, {y2})")
        elif len(positions) == 1:
            # Only one endpoint found - this shouldn't happen in valid puzzles
            # But handle it gracefully
            (x1, y1) = positions[0]
            lines.append(f"({x1}, {y1}) ({x1}, {y1})")  # Duplicate as fallback
        else:
            raise ValueError(f"Color '{color}' has {len(positions)} endpoints, expected 2")
    
    return "\n".join(lines) + "\n"


def run_solver(solver_bin: str, puzzle_input: str) -> Tuple[str, str, int]:
    """
    Run the modified C solver with puzzle input.
    Returns: (stdout, stderr, returncode)
    """
    # Resolve path to absolute
    solver_path = Path(solver_bin).resolve()
    if not solver_path.exists():
        raise SystemExit(f"Solver binary not found: {solver_path}")
    
    try:
        proc = subprocess.run(
            [str(solver_path)],
            input=puzzle_input,
            text=True,
            capture_output=True,
            check=False,
        )
        return proc.stdout, proc.stderr, proc.returncode
    except FileNotFoundError:
        raise SystemExit(f"Solver binary not found: {solver_path}")


def parse_all_solutions(solver_output: str, cols: int, rows: int) -> List[List[List[str]]]:
    """
    Parse solver output to extract ALL solution blocks.
    Each solution block contains paths: (x1, y1) (x2, y2) ... (xn, yn) per color.
    Solutions are separated by empty lines.
    Returns: List of 2D grids (one per solution found).
    """
    lines = solver_output.splitlines()
    solutions = []
    i = 0
    
    # Find the number of colors from the first solution block
    # We'll infer it from the first complete solution we find
    num_colors = None
    
    while i < len(lines):
        # Skip status lines
        if (SOLUTIONS_RE.match(lines[i]) or 
            "Touching" in lines[i] or 
            "Nodes" in lines[i] or 
            "Attempts" in lines[i] or
            HEADER_RE.match(lines[i])):  # Skip header lines if present
            i += 1
            continue
        
        # Look for a solution block starting at an empty line or coordinate line
        # Solutions start with an empty line (from puts("") in the solver)
        # or directly with coordinate lines
        if not lines[i].strip():
            i += 1
            # Next lines should be coordinate lines for a solution
        
        # Collect coordinate lines for one solution
        paths = []
        j = i
        
        while j < len(lines):
            line = lines[j].strip()
            
            # Stop at status lines
            if (SOLUTIONS_RE.match(lines[j]) or 
                "Touching" in lines[j] or 
                "Nodes" in lines[j] or
                "Attempts" in lines[j]):
                break
            
            # Stop at empty line if we already have paths (next solution)
            if not line:
                if paths:
                    break
                j += 1
                continue
            
            # Try to parse coordinates
            coords = COORD_RE.findall(line)
            if coords:
                path = [(int(x), int(y)) for x, y in coords]
                paths.append(path)
                j += 1
            else:
                # Non-coordinate line - might be end of solution or start of next
                if paths:
                    break
                j += 1
        
        # If we found paths, it's a solution
        if paths:
            # Infer num_colors from first solution
            if num_colors is None:
                num_colors = len(paths)
            
            # Only process if we have the expected number of colors
            if len(paths) == num_colors:
                try:
                    labels = letter_labels(num_colors)
                    grid = build_grid(cols, rows)
                    grid = place_paths_on_grid(cols, rows, paths, labels)
                    solutions.append(grid)
                except Exception as e:
                    # Skip invalid solutions
                    pass
            
            i = j
        else:
            i += 1
    
    return solutions


def build_grid(cols: int, rows: int) -> List[List[str]]:
    """Build an empty grid."""
    return [['.' for _ in range(cols)] for _ in range(rows)]


def place_paths_on_grid(cols: int, rows: int, paths: List[List[Tuple[int, int]]], labels: List[str]) -> List[List[str]]:
    """
    Fill the grid with labels along paths.
    Reused from convert_freeflow.py logic.
    """
    grid = build_grid(cols, rows)
    for label, path in zip(labels, paths):
        for (x, y) in path:
            if not (0 <= x < cols and 0 <= y < rows):
                raise ValueError(f"Coordinate {(x,y)} out of bounds for {cols}x{rows}")
            if grid[y][x] != '.' and grid[y][x] != label:
                raise ValueError(f"Cell {(x,y)} already occupied by '{grid[y][x]}' (overlap).")
            grid[y][x] = label
    return grid


def convert_solution_to_ascii(grid: List[List[str]]) -> str:
    """Convert 2D grid back to ASCII string format."""
    return '\n'.join(''.join(row) for row in grid)


def normalize_ascii_board(ascii_str: str) -> str:
    """Normalize ASCII board for comparison (handle whitespace, newlines)."""
    lines = [line.strip() for line in ascii_str.strip().split('\n') if line.strip()]
    return '\n'.join(lines)


def verify_solution(
    problem_ascii: str,
    solution_ascii: str,
    solver_src: str = "./flowfree_all_solutions.c",
    solver_bin: str = "./flowfree_all_solutions",
    print_solutions: bool = False
) -> Tuple[bool, List[List[List[str]]]]:
    """
    Main verification function.
    Returns: (is_valid, all_solutions) where:
        - is_valid: True if solution matches any valid solution, False otherwise
        - all_solutions: List of all valid solutions found by the solver (as 2D grids)
    """
    solver_src_path = Path(solver_src)
    solver_bin_path = Path(solver_bin)
    
    # Build solver if needed
    if not solver_bin_path.exists():
        if not solver_src_path.exists():
            raise SystemExit(f"Solver source not found: {solver_src_path}")
        build_all_solutions_solver(solver_src_path, solver_bin_path)
    
    # Parse problem board
    try:
        problem_grid, cols, rows = parse_ascii_board(problem_ascii)
    except Exception as e:
        print(f"Error parsing problem board: {e}", file=sys.stderr)
        return False, []
    
    # Extract endpoints
    try:
        endpoints = extract_endpoints(problem_grid, cols, rows)
    except Exception as e:
        print(f"Error extracting endpoints: {e}", file=sys.stderr)
        return False, []
    
    # Convert to solver input
    try:
        puzzle_input = convert_to_solver_input(endpoints, cols, rows)
    except Exception as e:
        print(f"Error converting to solver input: {e}", file=sys.stderr)
        return False, []
    
    # Run solver
    try:
        stdout, stderr, returncode = run_solver(str(solver_bin_path), puzzle_input)
        if returncode != 0:
            print(f"Solver failed with exit code {returncode}", file=sys.stderr)
            if stderr:
                print(f"Stderr: {stderr}", file=sys.stderr)
            return False, []
    except Exception as e:
        print(f"Error running solver: {e}", file=sys.stderr)
        return False, []
    
    # Parse all solutions
    try:
        solutions = parse_all_solutions(stdout, cols, rows)
    except Exception as e:
        print(f"Error parsing solutions: {e}", file=sys.stderr)
        return False, []
    
    if not solutions:
        print("No solutions found by solver", file=sys.stderr)
        return False, []
    
    # Print all solutions if requested
    if print_solutions:
        print(f"\nFound {len(solutions)} solution(s):", file=sys.stderr)
        for i, sol_grid in enumerate(solutions, 1):
            sol_ascii = convert_solution_to_ascii(sol_grid)
            print(f"\nSolution {i}:", file=sys.stderr)
            print(sol_ascii, file=sys.stderr)
    
    # Normalize the given solution
    normalized_solution = normalize_ascii_board(solution_ascii)
    
    # Compare against all solutions
    for sol_grid in solutions:
        sol_ascii = convert_solution_to_ascii(sol_grid)
        normalized_sol = normalize_ascii_board(sol_ascii)
        if normalized_solution == normalized_sol:
            return True, solutions
    
    return False, solutions


def main():
    ap = argparse.ArgumentParser(
        description="Verify if an ASCII board state is a valid solution to a FlowFree puzzle",
        epilog="""
Example usage:
  python verifier.py \\
    --problem "BBBBBBBB\\nBFFFFFFB\\nFFGGGGFB\\nFGGAAGFB\\nFGAAGGBB\\nEGGGGDBC\\nEGGGDDBC\\nEEEEEBBC" \\
    --solution "BBBBBBBB\\nBFFFFFFB\\nFFGGGGFB\\nFGGAAGFB\\nFGAAGGBB\\nEGGGGDBC\\nEGGGDDBC\\nEEEEEBBC"
        """
    )
    ap.add_argument("--problem", required=True, help="Problem board as ASCII string (with \\n for newlines)")
    ap.add_argument("--solution", required=True, help="Solution board as ASCII string (with \\n for newlines)")
    ap.add_argument("--solver-src", default="./flowfree_all_solutions.c", help="Path to solver source")
    ap.add_argument("--solver-bin", default="./flowfree_all_solutions", help="Path to solver binary")
    ap.add_argument("--print-solutions", action="store_true", help="Print all solutions found by the solver")
    args = ap.parse_args()
    
    # Convert \n escape sequences to actual newlines
    problem = args.problem.replace('\\n', '\n')
    solution = args.solution.replace('\\n', '\n')
    
    is_valid, all_solutions = verify_solution(problem, solution, args.solver_src, args.solver_bin, args.print_solutions)
    
    if is_valid:
        print("VALID: Solution matches a valid solution found by the solver")
        sys.exit(0)
    else:
        print("INVALID: Solution does not match any valid solution")
        if args.print_solutions and all_solutions:
            print(f"\nNote: The solver found {len(all_solutions)} valid solution(s) (printed above).", file=sys.stderr)
        sys.exit(1)


# Example usage as a Python function:
# 
# problem = '''BBBBBBBB
# BFFFFFFB
# FFGGGGFB
# FGGAAGFB
# FGAAGGBB
# EGGGGDBC
# EGGGDDBC
# EEEEEBBC'''
# 
# solution = '''BBBBBBBB
# BFFFFFFB
# FFGGGGFB
# FGGAAGFB
# FGAAGGBB
# EGGGGDBC
# EGGGDDBC
# EEEEEBBC'''
# 
# is_valid = verify_solution(problem, solution)
# print(f"Solution is valid: {is_valid}")


if __name__ == "__main__":
    main()

