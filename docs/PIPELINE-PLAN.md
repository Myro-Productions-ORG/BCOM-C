# BCOM-C — Closed-Loop Training Pipeline Plan

**Status:** Design
**Goal:** A model-agnostic, backend-agnostic closed-loop pipeline that takes any base model + any eval suite and iteratively improves it through targeted data generation and fine-tuning until a pass-rate target is hit.

---

## The Loop

```
START
  │
  ▼
[01 EVALUATE]──────────────────────────────────────────────────────────────────
  │  Run base model against eval suite. Record per-service failure breakdown.
  │
  ▼
[02 ANALYZE]
  │  Claude Sonnet (Bedrock) reads the failure report.
  │  Outputs: top 3-5 weak service areas + recommended generation config.
  │
  ▼
[03 GENERATE]
  │  Coordinator spins up datagen workers.
  │  Workers: Claude Haiku (Bedrock) — one call per Q&A pair.
  │  Optional: Sonnet synthesis pass for quality lift.
  │  Output: grounded JSONL dataset targeting identified weak areas.
  │
  ▼
[04 FINE-TUNE]
  │  LoRA training on generated dataset + any cumulative prior data.
  │  Produces: merged checkpoint.
  │
  ▼
[05 DEPLOY CHECKPOINT]   ← the step Ross was skipping
  │  Load the fine-tuned checkpoint into the inference endpoint
  │  (vLLM hot-swap or Ollama model create).
  │  Wait for endpoint ready.
  │
  ▼
[06 RE-EVAL]
  │  Run the SAME eval suite against the LIVE fine-tuned endpoint.
  │  Record new pass rate. Calculate delta vs. prior iteration.
  │
  ▼
[CHECK]
  ├── pass_rate >= target  ──→  COMPLETE (target_reached)
  ├── iteration >= max     ──→  COMPLETE (max_iterations_reached)
  └── pass_rate < target   ──→  increment iteration, go to [02 ANALYZE]
                                (re-eval score becomes next iteration's base eval)
```

---

## Stage Breakdown

### 01 — EVALUATE

- **What:** Run the base model against the configured eval suite via the judge model.
- **API:** `POST /api/evals/run` → poll `GET /api/evals/{run_id}`
- **Input:** `{model_name, model_backend, eval_suite}`
- **Output:** `{run_id, pass_rate, results_by_service}` — per-service pass/fail breakdown is critical for the analyzer.
- **Iteration 2+:** Skip this step. Use the previous re-eval score as the starting point. Only run a full fresh eval on the first iteration of a new pipeline launch.

---

### 02 — ANALYZE

- **What:** Claude Sonnet reads the eval failure report and identifies where the model is weakest.
- **API:** `POST /api/training/analyze`
- **Model:** `claude-3-5-sonnet` via Bedrock (always Sonnet — this is a reasoning call, not volume work)
- **Input:** full eval results including per-service pass rates and example failures
- **Output:**
  ```json
  {
    "summary": "Model struggles with...",
    "priority_services": {"Service A": 5, "Service B": 4},
    "datagen_services": "Service A, Service B, Service C",
    "datagen_count": 150,
    "suggested_actions": ["..."],
    "trend_analysis": "..."
  }
  ```
- **Cost:** ~1 call per iteration, ~$0.02–0.05 (negligible)

---

### 03 — GENERATE

- **What:** Coordinator dispatches Q&A generation jobs to worker model instances.
- **API:** `POST /api/datagen/start`
- **Architecture:**
  - **Workers:** Claude Haiku via Bedrock — fast, cheap, good enough for structured Q&A
  - **Synthesis (optional):** Claude Sonnet final pass over batches of raw pairs for quality lift
  - **Grounding:** Each call receives a documentation snippet as context — no hallucinated answers
  - **Self-healing:** Failed services are retried up to N times before being skipped
- **Config:**
  ```json
  {
    "services": ["Service A", "Service B", "Service C"],
    "examples_per_service": 50,
    "generator_model": "claude-3-5-haiku",
    "generator_backend": "bedrock",
    "synthesizer_enabled": true,
    "synthesizer_model": "claude-3-5-sonnet",
    "dataset_type": "qa-grounded",
    "prompt_config": {
      "domain": "...",
      "persona": "...",
      "doc_label": "..."
    }
  }
  ```
- **Output:** JSONL file at `output_path`, cumulative across all iterations of the pipeline run
- **Cost (50 examples × 3 services):** ~$0.10 Haiku only, ~$0.80 with Sonnet synthesis

---

### 04 — FINE-TUNE

- **What:** LoRA fine-tune on the generated dataset. Cumulative — each iteration adds to prior data.
- **API:** `POST /api/finetune/start`
- **Config:**
  ```json
  {
    "base_model": "...",
    "dataset_path": "path/to/cumulative_grounded.jsonl",
    "rank": 16,
    "epochs": 3,
    "learning_rate": 0.0002,
    "output_dir": "path/to/checkpoint"
  }
  ```
