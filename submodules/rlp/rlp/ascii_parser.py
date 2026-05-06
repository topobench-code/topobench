"""
ASCII parser for bridges, undead, galaxies, pattern, and loopy puzzles.

This module provides functionality to parse ASCII text representations
of puzzle games and convert them to state dictionaries that match
the format defined in rlp.specific_api.get_puzzle_state_<puzzle_name>.
"""

def filter_control_chars(text):
    """
    Filter out control characters from text, keeping only printable characters
    and essential whitespace (newlines, carriage returns, tabs).
    Also removes trailing junk lines that don't match grid patterns.
    """
    text = "".join(c for c in text if c.isprintable() or c in "\n\r\t")

    # For pattern puzzles, find the last valid separator line and truncate after it.
    lines = text.split("\n")

    # Find the last valid separator line (starts with spaces, contains +-- pattern).
    last_valid_index = -1
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        stripped = line.strip()
        if line.startswith(" ") and "+" in line and "--" in line:
            if all(c in "+- " for c in stripped):
                last_valid_index = i
                break

    if last_valid_index >= 0:
        lines = lines[: last_valid_index + 1]

    # Filter individual junk lines.
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped == "":
            cleaned_lines.append(line)
        elif len(stripped) == 1:
            continue
        elif any(c in line for c in ["|", "#", ".", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]):
            cleaned_lines.append(line)
        elif "+" in line:
            if "--" in line:
                if all(c in " +-\n\r\t" for c in stripped):
                    if line.startswith(" ") or len(stripped) >= 15:
                        cleaned_lines.append(line)
                    else:
                        continue
                else:
                    continue
            elif len(stripped) > 5:
                cleaned_lines.append(line)
            else:
                continue
        elif len(stripped) > 3:
            cleaned_lines.append(line)
        else:
            continue

    return "\n".join(cleaned_lines)

# Grid flags matching bridges.c definitions
G_ISLAND = 0x0001
G_LINEV = 0x0002  # contains a vertical line
G_LINEH = 0x0004  # contains a horizontal line

# Cell types matching undead.c enum
CELL_EMPTY = 0
CELL_MIRROR_L = 1
CELL_MIRROR_R = 2
CELL_GHOST = 3
CELL_VAMPIRE = 4
CELL_ZOMBIE = 5

# Flag constants matching galaxies.c definitions
F_DOT = 1
F_EDGE_SET = 2
F_TILE_ASSOC = 4

# Space types matching galaxies.c enum
s_tile = 0
s_edge = 1
s_vertex = 2

# Grid cell values matching pattern.c definitions
GRID_UNKNOWN = 2
GRID_FULL = 1
GRID_EMPTY = 0


def check_bridges_structural_validity(ascii_text: str, problem_ascii: str = None) -> bool:
    """
    Check structural validity of a bridges ASCII state.
    
    Validates:
    1. Lines between islands are contiguous (no breaks)
    2. Island clues haven't been modified (basic sanity check)
    3. If problem_ascii is provided, checks that islands haven't been moved or changed
    
    Args:
        ascii_text: The ASCII representation of the puzzle state (response)
        problem_ascii: Optional ASCII representation of the original problem state
        
    Returns:
        bool: True if structurally valid, False otherwise
    """
    if not ascii_text or not ascii_text.strip():
        return False
    
    # Parse to get dimensions and island positions
    lines = ascii_text.strip().split('\n')
    h = len(lines)
    if h == 0:
        return False
    
    # Find maximum width
    max_w = 0
    for line in lines:
        stripped = line.rstrip()
        w = len(stripped)
        if w > max_w:
            max_w = w
    
    if max_w == 0:
        return False
    
    w = max_w
    
    # Build grid representation and find islands
    grid = [[None for _ in range(w)] for _ in range(h)]
    islands = []
    
    for y, line in enumerate(lines):
        stripped = line.rstrip()
        for x in range(min(len(stripped), w)):
            c = stripped[x]
            grid[y][x] = c
            
            # Record islands
            if (c >= '0' and c <= '9') or (c >= 'A' and c <= 'G'):
                islands.append((x, y, c))
    
    # Check if islands match the problem (if provided)
    if problem_ascii and problem_ascii.strip():
        problem_lines = problem_ascii.strip().split('\n')
        problem_islands = []
        
        for y, line in enumerate(problem_lines):
            stripped = line.rstrip()
            for x in range(len(stripped)):
                c = stripped[x]
                if (c >= '0' and c <= '9') or (c >= 'A' and c <= 'G'):
                    problem_islands.append((x, y, c))
        
        # Convert to sets for comparison (position and value must match)
        problem_island_set = set(problem_islands)
        response_island_set = set(islands)
        
        # All problem islands must exist in response at same positions with same values
        if problem_island_set != response_island_set:
            return False  # Islands were modified, moved, or removed
    
    # Check line continuity: verify all paths between islands are contiguous
    # This is similar to path_has_all_lines in bridges.c
    
    def path_has_all_lines_vertical(x, y1, y2):
        """Check if vertical path between y1 and y2 at column x has all line characters.
        
        Lines can cross, so we accept both vertical (|, ") and horizontal (-, =) line chars.
        """
        if y1 > y2:
            y1, y2 = y2, y1
        start_y = y1 + 1
        end_y = y2 - 1
        for yy in range(start_y, end_y + 1):
            if yy < len(lines) and x < len(lines[yy].rstrip()):
                path_char = grid[yy][x]
                # Accept vertical lines and crossings (horizontal lines)
                if path_char not in ('|', '"', '-', '='):
                    return False
        return True
    
    def path_has_all_lines_horizontal(y, x1, x2):
        """Check if horizontal path between x1 and x2 at row y has all line characters.
        
        Lines can cross, so we accept both horizontal (-, =) and vertical (|, ") line chars.
        """
        if x1 > x2:
            x1, x2 = x2, x1
        start_x = x1 + 1
        end_x = x2 - 1
        for xx in range(start_x, end_x + 1):
            if y < len(lines) and xx < len(lines[y].rstrip()):
                path_char = grid[y][xx]
                # Accept horizontal lines and crossings (vertical lines)
                if path_char not in ('-', '=', '|', '"'):
                    return False
        return True
    
    # Check all vertical line segments
    for y in range(h):
        for x in range(w):
            if x >= len(lines[y].rstrip()):
                continue
                
            c = grid[y][x]
            
            # Check vertical lines
            if c == '|' or c == '"':
                # Find islands above and below
                island_above = None
                island_below = None
                
                # Look above
                for yy in range(y - 1, -1, -1):
                    if yy < len(lines) and x < len(lines[yy].rstrip()):
                        char_above = grid[yy][x]
                        if char_above and ((char_above >= '0' and char_above <= '9') or 
                                          (char_above >= 'A' and char_above <= 'G')):
                            island_above = (x, yy)
                            break
                        # Stop if we hit something that's not a line character (including crossings) or empty
                        if char_above and char_above not in ('|', '"', '-', '=', '.'):
                            return False
                
                # Look below
                for yy in range(y + 1, h):
                    if yy < len(lines) and x < len(lines[yy].rstrip()):
                        char_below = grid[yy][x]
                        if char_below and ((char_below >= '0' and char_below <= '9') or 
                                          (char_below >= 'A' and char_below <= 'G')):
                            island_below = (x, yy)
                            break
                        # Stop if we hit something that's not a line character (including crossings) or empty
                        if char_below and char_below not in ('|', '"', '-', '=', '.'):
                            return False
                
                # If we have islands on both sides, verify path is contiguous
                if island_above and island_below:
                    if not path_has_all_lines_vertical(x, island_above[1], island_below[1]):
                        return False  # Break in vertical line
                
            # Check horizontal lines
            elif c == '-' or c == '=':
                # Find islands left and right
                island_left = None
                island_right = None
                
                # Look left
                for xx in range(x - 1, -1, -1):
                    if y < len(lines) and xx < len(lines[y].rstrip()):
                        char_left = grid[y][xx]
                        if char_left and ((char_left >= '0' and char_left <= '9') or 
                                        (char_left >= 'A' and char_left <= 'G')):
                            island_left = (xx, y)
                            break
                        # Stop if we hit something that's not a line character (including crossings) or empty
                        if char_left and char_left not in ('-', '=', '|', '"', '.'):
                            return False
                
                # Look right
                for xx in range(x + 1, w):
                    if y < len(lines) and xx < len(lines[y].rstrip()):
                        char_right = grid[y][xx]
                        if char_right and ((char_right >= '0' and char_right <= '9') or 
                                         (char_right >= 'A' and char_right <= 'G')):
                            island_right = (xx, y)
                            break
                        # Stop if we hit something that's not a line character (including crossings) or empty
                        if char_right and char_right not in ('-', '=', '|', '"', '.'):
                            return False
                
                # If we have islands on both sides, verify path is contiguous
                if island_left and island_right:
                    if not path_has_all_lines_horizontal(y, island_left[0], island_right[0]):
                        return False  # Break in horizontal line
    
    # Basic sanity check: all islands should have valid clue values
    for x, y, c in islands:
        if c >= '0' and c <= '9':
            count = ord(c) - ord('0')
            if count < 0 or count > 9:
                return False
        elif c >= 'A' and c <= 'G':
            count = (ord(c) - ord('A')) + 10
            if count < 10 or count > 16:
                return False
    
    return True


