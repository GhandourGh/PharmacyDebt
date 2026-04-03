"""
Ollama LLM client for intent parsing.

Model: qwen2.5:7b  — best free bilingual Arabic/English model.
Runs 100% locally via Ollama (localhost:11434). No cloud APIs.

Fallback: if Ollama is unavailable, caller falls back to rule-based engine.
"""

import json
import logging
import os
import re
import urllib.request
import urllib.error
from typing import Optional

try:
    import config_env

    config_env.load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


def _resolve_ollama_base_url() -> str:
    """
    Ollama API base, no trailing slash.
    - OLLAMA_BASE_URL=http://host:11434 (preferred for Docker / remote)
    - Else OLLAMA_HOST=127.0.0.1:11434 or host:port
    - Default 127.0.0.1 (avoids occasional localhost/IPv6 issues)
    """
    explicit = (os.environ.get("OLLAMA_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    host = (os.environ.get("OLLAMA_HOST") or "").strip()
    if host:
        if host.startswith("http://") or host.startswith("https://"):
            return host.rstrip("/")
        return f"http://{host}".rstrip("/")
    return "http://127.0.0.1:11434"


OLLAMA_BASE_URL = _resolve_ollama_base_url()
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")
# Short timeout for /api/generate (intent JSON) so the UI does not hang
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "25"))
# Longer timeout for /api/chat (conversational + rephrase); CPU-bound models can be slow
OLLAMA_CHAT_TIMEOUT = int(os.environ.get("OLLAMA_CHAT_TIMEOUT", "180"))
# Thinking models (e.g. Qwen3 in Ollama): false = faster replies, no chain-of-thought in the chat.
OLLAMA_THINK = os.environ.get("OLLAMA_THINK", "false").strip().lower() in ("1", "true", "yes")
OLLAMA_CONV_NUM_PREDICT = int(os.environ.get("OLLAMA_CONV_NUM_PREDICT", "160"))
OLLAMA_INTENT_NUM_PREDICT = int(os.environ.get("OLLAMA_INTENT_NUM_PREDICT", "120"))


def ollama_enabled() -> bool:
    """
    If false (default): skip all Ollama requests and UI install hints until you set OLLAMA_ENABLED=true.
    """
    return os.environ.get("OLLAMA_ENABLED", "false").strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# System prompt — bilingual, JSON-enforcing, pharmacy-domain
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an intent parser for a Lebanese pharmacy debt management system.
You understand English, Modern Standard Arabic, and Lebanese Arabizi.

Extract the user's intent and return ONLY a JSON object with this exact schema:
{
  "intent": "check_balance|add_payment|add_debt|list_debtors|add_customer|undo|help|greeting|thanks|farewell|unknown",
  "customer_name": "string or null",
  "amount": number or null,
  "payment_method": "CASH|CARD|CHECK|CREDIT|SPLIT or null",
  "confidence": 0.0-1.0,
  "language_detected": "en|ar|arabizi|mixed"
}

Intent definitions:
- check_balance: user wants to know how much a customer owes
- add_payment: customer made a payment / paid money
- add_debt: customer bought something / owes new money
- list_debtors: show who owes money; if user asks for "top N" / "first N" / "N biggest debtors", set intent list_debtors and put N in amount (it is a count, not dollars)
- add_customer: register a new customer
- undo: reverse / cancel the last action
- help: user needs help or instructions
- greeting: user is saying hello/hi/marhaba/kifak (no action intent)
- thanks: user is expressing gratitude (شكرا, thanks, yeslamo)
- farewell: user is saying goodbye (bye, مع السلامة, yalla bye)
- unknown: cannot determine intent

Rules:
- Extract customer_name as spoken (keep Arabic script if present)
- amount must be a plain number (convert "50 dollar" → 50, "50 alf" → 50000, "alf w nuss" → 1500)
- If payment method not mentioned, use null (do not guess)
- confidence: 0.95+ for very clear, 0.7-0.94 for likely, below 0.7 for unclear
- Never add commentary outside the JSON