- **Poll:** `GET /api/finetune/{job_id}` for epoch/step/loss progress
- **Cost:** $0 — runs locally on DGX

---

### 05 — DEPLOY CHECKPOINT  *(the critical missing step)*

- **What:** Swap the inference endpoint to serve the fine-tuned checkpoint before re-eval.
- **Without this step, re-eval is meaningless** — you're scoring the base model again.
- **Implementation:**
  - **vLLM:** `POST /api/deploy/start` with checkpoint path → wait for endpoint ready
  - **Ollama:** SSH to DGX, `ollama create {model_name} -f Modelfile` pointing to merged weights
- **API:** `POST /api/deploy/start` → poll `GET /api/deploy/active`
- **Rollback:** On pipeline failure or target not hit after max iterations, optionally restore base model
- **Cost:** $0 — local operation

---

### 06 — RE-EVAL

- **What:** Run the same eval suite against the now-live fine-tuned endpoint.
- **API:** `POST /api/evals/run` (same as step 01, but hitting the fine-tuned endpoint)
- **Output:** `{run_id, pass_rate, improvement_delta}`
- **This result becomes the base score for the next iteration's ANALYZE step**

---

## Configuration Schema (Pipeline Launch)

```json
{
  "model_name": "llama3.2:3b",
  "model_backend": "ollama",
  "eval_suite": "hard_15",
  "target_pass_rate": 80,
  "max_iterations": 5,
  "auto_advance": true,

  "datagen": {
    "generator_model": "claude-3-5-haiku",
    "generator_backend": "bedrock",
    "synthesizer_enabled": true,
    "synthesizer_model": "claude-3-5-sonnet",
    "examples_per_service": 50,
    "dataset_type": "qa-grounded",
    "prompt_config": {}
  },

  "finetune": {
    "rank": 16,
    "epochs": 3,
    "learning_rate": 0.0002
  }
}
```

---

## Cost Model

Based on Bedrock on-demand pricing (Dec 2025):
Haiku: $0.80/$4.00 per 1M tokens | Sonnet: $6.00/$30.00 per 1M tokens

Assumes: 3 weak services × 50 pairs each = 150 pairs/iteration
Each pair: ~1,200 input tokens, ~250 output tokens

| Component | Model | Per Iteration | Per 5-Iteration Run |
|---|---|---|---|
| Advisor analysis | Sonnet | ~$0.03 | ~$0.15 |
| Q&A generation (150 pairs) | Haiku | ~$0.24 | ~$1.20 |
| Synthesis pass (optional) | Sonnet | ~$0.47 | ~$2.35 |
| Fine-tune + eval + deploy | Local | $0 | $0 |
| **Total (with synthesis)** | | **~$0.74** | **~$3.70** |
| **Total (no synthesis)** | | **~$0.27** | **~$1.35** |

**At 10 full runs (50 iterations):** ~$37 with synthesis, ~$13.50 without.

---

## What Makes This Different From Ross's Implementation

| Issue | Ross's Pipeline | BCOM-C Plan |
|---|---|---|
| Re-eval target | Cached previous score | Always evaluates live fine-tuned endpoint |
| Datagen per iteration | Skipped on iter 2+ | Fresh generation every iteration |
| Generator quality | Gemma 3 4B (local) | Claude Haiku via Bedrock |
| Synthesis layer | Not consistently used | Optional Sonnet pass, configurable |
| Checkpoint deploy | Missing | Explicit step between fine-tune and re-eval |
| Data accumulation | Per-iteration only | Cumulative JSONL across all iterations |

---

## Agnostic Design Principles

The pipeline makes no assumptions about:

- **What model is being trained** — any model that fits the DGX and has an Ollama/vLLM endpoint
- **What domain the eval suite covers** — prompt_config adapts the generator persona/context
- **What backend runs inference** — vLLM, Ollama, or Bedrock all use the same eval API
- **What backend runs generation** — Bedrock, local Ollama, or direct Anthropic API
- **How many iterations are needed** — auto-loops until target or max_iterations

The only hard dependency is: a working eval suite and a measurable pass rate metric.

---

## Open Questions / Next Steps

- [ ] Confirm `/api/deploy/start` checkpoint hot-swap works for vLLM on our DGX
- [ ] Define prompt_config schema for different dataset types (aws-qa, gov-qa, form-qa, custom)
- [ ] Decide default examples_per_service (50 is conservative — can go higher as costs allow)
- [ ] Confirm Bedrock credentials work from DGX for Haiku calls
- [ ] Build BCOM-C pipeline.html config form to expose datagen fields
- [ ] Test the full loop end-to-end with a simple eval suite and a small model
