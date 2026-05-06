# Load State Dict Implementation Guide

This document summarizes the implementation of `load_state_dict` functionality for Bridges puzzle, which allows loading a Python state dict into a C game state. This can be used as a guide for implementing the same functionality for other puzzles (e.g., undead).

## Overview

The `load_state_dict` feature enables:
- Loading arbitrary puzzle states from Python dictionaries
- Verifying if an ASCII board state (from LLM or other sources) is solved
- Swapping states between puzzle instances
- Round-trip testing: state → dict → load → dict → compare

## Architecture

The implementation follows a three-layer architecture:

1. **C Layer**: Defines repr structs and reconstruction function
2. **Python ctypes Layer**: Defines Python structs matching C structs
3. **Python API Layer**: Provides user-facing functions with validation

## Implementation Steps

### 1. C Layer: Define Repr Structs

**Location**: In the puzzle's `.c` file (e.g., `puzzles/bridges.c`)

**Add before the `game_state` struct**:

```c
/* Repr structs for Python state dict loading */
typedef struct puzzle_island_repr {  /* Adjust name for puzzle */
    int x;
    int y;
    int count;      /* or other relevant fields */
} puzzle_island_repr;

typedef struct puzzle_state_repr {
    int w;
    int h;
    /* Add puzzle-specific canonical fields */
    int maxb;       /* Example: bridges-specific */
    bool allowloops; /* Example: bridges-specific */
    int n_islands;  /* Adjust for puzzle structure */
    const puzzle_island_repr *islands;  /* Adjust type */
    const grid_type *grid;   /* Adjust type */
    const unsigned char *lines; /* Adjust type */
    /* Only include fields needed for reconstruction */
} puzzle_state_repr;
```

**Key Points**:
- Only include **canonical fields** needed for reconstruction
- Do NOT include derived fields (computed by backend)
- Do NOT include generation parameters (islands, expansion, difficulty)
- Do NOT include UI/solver flags

### 2. C Layer: Implement Reconstruction Function

**Location**: After existing parse functions (e.g., after `puzzle_text_parse`)

**Function signature**:
```c
game_state *puzzle_state_from_repr(const puzzle_state_repr *r)
```

**Implementation pattern**:
```c
game_state *puzzle_state_from_repr(const puzzle_state_repr *r)
{
    game_params params;
    game_state *st;
    int wh, i;

    if (!r) {
        return NULL;
    }

    /* Fill params from repr - only canonical fields */
    params.w = r->w;
    params.h = r->h;
    /* Add puzzle-specific params */
    params.maxb = r->maxb;
    params.allowloops = r->allowloops;

    /* Generation parameters - set to 0 (not needed for verification) */
    params.islands = 0;
    params.expansion = 0;
    params.difficulty = 0;

    /* Create new state */
    st = new_state(&params);
    if (!st) {
        return NULL;
    }

    wh = r->w * r->h;

    /* Copy canonical arrays */
    if (r->grid) {
        for (i = 0; i < wh; i++) {
            st->grid[i] = r->grid[i];
        }
    }

    if (r->lines) {
        for (i = 0; i < wh; i++) {
            st->lines[i] = r->lines[i];
        }
    }

    /* Rebuild puzzle-specific structures */
    /* Example for bridges: rebuild islands */
    sfree(st->islands);
    st->islands = NULL;
    st->n_islands = 0;
    st->n_islands_alloc = 0;

    /* Clear flags first */
    for (i = 0; i < wh; i++) {
        st->grid[i] &= ~G_ISLAND;  /* Adjust for puzzle */
    }

    /* Add structures from repr */
    if (r->islands && r->n_islands > 0) {
        for (i = 0; i < r->n_islands; i++) {
            const puzzle_island_repr *ir = &r->islands[i];
            puzzle_add_island(st, ir->x, ir->y, ir->count);  /* Adjust function name */
        }
    }

    /* Fix up internal structures */
    puzzle_fixup_internal(st);  /* Adjust function name */
    puzzle_find_connections(st);  /* Adjust function name */

    /* Recompute derived fields */
    puzzle_update_derived(st);  /* Adjust function name */

    /* Verify state */
    st->completed = puzzle_check(st);  /* Adjust function name */
    st->solved = false;

    /* IMPORTANT: Clear solver flags that verification might set */
    for (i = 0; i < wh; i++) {
        st->grid[i] &= ~(G_SWEEP | G_WARN);  /* Adjust flags for puzzle */
    }

    return st;
}
```

