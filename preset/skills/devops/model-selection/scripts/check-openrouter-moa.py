#!/usr/bin/env python3
"""
Quick script to identify Mixture of Agents (MoA) vs Mixture of Experts (MoE)
models in OpenRouter model picker. Run with:
    python3 ~/.hermes/skills/devops/model-selection/scripts/check-openrouter-moa.py
"""
import json
import sys
import urllib.request

def fetch_models():
    url = "https://openrouter.ai/api/v1/models"
    with urllib.request.urlopen(url) as response:
        return json.load(response)

def classify_model(model):
    """Classify a model as MoA, MoE, Router, or Regular."""
    model_id = model['id'].lower()
    name = model.get('name', '').lower()
    desc = model.get('description', '').lower()
    
    # Mixture of Agents (multi-model deliberation)
    if model_id == 'openrouter/fusion':
        return 'MoA (Mixture of Agents)'
    
    # Routers (route to single model)
    if model_id.startswith('openrouter/') and model_id not in ['openrouter/fusion', 'openrouter/bodybuilder']:
        return 'Router (single-model)'
    if 'router' in model_id or 'router' in name:
        return 'Router (single-model)'
    
    # Mixture of Experts (architecture inside one model)
    moe_indicators = ['mixture-of-experts', 'mixture of experts', 'moe', 'sparse mixture', 'mixture-of-expert']
    if any(ind in desc for ind in moe_indicators):
        return 'MoE (Mixture of Experts)'
    
    # Check for MoE in ID patterns (common naming)
    if any(x in model_id for x in ['-a', 'maverick', 'scout', 'nemotron-3-ultra', 'nemotron-3-super', 
                                     'hy3', 'deepseek-v4', 'qwen3-235b', 'qwen3-30b', 'qwen3-coder',
                                     'llama-4', 'mixtral', 'kimi-k2', 'glm-4.5', 'step-3', 'ernie-4.5',
                                     'minimax-m1', 'solar-pro', 'trinity-mini', 'gpt-oss', 'lfm-2']):
        # These are known MoE models by ID pattern
        return 'MoE (likely)'
    
    return 'Regular (dense)'

def main():
    data = fetch_models()
    
    print("=== OpenRouter Model Classification ===\n")
    
    # MoA models
    moa = [m for m in data['data'] if classify_model(m) == 'MoA (Mixture of Agents)']
    if moa:
        print("🧠 MIXTURE OF AGENTS (MoA) - Multi-model deliberation:")
        for m in moa:
            pricing = m.get('pricing', {})
            print(f"  {m['id']} — {m.get('name', 'N/A')}")
            print(f"    Pricing: {pricing.get('prompt', 'N/A')}/{pricing.get('completion', 'N/A')} per 1M tokens")
            print(f"    Context: {m.get('context_length', 'N/A')}")
            print(f"    {m.get('description', '')[:120]}...")
            print()
    
    # Routers
    routers = [m for m in data['data'] if classify_model(m) == 'Router (single-model)']
    if routers:
        print("🔀 ROUTERS (route to single model):")
        for m in routers:
            pricing = m.get('pricing', {})
            print(f"  {m['id']} — {m.get('name', 'N/A')}")
            print(f"    Pricing: {pricing.get('prompt', 'N/A')}/{pricing.get('completion', 'N/A')}")
            print(f"    {m.get('description', '')[:100]}...")
            print()
    
    # MoE models (top 15)
    moe = [m for m in data['data'] if 'MoE' in classify_model(m)]
    if moe:
        print(f"🏗️  MIXTURE OF EXPERTS (MoE) models found: {len(moe)} total")
        print("  (showing first 15)")
        for m in moe[:15]:
            pricing = m.get('pricing', {})
            p_str = f"{pricing.get('prompt', 'N/A')}/{pricing.get('completion', 'N/A')}"
            print(f"  {m['id']} — {m.get('name', 'N/A')} — ${p_str}/1M — ctx: {m.get('context_length', 'N/A')}")

if __name__ == '__main__':
    main()