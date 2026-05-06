#!/usr/bin/env python3
"""
Simple script to verify if a puzzle ASCII state is solved.

Supports: bridges, undead, galaxies, pattern, loopy

Usage:
    # From stdin
    python verifier.py bridges < ascii_state.txt
    python verifier.py undead < ascii_state.txt
    
    # From command line argument
    python verifier.py bridges "3|.|2\n..."
    python verifier.py undead "G: 3 V: 1 Z: 6\n\n   2 3 1 1  \n..."
    python verifier.py galaxies "+-+-+\n|o o|\n+-+-+\n|o o|\n+-+-+\n"
    python verifier.py loopy " x x x - x \nx x0x |3| x\n..."
    
    # With escape sequences
    echo "3|.|2\n..." | python verifier.py bridges
    echo "G: 3 V: 1 Z: 6\n\n..." | python verifier.py undead
    echo "+-+-+\n|o o|\n..." | python verifier.py galaxies
"""

import sys
import argparse
import warnings
from rlp.puzzle import Puzzle
from rlp.ascii_parser import parse_ascii_bridges, check_bridges_structural_validity, parse_ascii_undead, check_undead_structural_validity, parse_ascii_galaxies, check_galaxies_structural_validity, parse_ascii_pattern, parse_ascii_loopy


