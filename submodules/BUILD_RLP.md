# Building the RLP (Reinforcement Learning Puzzles) Library

This document provides instructions for building the rlp puzzle library, which is required for the verifier API.

## Prerequisites

Install the required system packages:

```bash
# On Debian/Ubuntu
apt-get update
apt-get install -y cmake build-essential pkg-config libgtk-3-dev imagemagick
```

## Building the Library

1. Navigate to the rlp submodule directory:
```bash
cd submodules/rlp
```

2. Create the library output directory:
```bash
mkdir -p rlp/lib
```

3. Run cmake to configure the build:
```bash
cd rlp/lib
cmake ../../puzzles
```

4. Build the libraries (this will also generate icons if ImageMagick is installed):
```bash
make -j4
```

5. Verify the build was successful by checking for .so files:
```bash
ls *.so
# Should show: libbridges.so, libgalaxies.so, libloopy.so, libpattern.so, libundead.so, etc.
```

6. Verify icons were generated:
```bash
ls icons/*.png | head -5
# Should show PNG files like bridges-96d24.png, etc.
```

## Quick One-Liner

For a fresh build from the repository root:

```bash
cd submodules/rlp && mkdir -p rlp/lib && cd rlp/lib && cmake ../../puzzles && make -j4
```

## Troubleshooting

### Missing pkg-config
```
Could NOT find PkgConfig (missing: PKG_CONFIG_EXECUTABLE)
```
Solution: `apt-get install -y pkg-config`

### Missing GTK
```
Could not find gtk+-3.0
```
Solution: `apt-get install -y libgtk-3-dev`

### Icons not generated
```
Puzzle icons cannot be rebuilt (did not find ImageMagick)
```
Solution: `apt-get install -y imagemagick`

Then rebuild:
```bash
cd rlp/lib && rm -rf * && cmake ../../puzzles && make -j4
```

### Segfaults when running verifier
This usually happens when:
1. Icons are missing - rebuild with ImageMagick installed
2. Too many puzzle instances created - the verifier code caches instances to avoid this

## Supported Puzzle Types

The verifier supports these puzzle types from the rlp library:
- **bridges** - Connect islands with bridges
- **undead** - Place ghosts, vampires, and zombies
- **galaxies** - Divide grid into rotationally symmetric regions
- **pattern** - Fill grid based on row/column clues (nonogram)
- **loopy** - Draw a single loop through the grid

## Using the Verifier

After building, you can use the verifier from Python:

```python
import sys
sys.path.insert(0, 'submodules/rlp')

from rlp.puzzle import Puzzle
from verifier import verify_ascii_state

# Create puzzle instance
puzzle = Puzzle('bridges', arg='5x5deL', headless=True)
puzzle.new_game()

# Verify an ASCII solution
result = verify_ascii_state(puzzle, ascii_solution, problem_ascii=original_problem)
print(result)  # "SOLVED" or "NOT SOLVED"
```

See `submodules/rlp/VERIFIER_README.md` for detailed API documentation.
