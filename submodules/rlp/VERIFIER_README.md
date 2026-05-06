# Puzzle Verifier - How to Use

## Overview

The `verifier.py` script verifies whether an ASCII representation of a puzzle state is correctly solved. It supports five puzzle types: **bridges**, **undead**, **galaxies**, **pattern**, and **loopy**.

## Supported Puzzle Types

| Puzzle Type | Default Argument | Solved Field | Notes |
|------------|------------------|--------------|-------|
| **bridges** | `5x5deL` | `completed` | Checks structural validity before verification |
| **undead** | `4x4` | `solved` | Checks structural validity before verification |
| **galaxies** | `4x4` | `completed` | Direct verification |
| **pattern** | `5x5` | `completed` | Direct verification |
| **loopy** | `5x5t0` | `solved` | Handles dimension validation errors gracefully |

## How It Works

The verifier uses a **parse → load → check** pipeline:

1. **Parse**: Converts ASCII text to a structured state dictionary using puzzle-specific parsers
2. **Load**: Loads the state dictionary into the puzzle's C backend
3. **Check**: Queries the puzzle's solved/completed flag to determine if the state is valid

### Verification Process

For each puzzle type:

1. **Bridges & Undead**: 
   - First performs structural validity checks (ensures no broken lines, modified clues, etc.)
   - If structurally invalid, returns "NOT SOLVED" immediately
   - Otherwise, parses and verifies the state

2. **Galaxies, Pattern, Loopy**:
   - Directly parses the ASCII state
   - For loopy, handles dimension validation errors (treats malformed responses as "NOT SOLVED")

3. **Error Handling**:
   - Dimension validation errors (invalid canvas width/height) are treated as "NOT SOLVED" (model mistakes)
   - Other parsing errors are re-raised as exceptions

## Usage

### Basic Usage

#### From Command Line Argument

```bash
# Bridges
python verifier.py bridges "3|.|2\n..."

# Undead
python verifier.py undead "G: 3 V: 1 Z: 6\n\n   2 3 1 1  \n..."

# Galaxies
python verifier.py galaxies "+-+-+\n|o o|\n+-+-+\n|o o|\n+-+-+\n"

# Pattern
python verifier.py pattern " 1 2 3\n 4 5 6\n 7 8 9\n"

# Loopy
python verifier.py loopy " x x x - x \nx x0x |3| x\n..."
```

#### From Standard Input

```bash
# Read from file
python verifier.py bridges < ascii_state.txt

# Pipe from another command
echo "3|.|2\n..." | python verifier.py bridges

# Multi-line input
cat <<EOF | python verifier.py undead
G: 3 V: 1 Z: 6

   2 3 1 1  
   1 2 3 4
EOF
```

### With Custom Puzzle Arguments

Use the `--arg` flag to specify puzzle initialization parameters:

```bash
# Bridges with custom size and difficulty
python verifier.py bridges --arg "7x7dm" "..."

# Undead with custom size
python verifier.py undead --arg "5x5" "..."

# Galaxies with custom size
python verifier.py galaxies --arg "6x6" "..."

# Pattern with custom size
python verifier.py pattern --arg "10x10" "..."

# Loopy with custom grid (square grid, type 0)
python verifier.py loopy --arg "7x7t0" "..."
```

### Escape Sequences

The verifier automatically converts escape sequences in command-line arguments:

```bash
# \n is converted to actual newlines
python verifier.py bridges "3|.|2\n4|.|3\n5|.|2"
```

## Output

The verifier prints one of two results:

- **`SOLVED`** - The puzzle state is correctly solved (exit code 0)
- **`NOT SOLVED`** - The puzzle state is not solved or invalid (exit code 1)

### Example Output

```bash
$ python verifier.py bridges "3|.|2\n..."
SOLVED

$ echo $?
0

$ python verifier.py bridges "3|.|2\n..."  # Invalid state
NOT SOLVED

$ echo $?
1
```

## Puzzle-Specific Details

### Bridges

- **Structural Validity**: Checks for broken lines, modified clues, and invalid connections
- **Solved Field**: Uses `completed` flag
- **Default Arg**: `5x5deL` (5x5, difficulty easy, left-right symmetry)

### Undead

- **Structural Validity**: Checks for missing header, invalid grid format, and malformed state
- **Solved Field**: Uses `solved` flag (not `completed`)
- **Default Arg**: `4x4` (4x4 grid)

### Galaxies

- **Direct Verification**: No structural validity pre-check
- **Solved Field**: Uses `completed` flag
- **Default Arg**: `4x4` (4x4 grid)

