"""
ai_insights.py
AI budget analysis — tries Ollama (offline) first, falls back to
Anthropic claude-haiku (online) if an API key is stored.

Supports both one-shot insight and multi-turn chat.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error

# A message dict used for conversation history
# {"role": "user" | "assistant", "content": str}
Message = dict[str, str]


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


def _ask_ollama_chat(messages: list[Message]) -> str | None:
    """Send a full conversation history to Ollama. Returns reply or None."""
    try:
        import ollama
        model = _pick_ollama_model()
        response = ollama.chat(
            model=model,
            messages=messages,
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


def _ask_anthropic_chat(
    messages: list[Message],
    api_key: str,
    system_prompt: str = "",
) -> str | None:
    """Send full conversation history to Anthropic. Returns reply or None."""
    if not api_key:
        return None
    payload_dict: dict = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 800,
        "messages": messages,
    }
    if system_prompt:
        payload_dict["system"] = system_prompt

    payload = json.dumps(payload_dict).encode("utf-8")
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
# System / context prompt builder
# ---------------------------------------------------------------------------

def _build_system_prompt(financial_context: str) -> str:
    return f"""You are a smart, friendly personal finance advisor built into a budget tracking app.
Your user can be from any country — adapt your language based on their currency and spending context.

You have access to the user's current financial data below. Use it to give accurate, personalized advice.
When the user asks questions, answer based on this data. Be conversational, concise, and encouraging.

Guidelines:
- Write in plain, friendly language anyone can understand
- Keep replies concise — 2 to 4 short paragraphs or bullet points max
- Use the currency symbol from the data (do not assume it's always peso)
- Flag budget issues clearly but kindly
- Give actionable tips the user can act on right now
- Do NOT use markdown headers or bold formatting — plain text or bullet points only

Current financial data:
{financial_context}
"""


def _build_initial_prompt() -> str:
    """The opening message the AI sends when the chat is first opened."""
    return (
        "Please greet the user warmly and give a concise analysis of their current "
        "financial data in 3 to 4 bullet points. Flag any concerns, highlight anything "
        "positive, and invite them to ask follow-up questions."
    )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def get_ai_insight(expenses_summary: str, api_key: str = "") -> str:
    """Legacy one-shot insight (still used if needed)."""
    system = _build_system_prompt(expenses_summary)
    messages: list[Message] = [{"role": "user", "content": _build_initial_prompt()}]

    # Ollama: pass system as first user message since it doesn't have a system param
    ollama_messages = [{"role": "user", "content": system + "\n\n" + _build_initial_prompt()}]
    result = _ask_ollama_chat(ollama_messages)
    if result:
        return result.strip()

    if api_key:
        result = _ask_anthropic_chat(messages, api_key, system_prompt=system)
        if result:
            return result.strip()
        return (
            "⚠️ Your API key was found but we could not reach Anthropic. "
            "Please check your internet connection and try again."
        )

    return (
        "🤖 AI is not available right now.\n\n"
        "You have two options to enable it:\n"
        "• Offline: Install Ollama (ollama.com) and pull a model like llama3.2 — "
        "works without internet once set up.\n"
        "• Online: Add your Anthropic API key in Settings → AI Setup — "
        "works on any device with an internet connection.\n\n"
        "Tap Ask AI again once either option is ready."
    )


def chat_with_ai(
    history: list[Message],
    financial_context: str,
    api_key: str = "",
) -> str:
    """
    Multi-turn chat. `history` is the full conversation so far
    (list of {"role": "user"/"assistant", "content": str}).
    Returns the AI's next reply as a string.
    """
    system = _build_system_prompt(financial_context)

    # --- Ollama: inject system as a leading user message ---
    ollama_messages: list[Message] = [
        {"role": "user", "content": system}
    ] + history
    result = _ask_ollama_chat(ollama_messages)
    if result:
        return result.strip()

    # --- Anthropic: use proper system param ---
    if api_key:
        result = _ask_anthropic_chat(history, api_key, system_prompt=system)
        if result:
            return result.strip()
        return (
            "⚠️ Could not reach Anthropic. "
            "Please check your internet connection and try again."
        )

    return (
        "🤖 AI is not available. Enable Ollama (offline) or add your "
        "Anthropic API key in Settings → AI Setup."
    )