Lebanese Arabizi examples:
- "Ahmad dafa3 100 dollar" → {"intent":"add_payment","customer_name":"Ahmad","amount":100,"payment_method":"CASH","confidence":0.97,"language_detected":"arabizi"}
- "choufle adeh 3leh Ali" → {"intent":"check_balance","customer_name":"Ali","amount":null,"payment_method":null,"confidence":0.95,"language_detected":"arabizi"}
- "shou 3leh Ahmad" → {"intent":"check_balance","customer_name":"Ahmad","amount":null,"payment_method":null,"confidence":0.96,"language_detected":"arabizi"}
- "كم عند احمد" → {"intent":"check_balance","customer_name":"أحمد","amount":null,"payment_method":null,"confidence":0.98,"language_detected":"ar"}
- "3ndo samer 50" → {"intent":"add_debt","customer_name":"samer","amount":50,"payment_method":null,"confidence":0.94,"language_detected":"arabizi"}
- "kell l mdyouneen" → {"intent":"list_debtors","customer_name":null,"amount":null,"payment_method":null,"confidence":0.98,"language_detected":"arabizi"}
- "add customer Rania" → {"intent":"add_customer","customer_name":"Rania","amount":null,"payment_method":null,"confidence":0.99,"language_detected":"en"}

Note on Arabic/Arabizi distinctions:
- "choufle/adeh/3leh/shou" without an amount = check_balance (asking how much someone owes)
- "dafa3/paid/wdaf3" with an amount = add_payment (recording money received)
- "3ndo/3ando/owes/dayn" WITH an amount = add_debt (recording new debt, e.g. "3ndo samer 75" = Samer owes 75)
- "3ndo/shou 3leh" WITHOUT an amount = check_balance (asking about existing balance)