### Pattern

- **Direct Verification**: No structural validity pre-check
- **Solved Field**: Uses `completed` flag
- **Default Arg**: `5x5` (5x5 grid)
- **Note**: Leading spaces are significant for clue alignment

### Loopy

- **Dimension Validation**: Handles invalid canvas dimensions gracefully (treats as "NOT SOLVED")
- **Solved Field**: Uses `solved` flag
- **Default Arg**: `5x5t0` (5x5 square grid, type 0)
- **Grid Type**: Currently only supports square grids (`grid_type=0`)
- **Note**: Reuses existing puzzle instances to avoid conflicts when called programmatically

## Programmatic Usage

The verifier can also be used as a Python module:

```python
from rlp.puzzle import Puzzle
from verifier import verify_ascii_state

# Create and initialize puzzle
puzzle = Puzzle('bridges', arg='5x5deL', headless=True)
puzzle.new_game()

# Verify ASCII state
ascii_text = "3|.|2\n..."
result = verify_ascii_state(puzzle, ascii_text)

if result == "SOLVED":
    print("Puzzle is solved!")
else:
    print("Puzzle is not solved.")
```

### Important Notes for Programmatic Usage

1. **Puzzle Instance**: The puzzle must be initialized with `new_game()` before calling `verify_ascii_state()`
2. **Loopy Puzzles**: When verifying loopy puzzles, the verifier automatically reuses the provided puzzle instance to avoid creating temporary instances (prevents conflicts)
3. **Memory Management**: The verifier automatically frees loaded states after verification
4. **Error Handling**: Dimension validation errors are caught and treated as "NOT SOLVED" for loopy puzzles

## Error Handling

### Dimension Validation Errors

For loopy puzzles, if the ASCII text has invalid dimensions (e.g., malformed model responses), the verifier returns "NOT SOLVED" instead of raising an exception. This handles cases where:

- Canvas width doesn't satisfy `W = 2*w + 2` (W-2 must be even)
- Canvas height doesn't satisfy `H = 2*h + 1` (H-1 must be even)
- Dimensions don't match expected relationships

### Other Errors

- **Parsing Errors**: If the ASCII text cannot be parsed (except dimension errors), an exception is raised
- **Invalid Puzzle Type**: If an unsupported puzzle type is specified, an error is raised
- **Missing Input**: If no ASCII state is provided, the script exits with an error

## Examples

### Example 1: Verify a Bridges Puzzle

```bash
# Create a solved bridges state
cat > bridges_solved.txt <<EOF
3|.|2
-+-+-
.|.|.
-+-+-
2|.|3
EOF

# Verify it
python verifier.py bridges < bridges_solved.txt
# Output: SOLVED
```

### Example 2: Verify Multiple Puzzles

```bash
# Verify bridges
echo "..." | python verifier.py bridges

# Verify undead
echo "..." | python verifier.py undead

# Verify galaxies
echo "..." | python verifier.py galaxies
```

### Example 3: Use in Scripts

```bash
#!/bin/bash
result=$(python verifier.py bridges "$ascii_state")
if [ "$result" == "SOLVED" ]; then
    echo "Correct!"
else
    echo "Incorrect or invalid state"
fi
```

## Integration with Evaluation Scripts

The verifier is used by:

- **`evaluate-predictions.py`**: Evaluates model predictions from CSV files
- **`evaluate_puzzle_type_worker.py`**: Worker script for parallel evaluation
- **`test_verifier.py`**: Test suite for verifier functionality

These scripts use `verify_ascii_state()` programmatically to check if model-generated puzzle solutions are correct.

## Troubleshooting

### Issue: "Error: No ASCII state provided"

**Solution**: Ensure you're providing ASCII input either via command-line argument or stdin.

### Issue: Dimension validation errors for loopy

**Solution**: This is expected behavior for malformed model responses. The verifier correctly treats these as "NOT SOLVED".

### Issue: Parsing errors

**Solution**: Check that the ASCII format matches the expected puzzle format. Each puzzle type has a specific ASCII representation format.

### Issue: Puzzle instance conflicts (loopy)

**Solution**: The verifier automatically handles this by reusing puzzle instances. If you're creating multiple puzzle instances programmatically, ensure proper cleanup.

## See Also

- `test_verifier.py` - Test suite with examples
- `evaluate-predictions.py` - Evaluation script using the verifier
- `rlp/ascii_parser.py` - ASCII parsing implementations for each puzzle type

