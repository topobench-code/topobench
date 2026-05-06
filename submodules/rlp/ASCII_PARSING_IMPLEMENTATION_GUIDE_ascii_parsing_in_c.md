# ASCII Parsing Implementation Guide Old

This document summarizes the implementation of ASCII-to-state-dict () parsing functionality for puzzles, using the Bridges puzzle as a reference implementation.

## Overview

The goal is to create an inverse function to `game_text_format()` that can parse an ASCII representation of a puzzle state and recreate the internal game state. This enables:
- Verifying if an arbitrary ASCII state is solved
- Converting ASCII states to state dictionaries
- Validating puzzle states from external sources

## Implementation Steps

### 1. Add C-Level Parsing Function

**Location**: In the puzzle's `.c` file (e.g., `puzzles/bridges.c`)

**Function Signature**:
```c
static game_state *game_text_parse(const char *text)
```

**Key Responsibilities**:
- Parse ASCII text to infer dimensions (width, height)
- Initialize game parameters with defaults
- Create a new game state
- Parse islands/clues from ASCII
- Parse lines/connections from ASCII
- Validate the parsed state
- Check if the state is solved

**Wrapper Function** (for Python exposure):
```c
game_state *puzzle_name_text_parse(const char *text)
{
    return game_text_parse(text);
}
```

**Placement**: Place these functions after all helper functions they depend on (e.g., `new_state`, `island_add`, `map_find_orthogonal`, etc.) to avoid implicit declaration warnings.

### 2. Add Python Wrapper

**Location**: `rlp/puzzle.py` in the `Puzzle.__init__` method

**Code Pattern**:
```python
self._text_parse = None
if self.puzzle_name == "puzzle_name":
    self._text_parse = wrap_function(
        self._lib, "puzzle_name_text_parse", api.specific.GAMESTATE_PTR, [c.c_char_p]
    )
```

### 3. Add Python Methods

**Location**: `rlp/puzzle.py` in the `Puzzle` class

**Methods to Add**:

#### `check_ascii_solved(ascii_text: str) -> bool`
- Parses ASCII and checks if the state is solved
- Returns `True` if solved, `False` otherwise
- Handles memory cleanup properly

#### `get_state_dict_from_ascii(ascii_text: str) -> dict`
- Parses ASCII and returns the state dictionary
- Uses `specific.get_puzzle_state_dict()` to convert C state to Python dict
- Handles memory cleanup properly

### 4. Recompile the Library

**Command**:
```bash
cd /home/ubuntu/projects/rlp/rlp/lib
cmake --build . --target libpuzzle_name --clean-first
```

Or use the full install script:
```bash
cd /home/ubuntu/projects/rlp
./install_new.sh
```

## Bridges Implementation Details

### ASCII Format

The Bridges puzzle uses the following ASCII characters:
- `0-9`, `A-G`: Island with count (0-16)
- `|`: Single vertical bridge
- `"`: Double vertical bridge
- `-`: Single horizontal bridge
- `=`: Double horizontal bridge
- `.`: Empty cell
- `\n`: Row separator

### Parsing Logic

1. **Dimension Inference**: Parse ASCII to determine width and height
2. **Island Parsing**: Extract islands and their counts from digits/letters
3. **Line Parsing**: Extract bridges from line characters (`|`, `"`, `-`, `=`)
4. **Validation**: Ensure all bridge paths are complete in ASCII
5. **Solved Check**: Verify all islands have correct bridge counts

### Critical Validation Function

**`path_has_all_lines()`**: Validates that all cells in a bridge path have corresponding line characters in the ASCII. This prevents creating bridges when the ASCII has gaps.

**Why it's needed**: Without this, `island_join()` would fill all cells between two islands, even if the ASCII doesn't show line characters in all those cells.

### Explicit Bridge Count Check

After parsing, explicitly verify each island has the correct number of bridges:
```c
bool all_islands_correct = true;
for (int i = 0; i < state->n_islands; i++) {
    struct island *is = &state->islands[i];
    int bridge_count = island_countbridges(is);
    if (bridge_count != is->count) {
        all_islands_correct = false;
        break;
    }
}
```

## Important Caveats and Considerations

### 1. Memory Management

**Critical**: Always free the parsed state after use:
```python
try:
    # Use state_ptr
    ...
finally:
    if state_ptr:
        free_game_func(state_ptr)
```

**Important**: Get `free_game` function pointer BEFORE accessing `state_ptr.contents` to avoid use-after-free issues.

### 2. Function Declaration Order

**Problem**: Implicit declaration warnings if functions are called before they're defined.

**Solution**: Place `game_text_parse` after all helper functions it depends on. Check for:
- `new_state()`
- Island manipulation functions (`island_add`, `island_join`, etc.)
- Map functions (`map_find_orthogonal`, `map_update_possibles`, `map_check`)
- Any other helper functions used

### 3. Parameter Defaults

When parsing ASCII, you may need to infer or default parameters:
- **Dimensions**: Infer from ASCII structure
- **Difficulty**: Default to 0 (not needed for parsing)
- **Game-specific params**: Use sensible defaults (e.g., `allowloops = true` for Bridges)
- **Island/expansion params**: Not needed for parsing (set to 0)

### 4. Path Validation

**Critical for Bridges**: Always validate that bridge paths are complete in ASCII before creating bridges. This prevents:
- Creating bridges when ASCII has gaps
- Incorrectly marking incomplete states as solved
- Different ASCII states producing the same internal representation