def verify_ascii_state(puzzle, ascii_text: str, problem_ascii: str = None) -> str:
    """
    Verify if an ASCII puzzle state is solved.
    
    Args:
        puzzle: Puzzle instance (must be initialized with new_game())
        ascii_text: ASCII representation of puzzle state
        problem_ascii: Optional ASCII representation of the original problem state.
                      When provided, checks that pre-filled cells haven't been modified.
                      For bridges: checks islands haven't moved/changed.
                      For galaxies: checks dots haven't moved/removed.
        
    Returns:
        str: "SOLVED" if the state is solved, "NOT SOLVED" otherwise
        
    Raises:
        Exception: If verification fails
    """
    puzzle_type = puzzle.puzzle_name
    
    try:
        if puzzle_type == "bridges":
            # Warn if problem_ascii not provided
            if problem_ascii is None:
                warnings.warn(
                    "verify_ascii_state called for bridges without problem_ascii. "
                    "Startboard modification check will be skipped.",
                    UserWarning
                )
            
            # First check structural validity (includes island modification check if problem_ascii provided)
            if not check_bridges_structural_validity(str(ascii_text), problem_ascii=problem_ascii):
                # Structurally invalid (broken lines, modified clues, etc.)
                return "NOT SOLVED"
            
            # Parse ASCII with Python parser
            state_dict = parse_ascii_bridges(str(ascii_text))
            
            # Load state dict
            loaded_state_ptr = puzzle.load_state_dict(state_dict)
            
            # Get free_game function
            me = puzzle.fe.contents.me.contents
            game = me.ourgame.contents
            free_game_func = game.free_game
            
            try:
                # Check if solved (completed flag)
                is_solved = loaded_state_ptr.contents.completed
                
                if is_solved:
                    return "SOLVED"
                else:
                    return "NOT SOLVED"
            finally:
                # Free the loaded state
                if loaded_state_ptr:
                    free_game_func(loaded_state_ptr)
        elif puzzle_type == "undead":
            # First check structural validity
            if not check_undead_structural_validity(str(ascii_text)):
                # Structurally invalid (missing header, no grid, invalid format, etc.)
                return "NOT SOLVED"
            
            # Use new pipeline: parse → load → check
            # Parse ASCII with Python parser
            state_dict = parse_ascii_undead(str(ascii_text))
            
            # Load state dict
            loaded_state_ptr = puzzle.load_state_dict(state_dict)
            
            # Get free_game function
            me = puzzle.fe.contents.me.contents
            game = me.ourgame.contents
            free_game_func = game.free_game
            
            try:
                # Check if solved (undead only has 'solved' field, not 'completed')
                is_solved = loaded_state_ptr.contents.solved
                
                if is_solved:
                    return "SOLVED"
                else:
                    return "NOT SOLVED"
            finally:
                # Free the loaded state
                if loaded_state_ptr:
                    free_game_func(loaded_state_ptr)
        elif puzzle_type == "galaxies":
            # Warn if problem_ascii not provided
            if problem_ascii is None:
                warnings.warn(
                    "verify_ascii_state called for galaxies without problem_ascii. "
                    "Startboard modification check will be skipped.",
                    UserWarning
                )
            
            # First check structural validity (includes dot modification check if problem_ascii provided)
            if not check_galaxies_structural_validity(str(ascii_text), problem_ascii=problem_ascii):
                # Structurally invalid (invalid dimensions, dots modified, etc.)
                return "NOT SOLVED"
            
            # Use new pipeline: parse → load → check
            # Parse ASCII with Python parser
            state_dict = parse_ascii_galaxies(str(ascii_text))
            
            # Load state dict
            loaded_state_ptr = puzzle.load_state_dict(state_dict)
            
            # Get free_game function
            me = puzzle.fe.contents.me.contents
            game = me.ourgame.contents
            free_game_func = game.free_game
            
            try:
                # Check if solved (galaxies uses 'completed' field)
                is_solved = loaded_state_ptr.contents.completed
                
                if is_solved:
                    return "SOLVED"
                else:
                    return "NOT SOLVED"
            finally:
                # Free the loaded state
                if loaded_state_ptr:
                    free_game_func(loaded_state_ptr)
        elif puzzle_type == "pattern":
            # Use new pipeline: parse → load → check
            # Parse ASCII with Python parser
            state_dict = parse_ascii_pattern(str(ascii_text))
            
            # Load state dict
            loaded_state_ptr = puzzle.load_state_dict(state_dict)
            
            # Get free_game function
            me = puzzle.fe.contents.me.contents
            game = me.ourgame.contents
            free_game_func = game.free_game
            
            try:
                # Check if solved (pattern uses 'completed' field)
                is_solved = loaded_state_ptr.contents.completed
                
                if is_solved:
                    return "SOLVED"
                else:
                    return "NOT SOLVED"
            finally:
                # Free the loaded state
                if loaded_state_ptr:
                    free_game_func(loaded_state_ptr)
        elif puzzle_type == "loopy":
            # Use new pipeline: parse → load → check
            
            # IMPORTANT: Early dimension check to prevent segfaults
            # Creating temp puzzle instances for each unique dimension causes segfaults
            # after ~20 instances. Validate dimensions BEFORE calling parse_ascii_loopy
            # to avoid creating temp puzzles for invalid/malformed ASCII.
            expected_dimensions = {(5, 5), (7, 7), (10, 10)}  # easy, medium, hard
            
            # Pre-check dimensions without creating any puzzle instances
            try:
                ascii_str = str(ascii_text)
                if ascii_str.endswith('\n'):
                    lines = ascii_str[:-1].split('\n')
                else:
                    lines = ascii_str.split('\n')
                
                content_lines = [line for line in lines if line.strip() or len(line) > 0]
                H = len(content_lines) if len(content_lines) > 0 else len(lines)
                max_W_content = max((len(line) for line in lines), default=0)
                
                if max_W_content == 0:
                    return "NOT SOLVED"
                
                W = max_W_content + 1
                if (H - 1) % 2 != 0:
                    H += 1
                
                # Check valid dimension format
                if (W - 2) % 2 != 0 or (H - 1) % 2 != 0:
                    return "NOT SOLVED"
                
                w = (W - 2) // 2
                h = (H - 1) // 2
                
                if w < 1 or h < 1:
                    return "NOT SOLVED"
                
                # Reject unexpected dimensions to prevent temp puzzle creation
                if (w, h) not in expected_dimensions:
                    return "NOT SOLVED"
            except Exception:
                return "NOT SOLVED"
            
            try:
                # Parse ASCII with Python parser, passing existing puzzle instance to avoid creating temp ones
                state_dict = parse_ascii_loopy(str(ascii_text), grid_type=0, puzzle_instance=puzzle)
            except ValueError as e:
                # Check if this is a dimension validation error (model mistake in response format)
                error_msg = str(e)
                if any(keyword in error_msg for keyword in [
                    "Invalid canvas width",
                    "Invalid canvas height", 
                    "Invalid dimensions",
                    "Dimension mismatch"
                ]):
                    # Model made a mistake in the response format - treat as NOT SOLVED
                    return "NOT SOLVED"
                else:
                    # Other ValueError - might indicate a bug, re-raise
                    raise
            
            # Load state dict
            loaded_state_ptr = puzzle.load_state_dict(state_dict)
            
            # Get free_game function
            me = puzzle.fe.contents.me.contents
            game = me.ourgame.contents
            free_game_func = game.free_game
            
            try:
                # Check if solved (loopy uses 'solved' field)
                is_solved = loaded_state_ptr.contents.solved
                
                if is_solved:
                    return "SOLVED"
                else:
                    return "NOT SOLVED"
            finally:
                # Free the loaded state
                if loaded_state_ptr:
                    free_game_func(loaded_state_ptr)
        else:
            # For other puzzles, fall back to old method
            is_solved = puzzle.check_ascii_solved(str(ascii_text))
            
            if is_solved:
                return "SOLVED"
            else:
                return "NOT SOLVED"
    except ValueError as e:
        # Check if this is a dimension validation error from parsing (model mistake)
        error_msg = str(e)
        if any(keyword in error_msg for keyword in [
            "Invalid canvas width",
            "Invalid canvas height",
            "Invalid dimensions", 
            "Dimension mismatch",
            "Invalid grid width",
            "Invalid grid height"
        ]):
            # Model made a mistake in the response format - treat as NOT SOLVED
            return "NOT SOLVED"
        else:
            # Other ValueError - might indicate a bug, re-raise
            raise
    except Exception as e:
        # Other unexpected errors - re-raise with context
        raise Exception(f"Failed to check puzzle state: {e}") from e