**Critical Steps**:
1. Create params from repr (only canonical fields)
2. Create new state
3. Copy canonical arrays
4. Rebuild puzzle-specific structures (islands, etc.)
5. Fix up internal structures (pointers, indices)
6. Recompute derived fields (possibles, max values, etc.)
7. Run verification (`puzzle_check`) to set `completed` flag
8. **Clear solver flags** (G_SWEEP, G_WARN, etc.) - these are not part of game state

### 3. Python ctypes Layer: Define Structs

**Location**: `rlp/specific_api.py` in `set_api_structures_puzzle()` function

**Add at module level** (before the function):
```python
class PuzzleIslandRepr(c.Structure):
    pass

class PuzzleStateRepr(c.Structure):
    pass
```

**Inside `set_api_structures_puzzle()` function**:
```python
PuzzleIslandRepr._fields_ = [
    ("x", c.c_int),
    ("y", c.c_int),
    ("count", c.c_int),  # Adjust fields for puzzle
]

PuzzleStateRepr._fields_ = [
    ("w", c.c_int),
    ("h", c.c_int),
    ("maxb", c.c_int),  # Adjust for puzzle
    ("allowloops", c.c_bool),  # Adjust for puzzle
    ("n_islands", c.c_int),
    ("islands", CT_PTR(PuzzleIslandRepr)),
    ("grid", CT_UINT_PTR),
    ("lines", CT_PTR(c.c_ubyte)),
]
```

**Key Points**:
- Struct fields must match C struct exactly (order, types)
- Use `CT_PTR` for pointers
- Use appropriate ctypes types (`c.c_int`, `c.c_bool`, `c.c_ubyte`, etc.)

### 4. Python API Layer: Wire C Function

**Location**: `rlp/puzzle.py` in `Puzzle.__init__()` method

**Add near other puzzle-specific function wrappers**:
```python
if self.puzzle_name == "puzzle_name":
    # ... existing code ...
    
    # Add state_from_repr function
    from rlp import specific_api as specific
    self._state_from_repr = wrap_function(
        self._lib, "puzzle_state_from_repr",
        api.specific.GAMESTATE_PTR,
        [c.POINTER(specific.PuzzleStateRepr)]
    )
```

### 5. Python API Layer: Implement Load Function

**Location**: `rlp/specific_api.py` after `get_puzzle_state_puzzle()` function

