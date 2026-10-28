#!/usr/bin/env python3
"""Smoke test for the LLM setup: one tiny request, prints provider, model,
latency and the answer. Run it after putting the API key into .env."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from evolve_demo import llm  # noqa: E402


def main():
    cfg = llm.settings()
    print(f"provider {cfg['provider']}, model {cfg['model']}, endpoint {cfg['base_url']}")
    t = time.time()
    try:
        answer = llm.complete('Rewrite as a boolean search query (use AND/OR, quote phrases), '
                              'output only the query: senior Power BI consultant who also knows dbt.',
                              max_tokens=512)
    except llm.LLMError as e:
        sys.exit(f"FAILED: {e}")
    print(f"answer in {time.time() - t:.1f}s: {answer.strip()}")


if __name__ == "__main__":
    main()