def main():
    """Read ASCII state and check if solved."""
    parser = argparse.ArgumentParser(
        description='Verify if a puzzle ASCII state is solved',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python verifier.py bridges "3|.|2\\n..."
  python verifier.py undead "G: 3 V: 1 Z: 6\\n\\n   2 3 1 1  \\n..."
  python verifier.py galaxies "+-+-+\\n|o o|\\n..."
  echo "..." | python verifier.py bridges
        """
    )
    parser.add_argument(
        'puzzle_type',
        choices=['bridges', 'undead', 'galaxies', 'pattern', 'loopy'],
        help='Type of puzzle to verify'
    )
    parser.add_argument(
        'ascii_text',
        nargs='?',
        help='ASCII representation of puzzle state (if not provided, read from stdin)'
    )
    parser.add_argument(
        '--arg',
        default=None,
        help='Puzzle initialization argument (e.g., "5x5deL" for bridges, "4x4" for undead)'
    )
    parser.add_argument(
        '--problem',
        default=None,
        help='Original problem ASCII state (for checking startboard modifications)'
    )
    
    args = parser.parse_args()
    
    # Read ASCII input
    if args.ascii_text:
        # ASCII state provided as command line argument
        ascii_text = args.ascii_text
        # Convert escape sequences like \n to actual newlines
        # This handles cases where user passes "text\nmore" from command line
        ascii_text = ascii_text.encode().decode('unicode_escape')
    else:
        # Read from stdin
        ascii_text = sys.stdin.read()
    
    if not ascii_text.strip():
        print("Error: No ASCII state provided", file=sys.stderr)
        sys.exit(1)
    
    # Determine puzzle initialization argument if not provided
    if args.arg is None:
        if args.puzzle_type == "bridges":
            args.arg = '5x5deL'  # Default for bridges
        elif args.puzzle_type == "undead":
            args.arg = '4x4'  # Default for undead
        elif args.puzzle_type == "galaxies":
            args.arg = '4x4'  # Default for galaxies
        elif args.puzzle_type == "pattern":
            args.arg = '5x5'  # Default for pattern
        elif args.puzzle_type == "loopy":
            args.arg = '5x5t0'  # Default for loopy (5x5 square grid)
    
    # Create puzzle instance
    puzzle = Puzzle(args.puzzle_type, arg=args.arg, headless=True)
    puzzle.new_game()  # Initialize the game structure
    
    try:
        # Process problem ASCII if provided
        problem_ascii = None
        if args.problem:
            problem_ascii = args.problem.encode().decode('unicode_escape')
        
        # Verify the ASCII state
        result = verify_ascii_state(puzzle, ascii_text, problem_ascii=problem_ascii)
        print(result)
        sys.exit(0 if result == "SOLVED" else 1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up puzzle instance
        import gc
        gc.collect()
        del puzzle
        gc.collect()


if __name__ == "__main__":
    main()



