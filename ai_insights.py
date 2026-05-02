"""
ai_insights.py
AI budget analysis - chooses between local Ollama and Anthropic.

Supports both one-shot insight and multi-turn chat.
"""
from __future__ import annotations

import json
import re
import urllib.request
from collections.abc import Sequence

# A message dict used for conversation history
# {"role": "user" | "assistant", "content": str}
Message = dict[str, str]
ContextPayload = str | dict[str, object]

DEFAULT_OLLAMA_MODEL = "llama3.2"
OLLAMA_API_TAGS_URL = "http://127.0.0.1:11434/api/tags"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
_ollama_model_cache: str | None = None


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def _get_provider_preference() -> str:
    try:
        from backend import database as db
        return db.get_ai_provider_mode()
    except Exception:
        return "smart"


def _get_provider_order(api_key: str, preference: str | None = None) -> list[str]:
    mode = preference or _get_provider_preference()
    has_online = bool(api_key)

    if mode == "online_first":
        return (["anthropic"] if has_online else []) + ["ollama"]
    if mode == "offline_first":
        return ["ollama"] + (["anthropic"] if has_online else [])
    return (["anthropic"] if has_online else []) + ["ollama"]


# ---------------------------------------------------------------------------
# Ollama (offline / local LLM)
# ---------------------------------------------------------------------------

def _is_ollama_reachable(timeout: float = 0.75) -> bool:
    try:
        with urllib.request.urlopen(OLLAMA_API_TAGS_URL, timeout=timeout):
            return True
    except Exception:
        return False


def _pick_ollama_model() -> str:
    global _ollama_model_cache
    if _ollama_model_cache:
        return _ollama_model_cache

    try:
        import ollama

        data = ollama.list()
        if hasattr(data, "models"):
            names = [getattr(m, "model", None) or getattr(m, "name", None) for m in data.models]
        else:
            names = [m.get("model") or m.get("name") for m in data.get("models", [])]

        names = [n for n in names if n]
        for preferred in (
            "llama3.2:1b",
            "qwen2.5:0.5b",
            "phi3:mini",
            "gemma2:2b",
            "llama3.2",
            "qwen2.5",
            "phi3",
            "mistral",
            "gemma",
        ):
            for model in names:
                if preferred in model.lower():
                    _ollama_model_cache = model
                    return model

        _ollama_model_cache = names[0] if names else DEFAULT_OLLAMA_MODEL
        return _ollama_model_cache
    except Exception:
        return DEFAULT_OLLAMA_MODEL


def _ask_ollama_chat(messages: list[Message]) -> str | None:
    """Send a full conversation history to Ollama. Returns reply or None."""
    if not _is_ollama_reachable():
        return None

    try:
        import ollama

        response = ollama.chat(
            model=_pick_ollama_model(),
            messages=messages,
            options={"temperature": 0.35},
        )
        if hasattr(response, "message"):
            return response.message.content
        return response["message"]["content"]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Anthropic API (online fallback)
# ---------------------------------------------------------------------------

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
        "max_tokens": 500,
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

def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9_]+", (text or "").lower())
        if len(token) > 1
    }


def _fallback_rank_documents(query: str, documents: Sequence[str], limit: int) -> list[str]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return [doc for doc in documents[:limit] if doc]

    scored: list[tuple[int, str]] = []
    for doc in documents:
        if not doc:
            continue
        doc_tokens = _tokenize(doc)
        overlap = len(query_tokens & doc_tokens)
        if overlap > 0:
            scored.append((overlap, doc))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [doc for _, doc in scored[:limit]]


def _retrieve_documents(query: str, documents: Sequence[str], limit: int = 6) -> list[str]:
    docs = [doc.strip() for doc in documents if isinstance(doc, str) and doc.strip()]
    if not docs:
        return []
    if not query.strip():
        return docs[:limit]

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import linear_kernel

        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform(docs + [query])
        doc_matrix = matrix[:-1]
        query_vector = matrix[-1]
        scores = linear_kernel(query_vector, doc_matrix).flatten()
        ranked_indices = sorted(
            range(len(docs)),
            key=lambda idx: float(scores[idx]),
            reverse=True,
        )
        ranked_docs = [docs[idx] for idx in ranked_indices if float(scores[idx]) > 0]
        return ranked_docs[:limit] if ranked_docs else _fallback_rank_documents(query, docs, limit)
    except Exception:
        return _fallback_rank_documents(query, docs, limit)


