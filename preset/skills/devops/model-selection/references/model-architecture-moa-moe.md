# MoA vs MoE vs Router — classifying models in a provider picker

Depth for the architecture question: **"is this one model or a panel?"**
Always-on rule: if the pricing is `dynamic`/`-1`, treat the cost as unknown
until the composition is resolved.

## Mixture of Experts (MoE) vs Mixture of Agents (MoA)

| | **Mixture of Experts (MoE)** | **Mixture of Agents (MoA)** |
|---|---|---|
| **Architecture** | One model with many "experts" inside (sparse routing) | Multiple **different** models working together |
| **How it works** | Single forward pass, activates only some experts | Pipeline: model A proposes → model B critiques → model C synthesizes |
| **Cost model** | Fixed price of that one model (usually cheaper than dense equivalent) | **Sum of costs of all models in the panel** (usually more expensive) |
| **Examples in picker** | `tencent/hy3`, `nvidia/nemotron-3-ultra-550b-a55b`, `qwen/qwen3-235b-a22b`, `deepseek/deepseek-v4-pro`, `meta-llama/llama-4-maverick` | `openrouter/fusion` |

### The MoA model: `openrouter/fusion`

| Parameter | Value |
|---|---|
| **Model ID** | `openrouter/fusion` |
| **Provider** | OpenRouter (internal router) |
| **Type** | **Mixture of Agents** (multi-model deliberation + web search/fetch) |
| **Description** | "Turns your prompt into a small multi-model deliberation. A panel of expert models analyzes your prompt in parallel with web search and web fetch enabled, then a synthesizing model combines the outputs" |
| **Pricing** | `prompt: -1, completion: -1` — **dynamic**, depends on which models are selected for the panel (typically top-tier paid models) |
| **Context** | 1,000,000 tokens |
| **Architecture token** | `Router` (not a real tokenizer) |

**Cost implication:** you pay for the **sum of all models in the panel** + the
synthesizer. Usually more expensive than a single model; quality on complex
problems is often higher.

### Router models (NOT MoA — they route to ONE model)

| Model ID | Type | Pricing |
|---|---|---|
| `openrouter/auto` | Auto-router (meta-model picks ONE best) | Dynamic (`-1`) |
| `openrouter/free` | Random free model router | **Free** (`0`) |
| `openrouter/pareto-code` | Coding model router (by Artificial Analysis rank) | Dynamic (`-1`) |
| `switchpoint/router` | Third-party router | `$0.00085 / $0.0034` per 1K tokens |

### Identification checklist

- **"Mixture of Agents"** or **"OpenRouter: Fusion"** → MoA, dynamic pricing,
  multi-model.
- **"Mixture of Experts"** in name/description (Hy3, Nemotron 3 Ultra, Qwen3
  MoE, DeepSeek V4, Llama 4) → MoE **inside one model**, fixed price.
- **"Router"**, **"Auto"**, **"Free Router"**, **"Pareto"** → routes to a
  **single** model, not multi-agent.
