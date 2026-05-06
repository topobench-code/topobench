# ASCII Parser Implementation Guide for Bridges Puzzles

This document provides a comprehensive guide to implementing ASCII parsers for puzzle games, using the Bridges puzzle as a reference implementation. This guide can be used to create similar parsers for other puzzles (undead, loopy, etc.).

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Implementation Structure](#implementation-structure)
4. [Key Components](#key-components)
5. [Testing Strategy](#testing-strategy)
6. [Gotchas and Lessons Learned](#gotchas-and-lessons-learned)
7. [Integration Points](#integration-points)
8. [Step-by-Step Implementation Checklist](#step-by-step-implementation-checklist)

---

## Overview

### Purpose

The ASCII parser converts ASCII text representations of puzzle states into Python dictionaries that match the format produced by `get_puzzle_state_<puzzle_name>()` functions. This enables:

- **Verification**: Check if an ASCII state (from LLM or other sources) is solved
- **State Loading**: Load arbitrary puzzle states from ASCII text
- **Round-trip Testing**: Verify ASCII → state dict → load → format → ASCII works correctly
- **Integration**: Use ASCII states with existing `load_state_dict` functionality

### Pipeline

The complete pipeline follows this flow:

```
ASCII Text → Parse (Python) → State Dict → Load (C) → Game State → Verify/Format
```

1. **Parse ASCII** (Python): Convert ASCII text to state dictionary
2. **Load State Dict** (C): Use existing `load_state_dict_<puzzle>()` function
3. **Verify/Format** (C): Check `completed` flag or format back to ASCII

---

## Architecture

### Three-Layer Design

1. **Python Parser Layer** (`rlp/ascii_parser.py`)
   - Pure Python implementation
   - Parses ASCII text into state dictionaries
   - No C dependencies for parsing logic

2. **State Dict Format Layer** (`rlp/specific_api.py`)
   - Must match `get_puzzle_state_<puzzle>()` format exactly
   - Defines the canonical state representation

3. **C Loading Layer** (existing `load_state_dict_<puzzle>()`)
   - Reconstructs C game state from state dict
   - Computes derived fields (possibles, max arrays, etc.)
   - Validates and checks if solved

### Key Design Principle

**The parser only needs to produce the minimal canonical fields required for reconstruction.** The C code will:
- Recompute derived arrays (possibles, max arrays, etc.)
- Rebuild internal structures (island adjacencies, etc.)
- Validate the state and set `completed`/`solved` flags

---

## Implementation Structure

### File Organization

```
rlp/
  ascii_parser.py          # Main parser module (puzzle-specific functions)
  specific_api.py          # State dict format definitions
  puzzle.py                # Puzzle class (load_state_dict method)
verifier.py                # Verification script using new pipeline
test_ascii_parser.py       # Parser-specific tests
test_verifier.py           # Integration tests
```

### Parser Function Signature

```python
def parse_ascii_<puzzle_name>(ascii_text: str) -> dict:
    """
    Parse ASCII text representation of a <puzzle_name> puzzle and return a state dict.
    
    Args:
        ascii_text: The ASCII representation of the puzzle state
        
    Returns:
        dict: State dictionary matching get_puzzle_state_<puzzle_name> format
        
    Raises:
        ValueError: If the ASCII text is invalid or empty
    """
```

### State Dict Format

The parser must produce a dictionary that **exactly matches** the format from `get_puzzle_state_<puzzle_name>()`. For bridges, this includes:

```python
{
    "w": int,                    # Width
    "h": int,                    # Height
    "completed": bool,           # Will be computed by C code (set to False)
    "solved": bool,              # Will be computed by C code (set to False)
    "grid": List[int],           # Grid flags array (w*h elements)
    "lines": List[int],          # Lines array (w*h elements)
    "islands": List[dict],       # Island structures
    "n_islands": int,            # Number of islands
    "n_islands_alloc": int,      # Allocation size (same as n_islands for parsed)
    "params": {                  # Minimal params (only for verification/printing)
        "w": int,
        "h": int,
        "maxb": int,             # Default: 2 for bridges
        "allowloops": bool,      # Default: True for bridges
    },
    # Derived arrays - initialized to zeros, computed by C code
    "wha": List[int],            # w*h elements
    "possv": List[int],          # w*h elements
    "possh": List[int],          # w*h elements
    "maxv": List[int],           # w*h elements
    "maxh": List[int],           # w*h elements
}
```

---

## Key Components

### 1. ASCII Format Understanding

**For Bridges:**
- Islands: `'0'-'9'` (count 0-9) or `'A'-'G'` (count 10-16)
- Vertical bridges: `'|'` (single), `'"'` (double)
- Horizontal bridges: `'-'` (single), `'='` (double)
- Empty cells: `'.'`

**Key Insight**: Study the C `game_text_format()` function to understand the exact ASCII format. This is the inverse operation.

### 2. Dimension Inference

```python
# First pass: infer dimensions
lines = ascii_text.strip().split('\n')
h = len(lines)
max_w = max(len(line.rstrip()) for line in lines)
w = max_w
```

**Important**: Handle variable line lengths gracefully. Shorter lines are treated as empty cells.

### 3. Grid Flags

Define constants matching the C definitions:

```python
# Grid flags matching <puzzle>.c definitions
G_ISLAND = 0x0001
G_LINEV = 0x0002   # contains a vertical line
G_LINEH = 0x0004   # contains a horizontal line
```

**Critical**: These must match the C `#define` values exactly.

### 4. State Dict Construction

```python
# Initialize arrays
wh = w * h
grid = [0] * wh
lines_array = [0] * wh
islands = []

# Parse each cell
for y, line in enumerate(lines):
    for x in range(w):
        c = stripped[x] if x < len(stripped) else None
        idx = y * w + x
        
        if c is island_char:
            grid[idx] |= G_ISLAND
            islands.append({"x": x, "y": y, "count": count})
        elif c is line_char:
            grid[idx] |= G_LINE_FLAG
            lines_array[idx] = line_count  # 1 or 2
        # Empty cells remain 0
```

### 5. Minimal Params

Only include params needed for verification/printing:

```python
"params": {
    "w": w,
    "h": h,
    # Only include fields needed for load_state_dict
    # Omit generation params: islands, expansion, difficulty
}
```

---

## Testing Strategy

### 1. Unit Tests (Parser-Specific)

**File**: `test_ascii_parser.py`

Test cases:
- **Problem states** (initial puzzle, no solution)
- **Solution states** (complete solution with all elements)
- **Edge cases**: Empty states, single cell, maximum size
- **Special characters**: Letter islands (A-G), double bridges
- **Round-trip**: ASCII → parse → load → format → ASCII (must match)

### 2. Integration Tests (Verifier)

**File**: `test_verifier.py`

Test cases:
- **CSV predictions**: Verify problems return `solved=False`, solutions return `solved=True`
- **State comparison**: Compare two similar ASCII states
- **Large-scale testing**: Test all problems/solutions from dataset

### 3. Round-Trip Testing

The most important test pattern:

```python
# 1. Get ASCII from a puzzle state
ascii_original = game.text_format(state).decode('utf-8')

# 2. Parse with Python parser
state_dict = parse_ascii_bridges(ascii_original)

# 3. Load into C
loaded_state_ptr = puzzle.load_state_dict(state_dict)

# 4. Format back to ASCII
ascii_loaded = game.text_format(loaded_state_ptr).decode('utf-8')

# 5. Compare (should match exactly)
assert ascii_original.strip() == ascii_loaded.strip()
```

### 4. Structural Validity (Optional but Recommended)

For puzzles with connectivity requirements (like bridges), add a structural validity check:

```python
def check_<puzzle>_structural_validity(ascii_text: str) -> bool:
    """
    Check structural validity before parsing.
    
    Validates:
    - Lines are contiguous (no breaks)
    - Clues haven't been modified
    - Basic sanity checks
    """
```

This catches common errors early (broken lines, modified clues, etc.).

---

## Gotchas and Lessons Learned

### 1. Grid Flags Must Match C Exactly

**Problem**: Grid flag values must match C `#define` values exactly.

**Solution**: Copy the exact hex values from the C source file.

```python
# From bridges.c:
#define G_ISLAND        0x0001
#define G_LINEV         0x0002
#define G_LINEH         0x0004

# In Python:
G_ISLAND = 0x0001  # Must match exactly
G_LINEV = 0x0002
G_LINEH = 0x0004
```

### 2. Derived Arrays Can Be Zeros

**Problem**: Don't try to compute derived arrays (possibles, max arrays) in Python.

**Solution**: Initialize to zeros. The C code will recompute them:

```python
# Derived arrays - initialized to zeros, will be computed by C code
"wha": [0] * wh,
"possv": [0] * wh,
"possh": [0] * wh,
"maxv": [0] * wh,
"maxh": [0] * wh,
```

### 3. Only Include Canonical Fields

**Problem**: Including non-canonical fields (generation params, solver flags) causes issues.

**Solution**: Only include fields needed for reconstruction. Omit:
- Generation params: `islands`, `expansion`, `difficulty`
- Solver flags: `G_SWEEP`, `G_WARN` (these are computed by C)
- Allocation details: `n_islands_alloc` can be set to `n_islands` for parsed states

### 4. Handle Variable Line Lengths

**Problem**: ASCII text may have lines of different lengths.

**Solution**: Use maximum width, treat shorter lines as having empty cells:

```python
max_w = max(len(line.rstrip()) for line in lines)
# For cells beyond line length, treat as empty (already 0)
```

### 5. Memory Management

**Problem**: Must free loaded states to avoid memory leaks.

**Solution**: Always use try/finally:

```python
loaded_state_ptr = puzzle.load_state_dict(state_dict)
try:
    # Use the state
    is_solved = loaded_state_ptr.contents.completed
finally:
    if loaded_state_ptr:
        free_game_func(loaded_state_ptr)
```

### 6. State Dict Format Must Match Exactly

**Problem**: Even small differences in state dict format cause failures.

**Solution**: 
- Copy the exact structure from `get_puzzle_state_<puzzle>()`
- Use the same field names and types
- Test with round-trip verification

### 7. Letter Islands (A-G)

**Problem**: Islands can have counts 10-16 represented as letters.

**Solution**: Handle both digits and letters:

```python
if c >= '0' and c <= '9':
    count = ord(c) - ord('0')
elif c >= 'A' and c <= 'G':
    count = (ord(c) - ord('A')) + 10
```

### 8. Double Bridges

**Problem**: Double bridges use different characters (`"` for vertical, `=` for horizontal).

**Solution**: Check for both single and double bridge characters:

```python
elif c == '|':
    lines_array[idx] = 1
elif c == '"':
    lines_array[idx] = 2
elif c == '-':
    lines_array[idx] = 1
elif c == '=':
    lines_array[idx] = 2
```

### 9. Empty Cells vs Missing Cells

**Problem**: Need to distinguish between empty cells (`.`) and cells beyond line length.

**Solution**: Both are treated the same (grid=0, lines=0), but handle bounds checking:

```python
if x >= len(stripped):
    continue  # Beyond line length, already initialized to 0
elif c == '.':
    pass  # Empty cell, already initialized to 0
```

### 10. Testing with Real Data

**Problem**: Unit tests may not catch all edge cases.

**Solution**: Test with real dataset:
- Parse all problems and solutions from CSV
- Verify round-trip works for all
- Check that problems are unsolved and solutions are solved

---

## Integration Points

### 1. Verifier Script

The verifier uses the parser in a complete pipeline:

```python
def verify_ascii_state(puzzle, ascii_text: str) -> str:
    # 1. Optional: Check structural validity
    if not check_bridges_structural_validity(ascii_text):
        return "NOT SOLVED"
    
    # 2. Parse ASCII
    state_dict = parse_ascii_bridges(ascii_text)
    
    # 3. Load state dict
    loaded_state_ptr = puzzle.load_state_dict(state_dict)
    
    # 4. Check completed flag
    is_solved = loaded_state_ptr.contents.completed
    return "SOLVED" if is_solved else "NOT SOLVED"
```

### 2. Load State Dict Function

The parser output must be compatible with existing `load_state_dict_<puzzle>()`:

```python
# In rlp/specific_api.py
def load_state_dict_bridges(state_dict: dict, lib: c.PyDLL) -> c.POINTER(GameState):
    # Validates required fields
    # Creates C structures
    # Calls bridges_state_from_repr()
```

### 3. Puzzle Class

The Puzzle class provides the interface:

```python
# In rlp/puzzle.py
puzzle = Puzzle('bridges', arg='5x5de', headless=True)
puzzle.new_game()
state_dict = parse_ascii_bridges(ascii_text)
loaded_state = puzzle.load_state_dict(state_dict)
```

---

## Step-by-Step Implementation Checklist

### Phase 1: Research and Understanding

- [ ] Study the C `game_text_format()` function to understand ASCII format
- [ ] Review `get_puzzle_state_<puzzle>()` to understand state dict format
- [ ] Identify all ASCII characters and their meanings
- [ ] Identify grid flags and their values from C source
- [ ] Understand the puzzle's state structure

### Phase 2: Parser Implementation

- [ ] Create `rlp/ascii_parser.py` (or add to existing file)
- [ ] Define grid flag constants matching C
- [ ] Implement dimension inference
- [ ] Implement cell-by-cell parsing
- [ ] Build grid array with correct flags
- [ ] Build lines/connections array
- [ ] Extract puzzle-specific structures (islands, etc.)
- [ ] Construct state dict matching `get_puzzle_state_<puzzle>()` format
- [ ] Add error handling and validation

### Phase 3: Structural Validity (Optional)

- [ ] Implement structural validity checker
- [ ] Validate connectivity (if applicable)
- [ ] Validate clues haven't been modified
- [ ] Add sanity checks

### Phase 4: Testing

- [ ] Create `test_ascii_parser.py`
- [ ] Test problem states (unsolved)
- [ ] Test solution states (solved)
- [ ] Test edge cases (empty, single cell, max size)
- [ ] Test special characters/features
- [ ] Implement round-trip tests
- [ ] Test with real dataset (CSV)

### Phase 5: Integration

- [ ] Update `verifier.py` to use new parser
- [ ] Create/update `test_verifier.py`
- [ ] Test CSV predictions (problems vs solutions)
- [ ] Verify memory management (no leaks)

### Phase 6: Documentation

- [ ] Document ASCII format
- [ ] Document parser function
- [ ] Document state dict format
- [ ] Add examples and usage

---

## Example: Bridges Parser Structure

```python
# rlp/ascii_parser.py

# 1. Grid flags (must match C)
G_ISLAND = 0x0001
G_LINEV = 0x0002
G_LINEH = 0x0004

# 2. Structural validity (optional)
def check_bridges_structural_validity(ascii_text: str) -> bool:
    # Validates line continuity, clue integrity, etc.
    pass

# 3. Main parser
def parse_ascii_bridges(ascii_text: str) -> dict:
    # Dimension inference
    lines = ascii_text.strip().split('\n')
    h = len(lines)
    w = max(len(line.rstrip()) for line in lines)
    
    # Initialize arrays
    wh = w * h
    grid = [0] * wh
    lines_array = [0] * wh
    islands = []
    
    # Parse cells
    for y, line in enumerate(lines):
        for x in range(w):
            c = line[x] if x < len(line.rstrip()) else None
            idx = y * w + x
            
            if c in '0-9A-G':  # Island
                grid[idx] |= G_ISLAND
                islands.append({"x": x, "y": y, "count": ...})
            elif c in '|"':  # Vertical line
                grid[idx] |= G_LINEV
                lines_array[idx] = 2 if c == '"' else 1
            elif c in '-=':  # Horizontal line
                grid[idx] |= G_LINEH
                lines_array[idx] = 2 if c == '=' else 1
    
    # Build state dict
    return {
        "w": w,
        "h": h,
        "grid": grid,
        "lines": lines_array,
        "islands": islands,
        # ... rest of fields
    }
```

---

## Key Takeaways

1. **Study the C code first**: Understand `game_text_format()` and state structure
2. **Match formats exactly**: State dict must match `get_puzzle_state_<puzzle>()` exactly
3. **Minimal canonical fields**: Only include what's needed for reconstruction
4. **Let C compute derived fields**: Initialize derived arrays to zeros
5. **Round-trip testing is critical**: ASCII → parse → load → format → ASCII must match
6. **Handle edge cases**: Variable line lengths, special characters, empty states
7. **Memory management**: Always free loaded states
8. **Test with real data**: Use actual problems and solutions from datasets

---

## References

- Bridges parser: `rlp/ascii_parser.py`
- State dict format: `rlp/specific_api.py` (lines 2576-2585)
- C text format: `puzzles/bridges.c` (lines 234-266)
- C state structure: `puzzles/bridges.c` (lines 177-189)
- Load state dict: `rlp/specific_api.py` (lines 2588-2686)
- Tests: `test_ascii_parser.py`, `test_verifier.py`
- Verifier: `verifier.py`

