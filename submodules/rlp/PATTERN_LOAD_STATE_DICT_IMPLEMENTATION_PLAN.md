# Pattern Puzzle Load State Dict Implementation Plan

This document provides a detailed implementation plan for adding `load_state_dict` functionality to the Pattern puzzle, following the template from Bridges puzzle implementation.

## Overview

The `load_state_dict` feature for Pattern puzzle will enable:
- Loading arbitrary puzzle states from Python dictionaries
- Verifying if an ASCII board state (from LLM or other sources) is solved
- Swapping states between puzzle instances
- Round-trip testing: state → dict → load → dict → compare

## Pattern Puzzle Structure

### Canonical Fields (Must Include in Repr)
- `w`, `h` - grid dimensions
- `rowdata` - flattened array of clue values (size: `rowsize * (w + h)`)
- `rowlen` - array of clue lengths for each row/column (size: `w + h`)
- `immutable` - boolean array marking which cells are immutable clues (size: `w * h`)
- `grid` - player's current marks (size: `w * h`, values: GRID_UNKNOWN=2, GRID_FULL=1, GRID_EMPTY=0)

### Non-Canonical / Derived Fields (Recompute)
- `rowsize` - `max(w, h)` - recompute
- `refcount` - internal, set to 1
- `fontsize` - recompute from rowdata (FS_LARGE if all clues < 10, else FS_SMALL)
- `completed` - recompute via `compute_rowdata` comparison (like `execute_move` does)
- `cheated` - set to false

## Implementation Steps

### 1. C Layer: Define Repr Structs

**Location**: `puzzles/pattern.c` - Add before the `game_state` struct (around line 60)

```c
/* Repr structs for Python state dict loading */
typedef struct pattern_state_repr {
    int w;
    int h;
    int rowsize;  /* max(w, h) - for array sizing */
    int n_rowcol;  /* w + h - number of rows + columns */
    const int *rowdata;  /* flattened, size rowsize * n_rowcol */
    const int *rowlen;   /* size n_rowcol */
    const bool *immutable;  /* size w * h */
    const unsigned char *grid;  /* size w * h */
} pattern_state_repr;
```

**Key Points**:
- No separate "island" struct needed (unlike Bridges)
- `rowdata` is flattened: `rowdata[rowsize * i + j]` for row/column `i`, clue `j`
- `rowlen[i]` gives the number of clues for row/column `i`
- `n_rowcol = w + h` (first `w` entries are columns, next `h` entries are rows)

### 2. C Layer: Implement Reconstruction Function

**Location**: `puzzles/pattern.c` - Add after existing functions (after `new_game`, around line 1045)

**Function signature**:
```c
game_state *pattern_state_from_repr(const pattern_state_repr *r)
```

