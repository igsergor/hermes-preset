# DeepSeek V4 Models on OpenRouter — Detailed Reference

## Model IDs

| Display Name | OpenRouter ID |
|-------------|---------------|
| V4 Flash (free) | `deepseek/deepseek-v4-flash:free` |
| V4 Flash | `deepseek/deepseek-v4-flash` |
| V4 Pro | `deepseek/deepseek-v4-pro` |

## Architecture

- **V4 Flash**: 284B total / 13B activated (MoE), hybrid attention (CSA + HCA) for long context
- **V4 Pro**: 1.6T total / 49B activated (MoE), same architecture, larger
- Both: 1M context, FP4+FP8 mixed precision, Muon optimizer, mHC (manifold-constrained hyper-connections)
- Key innovation: 1M context needs only 27% of single-token FLOPs vs DeepSeek-V3.2

## Benchmarks (Instruct Models, April 2026)

### V4 Pro Max vs Frontier Models

| Benchmark | Opus-4.6 Max | GPT-5.4 xHigh | Gemini 3.1 Pro High | DS-V4-Pro Max |
|-----------|-------------|---------------|---------------------|---------------|
| MMLU-Pro (EM) | 89.1 | 87.5 | **91.0** | 87.5 |
| GPQA Diamond | 91.3 | 93.0 | **94.3** | 90.1 |
| HLE | 40.0 | 39.8 | **44.4** | 37.7 |
| LiveCodeBench | 88.8 | - | 91.7 | **93.5** |
| Codeforces (Rating) | - | 3168 | 3052 | **3206** |
| HMMT 2026 Feb | 96.2 | **97.7** | 94.7 | 95.2 |
| IMOAnswerBench | 75.3 | **91.4** | 81.0 | 89.8 |
| SWE Verified | **80.8** | - | 80.6 | 80.6 |
| BrowseComp | 83.7 | 82.7 | **85.9** | 83.4 |
| Terminal Bench 2.0 | 65.4 | **75.1** | 68.5 | 67.9 |
| MRCR 1M | **92.9** | - | 76.3 | 83.5 |

### Comparison Across Reasoning Modes

| Benchmark | Flash Non-Think | Flash High | Flash Max | Pro Non-Think | Pro High | Pro Max |
|-----------|----------------|------------|-----------|---------------|----------|---------|
| MMLU-Pro | 83.0 | 86.4 | 86.2 | 82.9 | 87.1 | **87.5** |
| GPQA Diamond | 71.2 | 87.4 | 88.1 | 72.9 | 89.1 | **90.1** |
| HLE | 8.1 | 29.4 | 34.8 | 7.7 | 34.5 | **37.7** |
| LiveCodeBench | 55.2 | 88.4 | 91.6 | 56.8 | 89.8 | **93.5** |
| Codeforces | - | 2816 | 3052 | - | 2919 | **3206** |
| SWE Verified | 73.7 | 78.6 | 79.0 | 73.6 | 79.4 | **80.6** |
| BrowseComp | - | 53.5 | 73.2 | - | 80.4 | **83.4** |
| MRCR 1M | 37.5 | 76.9 | 78.7 | 44.7 | 83.3 | **83.5** |

### Base Model Benchmarks

| Benchmark | V3.2-Base | V4-Flash-Base | V4-Pro-Base |
|-----------|-----------|---------------|-------------|
| MMLU (5-shot) | 87.8 | 88.7 | **90.1** |
| MMLU-Pro | 65.5 | 68.3 | **73.5** |
| MMLU-Redux | 87.5 | 89.4 | **90.8** |
| HumanEval | 62.8 | 69.5 | **76.8** |
| GSM8K | 91.1 | 90.8 | **92.6** |
| MATH | 60.5 | 57.4 | **64.5** |
| LongBench-V2 | 40.2 | 44.7 | **51.5** |
| Simple-QA verified | 28.3 | 30.1 | **55.2** |

## Reasoning Parameter

OpenRouter API parameter: `reasoning` with values `high` or `xhigh`
- `high` — extended reasoning chains (~5K reasoning tokens typical)
- `xhigh` — maximum reasoning, maps to max effort (~20K reasoning tokens typical)

Also supported: `include_reasoning` (boolean) — whether to include reasoning tokens in the response.

## Cost Calculation

Reasoning tokens are output tokens. Formula:
```
cost = (input_tokens × input_price + output_tokens × output_price) / 1_000_000
```

Where output_tokens includes both reasoning tokens and final response tokens.

### V4 Flash Examples (per request, pricing as of May 2026):

| Scenario | Input | Reasoning | Output | Total Cost |
|----------|-------|-----------|--------|------------|
| No reasoning | 10K | 0 | 2K | $0.0020 |
| reasoning=high (~5K thinking tokens) | 10K | 5K | 2K | $0.0120 |
| reasoning=xhigh (~20K thinking tokens) | 10K | 20K | 2K | $0.0600 |

### V4 Pro Examples (per request):

| Scenario | Input | Reasoning | Output | Total Cost |
|----------|-------|-----------|--------|------------|
| No reasoning | 10K | 0 | 2K | $0.0044 |
| reasoning=high (~5K thinking tokens) | 10K | 5K | 2K | $0.0485 |
| reasoning=xhigh (~20K thinking tokens) | 10K | 20K | 2K | $0.1780 |

### Cache Pricing (DeepSeek API, May 2026)

| Model | Cache Miss | Cache Hit | Cache Write |
|-------|-----------|-----------|-------------|
| V4 Flash | $0.14/1M | $0.0028/1M (98% off) | Free ≤128K |
| V4 Pro | $0.435/1M | $0.003625/1M (99% off) | Free ≤128K |

Real-world example (54.3M total tokens, actual user data):
- Input (cache miss): 3,987,588 × $0.14/1M = $0.5583
- Output: 199,118 × $0.28/1M = $0.0558
- Cache read (hit): 50,094,336 × $0.0028/1M = $0.1403
- **V4 Flash total: $0.7543** (cache is 92% of tokens but only 19% of cost)

## Context Windows

- V4 Flash (free): 1,048,576 tokens
- V4 Flash: 1,048,576 tokens
- V4 Pro: 1,048,576 tokens

## Source

Benchmarks sourced from HuggingFace model card raw README: `huggingface.co/deepseek-ai/DeepSeek-V4-Pro/raw/main/README.md`
