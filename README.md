# Inspect AI microsandbox integration

This repository provides an example for integrating microsandbox microvm runtimes for inspect AI with a simple wrapper.

## Setup

Install the requirements in `requirements.txt` (using `uv` is recommended).

## Tests

Run the smoke test scripts to verify microsandbox is working:

```bash
python -m tests.test_microsandbox
```

> NOTE: Running the tests the first time may take longer because of microsandbox initialization.

## Running the custom humaneval instance

> NOTE: humaneval benchmark is only reimplemented to provide an example for the use of inspect-AI, reimplementing a benchmark is  not required for the use of the microsandbox wrapper.

Run the example via:

```bash
inspect eval benchmarks/humaneval.py --model google/gemini-2.5-flash --limit 5
```

View the results via:

```bash
inspect view
```
