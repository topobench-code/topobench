# TopoBench

Standalone benchmark runner and local verifier for six puzzle families:

- `bridges`
- `flow_free`
- `galaxies`
- `loopy`
- `pattern`
- `undead`

It includes:

- the copied verifier/source trees from `submodules/`
- the prompt files for plain, `intformat`, and `intformat_json`
- the integer-format mappings needed to decode benchmark outputs
- a minimal CLI to run model evaluations, save raw responses, verify them locally, and export CSV summaries

## Quickstart

```bash
sudo bash scripts/install.sh
export OPENROUTER_KEY=...
python evals/src/main.py run-and-verify \
  --provider openrouter \
  --model inception/mercury-2 \
  --variant plain \
  --difficulty easy \
  --puzzle bridges \
  --limit 1
```

Outputs land in:

- `results/runs/<run-name>/`
- `results/reports/<run-name>_details.csv`
- `results/reports/<run-name>_summary.csv`

## Where The Code Comes From

This repo is assembled from selected pieces of the upstream research workspace at `multimodal_cot`.

Copied source trees:

- `submodules/rlp` is a copied upstream puzzle verifier/source tree, trimmed down to the files needed to build and run the local verifiers
- `submodules/flowfree` is a copied upstream Flow Free solver/verifier tree
- `mappings/topobench_mappings` is copied mapping metadata from the original research workspace
- `evals/prompts/*` and the slimmed `evals/src/*` files are adapted from the original evaluation code

This standalone release does not ship the large RLP training corpora, generated puzzle archives, or other research-only assets. The verifier libraries and icon assets are rebuilt locally by `scripts/install.sh`.

This release intentionally targets only three published dataset variants:

- `topobench/topobench`
- `topobench/topobench_intformat`
- `topobench/topobench_intformat_json`

Semantic variants are not included in this standalone release.

## Super Simple Setup

### Option 1: Docker

Build the container:

```bash
docker build -t topobench -f docker/Dockerfile .
```

Run it:

```bash
docker run --rm -it \
  -e OPENROUTER_KEY=your_key_here \
  topobench
```

### Option 2: Local Debian/Ubuntu setup

Run:

```bash
sudo bash scripts/install.sh
```

That script:

- installs the required system packages
- installs the Python dependencies
- builds the minimal `rlp.constants` extension in place
- builds the required RLP verifier libraries for `bridges`, `galaxies`, `loopy`, `pattern`, and `undead`
- builds the Flow Free verifier binary

## Required API Keys

Set only the keys you need for the provider you plan to use:

- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY` or `OPENROUTER_KEY`
- `DEEPSEEK_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`

The benchmark datasets are public, so no Hugging Face token is required for normal runs.

## Run Benchmarks

Run all six puzzles on the plain release:

```bash
python evals/src/main.py run \
  --provider openai \
  --model gpt-4.1-mini \
  --variant plain \
  --difficulty all
```

Run only `bridges` and `loopy` on the integer-format release:

```bash
python evals/src/main.py run \
  --provider openrouter \
  --model google/gemini-2.5-pro \
  --variant intformat \
  --difficulty easy \
  --puzzle bridges \
  --puzzle loopy \
  --limit 20
```

Run and immediately verify in one command:

```bash
python evals/src/main.py run-and-verify \
  --provider openrouter \
  --model inception/mercury-2 \
  --variant intformat_json \
  --difficulty easy \
  --puzzle bridges \
  --limit 1
```

## Tested Smoke Test

The standalone pipeline has been checked with:

- a gold-solution self-test for `plain`
- a gold-solution self-test for `intformat`
- a gold-solution self-test for `intformat_json`
- one live OpenRouter run on `inception/mercury-2` for each of:
  `topobench/topobench`, `topobench/topobench_intformat`, and `topobench/topobench_intformat_json`

Example commands:

```bash
python evals/src/main.py run-and-verify \
  --provider openrouter \
  --model inception/mercury-2 \
  --variant plain \
  --difficulty easy \
  --puzzle bridges \
  --limit 1

python evals/src/main.py run-and-verify \
  --provider openrouter \
  --model inception/mercury-2 \
  --variant intformat \
  --difficulty easy \
  --puzzle bridges \
  --limit 1

python evals/src/main.py run-and-verify \
  --provider openrouter \
  --model inception/mercury-2 \
  --variant intformat_json \
  --difficulty easy \
  --puzzle bridges \
  --limit 1
```

## Verify Existing Runs

Each run is saved under `results/runs/<run-name>/` with:

- `manifest.json`
- `responses.jsonl`

Verify a run and export CSV summaries:

```bash
python evals/src/main.py verify \
  --run-dir results/runs/<run-name>
```

Verification writes:

- `results/reports/<run-name>_details.csv`
- `results/reports/<run-name>_summary.csv`

The verifier also prints a summary table to the terminal.

## CLI Notes

Extra provider-specific request parameters can be passed with repeated `--request-arg` flags:

```bash
python evals/src/main.py run \
  --provider openai \
  --model gpt-5 \
  --request-arg reasoning='{"effort":"medium"}'
```

The accepted dataset variants are:

- `plain`
- `intformat`
- `intformat_json`