**Implementation**:
```c
game_state *pattern_state_from_repr(const pattern_state_repr *r)
{
    game_params params;
    game_state *st;
    game_state_common *common;
    int wh, wph, rowsize, i, j;

    if (!r) {
        return NULL;
    }

    /* Validate dimensions */
    if (r->w <= 0 || r->h <= 0) {
        return NULL;
    }
    if (r->rowsize != max(r->w, r->h)) {
        return NULL;  /* rowsize must match max(w, h) */
    }
    if (r->n_rowcol != r->w + r->h) {
        return NULL;  /* n_rowcol must match w + h */
    }

    /* Fill params from repr - only canonical fields */
    params.w = r->w;
    params.h = r->h;

    wh = r->w * r->h;
    wph = r->w + r->h;
    rowsize = max(r->w, r->h);

    /* Allocate game_state */
    st = snew(game_state);
    if (!st) {
        return NULL;
    }

    /* Allocate and initialize game_state_common */
    common = snew(game_state_common);
    if (!common) {
        sfree(st);
        return NULL;
    }

    common->w = r->w;
    common->h = r->h;
    common->rowsize = rowsize;
    common->refcount = 1;  /* Set to 1 for new state */

    /* Allocate arrays */
    st->grid = snewn(wh, unsigned char);
    common->rowdata = snewn(rowsize * wph, int);
    common->rowlen = snewn(wph, int);
    common->immutable = snewn(wh, bool);

    if (!st->grid || !common->rowdata || !common->rowlen || !common->immutable) {
        /* Cleanup on failure */
        if (st->grid) sfree(st->grid);
        if (common->rowdata) sfree(common->rowdata);
        if (common->rowlen) sfree(common->rowlen);
        if (common->immutable) sfree(common->immutable);
        sfree(common);
        sfree(st);
        return NULL;
    }

    st->common = common;

    /* Copy canonical arrays */
    if (r->grid) {
        for (i = 0; i < wh; i++) {
            st->grid[i] = r->grid[i];
        }
    } else {
        memset(st->grid, GRID_UNKNOWN, wh);
    }

    if (r->rowdata) {
        for (i = 0; i < rowsize * wph; i++) {
            common->rowdata[i] = r->rowdata[i];
        }
    } else {
        memset(common->rowdata, 0, rowsize * wph * sizeof(int));
    }

    if (r->rowlen) {
        for (i = 0; i < wph; i++) {
            common->rowlen[i] = r->rowlen[i];
        }
    } else {
        memset(common->rowlen, 0, wph * sizeof(int));
    }

    if (r->immutable) {
        for (i = 0; i < wh; i++) {
            common->immutable[i] = r->immutable[i];
        }
    } else {
        memset(common->immutable, 0, wh * sizeof(bool));
    }

    /* Recompute fontsize from rowdata */
    common->fontsize = FS_LARGE;
    for (i = 0; i < r->w; i++) {
        for (j = 0; j < common->rowlen[i]; j++) {
            if (common->rowdata[rowsize * i + j] >= 10) {
                common->fontsize = FS_SMALL;
                goto fontsize_done;
            }
        }
    }
fontsize_done:

    /* Initialize state flags */
    st->completed = false;
    st->cheated = false;

    /* Verify state: recompute completed flag using same logic as execute_move */
    if (st->grid && common->rowdata && common->rowlen) {
        int *rowdata_check = snewn(rowsize, int);
        bool all_match = true;

        /* Check columns (first w entries) */
        for (i = 0; i < r->w && all_match; i++) {
            int len = compute_rowdata(rowdata_check, st->grid + i,
                                      r->h, r->w);
            if (len != common->rowlen[i] ||
                memcmp(common->rowdata + rowsize * i,
                       rowdata_check, len * sizeof(int)) != 0) {
                all_match = false;
                break;
            }
        }

        /* Check rows (next h entries) */
        if (all_match) {
            for (i = 0; i < r->h && all_match; i++) {
                int len = compute_rowdata(rowdata_check,
                                          st->grid + i * r->w,
                                          r->w, 1);
                int row_idx = r->w + i;
                if (len != common->rowlen[row_idx] ||
                    memcmp(common->rowdata + rowsize * row_idx,
                           rowdata_check, len * sizeof(int)) != 0) {
                    all_match = false;
                    break;
                }
            }
        }

        st->completed = all_match;
        sfree(rowdata_check);
    }

    return st;
}
```

**Critical Steps**:
1. Validate input dimensions and array sizes
2. Allocate `game_state` and `game_state_common` separately
3. Copy all canonical arrays: `grid`, `rowdata`, `rowlen`, `immutable`
4. Recompute `fontsize` from `rowdata`
5. Recompute `completed` using `compute_rowdata` comparison (same as `execute_move`)
6. Set `refcount = 1` and `cheated = false`

### 3. Python ctypes Layer: Define Structs

**Location**: `rlp/specific_api.py`

**Add at module level** (around line 128, after other repr structs):
```python
class PatternStateRepr(c.Structure):
    pass
```

**Inside `set_api_structures_pattern()` function** (around line 1571, after `GameState._fields_`):
```python
PatternStateRepr._fields_ = [
    ("w", c.c_int),
    ("h", c.c_int),
    ("rowsize", c.c_int),
    ("n_rowcol", c.c_int),
    ("rowdata", CT_INT_PTR),
    ("rowlen", CT_INT_PTR),
    ("immutable", CT_BOOL_PTR),
    ("grid", CT_UCHAR_PTR),
]
```

**Key Points**:
- Struct fields must match C struct exactly (order, types)
- Use `CT_INT_PTR` for `int*` pointers
- Use `CT_BOOL_PTR` for `bool*` pointers
- Use `CT_UCHAR_PTR` for `unsigned char*` pointers

### 4. Python API Layer: Wire C Function

**Location**: `rlp/puzzle.py` in `Puzzle.__init__()` method (around line 163)