def parse_ascii_bridges(ascii_text: str) -> dict:
    """
    Parse ASCII text representation of a bridges puzzle and return a state dict.
    
    ASCII Format:
    - Islands: digits '0'-'9' (count 0-9) or letters 'A'-'G' (count 10-16)
    - Vertical bridges: '|' (single), '"' (double)
    - Horizontal bridges: '-' (single), '=' (double)
    - Empty cells: '.'
    
    Args:
        ascii_text: The ASCII representation of the puzzle state
        
    Returns:
        dict: State dictionary matching get_puzzle_state_bridges format
        
    Raises:
        ValueError: If the ASCII text is invalid or empty
    """
    if not ascii_text or not ascii_text.strip():
        raise ValueError("ASCII text cannot be empty")
    
    # First pass: infer dimensions
    lines = ascii_text.strip().split('\n')
    h = len(lines)
    if h == 0:
        raise ValueError("ASCII text must contain at least one line")
    
    # Find maximum width (handle variable line lengths)
    max_w = 0
    for line in lines:
        # Remove trailing whitespace and count non-whitespace characters
        stripped = line.rstrip()
        w = len(stripped)
        if w > max_w:
            max_w = w
    
    if max_w == 0:
        raise ValueError("ASCII text must contain at least one non-whitespace character")
    
    w = max_w
    
    # Initialize arrays
    wh = w * h
    grid = [0] * wh
    lines_array = [0] * wh
    islands = []
    
    # Second pass: parse islands and lines
    for y, line in enumerate(lines):
        stripped = line.rstrip()
        for x in range(w):
            if x >= len(stripped):
                # Line is shorter than max width, treat as empty
                continue
            
            c = stripped[x]
            idx = y * w + x
            
            # Parse island
            if c >= '0' and c <= '9':
                count = ord(c) - ord('0')
                grid[idx] |= G_ISLAND
                lines_array[idx] = 0
                islands.append({"x": x, "y": y, "count": count})
            elif c >= 'A' and c <= 'G':
                count = (ord(c) - ord('A')) + 10
                grid[idx] |= G_ISLAND
                lines_array[idx] = 0
                islands.append({"x": x, "y": y, "count": count})
            # Parse vertical lines
            elif c == '|':
                grid[idx] |= G_LINEV
                lines_array[idx] = 1
            elif c == '"':
                grid[idx] |= G_LINEV
                lines_array[idx] = 2
            # Parse horizontal lines
            elif c == '-':
                grid[idx] |= G_LINEH
                lines_array[idx] = 1
            elif c == '=':
                grid[idx] |= G_LINEH
                lines_array[idx] = 2
            # Empty cell ('.' or whitespace)
            else:
                # Already initialized to 0
                pass
    
    # Build state dict matching get_puzzle_state_bridges format
    state_dict = {
        "w": w,
        "h": h,
        "completed": False,  # Will be computed by C code
        "solved": False,     # Will be computed by C code
        "allowloops": True,   # Always True as specified
        "grid": grid,
        "islands": islands,
        "n_islands": len(islands),
        "n_islands_alloc": len(islands),  # Same as n_islands for parsed states
        "params": {
            "w": w,
            "h": h,
            "maxb": 2,  # Default max bridges
            "allowloops": True,  # Always True as specified
            # Note: islands, expansion, difficulty are generation params,
            # not needed for verification/printing, so we omit them
        },
        # Derived arrays - initialized to zeros, will be computed by C code
        "wha": [0] * wh,
        "possv": [0] * wh,
        "possh": [0] * wh,
        "lines": lines_array,
        "maxv": [0] * wh,
        "maxh": [0] * wh,
    }
    
    return state_dict


def _get_space_type(x: int, y: int) -> int:
    """
    Determine space type from coordinates (matching galaxies.c logic).
    
    Args:
        x: X coordinate
        y: Y coordinate
        
    Returns:
        Space type: s_vertex (2), s_edge (1), or s_tile (0)
    """
    if (x % 2) == 0 and (y % 2) == 0:
        return s_vertex
    elif (x % 2) == 0 or (y % 2) == 0:
        return s_edge
    else:
        return s_tile


def _is_vertical_edge(x: int) -> bool:
    """
    Check if an edge is vertical (matching galaxies.c IS_VERTICAL_EDGE macro).
    
    Args:
        x: X coordinate
        
    Returns:
        True if vertical edge (x % 2 == 0), False if horizontal
    """
    return (x % 2) == 0


def _manhattan_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """
    Calculate Manhattan distance between two points.
    
    Args:
        x1, y1: First point coordinates
        x2, y2: Second point coordinates
        
    Returns:
        Manhattan distance
    """
    return abs(x1 - x2) + abs(y1 - y2)


