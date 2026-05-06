# TopoBench

![TopoBench](figure1.png)

This repo provides the code to run the main TopoBench benchmark with different input formats.

Dataset Links:

-[Plain](https://huggingface.co/datasets/topobench/topobench)

-[Intformat](https://huggingface.co/datasets/topobench/topobench_intformat)

-[Intformat_json](https://huggingface.co/datasets/topobench/topobench_intformat_json)

## Setup (docker required)

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

Options for keys (only set the keys you need for the provider you plan to use):

- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `DEEPSEEK_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`

## Run Benchmarks

Run all six puzzles on the plain release:

```bash
python evals/src/main.py run \
  --provider openai \
  --model gpt-5-mini \
  --variant plain \
  --difficulty all
  --limit 50
```

Run only bridges and immediately verify in one command:

```bash
python evals/src/main.py run-and-verify \
  --provider openrouter \
  --model inception/mercury-2 \
  --variant intformat_json \
  --difficulty easy \
  --puzzle bridges \
  --limit 50
```

format options:
- plain
- intformat
- intformat_json

puzzle options:
- bridges
- flow_free
- galaxies
- loopy
- pattern
- undead

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