**Add in the puzzle-specific section**:
```python
elif self.puzzle_name == "pattern":
    # Add state_from_repr function
    from rlp import specific_api as specific
    self._state_from_repr = wrap_function(
        self._lib, "pattern_state_from_repr",
        api.specific.GAMESTATE_PTR,
        [c.POINTER(specific.PatternStateRepr)]
    )
    self._text_parse = None
```

### 5. Python API Layer: Implement Load Function

**Location**: `rlp/specific_api.py` after `get_puzzle_state_pattern()` function (around line 3047)

**Function**:
```python
def load_state_dict_pattern(state_dict: dict, lib: c.PyDLL) -> c.POINTER(GameState):
    """
    Load a Pattern puzzle game state from a Python state dict.
    
    Args:
        state_dict: Dictionary containing state information (from get_puzzle_state_pattern)
        lib: PyDLL instance for the puzzle library
        
    Returns:
        GameState pointer (caller must free it using game.free_game())
        
    Raises:
        ValueError: If required fields are missing or have wrong types
    """
    # Validate required fields exist
    required_fields = ["common", "grid", "completed", "cheated"]
    for field in required_fields:
        if field not in state_dict:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate types
    if not isinstance(state_dict["common"], dict):
        raise ValueError("common must be a dict")
    if not isinstance(state_dict["grid"], list):
        raise ValueError("grid must be a list")
    
    # Extract common fields
    common = state_dict["common"]
    required_common_fields = ["w", "h", "rowsize", "rowdata", "rowlen", "immutable"]
    for field in required_common_fields:
        if field not in common:
            raise ValueError(f"Missing required common field: {field}")
    
    w = common["w"]
    h = common["h"]
    rowsize = common["rowsize"]
    wh = w * h
    wph = w + h
    
    # Validate dimensions
    if not isinstance(w, int) or not isinstance(h, int):
        raise ValueError("w and h must be integers")
    if w <= 0 or h <= 0:
        raise ValueError("w and h must be positive")
    if rowsize != max(w, h):
        raise ValueError(f"rowsize ({rowsize}) must equal max(w, h) ({max(w, h)})")
    
    # Validate array types and lengths
    if not isinstance(common["rowdata"], list):
        raise ValueError("common.rowdata must be a list")
    if not isinstance(common["rowlen"], list):
        raise ValueError("common.rowlen must be a list")
    if not isinstance(common["immutable"], list):
        raise ValueError("common.immutable must be a list")
    if not isinstance(state_dict["grid"], list):
        raise ValueError("grid must be a list")
    
    # Validate array lengths
    expected_rowdata_len = rowsize * wph
    if len(common["rowdata"]) != expected_rowdata_len:
        raise ValueError(
            f"rowdata length ({len(common['rowdata'])}) does not match "
            f"rowsize * (w + h) ({expected_rowdata_len})"
        )
    if len(common["rowlen"]) != wph:
        raise ValueError(
            f"rowlen length ({len(common['rowlen'])}) does not match w + h ({wph})"
        )
    if len(common["immutable"]) != wh:
        raise ValueError(
            f"immutable length ({len(common['immutable'])}) does not match w * h ({wh})"
        )
    if len(state_dict["grid"]) != wh:
        raise ValueError(
            f"grid length ({len(state_dict['grid'])}) does not match w * h ({wh})"
        )
    
    # Validate array element types
    for i, val in enumerate(common["rowdata"]):
        if not isinstance(val, int):
            raise ValueError(f"rowdata[{i}] must be an integer")
    for i, val in enumerate(common["rowlen"]):
        if not isinstance(val, int):
            raise ValueError(f"rowlen[{i}] must be an integer")
        if val < 0 or val > rowsize:
            raise ValueError(f"rowlen[{i}] ({val}) must be between 0 and rowsize ({rowsize})")
    for i, val in enumerate(common["immutable"]):
        if not isinstance(val, bool):
            raise ValueError(f"immutable[{i}] must be a boolean")
    for i, val in enumerate(state_dict["grid"]):
        if not isinstance(val, int):
            raise ValueError(f"grid[{i}] must be an integer")
        if val not in (0, 1, 2):  # GRID_EMPTY, GRID_FULL, GRID_UNKNOWN
            raise ValueError(f"grid[{i}] ({val}) must be 0, 1, or 2")
    
    # Create ctypes arrays
    rowdata_arr = (c.c_int * (rowsize * wph))(*common["rowdata"])
    rowlen_arr = (c.c_int * wph)(*common["rowlen"])
    immutable_arr = (c.c_bool * wh)(*common["immutable"])
    grid_arr = (c.c_ubyte * wh)(*state_dict["grid"])
    
    # Build PatternStateRepr struct
    repr_obj = PatternStateRepr(
        w=w,
        h=h,
        rowsize=rowsize,
        n_rowcol=wph,
        rowdata=rowdata_arr,
        rowlen=rowlen_arr,
        immutable=immutable_arr,
        grid=grid_arr,
    )
    
    # Get the function from lib
    state_from_repr_func = lib.pattern_state_from_repr
    state_from_repr_func.restype = GAMESTATE_PTR
    state_from_repr_func.argtypes = [c.POINTER(PatternStateRepr)]
    
    # Call C function
    state_ptr = state_from_repr_func(c.byref(repr_obj))
    
    if not state_ptr:
        raise ValueError("Failed to create game state from repr")
    
    # Return the pointer (caller must free it)
    return state_ptr
```

