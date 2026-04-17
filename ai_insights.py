"""
ai_insights.py
AI budget analysis — tries Ollama (offline) first, falls back to
Anthropic claude-haiku (online) if an API key is stored.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error


# ---------------------------------------------------------------------------
# Ollama (offline / local LLM)
# ---------------------------------------------------------------------------

def _pick_ollama_model() -> str:
    try:
        import ollama
        data = ollama.list()
        if hasattr(data, "models"):
            names = [getattr(m, "model", None) or getattr(m, "name", None) for m in data.models]
        else:
            names = [m.get("model") or m.get("name") for m in data.get("models", [])]
        names = [n for n in names if n]
        for preferred in ("llama3.2", "llama3", "qwen2.5", "phi3", "mistral", "gemma"):
            for model in names:
                if preferred in model.lower():
                    return model
        return names[0] if names else "llama3.2"
    except Exception:
        return "llama3.2"


def _ask_ollama(prompt: str) -> str | None:
    """Returns response text, or None if Ollama is unavailable."""
    try:
        import ollama
        model = _pick_ollama_model()
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.5},
        )
        if hasattr(response, "message"):
            return response.message.content
        return response["message"]["content"]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Anthropic API (online fallback)
# ---------------------------------------------------------------------------

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL   = "claude-haiku-4-5-20251001"


def _ask_anthropic(prompt: str, api_key: str) -> str | None:
    """Returns response text, or None if the call fails."""
    if not api_key:
        return None
    payload = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 600,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["content"][0]["text"]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Prompt builder — universal, language-adaptive
# ---------------------------------------------------------------------------

def _build_prompt(expenses_summary: str) -> str:
    return f"""You are a smart, friendly personal finance advisor built into a budget tracking app.
Your user can be from any country — adapt your tone and language accordingly based on their currency and spending context.

Your job: analyze the user's spending data and give clear, practical, and encouraging financial advice.

Guidelines:
- Write in plain, friendly English that anyone can understand
- Keep it concise: 4–5 bullet points, each 1–2 sentences max
- Use the currency symbol shown in the data (do not assume it's always peso)
- If balance is low or a category is over budget, flag it clearly but kindly
- Give at least one specific, actionable tip the user can act on right now
- If spending looks healthy, say so and encourage keeping it up
- End with one short motivational sentence
- Do NOT use slang, regional expressions, or assume the user's nationality
- Do NOT use markdown headers or bold — plain bullet points only

User's financial data:
{expenses_summary}
"""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_ai_insight(expenses_summary: str, api_key: str = "") -> str:
    prompt = _build_prompt(expenses_summary)

    # 1 — Try offline Ollama first
    result = _ask_ollama(prompt)
    if result:
        return result.strip()

    # 2 — Fall back to Anthropic API (online)
    if api_key:
        result = _ask_anthropic(prompt, api_key)
        if result:
            return result.strip()
        return (
            "⚠️ Your API key was found but we could not reach Anthropic. "
            "Please check your internet connection and try again."
        )

    # 3 — Both unavailable — clear instructions
    return (
        "🤖 AI is not available right now.\n\n"
        "You have two options to enable it:\n"
        "• Offline: Install Ollama (ollama.com) and pull a model like llama3.2 — "
        "works without internet once set up.\n"
        "• Online: Add your Anthropic API key in Settings → AI Setup — "
        "works on any device with an internet connection.\n\n"
        "Tap Ask AI again once either option is ready."
    )