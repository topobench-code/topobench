# Galaxies Load State Dict Implementation Plan

This document outlines the plan for implementing `load_state_dict` functionality for the Galaxies puzzle, following the template from `LOAD_STATE_DICT_IMPLEMENTATION_GUIDE.md`.

## Clarifying Questions

Before proceeding with implementation, we need to clarify the following:

### 1. Canonical Fields Identification

**Question**: Which fields from `get_puzzle_state_galaxies()` are truly canonical vs derived?

Current `get_puzzle_state_galaxies()` returns:
- `w`, `h` - **Canonical** (from params)
- `sx`, `sy` - **Derived** (computed as `(w*2)+1`, `(h*2)+1`)
- `grid` - **Canonical** (array of space structs with flags, dotx, doty, nassoc)
- `completed` - **Derived** (computed by `check_complete()`)
- `used_solve` - **UI state** (not canonical)
- `ndots` - **Derived** (computed by `game_update_dots()`)
- `dots_indices` - **Derived** (computed from grid by scanning for F_DOT flags)
- `cdiff` - **Derived** (difficulty of current puzzle, not needed for reconstruction)

**Proposed canonical fields for repr struct**:
- `w`, `h` - dimensions
- `grid` - array of space structs (only canonical fields: x, y, type, flags, dotx, doty, nassoc)

**Questions**:
- Should we include `sx`, `sy` in the repr, or always compute them from `w`, `h`? compute from w,h
- Should we store `dots_indices` or reconstruct the `dots` array from grid by calling `game_update_dots()`? 
- Which flags in the `space.flags` field are canonical vs solver/UI flags? (F_DOT, F_EDGE_SET, F_TILE_ASSOC are canonical; F_MARK, F_REACHABLE, F_SCRATCH, F_MULTIPLE, F_DOT_HOLD, F_GOOD, F_DOT_BLACK are likely not)

### 2. Space Struct Fields

**Question**: Which fields in the `space` struct are canonical?

The `space` struct has:
- `x`, `y` - position (can be recomputed from index)
- `type` - s_tile, s_edge, s_vertex (can be recomputed from x, y position)
- `flags` - bitfield (needs careful filtering)
- `dotx`, `doty` - if F_TILE_ASSOC is set (canonical)
- `nassoc` - if F_DOT is set (canonical)

**Proposed approach**:
- Store only: `flags` (filtered), `dotx`, `doty`, `nassoc`
- Recompute `x`, `y`, `type` during reconstruction

### 3. Solver Flags to Clear

**Question**: Which flags need to be cleared after verification?

From the code, solver flags that should be cleared:
- `F_MARK` (0x10) - scratch flag
- `F_REACHABLE` (0x20)
- `F_SCRATCH` (0x40)
- `F_MULTIPLE` (0x80)
- `F_DOT_HOLD` (0x100)
- `F_GOOD` (0x200)

**Canonical flags to preserve**:
- `F_DOT` (0x1)
- `F_EDGE_SET` (0x2)
- `F_TILE_ASSOC` (0x4)
- `F_DOT_BLACK` (0x8) - UI flag, but might be needed?

### 4. Reconstruction Steps

**Question**: What internal structures need to be rebuilt?

From analyzing the code:
1. `dots` array - needs to be rebuilt from grid using `game_update_dots()`
2. `ndots` - computed by `game_update_dots()`
3. `completed` - computed by `check_complete()`
4. `sx`, `sy` - computed from `w`, `h` in `blank_game()`

**Proposed reconstruction order**:
1. Create params from repr (w, h, diff=0)
2. Create blank state using `blank_game()` or similar
3. Copy grid array (filtering flags)
4. Call `game_update_dots()` to rebuild dots array
5. Call `check_complete()` to set `completed` flag
6. Clear solver flags from grid

### 5. Validation Requirements

**Question**: What validation is needed in the Python layer?

- Validate `w`, `h` are integers and within reasonable bounds
- Validate `grid` is a list with length `sx * sy` where `sx = (w*2)+1`, `sy = (h*2)+1`
- Validate each space in grid has required fields (flags, dotx, doty, nassoc)
- Validate `dotx`, `doty` are within bounds if `F_TILE_ASSOC` is set
- Validate `nassoc` is non-negative if `F_DOT` is set

## Implementation Plan

### Phase 1: C Layer - Repr Structs

**File**: `puzzles/galaxies.c`

**Location**: Before `game_state` struct (around line 178)