### 6. Python API Layer: Add Puzzle Method

**Location**: `rlp/puzzle.py` in `Puzzle` class (check if method already exists, add if not)

**Method** (add if not already present):
```python
def load_state_dict(self, state_dict: dict) -> api.specific.GAMESTATE_PTR:
    """
    Load a puzzle game state from a Python state dict.
    
    Args:
        state_dict: Dictionary containing state information (from get_puzzle_state)
        
    Returns:
        GameState pointer (caller must free it using game.free_game())
        
    Raises:
        ValueError: If puzzle doesn't support this or if state dict is invalid
    """
    if self.puzzle_name != "pattern":
        raise ValueError(f"load_state_dict is only supported for pattern puzzle, not {self.puzzle_name}")
    
    if self._state_from_repr is None:
        raise ValueError("pattern_state_from_repr function not available")
    
    from rlp import specific_api as specific
    
    # Call the load function
    state_ptr = specific.load_state_dict_pattern(state_dict, self._lib)
    
    return state_ptr
```

## Critical Gotchas and Important Notes

### 1. Memory Management
- **Always return a pointer** from C function (not contents)
- **Caller must free** the returned state using `game.free_game(state_ptr)`
- Pattern uses refcounted `game_state_common` - `free_game` handles refcounting
- Use try/finally blocks in Python to ensure cleanup
- Pattern: `state_ptr = puzzle.load_state_dict(dict)` → use → `game.free_game(state_ptr)`

### 2. Rowdata Array Layout
- `rowdata` is **flattened**: `rowdata[rowsize * i + j]` where:
  - `i` is row/column index (0 to w+h-1)
  - First `w` entries (i=0 to w-1) are **columns**
  - Next `h` entries (i=w to w+h-1) are **rows**
  - `j` is clue index within that row/column (0 to rowlen[i]-1)
- When copying, must preserve this flattened layout

### 3. Only Include Canonical Fields
- **DO include**: w, h, rowdata, rowlen, immutable, grid
- **DON'T include**: 
  - `rowsize` - recompute as `max(w, h)`
  - `refcount` - set to 1
  - `fontsize` - recompute from rowdata
  - `completed`, `cheated` - recompute

### 4. Completion Verification
- Pattern's completion check uses `compute_rowdata` to compute actual row/column patterns
- Compare computed patterns against stored `rowdata` and `rowlen`
- Same logic as `execute_move` in `pattern.c` (lines 1477-1506)
- Must check all columns (first w entries) and all rows (next h entries)

### 5. Fontsize Recomputation
- Check all column clues (first w entries in rowlen)
- If any clue value >= 10, set `fontsize = FS_SMALL`
- Otherwise `fontsize = FS_LARGE`
- See `new_game` in `pattern.c` (lines 1019-1023)

### 6. Validation is Critical
- Validate all required fields exist
- Validate types (int, list, dict, bool)
- Validate array lengths match expected sizes
- Validate grid values are 0, 1, or 2
- Validate rowlen values are between 0 and rowsize
- Raise clear ValueError messages for debugging

### 7. Function Naming Convention
- C function: `pattern_state_from_repr`
- Python function: `load_state_dict_pattern`
- Struct name: `PatternStateRepr`

### 8. Recompilation Required
- After modifying C code, must recompile: `cmake --build rlp/lib --target libpattern`
- Python changes don't require recompilation (unless ctypes structs change)

## Testing Strategy

### Essential Tests

