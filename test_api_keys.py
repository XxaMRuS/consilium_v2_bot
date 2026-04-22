#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to check API keys loading
"""
import os
from dotenv import load_dotenv

print("=" * 50)
print("API KEYS LOADING TEST")
print("=" * 50)
print()

# Load .env
load_dotenv()

# Check keys
api_keys = {
    'YANDEX_API_KEY': os.getenv('YANDEX_API_KEY'),
    'GROQ_API_KEY': os.getenv('GROQ_API_KEY'),
    'GEMINI_API_KEY': os.getenv('GEMINI_API_KEY'),
    'OPENROUTER_API_KEY': os.getenv('OPENROUTER_API_KEY'),
    'DEEPSEEK_API_KEY': os.getenv('DEEPSEEK_API_KEY'),
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY')
}

print("API Keys Status:")
print("-" * 50)
for key, value in api_keys.items():
    if value:
        # Show only first 8 and last 4 characters for security
        masked = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else value
        print(f"[OK] {key}: {masked}")
    else:
        print(f"[FAIL] {key}: NOT LOADED")

print()
print("=" * 50)
loaded_count = sum(1 for v in api_keys.values() if v)
print(f"Loaded: {loaded_count}/{len(api_keys)} keys")
print("=" * 50)

if loaded_count == len(api_keys):
    print("[SUCCESS] All API keys loaded successfully!")
else:
    print("[WARNING] Some keys are not loaded. Check .env file.")