Arabic examples:
- "كم عند أحمد" → {"intent":"check_balance","customer_name":"أحمد","amount":null,"payment_method":null,"confidence":0.98,"language_detected":"ar"}
- "أحمد دفع ٥٠" → {"intent":"add_payment","customer_name":"أحمد","amount":50,"payment_method":"CASH","confidence":0.97,"language_detected":"ar"}
"""


class OllamaUnavailableError(Exception):
    """Raised when Ollama is not running or model not loaded."""


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

_ollama_available_cache: Optional[bool] = None


def is_available() -> bool:
    """Check if Ollama is reachable at OLLAMA_BASE_URL. Caches True; False is re-probed next call."""
    global _ollama_available_cache

    if not ollama_enabled():
        return False

    if _ollama_available_cache is True:
        return True

    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/tags",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                _ollama_available_cache = True
                return True
    except Exception as e:
        logger.debug("Ollama probe %s: %s", OLLAMA_BASE_URL, e)

    _ollama_available_cache = False
    return False


def invalidate_cache():
    """Force re-check on next is_available() call."""
    global _ollama_available_cache
    _ollama_available_cache = None


def _chat_response_text(raw: dict) -> str:
    """Extract assistant text from Ollama /api/chat JSON (handles some model variants)."""
    msg = raw.get("message") or {}
    text = (msg.get("content") or "").strip()
    if text:
        return _sanitize_leaked_reasoning(text)
    if OLLAMA_THINK:
        alt = (msg.get("thinking") or raw.get("response") or "").strip()
        return _sanitize_leaked_reasoning(alt)
    return ""


def _sanitize_leaked_reasoning(text: str) -> str:
    """Strip chain-of-thought if the model still emits it in content."""
    if not text:
        return text
    low = text.lower()
    if "thinking process" not in low and "analyze the request" not in low:
        return text.strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if len(ln) > 220:
            continue
        if ln[:2].isdigit() and ". " in ln[:4]:
            continue
        if ln.lstrip().startswith(("* ", "- ", "• ")):
            continue
        lowered = ln.lower()
        if any(
            w in lowered
            for w in ("hello", "hi ", "hey", "مرحب", "أهلا", "كيفك", "help", "sure", "welcome")
        ):
            return ln
    return lines[-1] if lines else text.strip()


def polish_chat_reply(text: str) -> str:
    """Clean model output before saving or showing (after streaming completes)."""
    return _sanitize_leaked_reasoning((text or "").strip())


# ---------------------------------------------------------------------------
# Intent parsing
# ---------------------------------------------------------------------------

def parse_intent(text: str, normalized_text: str = "") -> dict:
    """
    Send text to Ollama for JSON intent extraction.

    Args:
        text: Original user message
        normalized_text: Arabizi-normalized version (may be same as text)

    Returns:
        dict with intent, customer_name, amount, payment_method, confidence, language_detected

    Raises:
        OllamaUnavailableError: If Ollama is not reachable
        ValueError: If response is not valid JSON
    """
    # Use the normalized text if meaningfully different from original
    input_text = normalized_text if normalized_text and normalized_text != text else text

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "system": _SYSTEM_PROMPT,
        "prompt": input_text,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": OLLAMA_INTENT_NUM_PREDICT,
        },
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        invalidate_cache()
        raise OllamaUnavailableError(f"Ollama not reachable: {e}") from e
    except Exception as e:
        invalidate_cache()
        raise OllamaUnavailableError(f"Ollama request failed: {e}") from e

    try:
        outer = json.loads(raw)
        # qwen3 thinking models put output in "thinking", others use "response"
        response_text = outer.get("response") or outer.get("thinking") or "{}"
        # Strip any wrapping markdown code fences
        response_text = response_text.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r"^```[a-z]*\n?", "", response_text)
            response_text = re.sub(r"\n?```$", "", response_text)
        # For thinking models the JSON may be inline — find first { ... }
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)
        result = json.loads(response_text)
    except (json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Ollama returned invalid JSON: {raw[:200]}") from e

    # Validate and normalise fields
    result.setdefault("intent", "unknown")
    result.setdefault("customer_name", None)
    result.setdefault("amount", None)
    result.setdefault("payment_method", None)
    result.setdefault("confidence", 0.5)
    result.setdefault("language_detected", "en")

    # Coerce types
    if result["amount"] is not None:
        try:
            result["amount"] = float(result["amount"])
        except (TypeError, ValueError):
            result["amount"] = None

    if result["confidence"] is not None:
        try:
            result["confidence"] = float(result["confidence"])
        except (TypeError, ValueError):
            result["confidence"] = 0.5

    valid_intents = {"check_balance", "add_payment", "add_debt", "list_debtors",
                     "add_customer", "undo", "help", "greeting", "thanks",
                     "farewell", "unknown"}
    if result["intent"] not in valid_intents:
        result["intent"] = "unknown"
        result["confidence"] = 0.3

    logger.debug("Ollama intent: %s (confidence=%.2f)", result["intent"], result["confidence"])
    return result


# ---------------------------------------------------------------------------
# Conversational response (for open-ended queries)
# ---------------------------------------------------------------------------

_CONV_SYSTEM = """You are a real person behind the counter: helpful, relaxed, and easy to talk to. \
You work at a Lebanese pharmacy and help with customer debts and payments on the computer.

Speak in the same language / style the user uses:
- Arabic → Arabic
- Arabizi → Arabizi
- English → English
- Mixing is fine if they mix.

Sound human: use natural wording, contractions in English, small reactions ("sure", "got it", "no worries"). \
No bullet lists unless they really help. No "As an AI" or corporate tone. 1–4 short sentences is enough unless they ask for a list.

You can chat about anything briefly, but gently bring it back to balances, payments, or adding debt when it fits. \
If they want to record something, you don't run the system — they type it and the app handles it; you just explain clearly.

When a DATABASE SNAPSHOT section appears below, treat it as the truth for questions about customers, balances, totals, \
who owes what, or recent transactions. Only use facts from that snapshot; if something is not there, say you don't see it \
here and they can check the main app. Never invent names, amounts, or ledger lines.

Output rules: Reply with only what you would say out loud — one short paragraph at most for a hello. \
Never include planning, numbered steps, \"Thinking Process\", analysis, or alternatives you considered."""


