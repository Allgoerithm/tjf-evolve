"""Small chat-completion client (plain HTTP via requests) for any
OpenAI-compatible endpoint. Two providers are preconfigured:

  gemini      Gemini API, OpenAI-compatible endpoint (default)
  openrouter  OpenRouter (optional)

Configuration comes from environment variables, optionally from a `.env` file
in the repository root (see `.env.example`); real environment variables win.

  LLM_PROVIDER     gemini | openrouter                (default: gemini)
  GEMINI_API_KEY / OPENROUTER_API_KEY                 key of the chosen provider
  LLM_API_KEY      overrides the provider-specific key variable
  LLM_API_BASE     overrides the provider's base URL  (any OpenAI-compatible endpoint)
  REWRITER_MODEL   overrides the provider's default model
  LLM_CACHE_DIR    if set, responses are cached on disk (keyed by request)
"""
import hashlib
import json
import os
import random
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROVIDERS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_env": "GEMINI_API_KEY",
        "model": "gemini-3.5-flash-lite",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "model": "google/gemini-3.5-flash-lite",
    },
}


class LLMError(Exception):
    """The LLM call failed for good (bad request, missing key, retries used up)."""


def load_dotenv(path=os.path.join(ROOT, ".env")):
    """Read KEY=VALUE lines from .env into os.environ (existing variables win)."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def settings(provider=None):
    """Resolved provider, base URL, API key and model (the key may be empty)."""
    load_dotenv()
    provider = provider or os.environ.get("LLM_PROVIDER", "gemini")
    if provider not in PROVIDERS:
        raise LLMError(f"unknown LLM_PROVIDER '{provider}' (use one of {', '.join(PROVIDERS)})")
    p = PROVIDERS[provider]
    return {
        "provider": provider,
        "base_url": (os.environ.get("LLM_API_BASE") or p["base_url"]).rstrip("/"),
        "api_key": os.environ.get("LLM_API_KEY") or os.environ.get(p["key_env"], ""),
        "key_env": p["key_env"],
        "model": os.environ.get("REWRITER_MODEL") or p["model"],
    }


def complete(prompt, *, system=None, model=None, provider=None, temperature=None, max_tokens=2048,
             reasoning_effort=None, timeout=90, retries=4):
    """Send one chat completion and return the text of the answer.

    temperature/reasoning_effort are only sent when given. max_tokens also
    covers the model's internal thinking tokens, so keep it generous.
    Rate limits (429), server errors (5xx) and connection problems are retried
    with exponential backoff; everything else raises LLMError immediately."""
    cfg = settings(provider)
    if not cfg["api_key"]:
        raise LLMError(f"no API key: set {cfg['key_env']} (environment or .env file)")
    model = model or cfg["model"]
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if temperature is not None:
        body["temperature"] = temperature
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort

    cache_file = None
    if os.environ.get("LLM_CACHE_DIR"):
        key = hashlib.sha256(json.dumps([cfg["base_url"], body], sort_keys=True).encode()).hexdigest()
        cache_file = os.path.join(os.environ["LLM_CACHE_DIR"], key + ".json")
        if os.path.isfile(cache_file):
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)["text"]

    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    last = None
    for attempt in range(retries + 1):
        wait = min(30, 2 ** attempt) * random.uniform(0.7, 1.3)   # exponential backoff
        try:
            r = requests.post(f"{cfg['base_url']}/chat/completions", json=body, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            last = f"connection problem: {e}"
        else:
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}: {r.text[:200]}"
                retry_after = r.headers.get("Retry-After", "")
                if retry_after.replace(".", "", 1).isdigit():
                    wait = float(retry_after)
            elif r.status_code >= 400:
                raise LLMError(f"HTTP {r.status_code} from {cfg['provider']}: {r.text[:300]}")
            else:
                try:
                    choice = r.json()["choices"][0]
                    text = choice["message"]["content"]
                except (ValueError, KeyError, IndexError, TypeError):
                    raise LLMError(f"unexpected response: {r.text[:300]}")
                if not text:
                    raise LLMError(f"empty answer (finish reason: {choice.get('finish_reason')}); raise max_tokens?")
                if cache_file:
                    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump({"text": text}, f)
                return text
        if attempt < retries:
            time.sleep(wait)
    raise LLMError(f"giving up after {retries + 1} attempts; last problem: {last}")
