  
## Dataset Generation Pipeline

This repository includes a unified pipeline for generating ASCII puzzle datasets for training and evaluation. The pipeline generates puzzles, creates DataFrames with train/test splits, and can optionally upload to HuggingFace Hub.

### Quick Start

```bash
# Generate 100 samples of bridges puzzle (5x5, easy difficulty)
python run_ascii_puzzle_generation_pipeline.py --puzzles "bridges:5x5de" --n_samples 100

# Generate multiple puzzle configurations
python run_ascii_puzzle_generation_pipeline.py --puzzles "bridges:5x5de,bridges:7x7dm,loopy:5x5de" --n_samples 500

# Generate with a custom suffix and upload to HuggingFace
python run_ascii_puzzle_generation_pipeline.py --puzzles "bridges:5x5de" --suffix "grpo_train" --n_samples 1000
```

### Puzzle Configuration Format

Puzzles are specified using the format `puzzle_name:size_difficulty`:

| Component | Description | Examples |
|-----------|-------------|----------|
| `puzzle_name` | Name of the puzzle type | `bridges`, `galaxies`, `loopy`, `pattern`, `undead` |
| `size` | Grid dimensions | `5x5`, `7x7`, `10x10` |
| `difficulty` | Difficulty level suffix | `de` (easy), `dm` (medium), `dh` (hard) |

**Examples:**
- `bridges:5x5de` - 5x5 bridges puzzle, easy difficulty
- `galaxies:7x7dm` - 7x7 galaxies puzzle, medium difficulty
- `loopy:10x10dh` - 10x10 loopy puzzle, hard difficulty

### Available Puzzle Types and Difficulty Mappings

| Puzzle | Easy | Medium | Hard | Notes |
|--------|------|--------|------|-------|
| `bridges` | `d0` | `d1` | `d2` | Numeric difficulty |
| `galaxies` | `dn` (normal) | `du` (unreasonable) | `du` | Only 2 difficulty levels |
| `loopy` | `de` | `dt` (tricky) | `dh` | Uses square grid (`t0`) |
| `pattern` | N/A | N/A | N/A | No difficulty parameter |
| `undead` | `de` | `dn` (normal) | `dt` (tricky) | Grid sizes: 4x4, 5x5, 7x7 |

### Pipeline Arguments

```bash
python run_ascii_puzzle_generation_pipeline.py [OPTIONS]
```

| Argument | Description | Default |
|----------|-------------|---------|
| `--puzzles` | Comma-separated puzzle configs (required) | - |
| `--n_samples` | Number of samples per config | 1000 |
| `--n_workers` | Parallel workers for generation | 4 |
| `--output_dir` | Base output directory | `./pipeline_output` |
| `--suffix` | Suffix for dataset names | None |
| `--test_only` | Put all samples in test split | False |
| `--dedupe_test200` | Dedupe train against test200 datasets | False |
| `--skip_generation` | Skip puzzle generation step | False |
| `--skip_df` | Skip DataFrame creation step | False |
| `--skip_upload` | Skip HuggingFace upload step | False |
| `--run_folder` | Use existing run folder | None |
| `--hf_token` | HuggingFace authentication token | None |
| `--commit_message` | Commit message for HuggingFace | None |

### Output Structure

Each puzzle configuration gets its own timestamped folder:

```
pipeline_output/
├── bridges_5x5de_grpo_train_20251217_143052/
│   ├── txt/                              # Generated puzzle files
│   │   ├── bridges_5x5de_abc123.txt
│   │   └── ...
│   └── csvs/                             # CSV with train/test splits
│       └── bridges_5x5de_grpo_train_20251217_143052.csv
└── ...
```

### Common Use Cases

**Generate a test dataset (all samples in test split):**
```bash
python run_ascii_puzzle_generation_pipeline.py \
    --puzzles "bridges:5x5de,bridges:7x7dm,bridges:10x10dh" \
    --n_samples 200 \
    --suffix "test200" \
    --test_only
```

**Generate training data with deduplication:**
```bash
python run_ascii_puzzle_generation_pipeline.py \
    --puzzles "bridges:5x5de" \
    --n_samples 5000 \
    --suffix "grpo_5k" \
    --dedupe_test200 \
    --n_workers 16
```

**Reuse existing puzzles (skip generation):**
```bash
python run_ascii_puzzle_generation_pipeline.py \
    --puzzles "bridges:5x5de" \
    --skip_generation \
    --run_folder ./pipeline_output/bridges_5x5de_grpo_train_20251217_143052
```

### Pre-built Generation Scripts

The `scripts/` directory contains ready-to-use bash scripts for common dataset generation tasks:

| Script | Description |
|--------|-------------|
| `generate_all_rsft_1k.sh` | Generate all rsft_1k datasets (15k total) |
| `generate_bridges_rsft_1k.sh` | Bridges rsft_1k (3k samples) |
| `generate_bridges_grpo_5k.sh` | Bridges grpo_5k (30k samples) |
| `generate_*_test200.sh` | Test datasets (200 samples each) |

**Usage:**
```bash
# Generate only (no upload)
./scripts/generate_bridges_rsft_1k.sh

# Generate and upload to HuggingFace
./scripts/generate_bridges_rsft_1k.sh --upload
```

### Generated Puzzle File Format

Each generated `.txt` file contains:

```
Solved: True

Problem:
[ASCII representation of the initial puzzle state]

After move M1,0,3:
[ASCII state after move 1]

After move M2,1,4:
[ASCII state after move 2]

...

Final Solution:
[ASCII representation of the solved puzzle]
```

## License

The `RLP` code is released under the CC BY-NC 4.0 license. For more information, see [LICENSE](LICENSE).

Simon Tatham's Portable Puzzle Collection is licensed under the MIT License, see [puzzles/LICENCE](puzzles/LICENCE).
