# ASCII Parser Implementation Template

This template provides step-by-step instructions for implementing ASCII parsers for puzzle games. Use this guide to create parsers for new puzzle types following the established pattern from bridges and undead implementations.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Step-by-Step Implementation](#step-by-step-implementation)
4. [Code Structure](#code-structure)
5. [Testing Strategy](#testing-strategy)
6. [Integration Checklist](#integration-checklist)
7. [Common Patterns and Examples](#common-patterns-and-examples)
8. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

The ASCII parser converts ASCII text representations of puzzle states into Python dictionaries that match the format produced by `get_puzzle_state_<puzzle_name>()` functions. This enables:

- **Verification**: Check if an ASCII state (from LLM or other sources) is solved
- **State Loading**: Load arbitrary puzzle states from ASCII text
- **Round-trip Testing**: Verify ASCII → state dict → load → format → ASCII works correctly
- **Integration**: Use ASCII states with existing `load_state_dict` functionality

### Pipeline

```
ASCII Text → Structural Validation → Parse (Python) → State Dict → Load (C) → Game State → Verify/Format
```

1. **Structural Validation** (Python): Quick check if ASCII looks valid
2. **Parse ASCII** (Python): Convert ASCII text to state dictionary
3. **Load State Dict** (C): Use existing `load_state_dict_<puzzle>()` function
4. **Verify/Format** (C): Check `completed`/`solved` flag or format back to ASCII

---

## Prerequisites

Before starting, you need:

1. **Access to C source code**: `puzzles/<puzzle_name>.c`
2. **Understanding of ASCII format**: Study `game_text_format()` function in C
3. **Understanding of state dict format**: Review `get_puzzle_state_<puzzle_name>()` in `rlp/specific_api.py`
4. **Understanding of load function**: Review `load_state_dict_<puzzle_name>()` in `rlp/specific_api.py`
5. **Example ASCII states**: Have sample problem and solution states to test with

---

## Step-by-Step Implementation

### Phase 1: Research and Understanding

#### Step 1.1: Study the C ASCII Format Function

**Location**: `puzzles/<puzzle_name>.c`

**Function**: `game_text_format()`

**What to look for**:
- How the function formats the puzzle state to ASCII
- What characters represent different cell types
- How dimensions are represented
- What the header/prefix looks like (if any)
- How multi-line structures are formatted

**Example questions to answer**:
- What characters represent different cell states?
- Are there special characters for different values?
- How are dimensions encoded?
- Is there a header line (like "G: X V: Y Z: Z" for undead)?
- How are edge clues/borders represented?

**Document your findings**:
```python
# ASCII Format for <puzzle_name>:
# - Header: <description>
# - Cell types:
#   - <char1>: <meaning>
#   - <char2>: <meaning>
# - Grid structure: <description>
```

#### Step 1.2: Study the State Dict Format

**Location**: `rlp/specific_api.py`

**Function**: `get_puzzle_state_<puzzle_name>()`

**What to look for**:
- Required top-level fields
- Nested structures (like `common` for undead)
- Array types and lengths
- Field names and types
- Which fields are canonical (required) vs derived (computed by C)

**Key insight**: Only include canonical fields in the parser output. Derived fields should be initialized to zeros/False and computed by C code.

**Document the structure**:
```python
# State dict format for <puzzle_name>:
{
    "field1": <type>,      # Required
    "field2": <type>,      # Required
    "nested": {            # If applicable
        "subfield1": <type>,
    },
    "derived_array": [0] * size,  # Will be computed by C
}
```

#### Step 1.3: Study Cell Type Constants

**Location**: `puzzles/<puzzle_name>.c`

**What to look for**:
- `#define` statements for grid flags
- `enum` definitions for cell types
- Any constants used to represent cell states

**Example**:
```c
// From undead.c:
enum {
    CELL_EMPTY,
    CELL_MIRROR_L,
    CELL_MIRROR_R,
    CELL_GHOST,
    CELL_VAMPIRE,
    CELL_ZOMBIE,
};
```

**Action**: Copy these exact values to Python constants in `rlp/ascii_parser.py`

#### Step 1.4: Study the Load Function

**Location**: `rlp/specific_api.py`

**Function**: `load_state_dict_<puzzle_name>()`

**What to look for**:
- Required fields validation
- Array length requirements
- Type requirements
- Which fields are optional vs required

**This tells you**: What fields your parser MUST produce for the state dict to load successfully.

---

### Phase 2: Structural Validity Checker (Optional but Recommended)

#### Step 2.1: Implement `check_<puzzle_name>_structural_validity()`

**Purpose**: Quick validation before parsing to catch obviously invalid inputs.

**Location**: `rlp/ascii_parser.py`

**What to check**:
- [ ] Has required header/prefix (if applicable)
- [ ] Has grid structure present
- [ ] Grid has minimum dimensions
- [ ] Not empty text
- [ ] Not just long unstructured text
- [ ] Basic format sanity checks

**Template**:
```python
def check_<puzzle_name>_structural_validity(ascii_text: str) -> bool:
    """
    Check structural validity of a <puzzle_name> ASCII state.
    
    Validates:
    1. <Check 1>
    2. <Check 2>
    3. <Check 3>
    
    Args:
        ascii_text: The ASCII representation of the puzzle state
        
    Returns:
        bool: True if structurally valid, False otherwise
    """
    if not ascii_text or not ascii_text.strip():
        return False
    
    lines = ascii_text.strip().split('\n')
    if len(lines) == 0:
        return False
    
    # Check for required header/prefix
    # <implementation>
    
    # Check for grid structure
    # <implementation>
    
    # Check minimum dimensions
    # <implementation>
    
    # Check for invalid patterns (long text, etc.)
    # <implementation>
    
    return True
```

**Testing**: Create test cases with valid and invalid inputs.

---

### Phase 3: Parser Implementation

#### Step 3.1: Add Constants

**Location**: `rlp/ascii_parser.py`

Add cell type constants matching C definitions:

```python
# Cell types matching <puzzle_name>.c enum/defines
CONSTANT_NAME_1 = <value>
CONSTANT_NAME_2 = <value>
# ... etc
```

**Important**: Values must match C exactly (copy hex values, enum values, etc.)

#### Step 3.2: Implement Dimension Inference

**Pattern**:
```python
# First pass: infer dimensions
lines = ascii_text.strip().split('\n')
h = len(lines)
if h == 0:
    raise ValueError("ASCII text must contain at least one line")

# Find maximum width (handle variable line lengths)
max_w = 0
for line in lines:
    stripped = line.rstrip()
    w = len(stripped)
    if w > max_w:
        max_w = w

if max_w == 0:
    raise ValueError("ASCII text must contain at least one non-whitespace character")

w = max_w
```

**Variations**:
- Some puzzles have fixed-width cells (e.g., undead: 2 characters per cell)
- Some puzzles have headers to skip
- Some puzzles have border cells to account for

#### Step 3.3: Implement Cell-by-Cell Parsing

**Pattern**:
```python
# Initialize arrays
wh = w * h  # or (w+2)*(h+2) if including border
grid = [0] * wh
other_array = [0] * wh
structures = []  # For puzzle-specific structures (islands, etc.)

# Parse each cell
for y, line in enumerate(lines):
    stripped = line.rstrip()
    for x in range(w):
        if x >= len(stripped):
            # Line is shorter, treat as empty
            continue
        
        c = stripped[x]  # or cell_str = stripped[x*2:(x+1)*2] for fixed-width
        idx = y * w + x  # or y * grid_w + x if including border
        
        # Parse based on character/cell
        if c == '<char1>':
            grid[idx] = CONSTANT_1
            # ... set other fields
        elif c == '<char2>':
            grid[idx] = CONSTANT_2
            # ... set other fields
        # ... etc
```

**Key considerations**:
- Handle variable line lengths gracefully
- Map ASCII characters to cell type constants
- Build puzzle-specific structures (islands, monsters, etc.)
- Track indices correctly (especially if grid includes border)

#### Step 3.4: Build State Dict

**Pattern**:
```python
state_dict = {
    # Required top-level fields
    "field1": value1,
    "field2": value2,
    
    # Nested structures (if applicable)
    "nested": {
        "params": {
            "w": w,
            "h": h,
            # Only include canonical params, omit generation params
        },
        "array1": array1,
        "array2": array2,
    },
    
    # Derived arrays - initialized to zeros, computed by C code
    "derived_array": [0] * size,
    
    # Status flags - will be computed by C code
    "completed": False,
    "solved": False,
}
```

**Important**:
- Only include canonical fields (required for `load_state_dict`)
- Initialize derived arrays to zeros
- Set `completed`/`solved` to False (C will compute)
- Omit generation params (islands, expansion, difficulty, etc.)

#### Step 3.5: Add Error Handling

**Pattern**:
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
    if not ascii_text or not ascii_text.strip():
        raise ValueError("ASCII text cannot be empty")
    
    # ... parsing logic ...
    
    # Validate dimensions
    if w < 1 or h < 1:
        raise ValueError(f"Invalid grid dimensions: w={w}, h={h}")
    
    # ... return state_dict ...
```

---

### Phase 4: Testing

#### Step 4.1: Create Test File

**Location**: `test_ascii_parser_<puzzle_name>.py`

**Template structure**:
```python
"""
Test script for <puzzle_name> ASCII parser round-trip functionality.
"""
import sys
import os
import pandas as pd
from rlp import puzzle as rp
from rlp.ascii_parser import parse_ascii_<puzzle_name>, check_<puzzle_name>_structural_validity


def test_parse_example():
    """Test parsing with a known example."""
    # <example ASCII>
    # ... test logic ...


def test_structural_validity():
    """Test structural validity checker."""
    # Valid examples
    # Invalid examples
    # ... test logic ...


def test_round_trip():
    """Test round-trip: ASCII → parse → load → format → ASCII."""
    # ... test logic ...


def test_csv_predictions_round_trip():
    """Test round-trip for all problems and solutions in CSV."""
    # ... test logic ...


if __name__ == "__main__":
    # Run all tests
    # ... test runner ...
```

#### Step 4.2: Test Cases to Include

1. **Basic parsing test**: Known valid ASCII state
2. **Structural validity test**: Valid and invalid examples
3. **Round-trip test**: Generate puzzle → get ASCII → parse → load → format → compare
4. **Edge cases**: Empty states, single cell, maximum size, special characters
5. **CSV round-trip**: Test all problems/solutions from dataset

#### Step 4.3: Round-Trip Test Pattern

**Critical test**:
```python
# 1. Get ASCII from a puzzle state
ascii_original = game.text_format(state).decode('utf-8')

# 2. Parse with Python parser
state_dict = parse_ascii_<puzzle_name>(ascii_original)

# 3. Load into C
loaded_state_ptr = puzzle.load_state_dict(state_dict)

# 4. Format back to ASCII
ascii_loaded = game.text_format(loaded_state_ptr.contents).decode('utf-8')

# 5. Compare (should match exactly)
assert ascii_original.strip() == ascii_loaded.strip()
```

---

### Phase 5: Integration

#### Step 5.1: Update Verifier

**Location**: `verifier.py`

**Changes needed**:
1. Import parser function: `from rlp.ascii_parser import parse_ascii_<puzzle_name>, check_<puzzle_name>_structural_validity`
2. Add puzzle type case in `verify_ascii_state()`:
```python
elif puzzle_type == "<puzzle_name>":
    # First check structural validity
    if not check_<puzzle_name>_structural_validity(str(ascii_text)):
        return "NOT SOLVED"
    
    # Parse ASCII with Python parser
    state_dict = parse_ascii_<puzzle_name>(str(ascii_text))
    
    # Load state dict
    loaded_state_ptr = puzzle.load_state_dict(state_dict)
    
    # Get free_game function
    me = puzzle.fe.contents.me.contents
    game = me.ourgame.contents
    free_game_func = game.free_game
    
    try:
        # Check if solved (use correct field: completed or solved)
        is_solved = loaded_state_ptr.contents.<field>  # completed or solved
        
        if is_solved:
            return "SOLVED"
        else:
            return "NOT SOLVED"
    finally:
        if loaded_state_ptr:
            free_game_func(loaded_state_ptr)
```

**Important**: Check which field the puzzle uses (`completed` for bridges, `solved` for undead)

#### Step 5.2: Update Test Verifier

**Location**: `test_verifier.py`

**Changes needed**:
1. Add puzzle type parameter to test functions
2. Add puzzle-specific configuration (difficulty args, puzzle name in CSV)
3. Add puzzle type to command-line argument choices

#### Step 5.3: Update Evaluate Predictions (if applicable)

**Location**: `evaluate-predictions.py`

**Changes needed**:
1. Add puzzle type to command-line arguments
2. Add puzzle-specific configuration
3. Update puzzle name filtering

---

## Code Structure

### File: `rlp/ascii_parser.py`

**Structure**:
```python
# Constants for puzzle 1
CONSTANT_1 = value1
CONSTANT_2 = value2

# Structural validity for puzzle 1
def check_puzzle1_structural_validity(ascii_text: str) -> bool:
    ...

# Parser for puzzle 1
def parse_ascii_puzzle1(ascii_text: str) -> dict:
    ...

# Constants for puzzle 2
CONSTANT_3 = value3

# Structural validity for puzzle 2
def check_puzzle2_structural_validity(ascii_text: str) -> bool:
    ...

# Parser for puzzle 2
def parse_ascii_puzzle2(ascii_text: str) -> dict:
    ...
```

### Function Signature Template

```python
def parse_ascii_<puzzle_name>(ascii_text: str) -> dict:
    """
    Parse ASCII text representation of a <puzzle_name> puzzle and return a state dict.
    
    ASCII Format:
    - <Description of format>
    - <Cell types and meanings>
    - <Special structures>
    
    Args:
        ascii_text: The ASCII representation of the puzzle state
        
    Returns:
        dict: State dictionary matching get_puzzle_state_<puzzle_name> format
        
    Raises:
        ValueError: If the ASCII text is invalid or empty
    """
    # Implementation
```

---

## Testing Strategy

### Unit Tests (Parser-Specific)

**File**: `test_ascii_parser_<puzzle_name>.py`

**Test categories**:
1. **Basic parsing**: Valid ASCII states parse correctly
2. **Structural validity**: Valid vs invalid inputs
3. **Edge cases**: Empty, single cell, max size, special characters
4. **Round-trip**: ASCII → parse → load → format → ASCII (must match)
5. **CSV integration**: Test with real dataset

### Integration Tests (Verifier)

**File**: `test_verifier.py`

**Test categories**:
1. **CSV predictions**: Problems return `solved=False`, solutions return `solved=True`
2. **State comparison**: Compare two similar ASCII states
3. **Large-scale testing**: Test all problems/solutions from dataset

---

## Integration Checklist

### Parser Implementation
- [ ] Constants defined matching C values
- [ ] Structural validity checker implemented (optional but recommended)
- [ ] Parser function implemented
- [ ] State dict format matches `get_puzzle_state_<puzzle_name>()` exactly
- [ ] Error handling added
- [ ] Documentation added

### Testing
- [ ] Unit tests created (`test_ascii_parser_<puzzle_name>.py`)
- [ ] Structural validity tests pass
- [ ] Round-trip tests pass
- [ ] Edge case tests pass
- [ ] CSV round-trip tests pass (if applicable)

### Integration
- [ ] Verifier updated (`verifier.py`)
- [ ] Test verifier updated (`test_verifier.py`)
- [ ] Evaluate predictions updated (if applicable)
- [ ] All tests pass

---

## Common Patterns and Examples

### Pattern 1: Simple Grid (like bridges)

```python
# Dimension inference
lines = ascii_text.strip().split('\n')
h = len(lines)
w = max(len(line.rstrip()) for line in lines)

# Cell-by-cell parsing
for y, line in enumerate(lines):
    for x in range(w):
        c = line[x] if x < len(line.rstrip()) else None
        idx = y * w + x
        # Parse character
```

### Pattern 2: Grid with Border (like undead)

```python
# Grid is (w+2) x (h+2) including border
grid_w = max_cells  # from parsing
grid_h = len(grid_lines)
w = grid_w - 2
h = grid_h - 2

# Cell-by-cell parsing with border
for y, line in enumerate(grid_lines):
    for x in range(grid_w):
        cell_str = line[x*2:(x+1)*2]  # 2-character cells
        idx = y * grid_w + x
        # Parse cell
```

### Pattern 3: Header + Grid

```python
# Parse header
first_line = lines[0].strip()
# Extract header information

# Find grid start
grid_start = 1
if len(lines) > 1 and lines[1].strip() == '':
    grid_start = 2

grid_lines = lines[grid_start:]
# Parse grid
```

### Pattern 4: Helper Functions

```python
def helper_function_for_puzzle(x, y, w, h):
    """
    Helper function ported from C.
    
    Args:
        x, y: Coordinates
        w, h: Dimensions
        
    Returns:
        <return type>
    """
    # Ported logic from C
    pass
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: State Dict Format Mismatch

**Symptom**: `load_state_dict()` raises ValueError about missing fields

**Solution**:
- Compare your state dict with output from `get_puzzle_state_<puzzle_name>()`
- Ensure all required fields are present
- Check field names match exactly (case-sensitive)
- Verify array lengths match requirements

#### Issue 2: Round-Trip Mismatch

**Symptom**: ASCII after round-trip doesn't match original

**Solution**:
- Check dimension inference is correct
- Verify cell parsing maps characters correctly
- Ensure border cells are handled correctly (if applicable)
- Check if whitespace differences matter (use `.strip()` for comparison)

#### Issue 3: Grid Flags Don't Match

**Symptom**: Parsed state doesn't behave correctly

**Solution**:
- Verify constants match C `#define` values exactly
- Check hex values are correct (0x0001 vs 0x001, etc.)
- Ensure bitwise operations are correct

#### Issue 4: Derived Arrays Issues

**Symptom**: Errors about array access or computation

**Solution**:
- Initialize derived arrays to zeros (don't try to compute in Python)
- Let C code recompute them
- Ensure array lengths are correct

#### Issue 5: Memory Leaks

**Symptom**: Memory usage grows over time

**Solution**:
- Always use try/finally to free loaded states
- Call `free_game_func(loaded_state_ptr)` in finally block
- Don't forget to free states in test loops

#### Issue 6: Structural Validity Too Strict/Loose

**Symptom**: Valid states rejected or invalid states accepted

**Solution**:
- Adjust validation criteria
- Test with edge cases
- Balance between catching errors and being lenient

---

## Quick Reference

### Key Files

- **Parser implementation**: `rlp/ascii_parser.py`
- **State dict format**: `rlp/specific_api.py` (`get_puzzle_state_<puzzle_name>()`)
- **Load function**: `rlp/specific_api.py` (`load_state_dict_<puzzle_name>()`)
- **C ASCII format**: `puzzles/<puzzle_name>.c` (`game_text_format()`)
- **C state structure**: `puzzles/<puzzle_name>.c` (struct definitions)
- **Verifier**: `verifier.py`
- **Tests**: `test_ascii_parser_<puzzle_name>.py`, `test_verifier.py`

### Key Functions

- `parse_ascii_<puzzle_name>(ascii_text: str) -> dict`: Main parser
- `check_<puzzle_name>_structural_validity(ascii_text: str) -> bool`: Quick validation
- `verify_ascii_state(puzzle, ascii_text: str) -> str`: Verifier integration
- `puzzle.load_state_dict(state_dict: dict)`: Load state into C

### Key Principles

1. **Match formats exactly**: State dict must match `get_puzzle_state_<puzzle_name>()` exactly
2. **Minimal canonical fields**: Only include what's needed for reconstruction
3. **Let C compute derived fields**: Initialize derived arrays to zeros
4. **Round-trip testing is critical**: ASCII → parse → load → format → ASCII must match
5. **Handle edge cases**: Variable line lengths, special characters, empty states
6. **Memory management**: Always free loaded states
7. **Test with real data**: Use actual problems and solutions from datasets

---

## Example: Complete Implementation Checklist

For a new puzzle called "example":

### Phase 1: Research
- [ ] Study `puzzles/example.c` `game_text_format()` function
- [ ] Review `get_puzzle_state_example()` in `rlp/specific_api.py`
- [ ] Review `load_state_dict_example()` in `rlp/specific_api.py`
- [ ] Identify all ASCII characters and their meanings
- [ ] Identify cell type constants from C source
- [ ] Understand the puzzle's state structure

### Phase 2: Implementation
- [ ] Add constants to `rlp/ascii_parser.py`
- [ ] Implement `check_example_structural_validity()` (optional)
- [ ] Implement `parse_ascii_example()` function
- [ ] Test with known examples

### Phase 3: Testing
- [ ] Create `test_ascii_parser_example.py`
- [ ] Test structural validity (if implemented)
- [ ] Test basic parsing
- [ ] Test round-trip
- [ ] Test edge cases
- [ ] Test with CSV (if applicable)

### Phase 4: Integration
- [ ] Update `verifier.py` to use new parser
- [ ] Update `test_verifier.py` to test example puzzle
- [ ] Update `evaluate-predictions.py` (if applicable)
- [ ] Verify all tests pass

---

## References

- Bridges parser: `rlp/ascii_parser.py` (`parse_ascii_bridges`, `check_bridges_structural_validity`)
- Undead parser: `rlp/ascii_parser.py` (`parse_ascii_undead`, `check_undead_structural_validity`)
- Original guide: `ASCII_PARSER_IMPLEMENTATION_GUIDE_new.md`
- State dict format: `rlp/specific_api.py`
- C text format: `puzzles/<puzzle_name>.c` (`game_text_format()`)
- Tests: `test_ascii_parser.py`, `test_ascii_parser_undead.py`, `test_verifier.py`

---

## Notes

- This template is based on successful implementations for bridges and undead puzzles
- Adapt patterns to your specific puzzle's requirements
- When in doubt, refer to existing implementations (bridges, undead) as examples
- Test thoroughly with real data before considering implementation complete
- Round-trip testing is the most important validation

