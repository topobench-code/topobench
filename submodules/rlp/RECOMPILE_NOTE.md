# Recompilation Required

The bridges.c file has been modified to add the `game_text_parse` and `bridges_text_parse` functions.

## To recompile using install_new.sh:

The recommended approach is to use the `install_new.sh` script which handles all dependencies and builds:

```bash
cd /home/ubuntu/projects/rlp
./install_new.sh
```

This will:
1. Install system dependencies (if needed and if you have sudo access)
2. Set up Python virtual environment
3. Configure and build all libraries including libbridges
4. Install Python packages

## To recompile just libbridges (if CMake is already set up):

If you already have cmake and the build environment configured:

```bash
cd /home/ubuntu/projects/rlp
mkdir -p rlp/lib
cd rlp/lib

# Configure if not already done
if [ ! -f CMakeCache.txt ]; then
  cmake ../../puzzles
fi

# Build just libbridges
cmake --build . --target libbridges
```

Or use the helper script:
```bash
./build_bridges.sh
```

## Verify the library was updated:

```bash
ls -lh rlp/lib/libbridges.so
```

The library should be located at `rlp/lib/libbridges.so` and will be loaded by the Python code when creating a bridges puzzle.