def grid2range(x: int, y: int, w: int, h: int) -> int:
    """
    Determine if a grid cell is an edge clue cell.
    
    Ported from puzzles/undead.c grid2range() function.
    
    Args:
        x: Column index (0-based, in grid coordinates including border)
        y: Row index (0-based, in grid coordinates including border)
        w: Puzzle width (interior width, not including border)
        h: Puzzle height (interior height, not including border)
        
    Returns:
        Range index for edge clue cells, -1 for interior cells or corners
    """
    # Interior cells (not on border)
    if x > 0 and x < w + 1 and y > 0 and y < h + 1:
        return -1
    
    # Out of bounds
    if x < 0 or x > w + 1 or y < 0 or y > h + 1:
        return -1
    
    # Corner cells (not valid edge clues)
    if (x == 0 or x == w + 1) and (y == 0 or y == h + 1):
        return -1
    
    # Top edge (y == 0)
    if y == 0:
        return x - 1
    
    # Right edge (x == w + 1)
    if x == (w + 1):
        return y - 1 + w
    
    # Bottom edge (y == h + 1)
    if y == (h + 1):
        return 2 * w + h - x
    
    # Left edge (x == 0)
    return 2 * (w + h) - y


def check_undead_structural_validity(ascii_text: str) -> bool:
    """
    Check structural validity of an undead ASCII state.
    
    Validates:
    1. Has monster count header line (G: X V: Y Z: Z format)
    2. Has a grid present (at least 3x3 including border)
    3. Grid has proper structure (2-character cells)
    4. Not just empty text or invalid format
    
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
    
    # Check for monster count header line (first line should have "G: X V: Y Z: Z" format)
    first_line = lines[0].strip()
    if not first_line:
        return False
    
    # Check if first line looks like monster counts
    # Should contain "G:", "V:", "Z:" patterns
    has_g = 'G:' in first_line
    has_v = 'V:' in first_line
    has_z = 'Z:' in first_line
    
    if not (has_g or has_v or has_z):
        # Doesn't look like a valid undead puzzle header
        return False
    
    # Try to parse the counts to verify format
    try:
        parts = first_line.split()
        found_counts = False
        for i in range(len(parts)):
            if parts[i] in ('G:', 'V:', 'Z:') and i + 1 < len(parts):
                try:
                    int(parts[i + 1])
                    found_counts = True
                except ValueError:
                    pass
        if not found_counts:
            return False
    except Exception:
        # If parsing fails, it's not a valid header
        return False
    
    # Find grid start (skip header line and optional blank line)
    grid_start = 1
    if len(lines) > 1 and lines[1].strip() == '':
        grid_start = 2
    
    # Check if we have enough lines for a grid (at least 3 rows including border)
    grid_lines = lines[grid_start:]
    if len(grid_lines) < 3:
        return False
    
    # Check if grid lines have proper structure (2-character cells)
    # Each line should have even length (multiple of 2) or be empty
    has_valid_grid = False
    for line in grid_lines:
        stripped = line.rstrip()
        if len(stripped) == 0:
            continue  # Empty lines are okay
        # Should have even length (2-character cells)
        if len(stripped) % 2 != 0:
            # Odd length - might be invalid, but be lenient
            pass
        # Should have at least 6 characters (3 cells = 6 chars minimum for border)
        if len(stripped) >= 6:
            has_valid_grid = True
    
    if not has_valid_grid:
        return False
    
    # Check if grid has reasonable dimensions
    # Find maximum width in 2-character cell units
    max_cells = 0
    for line in grid_lines:
        stripped = line.rstrip()
        num_cells = len(stripped) // 2
        if num_cells > max_cells:
            max_cells = num_cells
    
    # Grid should have at least 3 columns (including border)
    if max_cells < 3:
        return False
    
    # Grid should have at least 3 rows (including border)
    if len(grid_lines) < 3:
        return False
    
    # Check if it looks like a long text (too many lines without proper structure)
    # If there are many lines but most don't have the expected 2-character cell structure,
    # it might be invalid text
    if len(lines) > 50:
        # Too many lines - might be invalid text
        # Check if most lines don't match expected pattern
        invalid_lines = 0
        for line in grid_lines:
            stripped = line.rstrip()
            if len(stripped) > 0:
                # Check if line has mostly spaces or doesn't match expected pattern
                # Expected: 2-character cells, so should have even length
                if len(stripped) % 2 != 0 and len(stripped) > 10:
                    invalid_lines += 1
        
        # If more than half the lines are invalid, probably not a valid puzzle
        if invalid_lines > len(grid_lines) / 2:
            return False
    
    return True


def check_galaxies_structural_validity(ascii_text: str, problem_ascii: str = None) -> bool:
    """
    Check structural validity of a galaxies ASCII state.
    
    Validates:
    1. Has valid grid dimensions (sx = 2*w+1, sy = 2*h+1)
    2. Contains valid characters for galaxies puzzle
    3. If problem_ascii is provided, checks that dots haven't been moved or removed
    
    Args:
        ascii_text: The ASCII representation of the puzzle state (response)
        problem_ascii: Optional ASCII representation of the original problem state
        
    Returns:
        bool: True if structurally valid, False otherwise
    """
    if not ascii_text or not ascii_text.strip():
        return False
    
    lines = ascii_text.strip().split('\n')
    if len(lines) == 0:
        return False
    
    # Infer dimensions
    sy = len(lines)
    
    max_sx = 0
    for line in lines:
        stripped = line.rstrip()
        sx_line = len(stripped)
        if sx_line > max_sx:
            max_sx = sx_line
    
    if max_sx == 0:
        return False
    
    sx = max_sx
    
    # Check dimensions are valid for galaxies (sx = 2*w + 1, sy = 2*h + 1)
    if (sx - 1) % 2 != 0:
        return False  # sx must be odd
    if (sy - 1) % 2 != 0:
        return False  # sy must be odd
    
    w = (sx - 1) // 2
    h = (sy - 1) // 2
    
    if w < 1 or h < 1:
        return False
    
    # Extract dots from response
    response_dots = set()
    for y, line in enumerate(lines):
        stripped = line.rstrip()
        for x in range(len(stripped)):
            c = stripped[x]
            if c == 'o':
                response_dots.add((x, y))
    
    # Check if dots match the problem (if provided)
    if problem_ascii and problem_ascii.strip():
        problem_lines = problem_ascii.strip().split('\n')
        problem_dots = set()
        
        for y, line in enumerate(problem_lines):
            stripped = line.rstrip()
            for x in range(len(stripped)):
                c = stripped[x]
                if c == 'o':
                    problem_dots.add((x, y))
        
        # All problem dots must exist in response at same positions
        if problem_dots != response_dots:
            return False  # Dots were modified, moved, or removed
    
    return True


def parse_ascii_undead(ascii_text: str) -> dict:
    """
    Parse ASCII text representation of an undead puzzle and return a state dict.
    
    ASCII Format:
    - First line: "G: %d V: %d Z: %d\n\n" (monster counts)
    - Grid is (w+2) x (h+2) with 2-character cells:
      - Edge clues: 2-digit numbers (e.g., " 2", "10")
      - Mirror left: " \\" (space + backslash)
      - Mirror right: " /" (space + forward slash)
      - Ghost: " G" (space + G)
      - Vampire: " V" (space + V)
      - Zombie: " Z" (space + Z)
      - Empty: " ." (space + dot)
      - Other: "  " (two spaces)
    
    Args:
        ascii_text: The ASCII representation of the puzzle state
        
    Returns:
        dict: State dictionary matching get_puzzle_state_undead format
        
    Raises:
        ValueError: If the ASCII text is invalid or empty
    """
    if not ascii_text or not ascii_text.strip():
        raise ValueError("ASCII text cannot be empty")
    
    lines = ascii_text.strip().split('\n')
    if len(lines) == 0:
        raise ValueError("ASCII text must contain at least one line")
    
    # Parse first line: "G: %d V: %d Z: %d"
    first_line = lines[0].strip()
    num_ghosts = 0
    num_vampires = 0
    num_zombies = 0
    
    try:
        # Parse "G: %d V: %d Z: %d" format
        parts = first_line.split()
        for i in range(len(parts)):
            if parts[i] == 'G:' and i + 1 < len(parts):
                num_ghosts = int(parts[i + 1])
            elif parts[i] == 'V:' and i + 1 < len(parts):
                num_vampires = int(parts[i + 1])
            elif parts[i] == 'Z:' and i + 1 < len(parts):
                num_zombies = int(parts[i + 1])
    except (ValueError, IndexError):
        # If parsing fails, try to continue with defaults
        # The counts might be inferred from the grid
        pass
    
    # Find grid start (skip header line and blank line)
    grid_start = 1
    if len(lines) > 1 and lines[1].strip() == '':
        grid_start = 2
    
    # Infer dimensions from grid
    # Grid is (w+2) x (h+2), so we need at least 3 lines and 3 columns
    grid_lines = lines[grid_start:]
    if len(grid_lines) < 3:
        raise ValueError("Grid must have at least 3 rows (including border)")
    
    # Each line should have 2-character cells
    # Find maximum width (in 2-character cell units)
    max_cells = 0
    for line in grid_lines:
        stripped = line.rstrip()
        # Each cell is 2 characters
        num_cells = len(stripped) // 2
        if len(stripped) % 2 != 0:
            # Handle odd-length lines (shouldn't happen, but be lenient)
            num_cells = (len(stripped) + 1) // 2
        if num_cells > max_cells:
            max_cells = num_cells
    
    if max_cells < 3:
        raise ValueError("Grid must have at least 3 columns (including border)")
    
    # Grid dimensions including border: (w+2) x (h+2)
    grid_w = max_cells
    grid_h = len(grid_lines)
    
    # Interior dimensions: w x h
    w = grid_w - 2
    h = grid_h - 2
    
    if w < 1 or h < 1:
        raise ValueError(f"Invalid grid dimensions: inferred w={w}, h={h} from grid size {grid_w}x{grid_h}")
    
    # Initialize arrays
    wh = grid_w * grid_h  # (w+2) * (h+2)
    grid = [0] * wh
    xinfo = [-1] * wh
    guess = []
    fixed = []
    
    # Track monster index counter
    monster_idx = 0
    
    # Parse grid cell-by-cell
    for y, line in enumerate(grid_lines):
        stripped = line.rstrip()
        # Each cell is 2 characters
        for x in range(grid_w):
            # Extract 2-character cell
            start_pos = x * 2
            if start_pos + 2 > len(stripped):
                # Line is shorter, treat as empty/other
                cell_str = "  "
            else:
                cell_str = stripped[start_pos:start_pos + 2]
            
            idx = y * grid_w + x
            
            # Check if this is an edge clue cell
            r = grid2range(x, y, w, h)
            
            if r != -1:
                # Edge clue cell - should contain a 2-digit number
                try:
                    clue_val = int(cell_str.strip())
                    grid[idx] = clue_val
                    xinfo[idx] = -2  # Clue marker (from C code)
                except ValueError:
                    # Not a valid clue, might be empty or invalid
                    grid[idx] = 0
                    xinfo[idx] = -2
            elif cell_str == " \\":
                # Mirror left
                grid[idx] = CELL_MIRROR_L
                xinfo[idx] = -1
            elif cell_str == " /":
                # Mirror right
                grid[idx] = CELL_MIRROR_R
                xinfo[idx] = -1
            elif cell_str == " G":
                # Ghost
                grid[idx] = CELL_GHOST
                xinfo[idx] = monster_idx
                guess.append(1)  # 1 = Ghost
                fixed.append(True)
                monster_idx += 1
            elif cell_str == " V":
                # Vampire
                grid[idx] = CELL_VAMPIRE
                xinfo[idx] = monster_idx
                guess.append(2)  # 2 = Vampire
                fixed.append(True)
                monster_idx += 1
            elif cell_str == " Z":
                # Zombie
                grid[idx] = CELL_ZOMBIE
                xinfo[idx] = monster_idx
                guess.append(4)  # 4 = Zombie
                fixed.append(True)
                monster_idx += 1
            elif cell_str == " .":
                # Empty monster cell (monster cell with unknown/empty assignment)
                # This means xi >= 0 but guess[xi] is not 1, 2, or 4
                grid[idx] = CELL_EMPTY
                xinfo[idx] = monster_idx
                guess.append(7)  # 7 = empty/unknown
                fixed.append(False)
                monster_idx += 1
            else:
                # Other (two spaces) - not a monster cell (xi < 0)
                # This is for cells that are not part of the puzzle interior
                grid[idx] = CELL_EMPTY
                xinfo[idx] = -1
    
    num_total = monster_idx
    
    # If monster counts weren't parsed from header, try to infer from grid
    if num_ghosts == 0 and num_vampires == 0 and num_zombies == 0:
        # Count monsters in guess array
        num_ghosts = sum(1 for g in guess if g == 1)
        num_vampires = sum(1 for g in guess if g == 2)
        num_zombies = sum(1 for g in guess if g == 4)
    
    # Build state dict matching get_puzzle_state_undead format
    state_dict = {
        "common": {
            "params": {
                "w": w,
                "h": h,
                "diff": 1,  # Default to DIFF_NORMAL (1)
            },
            "grid": grid,
            "xinfo": xinfo,
            "fixed": fixed,
            "num_ghosts": num_ghosts,
            "num_vampires": num_vampires,
            "num_zombies": num_zombies,
            "num_total": num_total,
            # Derived fields - initialized to defaults
            "wh": wh,
            "num_paths": 0,  # Will be computed by C code
            "paths": [],  # Will be computed by C code
        },
        "guess": guess,
        # Other fields - initialized to zeros/False
        "pencils": [0] * num_total if num_total > 0 else [],
        "cell_errors": [False] * wh,
        "hint_errors": [],  # Will be computed by C code
        "hints_done": [],  # Will be computed by C code
        "count_errors": [False, False, False],
        "solved": False,  # Will be computed by C code
        "cheated": False,
    }
    
    return state_dict


def parse_ascii_galaxies(ascii_text: str) -> dict:
    """
    Parse ASCII text representation of a galaxies puzzle and return a state dict.
    
    ASCII Format:
    - Grid dimensions: sx = 2*w+1 columns, sy = 2*h+1 rows
    - Characters:
      - 'o' = dot (F_DOT flag set)
      - 'B' or 'W' = tile with F_TILE_ASSOC (associated with a dot)
      - '?' = tile with F_TILE_ASSOC but invalid association
      - ' ' = empty tile (no flags) or edge without F_EDGE_SET
      - '+' = vertex (s_vertex type)
      - '|' = vertical edge with F_EDGE_SET (x % 2 == 0)
      - '-' = horizontal edge with F_EDGE_SET (x % 2 != 0)
    
    Args:
        ascii_text: The ASCII representation of the puzzle state
        
    Returns:
        dict: State dictionary matching get_puzzle_state_galaxies format
        
    Raises:
        ValueError: If the ASCII text is invalid or empty
    """
    if not ascii_text or not ascii_text.strip():
        raise ValueError("ASCII text cannot be empty")
    
    # Phase 1: Dimension Inference
    lines = ascii_text.strip().split('\n')
    if len(lines) == 0:
        raise ValueError("ASCII text must contain at least one line")
    
    # Infer sy from number of lines
    sy = len(lines)
    
    # Infer sx from maximum line length
    max_sx = 0
    for line in lines:
        stripped = line.rstrip()
        sx_line = len(stripped)
        if sx_line > max_sx:
            max_sx = sx_line
    
    if max_sx == 0:
        raise ValueError("ASCII text must contain at least one non-whitespace character")
    
    sx = max_sx
    
    # Compute w and h from sx and sy
    # sx = 2*w + 1, so w = (sx - 1) // 2
    # sy = 2*h + 1, so h = (sy - 1) // 2
    if (sx - 1) % 2 != 0:
        raise ValueError(f"Invalid grid width: sx={sx} must be odd (sx = 2*w + 1)")
    if (sy - 1) % 2 != 0:
        raise ValueError(f"Invalid grid height: sy={sy} must be odd (sy = 2*h + 1)")
    
    w = (sx - 1) // 2
    h = (sy - 1) // 2
    
    if w < 1 or h < 1:
        raise ValueError(f"Invalid dimensions: w={w}, h={h} (must be >= 1)")
    
    # Validate dimensions match expected relationship
    expected_sx = 2 * w + 1
    expected_sy = 2 * h + 1
    if sx != expected_sx or sy != expected_sy:
        raise ValueError(f"Dimension mismatch: sx={sx}, sy={sy} but expected sx={expected_sx}, sy={expected_sy} for w={w}, h={h}")
    
    # Phase 2: First Pass - Collect Dots
    dots = []
    for y, line in enumerate(lines):
        stripped = line.rstrip()
        for x in range(min(len(stripped), sx)):
            c = stripped[x]
            if c == 'o':
                dots.append((x, y))
    
    # Phase 3: Second Pass - Parse Grid
    sz = sx * sy
    grid = []
    dots_indices = []
    
    for y in range(sy):
        line = lines[y] if y < len(lines) else ""
        stripped = line.rstrip()
        
        for x in range(sx):
            # Get character at this position
            if x < len(stripped):
                c = stripped[x]
            else:
                c = ' '  # Beyond line length, treat as empty
            
            # Determine space type from coordinates
            space_type = _get_space_type(x, y)
            
            # Initialize space dict
            flags = 0
            dotx = -1
            doty = -1
            nassoc = 0
            
            # Parse character based on space type and character
            if c == 'o':
                # Dot
                flags |= F_DOT
                nassoc = 0  # Will be computed by C code
                idx = y * sx + x
                dots_indices.append(idx)
            elif c in ('B', 'W'):
                # Tile with association (ignore B/W distinction, treat as F_TILE_ASSOC)
                if space_type != s_tile:
                    # Best-effort: if not a tile, still try to set flag
                    # Let C code validate
                    pass
                flags |= F_TILE_ASSOC
                # Find nearest dot
                if dots:
                    nearest_dot = min(dots, key=lambda d: _manhattan_distance(x, y, d[0], d[1]))
                    dotx, doty = nearest_dot
                else:
                    # No dots found, set to -1 and let C validate
                    dotx = -1
                    doty = -1
            elif c == '?':
                # Tile with invalid association
                flags |= F_TILE_ASSOC
                dotx = -1
                doty = -1
            elif c == '+':
                # Vertex
                if space_type != s_vertex:
                    # Best-effort: if character says vertex but coordinates don't match,
                    # still record it and let C code validate
                    pass
                # No flags for vertices
            elif c == '|':
                # Vertical edge with F_EDGE_SET
                # Must be at an edge position with x % 2 == 0 and y % 2 != 0
                if space_type != s_edge:
                    # Not an edge position - skip setting F_EDGE_SET to avoid assertion failure
                    pass
                elif not _is_vertical_edge(x):
                    # Character says vertical but x coordinate suggests horizontal
                    # Skip setting F_EDGE_SET to avoid assertion failure
                    pass
                elif (y % 2) == 0:
                    # y % 2 == 0 means this is a vertex, not a valid edge position
                    # Skip setting F_EDGE_SET to avoid assertion failure
                    pass
                else:
                    # Valid vertical edge position: x % 2 == 0, y % 2 != 0
                    flags |= F_EDGE_SET
            elif c == '-':
                # Horizontal edge with F_EDGE_SET
                # Must be at an edge position with x % 2 != 0 and y % 2 == 0
                if space_type != s_edge:
                    # Not an edge position - skip setting F_EDGE_SET to avoid assertion failure
                    pass
                elif _is_vertical_edge(x):
                    # Character says horizontal but x coordinate suggests vertical
                    # Skip setting F_EDGE_SET to avoid assertion failure
                    pass
                elif (y % 2) != 0:
                    # y % 2 != 0 means this is not a horizontal edge position
                    # Skip setting F_EDGE_SET to avoid assertion failure
                    pass
                else:
                    # Valid horizontal edge position: x % 2 != 0, y % 2 == 0
                    flags |= F_EDGE_SET
            elif c == ' ':
                # Empty (no flags)
                pass
            else:
                # Invalid character - best-effort: treat as empty
                # Could raise error, but following best-effort approach
                pass
            
            # Build space dict
            space_dict = {
                "x": x,
                "y": y,
                "type": space_type,
                "flags": flags,
                "dotx": dotx,
                "doty": doty,
                "nassoc": nassoc,
            }
            grid.append(space_dict)
    
    # Phase 4: Build State Dict
    state_dict = {
        "w": w,
        "h": h,
        "sx": sx,
        "sy": sy,
        "grid": grid,
        "completed": False,  # Will be computed by C code
        "used_solve": False,
        "ndots": len(dots_indices),
        "dots_indices": dots_indices,
        "cdiff": -1,
    }
    
    return state_dict


def parse_ascii_pattern(ascii_text: str) -> dict:
    """
    Parse ASCII text representation of a pattern puzzle and return a state dict.
    
    ASCII Format:
    - Column clues at the top (right-aligned in columns)
    - Row clues on the left (space-separated)
    - Grid cells: '#' (GRID_FULL=1), '.' (GRID_EMPTY=0), ' ' (GRID_UNKNOWN=2)
    - Grid structure: '+' at intersections, '-' for horizontal lines, '|' for vertical lines
    - Cell width (cw) is at least 3, cell height (ch) is 2
    
    Args:
        ascii_text: The ASCII representation of the puzzle state
        
    Returns:
        dict: State dictionary matching get_puzzle_state_pattern format
        
    Raises:
        ValueError: If the ASCII text is invalid or empty
    """
    if not ascii_text or not ascii_text.strip():
        raise ValueError("ASCII text cannot be empty")
    
    # Clean the ASCII text first - remove control characters and trailing junk
    # This handles cases where the input has trailing characters like "+--+--+" or control chars
    # filter_control_chars now preserves clue lines (lines with digits before the grid)
    ascii_text = filter_control_chars(ascii_text)
    
    # Preserve leading whitespace - only strip trailing newlines
    # This is important for column clue alignment
    lines = ascii_text.rstrip().split('\n')
    if len(lines) == 0:
        raise ValueError("ASCII text must contain at least one line")
    
    # Find maximum line length
    max_line_len = max(len(line.rstrip()) for line in lines) if lines else 0
    if max_line_len == 0:
        raise ValueError("ASCII text must contain at least one non-whitespace character")
    
    # Phase 1: Find grid structure and infer dimensions
    # Look for grid pattern: lines with '+' characters indicate grid intersections
    # Grid rows alternate between border lines (with '+') and cell rows (with '|')
    
    # Find first grid border line (contains '+' and '-')
    grid_start_row = None
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if '+' in stripped and '-' in stripped:
            grid_start_row = i
            break
    
    if grid_start_row is None:
        raise ValueError("Could not find grid structure (no '+' characters found)")
    
    # Find left_gap: look at row clue area (rows with '|' that have numbers before '|')
    left_gap = 0
    for i in range(grid_start_row, len(lines)):
        line = lines[i].rstrip()
        if '|' in line:
            # Find position of first '|'
            pipe_pos = line.find('|')
            if pipe_pos > 0:
                # Check if there are numbers before the '|'
                before_pipe = line[:pipe_pos].strip()
                if before_pipe and any(c.isdigit() for c in before_pipe):
                    left_gap = max(left_gap, pipe_pos)
    
    # Find top_gap: count rows before grid_start_row that contain numbers
    # These are column clue rows
    top_gap = 0
    for i in range(grid_start_row):
        line = lines[i].rstrip()
        if line and any(c.isdigit() for c in line):
            top_gap = max(top_gap, i + 1)
    
    # Infer cell width (cw) from grid structure
    # Look at a border line: "+--+--+..." pattern
    # Count '-' characters between '+' to determine cw
    cw = 3  # Default minimum
    if grid_start_row < len(lines):
        border_line = lines[grid_start_row].rstrip()
        plus_positions = [i for i, c in enumerate(border_line) if c == '+']
        if len(plus_positions) >= 2:
            # Distance between first two '+' positions gives us cw
            if plus_positions[1] - plus_positions[0] > 0:
                cw = plus_positions[1] - plus_positions[0]
    
    ch = 2  # Cell height is always 2
    
    # Infer grid dimensions from structure
    # Count '+' characters in a border line to get w+1 (w columns + 1 extra)
    if grid_start_row < len(lines):
        border_line = lines[grid_start_row].rstrip()
        plus_count = border_line.count('+')
        if plus_count < 2:
            raise ValueError("Invalid grid structure: not enough '+' characters")
        w = plus_count - 1
    else:
        raise ValueError("Invalid grid structure: grid start row not found")
    
    # Count grid rows: look for alternating pattern of border lines and cell rows
    # Each grid row takes 2 lines (ch=2): one border line, one cell row
    h = 0
    i = grid_start_row
    while i < len(lines):
        line = lines[i].rstrip()
        if '+' in line and '-' in line:
            # This is a border line
            i += 1
            if i < len(lines) and '|' in lines[i].rstrip():
                # This is a cell row
                h += 1
                i += 1
            else:
                break
        else:
            break
    
    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid grid dimensions: w={w}, h={h}")
    
    # Calculate derived dimensions
    rowsize = max(w, h)
    wh = w * h
    wph = w + h
    lw = w * cw + 2 + left_gap  # Line width
    topleft = lw * top_gap + left_gap  # Top-left position of grid
    
    # Phase 2: Parse column clues (first w entries in rowlen/rowdata)
    # rowdata should be a flat list of clue values (not padded)
    # The padding to rowsize happens in load_state_dict_pattern
    rowdata = []
    rowlen = [0] * wph
    
    # Parse column clues from top section (first top_gap rows)
    # Column clues can be in a single row (space-separated) or multiple rows (one per row)
    # They are right-aligned in their columns
    
    # Check if we have multiple rows with clues (complex case)
    # If any row before the grid has numbers, we need to parse column-by-column
    has_multiple_clue_rows = False
    clue_row_count = 0
    for row in range(top_gap):
        if row >= len(lines):
            break
        line = lines[row]
        if any(c.isdigit() for c in line):
            clue_row_count += 1
    
    # If we have multiple rows with digits, use column-by-column parsing
    # Otherwise, try single-row parsing
    if clue_row_count > 1:
        has_multiple_clue_rows = True
    
    if not has_multiple_clue_rows:
        # Simple case: all clues likely in one row
        # Look for a row with multiple space-separated numbers
        single_row_clues = None
        for row in range(top_gap):
            if row >= len(lines):
                break
            line = lines[row].rstrip()
            # Check if this row has multiple numbers (likely all column clues)
            parts = line.split()
            numbers = [p for p in parts if p.isdigit()]
            if len(numbers) == w:
                # Found a row with exactly w numbers - these are the column clues
                single_row_clues = [int(n) for n in numbers]
                break
        
        if single_row_clues:
            # Simple case: all column clues in one row
            for col in range(w):
                rowlen[col] = 1
                rowdata.append(single_row_clues[col])
        else:
            # Fall through to column-by-column parsing
            has_multiple_clue_rows = True
    
    if has_multiple_clue_rows:
        # Complex case: clues in multiple rows, one per column
        # Parse each column separately
        # Column clues are RIGHT-ALIGNED in their columns
        
        # First pass: collect all numbers from clue rows with their positions
        all_numbers = []  # List of (row, num_start, num_end, number, num_right_edge)
        for row in range(top_gap):
            if row >= len(lines):
                break
            line = lines[row]  # Don't strip - preserve leading whitespace for alignment!
            
            # Find all numbers in this line
            i = 0
            while i < len(line):
                if line[i].isdigit():
                    # Found start of a number
                    num_start = i
                    num_end = i + 1
                    while num_end < len(line) and line[num_end].isdigit():
                        num_end += 1
                    num_str = line[num_start:num_end].strip()
                    if num_str.isdigit():
                        num_right_edge = num_end - 1  # Right edge of the number
                        all_numbers.append((row, num_start, num_end, int(num_str), num_right_edge))
                    i = num_end
                else:
                    i += 1
        
        # Second pass: assign each number to the column it's closest to
        # Each number goes to exactly one column (the one with the closest right edge)
        column_clues = [[] for _ in range(w)]  # List of (row, number) tuples for each column
        
        for row, num_start, num_end, number, num_right_edge in all_numbers:
            # Find the column with the closest right edge
            best_col = None
            best_distance = float('inf')
            
            for col in range(w):
                col_right_edge = left_gap + (col + 1) * cw
                distance = abs(num_right_edge - col_right_edge)
                if distance < best_distance:
                    best_distance = distance
                    best_col = col
            
            # Only assign if within reasonable tolerance (2 characters)
            if best_col is not None and best_distance <= 2:
                column_clues[best_col].append((row, number))
        
        # Third pass: build rowdata and rowlen
        for col in range(w):
            # Sort clues by row (top to bottom in ASCII)
            # The C code writes clues from bottom to top, so top row = first clue in rowdata
            column_clues[col].sort(key=lambda x: x[0])
            # Extract just the numbers in order (top to bottom = first to last in rowdata)
            clue_values = [num for _, num in column_clues[col]]
            # Don't reverse - top row is first clue in rowdata
            
            rowlen[col] = len(clue_values)
            rowdata.extend(clue_values)
    
    # Phase 3: Parse row clues (next h entries in rowlen/rowdata)
    # Row clues are on the left, space-separated
    for row in range(h):
        # Find the cell row (alternates with border rows)
        cell_row_idx = grid_start_row + 1 + row * 2  # Skip border row, then cell row
        if cell_row_idx >= len(lines):
            break
        
        line = lines[cell_row_idx].rstrip()
        if '|' not in line:
            break
        
        # Extract text before first '|'
        pipe_pos = line.find('|')
        if pipe_pos > 0:
            clue_text = line[:pipe_pos].strip()
            # Parse space-separated numbers
            clues = []
            if clue_text:
                parts = clue_text.split()
                for part in parts:
                    if part.isdigit():
                        clues.append(int(part))
            
            rowlen[w + row] = len(clues)
            rowdata.extend(clues)
    
    # Phase 4: Parse grid cells
    grid = [GRID_UNKNOWN] * wh  # Default to unknown
    
    for col in range(w):
        for row in range(h):
            # Find cell row (alternates with border rows)
            cell_row_idx = grid_start_row + 1 + row * 2
            if cell_row_idx >= len(lines):
                continue
            
            line = lines[cell_row_idx].rstrip()
            if '|' not in line:
                continue
            
            # Find cell position: after left_gap, then col*cw positions
            # Cell content is in the center of each cell
            cell_start = left_gap + 1 + col * cw  # After '|', then col*cw
            cell_center = cell_start + cw // 2
            
            if cell_center < len(line):
                cell_char = line[cell_center]
                # Note: grid is stored in column-major order: grid[col * w + row]
                # This matches game_text_format which uses grid[i*w+j] where i is column, j is row
                # Validation in pattern_state_from_repr transposes the grid before checking
                idx = col * w + row
                
                if cell_char == '#':
                    grid[idx] = GRID_FULL
                elif cell_char == '.':
                    grid[idx] = GRID_EMPTY
                # else: already GRID_UNKNOWN
    
    # Phase 5: Build state dict
    state_dict = {
        "common": {
            "w": w,
            "h": h,
            "rowsize": rowsize,
            "rowdata": rowdata,
            "rowlen": rowlen,
            "immutable": [False] * wh,  # All False for ASCII parsing
        },
        "grid": grid,
        "completed": False,  # Will be computed by C code
        "cheated": False,    # Will be computed by C code
    }
    
    return state_dict


# Cache for edge-to-canvas mappings (only for square grids, grid_type == 0)
# Key: (w, h), Value: (edge_to_canvas dict, face_to_canvas dict, num_faces, num_edges)
_loopy_square_grid_cache = {}

def parse_ascii_loopy(ascii_text: str, grid_type: int = 0, puzzle_instance=None) -> dict:
    """
    Parse ASCII text representation of a loopy puzzle and return a state dict.
    
    ASCII Format:
    - Canvas dimensions: W = 2*w + 2, H = 2*h + 1
    - Edges: Placed at midpoints (x = x1 + x2, y = y1 + y2 in canvas coords)
      - '-' = horizontal LINE_YES (when y1 == y2)
      - '|' = vertical LINE_YES (when y1 != y2)
      - 'x' = LINE_NO
      - ' ' (space) = LINE_UNKNOWN
    - Clues: Placed at face centers using CLUE2CHAR
      - ' ' (space) = -1 (no clue)
      - '0'-'9' = 0-9
      - 'A'-'Z' = 10-35
    
    Args:
        ascii_text: The ASCII representation of the puzzle state
        grid_type: Grid type (default 0 for square grids)
        puzzle_instance: Optional existing Puzzle instance to reuse for grid structure
                        (avoids creating temporary puzzle instances)
        
    Returns:
        dict: State dictionary matching load_state_dict_loopy format
        
    Raises:
        ValueError: If the ASCII text is invalid or empty
    """
    if not ascii_text or not ascii_text.strip():
        raise ValueError("ASCII text cannot be empty")
    
    # Phase 1: Dimension Inference
    # The format has newlines at the end of each line
    # When split by '\n', we get lines without the newline character
    # Handle case where text may or may not have trailing newline
    if ascii_text.endswith('\n'):
        lines = ascii_text[:-1].split('\n')
    else:
        lines = ascii_text.split('\n')
    
    if len(lines) == 0:
        raise ValueError("ASCII text must contain at least one line")
    
    # Filter out completely blank lines for dimension inference
    # (Some formats may have blank lines between content lines)
    # But keep original lines array for parsing (to preserve line indices)
    content_lines = [line for line in lines if line.strip() or len(line) > 0]
    
    # Use content lines for dimension inference, but keep original lines for parsing
    # Infer H from number of content lines (non-blank)
    H = len(content_lines) if len(content_lines) > 0 else len(lines)
    
    # Infer W from maximum line length
    # Each line in the canvas has W-1 content chars + 1 newline = W total
    # After splitting, we have W-1 chars per line, so W = max_line_length + 1
    max_W_content = 0
    for line in lines:
        # Include trailing spaces in line length
        W_line = len(line)
        if W_line > max_W_content:
            max_W_content = W_line
    
    if max_W_content == 0:
        raise ValueError("ASCII text must contain at least one non-whitespace character")
    
    # W is the canvas width: W = max_line_length + 1 (to account for newline)
    W = max_W_content + 1
    
    # Handle case where last line might be missing (common in user-provided examples)
    # H must be odd (H = 2*h + 1), so if H is even, we might be missing the last empty line
    if (H - 1) % 2 != 0:
        # H is even, which is invalid. Try adding 1 (assuming missing last line)
        H += 1
    
    # EARLY VALIDATION: Check dimensions BEFORE any parsing or C code execution
    # This prevents segfaults from invalid data reaching the C layer
    if (W - 2) % 2 != 0:
        raise ValueError(f"Invalid canvas width: W={W} must satisfy W = 2*w + 2 (W-2 must be even)")
    if (H - 1) % 2 != 0:
        raise ValueError(f"Invalid canvas height: H={H} must satisfy H = 2*h + 1 (H-1 must be even, got H={H})")
    
    w = (W - 2) // 2
    h = (H - 1) // 2
    
    if w < 1 or h < 1:
        raise ValueError(f"Invalid dimensions: w={w}, h={h} (must be >= 1)")
    
    # Validate dimensions match expected relationship
    expected_W = 2 * w + 2
    expected_H = 2 * h + 1
    if W != expected_W or H != expected_H:
        raise ValueError(f"Dimension mismatch: W={W}, H={H} but expected W={expected_W}, H={expected_H} for w={w}, h={h}")
    
    # Dimensions are now validated - safe to proceed with parsing
    
    # Phase 2: Get coordinate mappings (use cache for square grids)
    # For square grids (grid_type == 0), we cache the edge-to-canvas mapping
    # since edge ordering is determined by the C grid structure, not easily computed
    cache_key = (w, h)
    
    if grid_type == 0 and cache_key in _loopy_square_grid_cache:
        # Use cached mappings
        edge_to_canvas, face_to_canvas, num_faces, num_edges = _loopy_square_grid_cache[cache_key]
    else:
        # Build mappings - for square grids, create a temporary puzzle once to get the structure
        # This is cached so we only do it once per (w, h) combination
        if grid_type != 0:
            raise ValueError(f"Only square grids (grid_type=0) are supported, got grid_type={grid_type}")
        
        # Try to reuse provided puzzle instance if it matches dimensions
        puzzle_to_use = None
        create_temp = True
        
        if puzzle_instance is not None:
            try:
                # Check if puzzle_instance matches the dimensions we need
                # Extract w, h from puzzle_instance's arg
                if hasattr(puzzle_instance, 'arg') and puzzle_instance.arg:
                    arg_str = puzzle_instance.arg.decode('utf-8') if isinstance(puzzle_instance.arg, bytes) else str(puzzle_instance.arg)
                    # Parse 'wxht0' format
                    if 'x' in arg_str and 't' in arg_str:
                        parts = arg_str.split('x')
                        if len(parts) == 2:
                            w_str = parts[0]
                            rest = parts[1]
                            if 't' in rest:
                                h_str = rest.split('t')[0]
                                try:
                                    puzzle_w = int(w_str)
                                    puzzle_h = int(h_str)
                                    if puzzle_w == w and puzzle_h == h:
                                        # Dimensions match - reuse this instance
                                        puzzle_to_use = puzzle_instance
                                        create_temp = False
                                except ValueError:
                                    pass
            except Exception:
                # If anything goes wrong checking, fall back to creating temp
                pass
        
        temp_puzzle = None
        try:
            if create_temp:
                from rlp import puzzle as rp
                temp_puzzle = rp.Puzzle('loopy', arg=f'{w}x{h}t{grid_type}', headless=True)
                temp_puzzle.new_game()
                puzzle_to_use = temp_puzzle
            
            # Safety check: puzzle_to_use should never be None at this point
            if puzzle_to_use is None:
                raise ValueError(f"Failed to get puzzle instance for dimensions {w}x{h}")
            
            # Get grid structure from state
            state_dict_temp = puzzle_to_use.get_puzzle_state()
            game_grid = state_dict_temp['game_grid']
            
            # Extract grid metadata
            num_faces = game_grid['num_faces']
            num_edges = game_grid['num_edges']
            num_dots = game_grid['num_dots']
            lowest_x = game_grid['lowest_x']
            lowest_y = game_grid['lowest_y']
            
            # Calculate cell_size from first face
            first_face = game_grid['faces'][0]
            first_face_dots = [game_grid['dots'][idx] for idx in first_face['dots_indices']]
            if len(first_face_dots) >= 3:
                dot0 = first_face_dots[0]
                dot2 = first_face_dots[2]
                cell_size = abs(dot0['x'] - dot2['x'])
            else:
                cell_size = (game_grid['highest_x'] - lowest_x) // w if w > 0 else 1
            
            # Build edge-to-canvas mapping (matching C code's edge ordering)
            edge_to_canvas = {}
            for i, edge in enumerate(game_grid['edges']):
                dot1_idx = edge['dot1_index']
                dot2_idx = edge['dot2_index']
                dot1 = game_grid['dots'][dot1_idx]
                dot2 = game_grid['dots'][dot2_idx]
                
                x1 = (dot1['x'] - lowest_x) // cell_size
                x2 = (dot2['x'] - lowest_x) // cell_size
                y1 = (dot1['y'] - lowest_y) // cell_size
                y2 = (dot2['y'] - lowest_y) // cell_size
                
                canvas_x = x1 + x2
                canvas_y = y1 + y2
                edge_to_canvas[i] = (canvas_x, canvas_y)
            
            # Build face-to-canvas mapping
            face_to_canvas = {}
            for i, face in enumerate(game_grid['faces']):
                face_dots = [game_grid['dots'][idx] for idx in face['dots_indices']]
                if len(face_dots) >= 3:
                    dot0 = face_dots[0]
                    dot2 = face_dots[2]
                    
                    x1 = (dot0['x'] - lowest_x) // cell_size
                    x2 = (dot2['x'] - lowest_x) // cell_size
                    y1 = (dot0['y'] - lowest_y) // cell_size
                    y2 = (dot2['y'] - lowest_y) // cell_size
                    
                    canvas_x = x1 + x2
                    canvas_y = y1 + y2
                    face_to_canvas[i] = (canvas_x, canvas_y)
            
            # Cache the mappings
            _loopy_square_grid_cache[cache_key] = (edge_to_canvas, face_to_canvas, num_faces, num_edges)
            
        except Exception as e:
            raise ValueError(f"Failed to get grid structure: {e}")
        finally:
            # Clean up temporary puzzle (only if we created one)
            if temp_puzzle is not None:
                try:
                    import gc
                    del temp_puzzle
                    gc.collect()
                except:
                    pass
    
    # Phase 4: Parse clues from ASCII
    clues = [-1] * num_faces  # Initialize all to -1 (no clue)
    for face_idx, (canvas_x, canvas_y) in face_to_canvas.items():
        if canvas_y < len(lines):
            line = lines[canvas_y]
            stripped = line.rstrip()
            if canvas_x < len(stripped):
                c = stripped[canvas_x]
                # Parse CLUE2CHAR inverse
                if c == ' ':
                    clue_val = -1
                elif c >= '0' and c <= '9':
                    clue_val = ord(c) - ord('0')
                elif c >= 'A' and c <= 'Z':
                    clue_val = (ord(c) - ord('A')) + 10
                else:
                    # Invalid character, treat as no clue
                    clue_val = -1
                clues[face_idx] = clue_val
    
    # Phase 5: Parse lines from ASCII
    # LINE_YES = 0, LINE_UNKNOWN = 1, LINE_NO = 2
    lines_array = [1] * num_edges  # Initialize all to LINE_UNKNOWN
    for edge_idx, (canvas_x, canvas_y) in edge_to_canvas.items():
        if canvas_y < len(lines):
            line = lines[canvas_y]
            stripped = line.rstrip()
            if canvas_x < len(stripped):
                c = stripped[canvas_x]
                # Parse line state
                if c == '-' or c == '|':
                    lines_array[edge_idx] = 0  # LINE_YES
                elif c == 'x':
                    lines_array[edge_idx] = 2  # LINE_NO
                elif c == ' ':
                    lines_array[edge_idx] = 1  # LINE_UNKNOWN
                elif (c >= '0' and c <= '9') or (c >= 'A' and c <= 'Z'):
                    # This is a clue character at an edge position - skip it (keep as LINE_UNKNOWN)
                    # This can happen when clues are embedded in the solution format at positions
                    # that overlap with edge positions. The clue will be parsed from the face center,
                    # so we ignore it here to avoid treating it as a line state.
                    lines_array[edge_idx] = 1  # LINE_UNKNOWN
                # else: already LINE_UNKNOWN (default)
    
    # Phase 6: Validate array lengths match grid dimensions
    if len(clues) != num_faces:
        raise ValueError(f"Clues array length ({len(clues)}) does not match num_faces ({num_faces})")
    if len(lines_array) != num_edges:
        raise ValueError(f"Lines array length ({len(lines_array)}) does not match num_edges ({num_edges})")
    
    # Phase 7: Build state dict
    state_dict = {
        "params": {
            "w": w,
            "h": h,
            "type": grid_type,
        },
        "clues": clues,
        "lines": lines_array,
    }
    
    return state_dict