### 5. State Validation

**Always verify**:
- All required elements are present (islands, connections, etc.)
- All counts match (bridge counts, clue counts, etc.)
- Connectivity is correct
- State is actually solved (not just connected)

### 6. ASCII Format Consistency

**Ensure**:
- The ASCII format matches what `game_text_format()` produces
- Character encoding is consistent (UTF-8)
- Newline handling is correct (`\n`, `\r`, or both)
- Edge cases are handled (trailing newlines, empty lines, etc.)

### 7. Puzzle-Specific Considerations

**Bridges-specific**:
- `allowloops` parameter affects solved check (default to `true`)
- Bridge paths must be validated before joining
- Island counts must match bridge counts exactly

**For other puzzles**, consider:
- What constitutes a valid state?
- What parameters need to be inferred vs. defaulted?
- What validation is required?
- How does the ASCII format represent the puzzle state?

### 8. Testing Strategy

**Test Cases to Include**:
1. **Valid solved state**: Should parse correctly and return `solved = True`
2. **Valid unsolved state**: Should parse correctly and return `solved = False`
3. **Incomplete state**: Should parse but not mark as solved
4. **Invalid ASCII**: Should handle gracefully (return NULL or raise error)
5. **Edge cases**: Empty state, single island, maximum size, etc.
6. **Round-trip test**: Parse ASCII → get state → format to ASCII → should match original

### 9. Error Handling

**In C**:
- Return `NULL` if parsing fails
- Validate inputs (non-null text, valid dimensions)
- Check for memory allocation failures

**In Python**:
- Raise `ValueError` for unsupported puzzles
- Handle `None` returns from C functions
- Ensure proper cleanup in `finally` blocks

### 10. Performance Considerations

**Path validation** can be expensive if done naively:
- Consider building a lookup table/map of ASCII characters
- Cache parsed dimensions
- Optimize the validation loop

**For Bridges**: The `path_has_all_lines()` function parses the entire ASCII for each bridge, which is O(n*m) where n is ASCII length and m is number of bridges. For large puzzles, consider optimizing.

## Implementation Checklist for New Puzzles

- [ ] Understand the ASCII format from `game_text_format()`
- [ ] Identify required parameters and defaults
- [ ] Implement dimension inference
- [ ] Implement element parsing (islands, clues, etc.)
- [ ] Implement connection parsing (bridges, links, etc.)
- [ ] Add validation functions (path validation, count checks, etc.)
- [ ] Add explicit solved state verification
- [ ] Create wrapper function for Python exposure
- [ ] Add Python wrapper in `puzzle.py`
- [ ] Add `check_ascii_solved()` method
- [ ] Add `get_state_dict_from_ascii()` method
- [ ] Recompile library
- [ ] Write comprehensive tests
- [ ] Test edge cases and error conditions
- [ ] Document puzzle-specific considerations

## Example: Bridges Implementation Summary

### Files Modified

1. **`puzzles/bridges.c`**:
   - Added `path_has_all_lines()` helper function
   - Added `game_text_parse()` function
   - Added `bridges_text_parse()` wrapper function
   - Changed `params.allowloops = true` (was `false`)

2. **`rlp/puzzle.py`**:
   - Added `_text_parse` loading in `__init__`
   - Added `check_ascii_solved()` method
   - Added `get_state_dict_from_ascii()` method

3. **Test files**:
   - Created `test_verifier.py` with comprehensive tests
   - Created `verifier.py` standalone script

### Key Functions

- `path_has_all_lines()`: Validates bridge paths in ASCII
- `game_text_parse()`: Main parsing function
- `bridges_text_parse()`: Python-exposed wrapper
- `check_ascii_solved()`: Python method to check solved status
- `get_state_dict_from_ascii()`: Python method to get state dict

### Critical Fixes Applied

1. **Path validation**: Prevents creating bridges with gaps
2. **Explicit bridge count check**: Ensures all islands are correct
3. **Memory management**: Proper cleanup in Python wrappers
4. **Function order**: Moved functions after dependencies
5. **Parameter defaults**: Set `allowloops = true` for Bridges

## Notes for Future Implementations

1. **Start with understanding the ASCII format**: Study `game_text_format()` carefully
2. **Identify puzzle-specific elements**: What needs to be parsed? (islands, bridges, clues, etc.)
3. **Consider validation needs**: What can go wrong? What needs checking?
4. **Test thoroughly**: Especially edge cases and error conditions
5. **Document puzzle-specific quirks**: Each puzzle may have unique requirements

## Common Pitfalls to Avoid

1. **Memory leaks**: Always free parsed states
2. **Implicit declarations**: Order functions correctly
3. **Missing validation**: Don't trust ASCII blindly
4. **Incorrect defaults**: Understand what parameters mean
5. **Incomplete parsing**: Ensure all elements are parsed
6. **Wrong solved check**: Verify actual solved state, not just connectivity

## Questions to Answer for Each Puzzle

1. What does the ASCII format look like?
2. What parameters need to be inferred vs. defaulted?
3. What elements need to be parsed? (islands, bridges, clues, etc.)
4. What validation is required?
5. How is "solved" determined?
6. Are there puzzle-specific constraints? (e.g., no loops, connectivity requirements)
7. What edge cases exist?
8. How should errors be handled?

---

**Last Updated**: Based on Bridges puzzle implementation
**Status**: Bridges implementation complete and tested