def _merge_conv_system(base: str, language_hint: str, data_context: Optional[str]) -> str:
    system_prompt = base
    if language_hint and language_hint not in ('auto', 'en'):
        system_prompt += (
            f"\n\nThe user's interface language is: {language_hint}. "
            "Prefer responding in that language."
        )
    dc = (data_context or "").strip()
    if dc:
        system_prompt += (
            "\n\n--- DATABASE SNAPSHOT (read-only; use for factual answers) ---\n"
            + dc
            + "\n--- END SNAPSHOT ---"
        )
    return system_prompt


def _context_without_duplicate_user_tail(context: list, text: str) -> list:
    """If DB history already ends with this user message, drop it before appending `text` again."""
    if not context or not text:
        return context or []
    last = context[-1]
    if last.get('role') != 'user':
        return context
    last_msg = (last.get('message') or last.get('content') or '').strip()
    if last_msg == text.strip():
        return context[:-1]
    return context


def get_conversational_response(text: str, context: list,
                                 language_hint: str = 'auto',
                                 data_context: Optional[str] = None,
                                 num_predict: Optional[int] = None) -> str:
    """
    Get a natural language response for queries that don't map to a structured action.

    Args:
        text: User message
        context: Recent chat history [{"role": "user"|"assistant", "content": str}]
        language_hint: Language preference ('en', 'ar', or 'auto')
        data_context: Optional DB snapshot text appended to the system prompt
        num_predict: Max tokens (default OLLAMA_CONV_NUM_PREDICT)

    Returns:
        Response string, or empty string on failure (caller provides fallback)
    """
    global _ollama_available_cache

    if not is_available():
        invalidate_cache()
        if not is_available():
            return ""

    np = OLLAMA_CONV_NUM_PREDICT if num_predict is None else num_predict

    ctx = _context_without_duplicate_user_tail(context, text)
    messages = []
    for msg in ctx[-6:]:
        role = "user" if msg.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": msg.get("message", msg.get("content", ""))})
    messages.append({"role": "user", "content": text})

    system_prompt = _merge_conv_system(_CONV_SYSTEM, language_hint, data_context)

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "system": system_prompt,
        "messages": messages,
        "stream": False,
        "think": OLLAMA_THINK,
        "options": {
            "temperature": 0.55,
            "num_predict": np,
        },
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_CHAT_TIMEOUT) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            out = _chat_response_text(raw)
            if out:
                _ollama_available_cache = True
            return out
    except Exception as e:
        logger.warning("Ollama conversational response failed: %s", e)
        invalidate_cache()
        return ""


# ---------------------------------------------------------------------------
# Action response rephraser
# ---------------------------------------------------------------------------

_REPHRASE_SYSTEM = """You are a friendly Lebanese pharmacy assistant. \
Rephrase the following action result naturally in {language}. \
Keep it 1-2 sentences. Be warm but professional. \
Include the exact numbers and customer name from the data. \
Use markdown bold (**) for names and amounts. \
Do not add any information that is not in the data."""


def _build_rephrase_system(action_type: str, data: dict,
                            language_hint: str = 'auto') -> str:
    """Build the system prompt for rephrasing, including smart follow-up hints."""
    lang_map = {'en': 'English', 'ar': 'Arabic', 'arabizi': 'Arabizi (Lebanese Latin)',
                'mixed': 'mixed Arabic/English', 'auto': "the user's language"}
    lang_label = lang_map.get(language_hint, "the user's language")
    system = _REPHRASE_SYSTEM.format(language=lang_label)

    eff_balance = data.get('balance', data.get('new_balance', 0))
    if action_type == 'check_balance' and isinstance(eff_balance, (int, float)) and eff_balance > 0:
        system += "\nThe balance is outstanding — gently suggest they could record a payment."
    elif action_type == 'add_payment' and isinstance(eff_balance, (int, float)) and eff_balance == 0:
        system += "\nThe customer is all settled! Mention this positively."

    return system


