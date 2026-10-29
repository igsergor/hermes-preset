#!/usr/bin/env python3
"""
Check Nous Inference API for free models.
Run with: python3 ~/.hermes/skills/devops/model-selection/scripts/check-nous-api-free.py
"""

import json
import sys
import urllib.request

def fetch_nous_models():
    """Fetch models from Nous inference API."""
    url = "https://inference-api.nousresearch.com/v1/models"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Hermes-Agent/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)
    except Exception as e:
        print(f"Error fetching Nous models: {e}", file=sys.stderr)
        return None

def main():
    data = fetch_nous_models()
    if not data or 'data' not in data:
        print("Failed to fetch models from Nous API")
        return 1
    
    models = data['data']
    
    print("=== ALL MODELS ===")
    for m in models:
        model_id = m.get('id', '?')
        owned_by = m.get('owned_by', '?')
        print(f"{model_id} | owned_by: {owned_by}")
    
    print("\n=== FREE MODELS (contains ':free') ===")
    free_models = [m for m in models if ':free' in m.get('id', '')]
    for m in free_models:
        model_id = m.get('id', '?')
        owned_by = m.get('owned_by', '?')
        print(f"{model_id} | owned_by: {owned_by}")
    
    print(f"\nTotal models: {len(models)}")
    print(f"Free models: {len(free_models)}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())