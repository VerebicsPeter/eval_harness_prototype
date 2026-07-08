# Schema

## Global metadata

- `run_id: string` UUID for run
- `timestamp: string` start of the run (we have to decide a format)
- `benchmark: dict[str, str]` user facing benchmark name, url
- `target_model: dict[str, str]` user facing model name, url
- `inference_provider: enum string` inference provider (cloud or local)
  - cloud::openai
  - cloud::google
  - local::vllm
  - local::ollama
  - local::transformers

## Sampling hyperparams

- `temperature: float | null`
- `seed: int | null`
- `max_tokens: int | null`
- `top_p: float | null` (nucleus sampling cumulative probability cutoff)
- `top_k: int | null` (top k sampling token limit)
- `min_p: float | null` (minimum relative probability threshold)
- `freq_penalty: float | null` (oai like absolute token frequency penalty)
- `pres_penalty: float | null` (oai like absolute token presence penalty)

## Cloud Scope

- `api_provider: enum string` openai, google
- `api_enpoint: string` which endpoint of the API
- `system_fingerprint: string | null` system fingerprint if available
- `metadata: dict` any additional metadata

## Local Scope

- `backend: enum string` vllm, ollama, transformers
- `version: enum string` backend version (package version)
- `model_provider: enum string` huggingface, native_registry, local_registry
- `model_source: string` the exact path, url used to mount model weights
- `model_revision: string | null` model commit or digest hash (if applicable)
- `quantization_method: enum string | null` quantization method used
- `precision: enum string | null` precision of the weights
- `gpu_hardware: string | null` name of the gpu(s)
- `cuda_version: string | null` cuda version (if applicable)