def rephrase_action_response(action_type: str, data: dict,
                              context: list = None,
                              language_hint: str = 'auto') -> Optional[str]:
    """
    Use the LLM to rephrase a structured action result into natural language.

    Returns the rephrased text, or None on any failure (caller uses template fallback).
    """
    if not is_available():
        return None

    system = _build_rephrase_system(action_type, data, language_hint)
    user_content = f"Action: {action_type}\nData: {json.dumps(data, ensure_ascii=False, default=str)}"

    messages = []
    if context:
        for msg in context[-4:]:
            role = "user" if msg.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("message", msg.get("content", ""))})
    messages.append({"role": "user", "content": user_content})

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "system": system,
        "messages": messages,
        "stream": False,
        "think": OLLAMA_THINK,
        "options": {
            "temperature": 0.4,
            "num_predict": 100,
        },
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_CHAT_TIMEOUT) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            text = _chat_response_text(raw)
            return text if text else None
    except Exception as e:
        logger.warning("Ollama rephrase failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Streaming responses
# ---------------------------------------------------------------------------

def _stream_ollama_chat(system: str, messages: list, temperature: float = 0.3,
                         num_predict: int = 150):
    """
    Internal helper: stream tokens from Ollama /api/chat.
    Yields each text chunk as it arrives.
    """
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "system": system,
        "messages": messages,
        "stream": True,
        "think": OLLAMA_THINK,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=OLLAMA_CHAT_TIMEOUT) as resp:
        for line in resp:
            line = line.decode("utf-8").strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
                msg = chunk.get("message") or {}
                content = msg.get("content") or ""
                if content:
                    yield content
                if chunk.get("done"):
                    return
            except json.JSONDecodeError:
                continue


def stream_conversational_response(text: str, context: list = None,
                                    language_hint: str = 'auto',
                                    data_context: Optional[str] = None,
                                    num_predict: Optional[int] = None,
                                    temperature: float = 0.55):
    """
    Stream a conversational response token-by-token from Ollama.
    Yields each text chunk as it arrives.
    Falls back to a single yield if Ollama is unavailable.
    """
    global _ollama_available_cache

    if not ollama_enabled():
        return

    if not is_available():
        invalidate_cache()
        if not is_available():
            yield (
                "Can't reach Ollama at "
                + OLLAMA_BASE_URL
                + ". Start Ollama on this machine, or set OLLAMA_BASE_URL / OLLAMA_HOST, then try again."
            )
            return

    ctx = _context_without_duplicate_user_tail(context or [], text)
    messages = []
    for msg in ctx[-6:]:
        role = "user" if msg.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": msg.get("message", msg.get("content", ""))})
    messages.append({"role": "user", "content": text})

    system_prompt = _merge_conv_system(_CONV_SYSTEM, language_hint, data_context)

    np = OLLAMA_CONV_NUM_PREDICT if num_predict is None else num_predict

    try:
        yield from _stream_ollama_chat(
            system_prompt, messages,
            temperature=temperature, num_predict=np,
        )
        _ollama_available_cache = True
    except Exception as e:
        logger.warning("Ollama streaming failed: %s", e)
        invalidate_cache()
        yield (
            "The assistant hit an error — try again in a moment. "
            "For exact figures, use the Customers or Reports screens."
        )


def stream_rephrase_response(action_type: str, data: dict,
                              context: list = None,
                              language_hint: str = 'auto'):
    """
    Stream a rephrased action result token-by-token from Ollama.
    Yields text chunks. Yields nothing on error (caller should use template).
    """
    if not is_available():
        return

    system = _build_rephrase_system(action_type, data, language_hint)
    user_content = f"Action: {action_type}\nData: {json.dumps(data, ensure_ascii=False, default=str)}"

    messages = []
    if context:
        for msg in context[-4:]:
            role = "user" if msg.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("message", msg.get("content", ""))})
    messages.append({"role": "user", "content": user_content})

    try:
        yield from _stream_ollama_chat(system, messages,
                                        temperature=0.4, num_predict=100)
    except Exception as e:
        logger.warning("Ollama streaming rephrase failed: %s", e)