```c
/* Repr structs for Python state dict loading */
typedef struct galaxies_space_repr {
    unsigned int flags;      /* Only canonical flags: F_DOT, F_EDGE_SET, F_TILE_ASSOC */
    int dotx, doty;          /* If flags & F_TILE_ASSOC */
    int nassoc;              /* If flags & F_DOT */
} galaxies_space_repr;

typedef struct galaxies_state_repr {
    int w;
    int h;
    const galaxies_space_repr *grid;  /* Length: (w*2+1) * (h*2+1) */
} galaxies_state_repr;
```

**Key Decisions**:
- Only store canonical flags (F_DOT, F_EDGE_SET, F_TILE_ASSOC)
- Store dotx, doty, nassoc as they are part of the game state
- Do NOT store x, y, type (recomputed from position)
- Do NOT store sx, sy (recomputed from w, h)

### Phase 2: C Layer - Reconstruction Function

**File**: `puzzles/galaxies.c`

**Location**: After `load_game()` function (around line 1757)

**Function**: `galaxies_state_from_repr()`

**Implementation steps**:
1. Validate input (check r != NULL)
2. Create params: `w = r->w`, `h = r->h`, `diff = 0`
3. Create blank state using `blank_game(w, h)`
4. Compute `sx = (w*2)+1`, `sy = (h*2)+1`, `sz = sx * sy`
5. Copy grid array:
   - For each space in repr->grid:
     - Set `flags` (only canonical flags)
     - Set `dotx`, `doty` if `F_TILE_ASSOC` is set
     - Set `nassoc` if `F_DOT` is set
     - Preserve `x`, `y`, `type` from blank_game
6. Call `game_update_dots(state)` to rebuild dots array
7. Call `check_complete(state, NULL, NULL)` to set `completed` flag
8. Clear solver flags from grid:
   ```c
   for (i = 0; i < sz; i++) {
       state->grid[i].flags &= ~(F_MARK | F_REACHABLE | F_SCRATCH | 
                                  F_MULTIPLE | F_DOT_HOLD | F_GOOD);
   }
   ```
9. Set `used_solve = false`, `cdiff = -1`
10. Return state pointer

### Phase 3: Python ctypes Layer - Struct Definitions

**File**: `rlp/specific_api.py`

**Location**: In `set_api_structures_puzzle()` function, add before the function:

```python
class GalaxiesSpaceRepr(c.Structure):
    pass

class GalaxiesStateRepr(c.Structure):
    pass
```

**Inside `set_api_structures_puzzle()` function**:

```python
if puzzle_name == "galaxies":
    GalaxiesSpaceRepr._fields_ = [
        ("flags", c.c_uint),
        ("dotx", c.c_int),
        ("doty", c.c_int),
        ("nassoc", c.c_int),
    ]
    
    GalaxiesStateRepr._fields_ = [
        ("w", c.c_int),
        ("h", c.c_int),
        ("grid", CT_PTR(GalaxiesSpaceRepr)),
    ]
```

### Phase 4: Python API Layer - Wire C Function

**File**: `rlp/puzzle.py`

**Location**: In `Puzzle.__init__()` method, add after undead section (around line 188):

```python
elif self.puzzle_name == "galaxies":
    # Add state_from_repr function
    from rlp import specific_api as specific
    self._state_from_repr = wrap_function(
        self._lib, "galaxies_state_from_repr",
        api.specific.GAMESTATE_PTR,
        [c.POINTER(specific.GalaxiesStateRepr)]
    )
else:
    self._text_parse = None
    self._state_from_repr = None
```

### Phase 5: Python API Layer - Load Function

**File**: `rlp/specific_api.py`

**Location**: After `load_state_dict_undead()` function (around line 3460)

**Function**: `load_state_dict_galaxies()`

**Implementation**:
1. Validate required fields: `w`, `h`, `grid`
2. Validate types: `w`, `h` are ints, `grid` is a list
3. Compute `sx = (w*2)+1`, `sy = (h*2)+1`, `sz = sx * sy`
4. Validate `grid` length matches `sz`
5. Validate each space in grid:
   - Has `flags`, `dotx`, `doty`, `nassoc` fields
   - `flags` is an integer
   - `dotx`, `doty`, `nassoc` are integers
   - If `F_TILE_ASSOC` is set, validate `dotx`, `doty` are within bounds
   - If `F_DOT` is set, validate `nassoc >= 0`
6. Create ctypes arrays:
   - `grid_arr = (GalaxiesSpaceRepr * sz)(...)`
7. Build `GalaxiesStateRepr` struct
8. Call C function `galaxies_state_from_repr()`
9. Return state pointer

