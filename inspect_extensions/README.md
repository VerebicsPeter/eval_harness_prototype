# Inspect-AI microsandbox integration

This repository provides an example for integrating microsandbox microvm runtimes in Inspect-AI with a simple wrapper.

## Setup

Install the packages in `requirements.txt`:

```bash
uv pip install -r requirements.txt
```

Install the custom `inspect_extensions`:

```bash
uv pip install inspect_extensions
```

> NOTE: Using `uv` is optional but recommended

## Tests

Run the smoke test script to verify microsandbox is working:

```bash
python inspect_extensions/tests/test_integration.py
```

> NOTE: Running the tests the first time may take longer because of microsandbox initialization. Also the script will download the `python` image the first time.

## Running the custom humaneval instance

> NOTE: humaneval benchmark is only reimplemented to provide an example for the use of Inspect-AI, reimplementing a benchmark is  not required for the use of the microsandbox wrapper.

Run the example via:

```bash
inspect eval benchmarks/humaneval.py --model google/gemini-2.5-flash --limit 5
```

View the results via:

```bash
inspect view
```
