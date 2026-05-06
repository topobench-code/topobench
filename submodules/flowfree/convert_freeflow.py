# #!/usr/bin/env python3
# import re
# import sys
# from itertools import chain

# """
# Usage:
#   # From a file
#   python convert_flowfree.py puzzle.txt

#   # Or pipe the raw generator output
#   printf "3 5 5\n(2, 0) (2, 2)\n(3, 3) (1, 3)\n(1, 0) (1, 4)\n" | python convert_flowfree.py

# Notes:
# - Expects lines like:
#     <num_colors> <cols> <rows>
#     (x1, y1) (x2, y2)
#     ...
#   for exactly <num_colors> lines after the header.
# - Coordinates are zero-based and are (col, row).
# - Colors are labeled A, B, C, ... (wraps to aA... if >52 colors).
# """

# HEADER_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s*$")
# PAIR_RE   = re.compile(
#     r"\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)"
# )

# def letter_labels(n):
#     base = [chr(i) for i in range(ord('A'), ord('Z')+1)]
#     extra = [chr(i) for i in range(ord('a'), ord('z')+1)]
#     # If still more needed, go to double letters: AA, AB, ...
#     if n <= len(base) + len(extra):
#         return list(chain(base, extra))[:n]
#     labels = list(chain(base, extra))
#     i = 0
#     while len(labels) < n:
#         for ch in base:
#             labels.append(base[i % len(base)] + ch)
#             if len(labels) == n:
#                 break
#         i += 1
#     return labels

# def parse_blocks(lines):
#     """
#     Yields (num_colors, cols, rows, pairs_list) for each detected puzzle block.
#     pairs_list is a list of ((x1,y1),(x2,y2)) of length num_colors.
#     """
#     i = 0
#     while i < len(lines):
#         m = HEADER_RE.match(lines[i])
#         if not m:
#             i += 1
#             continue

#         num_colors, cols, rows = map(int, m.groups())
#         i += 1

#         pairs = []
#         while i < len(lines) and len(pairs) < num_colors:
#             pm = PAIR_RE.search(lines[i])
#             if pm:
#                 x1, y1, x2, y2 = map(int, pm.groups())
#                 pairs.append(((x1, y1), (x2, y2)))
#                 i += 1
#             else:
#                 # skip noise lines between pairs
#                 i += 1

#         if len(pairs) == num_colors:
#             yield num_colors, cols, rows, pairs
#         # else: header without enough pairs; skip and keep scanning

# def grid_from_puzzle(cols, rows, pairs, labels):
#     grid = [['.' for _ in range(cols)] for _ in range(rows)]
#     for label, ((x1, y1), (x2, y2)) in zip(labels, pairs):
#         for (x, y) in [(x1, y1), (x2, y2)]:
#             if not (0 <= x < cols and 0 <= y < rows):
#                 raise ValueError(f"Coordinate {(x,y)} out of bounds for {cols}x{rows}")
#             if grid[y][x] != '.':
#                 raise ValueError(f"Cell {(x,y)} already occupied (overlap).")
#             grid[y][x] = label
#     return grid

# def print_grid(grid):
#     for row in grid:
#         print(''.join(row))

# def main():
#     data = sys.stdin.read() if sys.stdin and not sys.stdin.isatty() else None
#     if data is None:
#         if len(sys.argv) < 2:
#             print("Provide a file or pipe the generator output to stdin.", file=sys.stderr)
#             sys.exit(1)
#         with open(sys.argv[1], 'r', encoding='utf-8') as f:
#             data = f.read()

#     lines = data.splitlines()
#     any_printed = False
#     for num_colors, cols, rows, pairs in parse_blocks(lines):
#         labels = letter_labels(num_colors)
#         grid = grid_from_puzzle(cols, rows, pairs, labels)
#         print('"""')
#         print_grid(grid)
#         print('"""')
#         any_printed = True

#     if not any_printed:
#         print("No valid puzzle blocks found.", file=sys.stderr)
#         sys.exit(2)

# if __name__ == "__main__":
#     main()




#!/usr/bin/env python3
import re
import sys
from itertools import chain

HEADER_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s*$")
COORD_RE  = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")

def letter_labels(n):
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

def parse_blocks(lines):
    """
    Yields (num_colors, cols, rows, paths_list) per puzzle block.
    paths_list: list of lists of (x,y). For endpoints format, each list has len 2.
    For solution format, each list may have len > 2 (full path).
    """
    i = 0
    while i < len(lines):
        m = HEADER_RE.match(lines[i])
        if not m:
            i += 1
            continue

        num_colors, cols, rows = map(int, m.groups())
        i += 1

        paths = []
        while i < len(lines) and len(paths) < num_colors:
            coords = COORD_RE.findall(lines[i])
            if coords:
                path = [(int(x), int(y)) for x, y in coords]
                paths.append(path)
            i += 1  # always advance; skip noise automatically

        if len(paths) == num_colors:
            yield num_colors, cols, rows, paths
        # else: header without enough lines -> skip and keep scanning

def build_grid(cols, rows):
    return [['.' for _ in range(cols)] for _ in range(rows)]

def place_paths_on_grid(cols, rows, paths, labels):
    """
    Fills the grid with labels along either endpoints (len 2) or full paths (len > 2).
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

def print_grid(grid):
    for row in grid:
        print(''.join(row))

def read_all_input():
    # Prefer stdin if piped; else read from file arg.
    if sys.stdin and not sys.stdin.isatty():
        return sys.stdin.read()
    if len(sys.argv) < 2:
        print("Provide a file or pipe the generator/solution output to stdin.", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        return f.read()

def main():
    data = read_all_input()
    lines = data.splitlines()

    any_printed = False
    for num_colors, cols, rows, paths in parse_blocks(lines):
        labels = letter_labels(num_colors)
        grid = place_paths_on_grid(cols, rows, paths, labels)
        print('"""')
        print_grid(grid)
        print('"""')
        any_printed = True

    if not any_printed:
        print("No valid puzzle blocks found.", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