def _latest_user_message(history: Sequence[Message]) -> str:
    for message in reversed(history):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def _resolve_financial_context(financial_context: ContextPayload, history: Sequence[Message]) -> str:
    if isinstance(financial_context, str):
        return financial_context

    summary = str(financial_context.get("summary", "")).strip()
    source_group = str(financial_context.get("rag_source_group", "")).strip()
    documents = financial_context.get("documents", [])
    documents = documents if isinstance(documents, list) else []
    query = _latest_user_message(history)
    retrieved: list[str] = []

    if source_group:
        try:
            from backend import database as db

            retrieved_rows = db.search_rag_chunks(query, source_group=source_group, limit=6)
            retrieved = [
                f"{row['title']} | {row['text']}"
                for row in retrieved_rows
            ]
        except Exception:
            retrieved = []

    if not retrieved:
        retrieved = _retrieve_documents(query, documents, limit=6)

    sections: list[str] = []
    if summary:
        sections.append("=== CURRENT FINANCIAL SUMMARY ===\n" + summary)
    if retrieved:
        sections.append("=== RETRIEVED RELEVANT RECORDS ===\n" + "\n".join(f"- {doc}" for doc in retrieved))
    elif documents:
        sections.append("=== RETRIEVED RELEVANT RECORDS ===\n- No closely related historical records matched this question.")

    return "\n\n".join(section for section in sections if section).strip()


def _build_system_prompt(financial_context: str) -> str:
    return f"""You are a smart, friendly personal finance advisor built into a budget tracking app.
Your user can be from any country - adapt your language based on their currency and spending context.

You have access to the user's current financial data below. Use it to give accurate, personalized advice.
When the user asks questions, answer based on this data. Be conversational, concise, and encouraging.

Guidelines:
- Write in plain, friendly language anyone can understand
- Keep replies concise - 2 to 4 short paragraphs or bullet points max
- Use the currency symbol from the data (do not assume it's always peso)
- Flag budget issues clearly but kindly
- Give actionable tips the user can act on right now
- Do NOT use markdown headers or bold formatting - plain text or bullet points only
- Treat the "Current Financial Summary" section as the source of truth for exact balances, monthly totals, and current budget status
- Treat the "Retrieved Relevant Records" section as the historical evidence most relevant to the user's latest question
- If the retrieved records do not contain enough evidence for a historical claim, say so instead of guessing

NOTIFICATION RULE - If you spot an urgent financial issue (budget exceeded, bill overdue, dangerously low balance, etc.), append this exact tag on its own line at the very end of your reply:
[NOTIFY: Short Alert Title | One-sentence description of the issue.]
Only include it when truly warranted. Do not include it for routine answers.
Examples:
[NOTIFY: Budget Exceeded - Food | You've spent 112% of your food budget this month.]
[NOTIFY: Low Balance Warning | Your balance is below your estimated monthly expenses.]
[NOTIFY: Bill Overdue - Electricity | Your electricity bill is past its due date.]

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

def get_ai_insight(expenses_summary: ContextPayload, api_key: str = "") -> str:
    """Legacy one-shot insight (still used if needed)."""
    system = _build_system_prompt(_resolve_financial_context(expenses_summary, []))
    messages: list[Message] = [{"role": "user", "content": _build_initial_prompt()}]
    ollama_messages = [{"role": "user", "content": system + "\n\n" + _build_initial_prompt()}]
    tried_anthropic = False

    for provider in _get_provider_order(api_key):
        if provider == "anthropic":
            tried_anthropic = True
            result = _ask_anthropic_chat(messages, api_key, system_prompt=system)
        else:
            result = _ask_ollama_chat(ollama_messages)

        if result:
            return result.strip()

    if api_key and tried_anthropic:
        return (
            "Your API key was found but we could not reach Anthropic. "
            "Please check your internet connection and try again."
        )

    return (
        "AI is not available right now.\n\n"
        "You have two options to enable it:\n"
        "- Offline: Install Ollama (ollama.com) and pull a model like llama3.2 - "
        "works without internet once set up.\n"
        "- Online: Add your Anthropic API key in Settings > AI Setup - "
        "works on any device with an internet connection.\n\n"
        "Tap Ask AI again once either option is ready."
    )


def chat_with_ai(
    history: list[Message],
    financial_context: ContextPayload,
    api_key: str = "",
) -> str:
    """
    Multi-turn chat. `history` is the full conversation so far
    (list of {"role": "user"/"assistant", "content": str}).
    Returns the AI's next reply as a string.
    """
    system = _build_system_prompt(_resolve_financial_context(financial_context, history))
    ollama_messages: list[Message] = [{"role": "user", "content": system}] + history
    tried_anthropic = False

    for provider in _get_provider_order(api_key):
        if provider == "anthropic":
            tried_anthropic = True
            result = _ask_anthropic_chat(history, api_key, system_prompt=system)
        else:
            result = _ask_ollama_chat(ollama_messages)

        if result:
            return result.strip()

    if api_key and tried_anthropic:
        return (
            "Could not reach Anthropic. Please check your internet connection and try again."
        )

    return (
        "AI is not available. Enable Ollama (offline) or add your "
        "Anthropic API key in Settings > AI Setup."
    )
