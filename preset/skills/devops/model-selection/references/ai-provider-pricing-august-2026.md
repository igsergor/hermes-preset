# AI Provider Pricing Research Reference (August 2026)

## Quick Extraction Pattern for Pricing Pages

```bash
# Universal pattern - works on any public pricing/doc page
curl -s "https://r.jina.ai/https://<provider>.com/pricing"
curl -s "https://r.jina.ai/https://<provider>.com/docs/pricing"
curl -s "https://r.jina.ai/https://<provider>.com/api/pricing"
```

## Provider-Specific URLs (Verified August 2026)

| Provider | Pricing URL | Docs URL | Notes |
|----------|-------------|----------|-------|
| **OpenAI** | https://openai.com/pricing | https://platform.openai.com/docs/pricing | ChatGPT plans + API separate |
| **Anthropic** | https://www.anthropic.com/pricing | https://docs.anthropic.com/en/docs/about-claude/pricing | Pro/Max/Team/Enterprise |
| **Google (Gemini API)** | https://ai.google.dev/pricing | https://ai.google.dev/gemini-api/docs/pricing | Free tier generous, paid per 1M tokens |
| **Mistral** | https://mistral.ai/pricing | https://docs.mistral.ai/ | Le Chat (chat) + API separate |
| **xAI (Grok)** | https://x.ai/api/pricing (404) → console.x.ai | https://docs.x.ai/ | Grok 4.6: $2/1M in, $6/1M out |
| **Groq** | https://console.groq.com/settings/billing | https://console.groq.com/docs/rate-limits | Free tier: 30 RPM, generous TPM |
| **Together AI** | https://www.together.ai/pricing | https://docs.together.ai/ | Cheapest open models, fine-tuning |
| **DeepInfra** | https://deepinfra.com/pricing | https://docs.deepinfra.com/ | Cheapest overall (DeepSeek V4 Flash $0.08/1M) |
| **Fireworks AI** | https://fireworks.ai/pricing | https://docs.fireworks.ai/ | LoRA at base price, serverless training |
| **AWS Bedrock** | https://aws.amazon.com/bedrock/pricing/ | https://docs.aws.amazon.com/bedrock/ | Complex regional, PTU reservations |
| **Azure OpenAI** | https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/ | https://learn.microsoft.com/azure/ai-services/openai/ | PTUs, data zones, batch 50% off |
| **Perplexity** | https://www.perplexity.ai/pro | https://help.perplexity.ai/ | Pro $17/mo (annual), Enterprise custom |
| **Cohere** | https://cohere.com/pricing | https://docs.cohere.com/ | Enterprise-focused, Model Vault |
| **OpenRouter** | https://openrouter.ai/pricing | https://openrouter.ai/docs | 5.5% fee, 500+ models, BYOK $25k/mo free |

## Token Cost Comparison (Input $/1M tokens, cheapest model each)

| Provider | Cheapest Model | Input $/1M | Output $/1M | Tokens/$1 (in) |
|----------|----------------|------------|-------------|----------------|
| **DeepInfra** | DeepSeek V4 Flash 0731 | **$0.08** | $0.18 | **12.5M** |
| **DeepInfra** | Qwen3.5-9B / Llama 3.1 8B Turbo | $0.10 | $0.15-0.32 | 10M |
| **Together AI** | DeepSeek V4 Flash 0731 | $0.14 | $0.28 | 7.1M |
| **Together AI** | Llama 3.1 8B / Qwen 3.5 9B | $0.14-0.17 | $0.14-0.25 | 5.9-7.1M |
| **Fireworks** | Llama 3.1 8B (serverless) | ~$0.10-0.20 | ~$0.30-0.60 | 5-10M |
| **OpenRouter** | Routes to above | Same as source | Same as source | Same as source |
| **AWS Bedrock** | Nova Micro / Llama 3.2 1B | ~$0.04-0.10 | ~$0.10-0.20 | 10-25M |
| **Google Gemini** | Gemini 2.5 Flash / 2.0 Flash-Lite | $0.10-0.30 | $0.40-2.50 | 3.3-10M |
| **xAI** | Grok 4.6 | $2.00 | $6.00 | 0.5M |

## Subscription Chat Products ≤$30/mo

| Plan | Price | Models | Key Features |
|------|-------|--------|--------------|
| **Perplexity Pro** | $17/mo (annual) | Sonar 2, GPT-5.6, Gemini 3.7, Claude 5, Kimi K3, GLM 5.2 | Deep Research, Computer (code exec), Citations, Premium data |
| **Mistral Le Chat Pro** | $14.99/mo | Mistral Medium/Large, Voxtral, Pixtral | Vibe coding agent, $30 API credits/mo, 15GB docs |
| **OpenAI ChatGPT Plus** | $20/mo | GPT-5.6 Sol/Terra/Luna, Thinking Mini | Codex, Deep Research, Projects, Custom GPTs, Voice+Video |
| **Anthropic Claude Pro** | $17/mo (annual) | Opus 5, Sonnet 5, Haiku 4.5 | Claude Code, Cowork, Design, Science, Artifacts, 200k ctx |
| **Google One AI Premium** | $19.99/mo | Gemini Advanced (2.5 Pro) | Workspace integration, 2TB Drive, NotebookLM Plus |

## Free Tiers Worth Knowing

| Provider | Free Models | Limits | Best For |
|----------|-------------|--------|----------|
| **Groq** | Llama 3.3 70B, GPT-OSS 120B/20B, Qwen 3.6 27B | 30 RPM, 1K-14K RPD, 6K-70K TPM | Speed, high throughput |
| **Google AI Studio** | Gemini 2.5 Flash/Pro, 2.0 Flash, 1.5 Flash | 1,500 RPD (Flash), 500 RPD (Pro) | Long context (1M+), grounding |
| **OpenRouter** | 25+ free models | 50 req/day | Model sampling, BYOK $25k/mo free |
| **Mistral Le Chat** | All models (limited) | Limited messages/searches | EU privacy, Vibe agent trial |
| **Perplexity** | Sonar, basic models | Limited Deep Research | Quick answers with citations |

## Hidden Costs & Gotchas

- **OpenRouter**: 5.5% platform fee on pay-as-you-go; BYOK avoids fee up to $25k/mo list price
- **Groq**: Free tier rate limits — upgrade to Dev plan for Batch/Flex processing
- **DeepInfra**: Usage tiers — invoicing at $20, $100, $500, $2k, $10k; set spend limits
- **Google Gemini API**: Free tier data **used to improve products**; paid tier opts out
- **AWS Bedrock / Azure OpenAI**: Complex regional pricing, PTU reservations for predictable load
- **Perplexity Pro**: Computer credits expire monthly; "Pro" ≠ API access (separate API platform)
- **Mistral Le Chat Pro**: $30 API credits included but expire monthly; Vibe CLI requires auth

## Research Workflow for Pricing Updates

1. **Start with known provider list** (table above)
2. **Extract each via r.jina.ai** — `curl -s "https://r.jina.ai/https://<url>"`
3. **Parse for tables** — Look for markdown tables with `$/1M tokens` or `$/month`
4. **Note date** — Pricing changes monthly; always capture extraction date
5. **Cross-reference** — Check OpenRouter models page for provider routing reality
6. **Document free tiers separately** — Often more valuable than paid for dev/test