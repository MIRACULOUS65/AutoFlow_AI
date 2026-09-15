# AutoFlow AI — Models

AutoFlow speaks the **OpenAI-compatible Chat Completions API**, so any provider
that exposes that surface works by setting a base URL, model id and API key.
Model weights are **never** committed. The local deterministic provider is
always available so the whole system runs offline with zero configuration.

## Supported model classes (manifest)

The canonical manifest lives in `autoflow_ai.lab.manifest`. Inspect it with:

```powershell
uv run python -m autoflow_ai.cli model list
uv run python -m autoflow_ai.cli model info
```

| Manifest id | Kind | Install method | Capabilities | Env keys |
|---|---|---|---|---|
| `local-deterministic` | local-deterministic | builtin (always available) | text, structured_output | — |
| `nvidia` | remote-openai | env-config | text, structured_output, streaming, vision, tool_calling | `PRIMARY_MODEL_BASE_URL`, `PRIMARY_MODEL_API_KEY`, `PRIMARY_MODEL_ID` |
| `qwen` | remote-openai | env-config | text, structured_output, streaming | `SECONDARY_MODEL_BASE_URL`, `SECONDARY_MODEL_API_KEY`, `SECONDARY_MODEL_ID` |
| `embedding` | remote-openai | env-config | embedding | `EMBEDDING_MODEL_BASE_URL`, `EMBEDDING_MODEL_ID` |

The runtime model ids used by the gateway/lab are `model_primary01` (NVIDIA),
`model_secondary01` (Qwen/ModelScope) and `model_local01` (local deterministic,
provider `local-rule`).

## Install / verify

`install` never downloads weights for remote providers — it validates that the
required env keys are **present** (reporting configured vs missing keys, never
the values). For local Ollama models it pulls into the model cache.

```powershell
uv run python -m autoflow_ai.cli model install local-deterministic   # builtin, always ok
uv run python -m autoflow_ai.cli model install nvidia                # reports configured/missing keys
uv run python -m autoflow_ai.cli model verify nvidia
```

Example (no keys set):

```json
{ "model_id": "nvidia", "installed": false, "method": "env-config",
  "configured_keys": [], "missing_keys": ["PRIMARY_MODEL_BASE_URL","PRIMARY_MODEL_API_KEY","PRIMARY_MODEL_ID"] }
```

## Model cache

Downloadable local models go to `AUTOFLOW_MODEL_HOME` (default
`~/.autoflow/models`) — never inside the repository. The `.autoflow/` directory
and common weight formats (`*.gguf`, `*.safetensors`, `*.bin`) are gitignored.

## Configuring providers

Set these in `.env` (copied from `.env.example`):

```ini
# NVIDIA NIM (primary)
PRIMARY_MODEL_PROVIDER=openai_compatible
PRIMARY_MODEL_BASE_URL=https://integrate.api.nvidia.com/v1
PRIMARY_MODEL_ID=meta/llama-3.2-11b-vision-instruct
PRIMARY_MODEL_API_KEY=            # your key, never committed

# ModelScope / Qwen (secondary, streaming)
SECONDARY_MODEL_PROVIDER=openai_compatible
SECONDARY_MODEL_BASE_URL=https://api-inference.modelscope.ai/v1
SECONDARY_MODEL_ID=Qwen/Qwen3-8B
SECONDARY_MODEL_API_KEY=
SECONDARY_MODEL_STREAMING=true
```

Other OpenAI-compatible providers (OpenAI, Groq, OpenRouter, vLLM, Ollama) work
by pointing `*_BASE_URL`/`*_ID` at them — see the comments in `.env.example`.

## Model Lab

The lab benchmarks and compares models **structurally** (schema validity,
malformed-output handling, hallucination resistance) with secret-free
observability.

```powershell
uv run python -m autoflow_ai.cli model lab list
uv run python -m autoflow_ai.cli model lab test model_local01
uv run python -m autoflow_ai.cli model lab task <task_id> --model model_primary01
uv run python -m autoflow_ai.cli model lab benchmark
uv run python -m autoflow_ai.cli model lab compare --models nvidia,qwen,deterministic
uv run python -m autoflow_ai.cli model console
```

## Live vs simulation

- **Local deterministic** — always LIVE, offline, deterministic. Not a semantic
  model; it is a rule provider used as a reproducible baseline and for
  simulation.
- **NVIDIA / Qwen** — LIVE only when the env keys are configured and the endpoint
  responds. The lab **fails closed** on timeouts (it will report a failure rather
  than fabricate a result). NVIDIA vision endpoints can be intermittently slow
  under load.
- Without configuration, missions run in **SIMULATION** over the deterministic
  provider — the full real loop, no real cloud call.

## Anti-fabrication guarantees

Model confidence is never treated as verification. Structured outputs are
schema-validated; malformed or hallucinated outputs are detected and labeled;
a run only reports success when independent verification confirms it.