**Function**:
```python
def load_state_dict_puzzle(state_dict: dict, lib: c.PyDLL) -> c.POINTER(GameState):
    """
    Load a puzzle game state from a Python state dict.
    
    Args:
        state_dict: Dictionary containing state information (from get_puzzle_state_puzzle)
        lib: PyDLL instance for the puzzle library
        
    Returns:
        GameState pointer (caller must free it using game.free_game())
        
    Raises:
        ValueError: If required fields are missing or have wrong types
    """
    # Validate required fields exist
    required_fields = ["w", "h", "params", "grid", "lines", "islands"]  # Adjust for puzzle
    for field in required_fields:
        if field not in state_dict:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate types
    if not isinstance(state_dict["w"], int) or not isinstance(state_dict["h"], int):
        raise ValueError("w and h must be integers")
    if not isinstance(state_dict["grid"], list) or not isinstance(state_dict["lines"], list):
        raise ValueError("grid and lines must be lists")
    if not isinstance(state_dict["islands"], list):
        raise ValueError("islands must be a list")
    if not isinstance(state_dict["params"], dict):
        raise ValueError("params must be a dict")
    
    # Extract values
    w = state_dict["w"]
    h = state_dict["h"]
    wh = w * h
    
    # Validate params (adjust for puzzle)
    if "maxb" not in state_dict["params"]:
        raise ValueError("params.maxb is required")
    if "allowloops" not in state_dict["params"]:
        raise ValueError("params.allowloops is required")
    
    maxb = state_dict["params"]["maxb"]
    allowloops = bool(state_dict["params"]["allowloops"])
    
    # Validate array lengths
    if len(state_dict["grid"]) != wh:
        raise ValueError(f"grid length ({len(state_dict['grid'])}) does not match w*h ({wh})")
    if len(state_dict["lines"]) != wh:
        raise ValueError(f"lines length ({len(state_dict['lines'])}) does not match w*h ({wh})")
    
    # Validate islands (adjust for puzzle structure)
    islands_list = state_dict["islands"]
    n_islands = len(islands_list)
    for i, island in enumerate(islands_list):
        if not isinstance(island, dict):
            raise ValueError(f"islands[{i}] must be a dict")
        if "x" not in island or "y" not in island or "count" not in island:
            raise ValueError(f"islands[{i}] must have x, y, and count fields")
        if not isinstance(island["x"], int) or not isinstance(island["y"], int) or not isinstance(island["count"], int):
            raise ValueError(f"islands[{i}] x, y, and count must be integers")
    
    # Create ctypes arrays
    grid_arr = (c.c_uint * wh)(*state_dict["grid"])
    lines_arr = (c.c_ubyte * wh)(*state_dict["lines"])
    
    # Create islands repr array (extract only needed fields, ignore adj/computed fields)
    islands_arr = (PuzzleIslandRepr * n_islands)(
        *[PuzzleIslandRepr(
            x=island["x"],
            y=island["y"],
            count=island["count"]
        ) for island in islands_list]
    )
    
    # Build PuzzleStateRepr struct
    repr_obj = PuzzleStateRepr(
        w=w,
        h=h,
        maxb=maxb,
        allowloops=allowloops,
        n_islands=n_islands,
        islands=islands_arr,
        grid=grid_arr,
        lines=lines_arr,
    )
    
    # Get the function from lib
    state_from_repr_func = lib.puzzle_state_from_repr
    state_from_repr_func.restype = GAMESTATE_PTR
    state_from_repr_func.argtypes = [c.POINTER(PuzzleStateRepr)]
    
    # Call C function
    state_ptr = state_from_repr_func(c.byref(repr_obj))
    
    if not state_ptr:
        raise ValueError("Failed to create game state from repr")
    
    # Return the pointer (caller must free it)
    return state_ptr
```

### 6. Python API Layer: Add Puzzle Method

**Location**: `rlp/puzzle.py` in `Puzzle` class

**Method**:
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
    if self.puzzle_name != "puzzle_name":
        raise ValueError(f"load_state_dict is only supported for puzzle_name puzzle, not {self.puzzle_name}")
    
    if self._state_from_repr is None:
        raise ValueError("puzzle_state_from_repr function not available")
    
    from rlp import specific_api as specific
    
    # Call the load function
    state_ptr = specific.load_state_dict_puzzle(state_dict, self._lib)
    
    return state_ptr