1. **test_load_problem_state**: Load initial problem state, verify it matches
2. **test_load_solution_state**: Load solved state, verify `completed=True`
3. **test_round_trip_problem**: Problem state → dict → load → dict → compare
4. **test_round_trip_solution**: Solution state → dict → load → dict → compare
5. **test_multiple_sizes**: Test with different puzzle sizes (5x5, 10x10, 15x15)
6. **test_state_verification**: Verify completion check results match
7. **test_swap_states_between_instances**: Swap states between two puzzle instances
8. **test_validation_errors**: Test invalid state dicts raise appropriate exceptions
9. **test_immutable_preservation**: Verify immutable cells are preserved correctly
10. **test_clue_arrays**: Verify rowdata and rowlen arrays are correctly preserved

### Test Pattern

```python
def test_pattern_example():
    puzzle = rp.Puzzle('pattern', arg='5x5', headless=True)
    puzzle.new_game()
    
    # Get state dict
    original_dict = puzzle.get_puzzle_state()
    
    # Load state dict
    me = puzzle.fe.contents.me.contents
    game = me.ourgame.contents
    free_game_func = game.free_game
    
    loaded_state_ptr = puzzle.load_state_dict(original_dict)
    
    try:
        # Use loaded state
        helper = getattr(puzzle, "_get_puzzle_state_helper", None)
        loaded_dict = specific.get_puzzle_state_dict(
            puzzle.puzzle_name, loaded_state_ptr.contents, helper
        )
        
        # Compare (with ignore_fields)
        ignore_fields = {
            'common.refcount',  # Internal refcounting
            'common.fontsize',  # Recomputed from rowdata
        }
        differences = deep_compare_dicts(original_dict, loaded_dict, ignore_fields=ignore_fields)
        assert len(differences) == 0, f"State dicts differ: {differences}"
    finally:
        # Always free
        if loaded_state_ptr:
            free_game_func(loaded_state_ptr)
```

## Files to Modify

1. **puzzles/pattern.c**:
   - Add `pattern_state_repr` struct definition
   - Implement `pattern_state_from_repr()` function

2. **rlp/specific_api.py**:
   - Add `PatternStateRepr` ctypes structure in `set_api_structures_pattern()`
   - Implement `load_state_dict_pattern()` function

3. **rlp/puzzle.py**:
   - Wire `pattern_state_from_repr` in `__init__()`
   - Add/update `load_state_dict()` method to support pattern

4. **test_load_state_dict.py** (or create new test file):
   - Create comprehensive test suite for pattern puzzle

## Checklist for Implementation

- [ ] Define C repr struct (`pattern_state_repr`) with canonical fields
- [ ] Implement C reconstruction function (`pattern_state_from_repr`)
  - [ ] Validate input dimensions and sizes
  - [ ] Allocate game_state and game_state_common
  - [ ] Copy canonical arrays (grid, rowdata, rowlen, immutable)
  - [ ] Recompute fontsize from rowdata
  - [ ] Recompute completed flag using compute_rowdata comparison
  - [ ] Set refcount = 1 and cheated = false
- [ ] Define Python ctypes struct (`PatternStateRepr`) matching C exactly
- [ ] Wire C function in puzzle.py `__init__()`
- [ ] Implement Python load function (`load_state_dict_pattern`) with validation
- [ ] Add/update `Puzzle.load_state_dict()` method
- [ ] Create comprehensive tests
- [ ] Recompile library: `cmake --build rlp/lib --target libpattern`
- [ ] Run tests and verify all pass

## Common Pitfalls

1. **Incorrect rowdata layout** → Clues don't match rows/columns
2. **Forgetting to recompute fontsize** → UI display issues
3. **Wrong completion check logic** → States marked complete when they shouldn't be
4. **Not validating array lengths** → Crashes or corruption
5. **Memory leaks** → Not freeing loaded states in tests
6. **Pointer vs contents confusion** → AttributeError or incorrect behavior
7. **Struct field order mismatch** → Silent corruption or crashes
8. **Not recompiling after C changes** → Old code runs, tests fail mysteriously
9. **Mixing up columns and rows** → First w entries are columns, next h are rows

## Success Criteria

- All tests pass
- Round-trip tests show no differences (except ignored fields: refcount, fontsize)
- State swapping works correctly
- Memory is properly managed (no leaks)
- Validation catches invalid inputs
- Completion verification works correctly
- Immutable cells are preserved
- Clue arrays (rowdata, rowlen) are correctly preserved





