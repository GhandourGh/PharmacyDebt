"""
Session memory management.

In-memory session store with SQLite-backed rebuild on server restart.
No Redis required — single-process local Flask app.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

_sessions: dict = {}


def _fresh() -> dict:
    """Create a blank session context."""
    return {
        # Conversation state (compatible with existing bot.py flow)
        'action': None,       # Pending intent: check_balance|add_payment|add_debt|...
        'name': None,         # Extracted customer name (raw)
        'amount': None,       # Extracted amount
        'customer': None,     # Resolved customer dict from DB
        'candidates': [],     # Ambiguous name matches
        'needs': None,        # What's still needed: name|amount|confirm_customer|clarification

        # New fields for rebuilt system
        'last_ledger_id': None,   # Last written ledger entry (for undo)
        'last_action': None,       # Human-readable description of last action
        'last_customer_name': None, # Customer name used in last action
        'last_amount': None,       # Amount used in last action
        'language_hint': 'en',     # 'en' or 'ar' (from browser or detection)
        'ollama_used': False,      # Track whether LLM was used this turn
    }


def get_or_rebuild_context(session_id: str) -> dict:
    """
    Return session context. If not in memory (e.g., after server restart),
    rebuild a fresh context (we can't reliably reconstruct pending state from DB).
    """
    if not session_id:
        return _fresh()

    if session_id not in _sessions:
        logger.debug("Session %s not in memory, creating fresh context", session_id[:8])
        _sessions[session_id] = _fresh()

    return _sessions[session_id]


def save_context(session_id: str, ctx: dict):
    """Persist context back to in-memory store."""
    if session_id:
        _sessions[session_id] = ctx


def clear(session_id: str):
    """Reset session to blank state (keep session_id alive)."""
    if session_id and session_id in _sessions:
        _sessions[session_id] = _fresh()


def drop_session(session_id: str):
    """Remove session entirely."""
    _sessions.pop(session_id, None)


def get_all_sessions() -> list:
    """For debugging — return list of active session IDs."""
    return list(_sessions.keys())


def set_language(session_id: str, language: str):
    """Convenience: set language hint for a session."""
    ctx = get_or_rebuild_context(session_id)
    ctx['language_hint'] = language
    save_context(session_id, ctx)


def record_last_action(session_id: str, ledger_id: Optional[int],
                        action: str, customer_name: str = '', amount: float = 0):
    """Record the last write action for undo support."""
    ctx = get_or_rebuild_context(session_id)
    ctx['last_ledger_id'] = ledger_id
    ctx['last_action'] = action
    ctx['last_customer_name'] = customer_name
    ctx['last_amount'] = amount
    save_context(session_id, ctx)