```

## Critical Gotchas and Important Notes

### 1. Memory Management
- **Always return a pointer** from C function (not contents)
- **Caller must free** the returned state using `game.free_game(state_ptr)`
- Use try/finally blocks in Python to ensure cleanup
- Pattern: `state_ptr = puzzle.load_state_dict(dict)` → use → `game.free_game(state_ptr)`

### 2. Solver Flags Must Be Cleared
- After calling verification (`puzzle_check`), **clear solver flags** (G_SWEEP, G_WARN, etc.)
- These flags are set during verification but are NOT part of the game state
- If not cleared, round-trip tests will fail with grid value mismatches
- Example: `st->grid[i] &= ~(G_SWEEP | G_WARN);`

### 3. Only Include Canonical Fields
- **DO include**: w, h, grid, lines, islands (x, y, count), puzzle-specific rules (maxb, allowloops)
- **DON'T include**: 
  - Derived fields (wha, possv, possh, maxv, maxh) - recomputed by backend
  - Generation parameters (islands, expansion, difficulty) - not needed for verification
  - UI flags (G_MARK, etc.)
  - Solver state (dsf, tmpdsf, etc.)
  - Computed adjacency data (adj) - recomputed by `puzzle_find_connections`

### 4. Test Comparison Logic
- Use `ignore_fields` in test comparisons to ignore:
  - Generation parameters (`params.islands`, `params.expansion`, `params.difficulty`)
  - Allocation details (`n_islands_alloc`)
  - Solver flags in grid values (mask out G_SWEEP, G_WARN when comparing)
- Compare grid values with flags masked: `val1 & ~(0x1000 | 0x0080)`

### 5. Pointer Dereferencing
- When accessing state fields: use `.contents` (e.g., `state_ptr.contents.completed`)
- When passing to functions expecting GameState: use `.contents`
- When freeing: pass the pointer directly (e.g., `game.free_game(state_ptr)`)

### 6. Validation is Critical
- Validate all required fields exist
- Validate types (int, list, dict)
- Validate array lengths match w*h
- Validate island structures have required fields
- Raise clear ValueError messages for debugging

### 7. Function Naming Convention
- C function: `puzzle_name_state_from_repr` (e.g., `bridges_state_from_repr`)
- Python function: `load_state_dict_puzzle_name` (e.g., `load_state_dict_bridges`)
- Struct names: `PuzzleNameIslandRepr`, `PuzzleNameStateRepr`

### 8. Recompilation Required
- After modifying C code, must recompile: `cmake --build rlp/lib --target libpuzzle_name`
- Python changes don't require recompilation (unless ctypes structs change)

## Testing Strategy

### Essential Tests

1. **test_load_problem_state**: Load initial problem state, verify it matches
2. **test_load_solution_state**: Load solved state, verify `completed=True`
3. **test_round_trip_problem**: Problem state → dict → load → dict → compare
4. **test_round_trip_solution**: Solution state → dict → load → dict → compare
5. **test_multiple_sizes**: Test with different puzzle sizes
6. **test_state_verification**: Verify `map_check()` results match
7. **test_swap_states_between_instances**: Swap states between two puzzle instances
8. **test_validation_errors**: Test invalid state dicts raise appropriate exceptions

### Test Pattern

```python
def test_example():
    puzzle = rp.Puzzle('puzzle_name', arg='5x5de', headless=True)
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
            'params.difficulty',
            'params.islands',  # If applicable
            'params.expansion',  # If applicable
            'n_islands_alloc',  # If applicable
        }
        differences = deep_compare_dicts(original_dict, loaded_dict, ignore_fields=ignore_fields)
        assert len(differences) == 0, f"State dicts differ: {differences}"
    finally:
        # Always free
        if loaded_state_ptr:
            free_game_func(loaded_state_ptr)
```

## Files Modified (Bridges Example)

1. **puzzles/bridges.c**:
   - Added `bridges_island_repr` and `bridges_state_repr` structs
   - Implemented `bridges_state_from_repr()` function

2. **rlp/specific_api.py**:
   - Added `BridgesIslandRepr` and `BridgesStateRepr` ctypes structures
   - Implemented `load_state_dict_bridges()` function

3. **rlp/puzzle.py**:
   - Wired `bridges_state_from_repr` in `__init__()`
   - Added `load_state_dict()` method

4. **test_load_state_dict.py**:
   - Created comprehensive test suite

## Checklist for New Puzzle Implementation

- [ ] Define C repr structs (only canonical fields)
- [ ] Implement C reconstruction function
  - [ ] Create params from repr
  - [ ] Create new state
  - [ ] Copy canonical arrays
  - [ ] Rebuild puzzle-specific structures
  - [ ] Fix up internal structures
  - [ ] Recompute derived fields
  - [ ] Run verification
  - [ ] Clear solver flags
- [ ] Define Python ctypes structs (match C exactly)
- [ ] Wire C function in puzzle.py
- [ ] Implement Python load function with validation
- [ ] Add Puzzle.load_state_dict() method
- [ ] Create comprehensive tests
- [ ] Recompile library
- [ ] Run tests and verify all pass

## Common Pitfalls

1. **Forgetting to clear solver flags** → Grid value mismatches in tests
2. **Including non-canonical fields** → Unnecessary complexity, potential bugs
3. **Not validating input** → Runtime crashes with unclear errors
4. **Memory leaks** → Not freeing loaded states in tests
5. **Pointer vs contents confusion** → AttributeError or incorrect behavior
6. **Struct field order mismatch** → Silent corruption or crashes
7. **Not recompiling after C changes** → Old code runs, tests fail mysteriously

## Success Criteria

- All tests pass
- Round-trip tests show no differences (except ignored fields)
- State swapping works correctly
- Memory is properly managed (no leaks)
- Validation catches invalid inputs
- ASCII strings match after loading