### Phase 6: Python API Layer - Add Puzzle Method

**File**: `rlp/puzzle.py`

**Location**: In `Puzzle` class, add `load_state_dict()` method (around line 530)

**Update existing method** to handle galaxies:

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
    if self.puzzle_name not in ("bridges", "undead", "galaxies"):
        raise ValueError(f"load_state_dict is only supported for bridges, undead, and galaxies puzzles, not {self.puzzle_name}")
    
    if self._state_from_repr is None:
        raise ValueError("puzzle_state_from_repr function not available")
    
    from rlp import specific_api as specific
    
    # Call the load function
    if self.puzzle_name == "galaxies":
        state_ptr = specific.load_state_dict_galaxies(state_dict, self._lib)
    elif self.puzzle_name == "undead":
        state_ptr = specific.load_state_dict_undead(state_dict, self._lib)
    elif self.puzzle_name == "bridges":
        state_ptr = specific.load_state_dict_bridges(state_dict, self._lib)
    
    return state_ptr
```

### Phase 7: Testing

**File**: `test_load_state_dict_galaxies.py` (new file)

**Test cases**:
1. `test_load_problem_state` - Load initial problem state, verify it matches
2. `test_load_solution_state` - Load solved state, verify `completed=True`
3. `test_round_trip_problem` - Problem state → dict → load → dict → compare
4. `test_round_trip_solution` - Solution state → dict → load → dict → compare
5. `test_multiple_sizes` - Test with different puzzle sizes (5x5, 7x7, 10x10)
6. `test_state_verification` - Verify `check_complete()` results match
7. `test_swap_states_between_instances` - Swap states between two puzzle instances
8. `test_validation_errors` - Test invalid state dicts raise appropriate exceptions
9. `test_dots_reconstruction` - Verify dots array is correctly rebuilt
10. `test_solver_flags_cleared` - Verify solver flags are cleared after loading

**Ignore fields for comparison**:
- `sx`, `sy` (computed from w, h)
- `ndots` (computed from grid)
- `dots_indices` (computed from grid)
- `completed` (computed by check_complete, but should match)
- `used_solve` (UI state)
- `cdiff` (derived)

## Open Questions Requiring Answers

1. **Should `F_DOT_BLACK` be considered canonical?** It's a UI flag but might affect puzzle state representation.

2. **Should we validate that `dots_indices` in the state dict matches the actual dots found in grid?** This could catch inconsistencies.

3. **How should we handle the `dots` array pointer comparison?** The pointers will be different after reconstruction, but the contents should match.

4. **Should `sx`, `sy` be included in the repr for validation purposes, even though they're derived?**

5. **What are the bounds for `dotx`, `doty`?** Should they be validated against `sx`, `sy` or `w`, `h`?

## Implementation Checklist

- [ ] Define C repr structs (`galaxies_space_repr`, `galaxies_state_repr`)
- [ ] Implement C reconstruction function (`galaxies_state_from_repr`)
  - [ ] Create params from repr
  - [ ] Create blank state
  - [ ] Copy grid array (filtering flags)
  - [ ] Rebuild dots array (`game_update_dots`)
  - [ ] Run verification (`check_complete`)
  - [ ] Clear solver flags
- [ ] Define Python ctypes structs (match C exactly)
- [ ] Wire C function in `puzzle.py`
- [ ] Implement Python load function with validation
- [ ] Update `Puzzle.load_state_dict()` method
- [ ] Create comprehensive tests
- [ ] Recompile library (`cmake --build rlp/lib --target libgalaxies`)
- [ ] Run tests and verify all pass

## Files to Modify

1. **puzzles/galaxies.c**:
   - Add repr structs
   - Implement `galaxies_state_from_repr()` function

2. **rlp/specific_api.py**:
   - Add `GalaxiesSpaceRepr` and `GalaxiesStateRepr` ctypes structures
   - Implement `load_state_dict_galaxies()` function

3. **rlp/puzzle.py**:
   - Wire `galaxies_state_from_repr` in `__init__()`
   - Update `load_state_dict()` method to handle galaxies

4. **test_load_state_dict_galaxies.py** (new):
   - Create comprehensive test suite

## Next Steps

1. **Answer clarifying questions** above
2. **Review and approve** this plan
3. **Implement Phase 1-2** (C layer)
4. **Test C layer** with simple test cases
5. **Implement Phase 3-6** (Python layer)
6. **Create and run tests** (Phase 7)
7. **Fix any issues** found during testing
8. **Document** any deviations from the plan

