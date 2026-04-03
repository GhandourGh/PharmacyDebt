"""
Pharmacy AI Chatbot Orchestrator — English, Arabic, Lebanese Arabizi.

Architecture:
  arabizi_normalizer → intent_parser (Ollama + rules) → action_executor → DB

Conversation flow: multi-turn with pending state (confirm/pick/amount/name).
Session state managed by memory_context (in-memory + SQLite rebuild).
"""

import os
import re
import logging
import uuid
from typing import Iterator, Optional, Tuple, Any, Dict

import database as db
from name_matcher import resolve_customer

from chatbot import arabizi_normalizer, intent_parser, action_executor, memory_context
from chatbot import ollama_client

logger = logging.getLogger(__name__)

# Second LLM call after DB actions — off by default for speed (template replies).
_OLLAMA_REPHRASE = os.environ.get("OLLAMA_REPHRASE", "false").strip().lower() in (
    "1", "true", "yes",
)

_LLM_UNAVAILABLE = (
    "Can't reach Ollama — check that it's running and matches OLLAMA_BASE_URL in the app environment. "
    "You can still use the main screens for balances and payments."
)

_RULES_ONLY_CHAT_FALLBACK = (
    "I'm in **quick mode** (built-in commands only). Try **help** for examples — payments, debt, "
    "balances, list debtors, and undo all work here."
)


def _conversational_fallback_text() -> str:
    return _LLM_UNAVAILABLE if ollama_client.ollama_enabled() else _RULES_ONLY_CHAT_FALLBACK

_MAX_TOP_DEBTORS = max(1, min(int(os.environ.get("CHAT_TOP_DEBTORS_MAX", "500")), 2000))

_TOP_DEBTOR_PATTERNS = (
    re.compile(r'(?:top|first)\s+(\d{1,4})\b', re.I),
    re.compile(r'\b(\d{1,4})\s+(?:top|first)\s+(?:debtors?|customers?|ow(?:e|ing))?\b', re.I),
    re.compile(r'(?:biggest|largest|highest)\s+(\d{1,4})\b', re.I),
    re.compile(r'\b(\d{1,4})\s+(?:biggest|largest|highest)\s*(?:debtors?)?\b', re.I),
    re.compile(
        r'(?:show|give|list|get)\s+(?:me\s+)?(\d{1,4})\s*(?:debtors?|customers?|ow(?:e|ing))?\b',
        re.I,
    ),
)


def _parse_top_debtors_count(text: str, amount: Optional[float]) -> Optional[int]:
    """Number from phrases like 'top 15 debtors', or parsed amount when clearly a count."""
    for pat in _TOP_DEBTOR_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                v = int(m.group(1))
                return max(1, min(v, _MAX_TOP_DEBTORS))
            except ValueError:
                pass
    if amount is not None and 1 <= amount <= _MAX_TOP_DEBTORS:
        tl = text.lower()
        if any(
            k in tl
            for k in (
                'top', 'first', 'biggest', 'largest', 'highest', 'debtor',
                'debtors', 'mdyouneen', 'mdyoun', 'list', 'show', 'give',
            )
        ):
            return int(amount)
    return None


def _top_debtors_limit_from_message(
    text: str, amount: Optional[float], intent: str,
) -> Optional[int]:
    """For list_debtors intent; None = show up to max_cap. Also handles some unknown+top-N questions."""
    if intent == 'list_debtors':
        return _parse_top_debtors_count(text, amount)
    if intent == 'unknown':
        n = _parse_top_debtors_count(text, amount)
        if n is None:
            return None
        tl = text.lower()
        if any(
            k in tl
            for k in (
                'debtor', 'debtors', 'debt', 'owe', 'owing', 'owed',
                'mdyoun', 'mdyouneen', 'balance', 'مديون', 'دين',
            )
        ):
            return n
    return None


# ─── Formatting ───────────────────────────────────────────────────────────────
def _fmt(n: float) -> str:
    return f"${n:,.2f}"


# ─── Customer helpers ─────────────────────────────────────────────────────────
def _all_customers() -> list:
    try:
        rows = [dict(r) for r in (db.get_all_customers() or [])]
        for c in rows:
            try:
                c['debt'] = float(db.get_customer_balance(c['id']))
            except Exception:
                c['debt'] = 0.0
        return rows
    except Exception:
        return []


# Arabizi digit normalization for name-only matching (e.g. '3ali' → 'ali')
_ARABIZI = {'2': '', '3': '', '5': 'kh', '6': 't', '7': 'h', '8': 'q', '9': 's'}


def _norm_name_for_matching(name: str) -> str:
    out = ''.join(_ARABIZI.get(c, c) for c in name)
    return out.strip() or name


def _resolve_name(name: str, require_pick_for_fuzzy: bool = False) -> dict:
    """Resolve a name string to a customer via fuzzy matching."""
    custs = _all_customers()
    if not custs:
        return {'status': 'no_match', 'message': 'No customers in database.'}
    normalized = _norm_name_for_matching(name)
    result = resolve_customer(
        normalized, custs, require_pick_for_fuzzy=require_pick_for_fuzzy,
    )
    if result['status'] == 'no_match' and normalized != name:
        result = resolve_customer(name, custs, require_pick_for_fuzzy=require_pick_for_fuzzy)
    return result


# ─── Session shortcuts ────────────────────────────────────────────────────────
def _ctx(session_id: str) -> dict:
    return memory_context.get_or_rebuild_context(session_id)


def drop_session(session_id: str):
    memory_context.drop_session(session_id)


# ─── Response helpers ─────────────────────────────────────────────────────────
def _r(text: str, needs=None, candidates=None, success=True,
       session_id=None, ctx=None, intent='unknown',
       ledger_id=None, action_preview=None) -> dict:
    undo_available = bool(ctx and ctx.get('last_ledger_id'))
    return {
        'response': text,
        'success': success,
        'needs': needs,
        'candidates': candidates or [],
        'intent': intent,
        'undo_available': undo_available,
        'action_preview': action_preview,
        'session_id': session_id,
    }


def _ledger_ui_extra(ar: action_executor.ActionResult, intent: str) -> dict:
    """Hints for frontend to refresh balances without full page reload."""
    if not ar.success:
        return {}
    if intent not in ('add_payment', 'add_debt', 'undo'):
        return {}
    out: Dict[str, Any] = {'ledger_changed': True}
    if intent == 'undo':
        return out
    cust = (ar.data or {}).get('customer') or {}
    cid = cust.get('id')
    if not cid:
        return out
    bal = ar.data.get('balance')
    if bal is None:
        try:
            bal = db.get_customer_balance(cid)
        except Exception:
            bal = None
    out['updated_customer_id'] = cid
    out['updated_customer_name'] = cust.get('name') or ''
    if bal is not None:
        try:
            out['updated_balance'] = float(bal)
        except (TypeError, ValueError):
            pass
    return out


def _from_action_result(ar: action_executor.ActionResult,
                         session_id: str, ctx: dict, intent: str = '') -> dict:
    """Convert ActionResult to the standard response dict."""
    # Record last action for undo (capture customer before ctx may be cleared)
    cust_for_undo = (ar.data or {}).get('customer') or {}
    if ar.ledger_id:
        ctx['last_ledger_id'] = ar.ledger_id
        ctx['last_action'] = intent.replace('_', ' ').title()
        ctx['last_customer_name'] = cust_for_undo.get('name', '') or (
            (ctx.get('customer') or {}).get('name', '')
        )
        ctx['last_amount'] = ar.data.get('amount', 0)

    base = {
        'response': ar.response,
        'success': ar.success,
        'needs': ar.needs,
        'candidates': ar.candidates,
        'intent': intent,
        'undo_available': bool(ar.undo_available or (ctx and ctx.get('last_ledger_id'))),
        'action_preview': ar.action_preview,
        'session_id': session_id,
    }
    base.update(_ledger_ui_extra(ar, intent))
    return base


# ─── Action handlers ─────────────────────────────────────────────────────────
def _do_balance(c: dict, session_id: str, ctx: dict) -> dict:
    fs = ctx.get('__stream__', False)
    chat_ctx = _build_chat_context(session_id)
    lang = ctx.get('language_hint', 'en')
    ar = action_executor.check_balance(
        c, context=chat_ctx, language_hint=lang, use_rephrase=_OLLAMA_REPHRASE and (not fs),
    )
    _clear(ctx)
    result = _from_action_result(ar, session_id, ctx, 'check_balance')
    if fs and ar.success and _OLLAMA_REPHRASE:
        result['_stream'] = {
            'kind': 'rephrase',
            'action_type': 'check_balance',
            'data': {'name': c['name'], 'balance': ar.data.get('balance', 0)},
            'context': chat_ctx,
            'language_hint': lang,
            'fallback': ar.response,
        }
    return result


def _do_payment(c: dict, amount: float, session_id: str, ctx: dict) -> dict:
    fs = ctx.get('__stream__', False)
    chat_ctx = _build_chat_context(session_id)
    lang = ctx.get('language_hint', 'en')
    ar = action_executor.execute_add_payment(
        c, amount, context=chat_ctx, language_hint=lang, use_rephrase=_OLLAMA_REPHRASE and (not fs),
    )
    _clear(ctx)
    result = _from_action_result(ar, session_id, ctx, 'add_payment')
    if fs and ar.success and _OLLAMA_REPHRASE:
        nb = ar.data.get('balance', 0)
        result['_stream'] = {
            'kind': 'rephrase',
            'action_type': 'add_payment',
            'data': {'name': c['name'], 'amount': amount, 'new_balance': nb},
            'context': chat_ctx,
            'language_hint': lang,
            'fallback': ar.response,
        }
    return result


def _do_debt(c: dict, amount: float, session_id: str, ctx: dict) -> dict:
    fs = ctx.get('__stream__', False)
    chat_ctx = _build_chat_context(session_id)
    lang = ctx.get('language_hint', 'en')
    ar = action_executor.execute_add_debt(
        c, amount, context=chat_ctx, language_hint=lang, use_rephrase=_OLLAMA_REPHRASE and (not fs),
    )
    _clear(ctx)
    result = _from_action_result(ar, session_id, ctx, 'add_debt')
    if fs and ar.success and _OLLAMA_REPHRASE:
        nb = ar.data.get('balance', 0)
        result['_stream'] = {
            'kind': 'rephrase',
            'action_type': 'add_debt',
            'data': {'name': c['name'], 'amount': amount, 'new_balance': nb},
            'context': chat_ctx,
            'language_hint': lang,
            'fallback': ar.response,
        }
    return result


def _do_list(session_id: str, ctx: dict, top_n: Optional[int] = None) -> dict:
    fs = ctx.get('__stream__', False)
    chat_ctx = _build_chat_context(session_id)
    lang = ctx.get('language_hint', 'en')
    ar = action_executor.list_debtors(
        context=chat_ctx, language_hint=lang, use_rephrase=_OLLAMA_REPHRASE and (not fs),
        top_n=top_n, max_cap=_MAX_TOP_DEBTORS,
    )
    result = _from_action_result(ar, session_id, ctx, 'list_debtors')
    if fs and ar.success and _OLLAMA_REPHRASE:
        customers = ar.data.get('customers_shown') or ar.data.get('customers') or []
        if customers:
            lines = [f"**{c['name']}** — {_fmt(c.get('debt', 0))}" for c in customers]
            suffix = "\n\n" + "\n".join(lines)
            total = ar.data.get('total_debt_all') or sum(c.get('debt', 0) for c in customers)
            total_owing = ar.data.get('owing_count', len(customers))
            result['_stream'] = {
                'kind': 'rephrase',
                'action_type': 'list_debtors',
                'data': {
                    'count': total_owing,
                    'total': total,
                    'top_debtors': [
                        {'name': c['name'], 'debt': c.get('debt', 0)} for c in customers[:5]
                    ],
                },
                'context': chat_ctx,
                'language_hint': lang,
                'fallback': ar.response,
                'suffix': suffix,
            }
    return result


def _do_add_customer(name: str, session_id: str, ctx: dict) -> dict:
    ar = action_executor.execute_add_customer(name)
    _clear(ctx)
    return _from_action_result(ar, session_id, ctx, 'add_customer')


def _do_help_streaming(session_id: str, ctx: dict, text: str, stream: bool) -> dict:
    """Help text comes from the LLM + DB snapshot, not a static cheat sheet."""
    if stream:
        chat_ctx = _build_chat_context(session_id)
        lang = ctx.get('language_hint', 'en')
        result = _r('', session_id=session_id, ctx=ctx, intent='help', success=True)
        result['_stream'] = {
            'kind': 'conversational',
            'user_text': text,
            'context': chat_ctx,
            'language_hint': lang,
            'data_snapshot': _build_pharmacy_data_snapshot(),
            'fallback': _conversational_fallback_text(),
        }
        return result
    return _conversational_reply(text, session_id, ctx, 'help')


# ─── Conversation state helpers ───────────────────────────────────────────────
def _clear(ctx: dict):
    ctx.update({
        'action': None, 'name': None, 'amount': None,
        'customer': None, 'candidates': [], 'needs': None,
    })


def _exec(action: str, customer: dict, amount: Optional[float],
           session_id: str, ctx: dict) -> dict:
    """Execute action with a confirmed, resolved customer."""
    if action == 'check_balance':
        return _do_balance(customer, session_id, ctx)
    elif action == 'add_payment':
        return _do_payment(customer, amount, session_id, ctx)
    elif action == 'add_debt':
        return _do_debt(customer, amount, session_id, ctx)
    elif action == 'add_customer':
        return _do_add_customer(customer.get('name', ''), session_id, ctx)
    _clear(ctx)
    return _r("Done!", session_id=session_id, ctx=ctx)


def _resolve_and_confirm(action: str, name: str, amount: Optional[float],
                          session_id: str, ctx: dict) -> dict:
    """Resolve customer name; add payment/debt always offers a pick list unless exact name match."""
    require_pick = action in ('add_payment', 'add_debt')
    res = _resolve_name(name, require_pick_for_fuzzy=require_pick)

    if res['status'] == 'matched':
        cust = res['customer']
        ctx.update(action=action, name=name, amount=amount, customer=cust)
        return _exec(action, cust, amount, session_id, ctx)

    if res['status'] == 'ambiguous':
        cands = res['candidates']
        ctx.update(action=action, name=name, amount=amount, candidates=cands, needs='pick')
        return _r(
            f"Multiple matches for **{name}** — tap the right one:",
            needs='clarification',
            candidates=cands,
            session_id=session_id,
            ctx=ctx,
            intent=action,
        )

    # No match — offer to create new customer
    ctx.update(action=action, customer={'name': name, 'id': None}, amount=amount, needs='confirm')
    return _r(
        f"No customer named **{name}** found.\nAdd them as a new customer? (Yes / No)",
        needs='confirm_customer',
        session_id=session_id,
        ctx=ctx,
        intent='add_customer',
    )


# ─── Pending state handlers ───────────────────────────────────────────────────
_KW_YES = frozenset([
    'yes', 'yeah', 'yep', 'ok', 'okay', 'sure', 'confirm', 'correct', 'yalla',
    'نعم', 'اي', 'اكيد', 'طبعا', 'ماشي', 'mashi', 'sah', 'aywa', 'aywah', 'tayeb',
])
_KW_NO = frozenset([
    'no', 'nah', 'nope', 'cancel', 'wrong', 'stop', 'la2', 'la',
    'لا', 'لأ', 'خلص', 'بلا',
])
_AMOUNT_RE = re.compile(
    r'(?<!\w)(\d[\d,]*)(?:\.\d+)?(?:\s*(?:dollar|dolar|usd|\$|lira|lbp|lb|دولار|ليرة))?(?!\w)',
    re.IGNORECASE,
)


def _extract_amount_local(text: str) -> Optional[float]:
    for m in _AMOUNT_RE.finditer(text):
        try:
            v = float(m.group(1).replace(',', ''))
            if v > 0:
                return v
        except ValueError:
            continue
    return None


def _on_confirm(text: str, session_id: str, ctx: dict) -> dict:
    tl = text.strip().lower()
    is_yes = tl in _KW_YES or any(w in tl.split() for w in _KW_YES)
    is_no = tl in _KW_NO or any(w in tl.split() for w in _KW_NO)

    if is_yes:
        cust = ctx.get('customer')
        action = ctx.get('action')
        amount = ctx.get('amount')

        # Auto-create customer if new
        if cust and cust.get('id') is None:
            try:
                nid = db.add_customer(name=cust['name'], phone='')
                cust = dict(db.get_customer(nid))
                ctx['customer'] = cust
            except Exception as e:
                logger.error("auto-add customer: %s", e)
                _clear(ctx)
                return _r("Failed to create new customer.", success=False,
                          session_id=session_id, ctx=ctx)

        return _exec(action, cust, amount, session_id, ctx)

    if is_no:
        _clear(ctx)
        return _r("Cancelled. What's the correct customer name?",
                  needs='name', success=False, session_id=session_id, ctx=ctx)

    # User typed a different name — treat as name correction
    name = text.strip()
    action = ctx.get('action')
    amount = ctx.get('amount')
    _clear(ctx)
    return _resolve_and_confirm(action, name, amount, session_id, ctx)


def _on_pick(text: str, session_id: str, ctx: dict) -> dict:
    cands = ctx.get('candidates', [])
    tl = text.strip().lower()

    if tl in _KW_NO:
        _clear(ctx)
        return _r("Cancelled. What else can I help with?",
                  session_id=session_id, ctx=ctx)

    # Number pick
    try:
        idx = int(tl) - 1
        if 0 <= idx < len(cands):
            return _exec(ctx['action'], cands[idx], ctx['amount'], session_id, ctx)
    except ValueError:
        pass

    # Name fragment match
    for c in cands:
        cn = c.get('name', '').lower()
        if tl in cn or cn.startswith(tl):
            return _exec(ctx['action'], c, ctx['amount'], session_id, ctx)

    return _r("Please tap a name from the list, or type a name.",
              success=False, needs='clarification', candidates=cands,
              session_id=session_id, ctx=ctx)


def _on_amount(text: str, session_id: str, ctx: dict) -> dict:
    amount = _extract_amount_local(text)
    if not amount:
        return _r("Please enter a valid amount, e.g. **50** or **100.50**.",
                  success=False, needs='amount', session_id=session_id, ctx=ctx)
    ctx['amount'] = amount
    ctx['needs'] = None
    name = ctx.get('name')
    action = ctx.get('action')
    if name:
        return _resolve_and_confirm(action, name, amount, session_id, ctx)
    ctx['needs'] = 'name'
    return _r("Which customer?", needs='name', success=False,
              session_id=session_id, ctx=ctx)


def _on_name(text: str, session_id: str, ctx: dict) -> dict:
    name = text.strip()
    action = ctx.get('action')
    amount = ctx.get('amount')
    ctx['name'] = name
    ctx['needs'] = None
    if action in ('add_payment', 'add_debt') and not amount:
        ctx['needs'] = 'amount'
        return _r("How much?", needs='amount', success=False,
                  session_id=session_id, ctx=ctx)
    return _resolve_and_confirm(action, name, amount, session_id, ctx)


# ─── Chat context & conversational LLM ─────────────────────────────────────

def _build_pharmacy_data_snapshot(
    max_customers: int = 120,
    recent_ledger_limit: int = 14,
) -> str:
    """
    Compact read-only snapshot from SQLite for LLM grounding (names, balances, recent activity).
    """
    lines = []
    try:
        rows = db.get_customers_with_debt() or []
    except Exception as e:
        logger.warning("snapshot customers: %s", e)
        return "(Could not load customers from the database.)"

    def _fdebt(r) -> float:
        try:
            return float(r.get("debt") or 0)
        except (TypeError, ValueError):
            return 0.0

    active = [r for r in rows if r.get("is_active", 1)]
    owing = [r for r in active if _fdebt(r) > 0.005]
    credits = [r for r in active if _fdebt(r) < -0.005]
    total_out = sum(_fdebt(r) for r in owing)
    total_cred = sum(abs(_fdebt(r)) for r in credits)

    lines.append(
        f"Summary: {len(active)} active customers on file; "
        f"{len(owing)} owe money (total outstanding ${total_out:,.2f}); "
        f"{len(credits)} with credit balance (total credit ${total_cred:,.2f})."
    )

    by_balance = sorted(active, key=_fdebt, reverse=True)
    shown = by_balance[:max_customers]
    lines.append("Customers (sorted by balance high → low; amounts are current balance):")
    for r in shown:
        nm = (r.get("name") or "").strip() or "?"
        bid = r.get("id")
        bal = _fdebt(r)
        lines.append(f"  • {nm} [id {bid}]: ${bal:,.2f}")
    if len(by_balance) > max_customers:
        lines.append(
            f"  … {len(by_balance) - max_customers} more customers not shown (snapshot cap)."
        )

    try:
        activity = db.get_recent_activity(limit=recent_ledger_limit) or []
    except Exception as e:
        logger.warning("snapshot activity: %s", e)
        activity = []

    if activity:
        lines.append("Recent ledger entries (newest first):")
        for entry in activity:
            cname = entry.get("customer_name") or "?"
            et = entry.get("entry_type") or "?"
            amt = entry.get("amount")
            try:
                amt_f = float(amt) if amt is not None else 0.0
            except (TypeError, ValueError):
                amt_f = 0.0
            ts = entry.get("created_at")
            ts_s = str(ts)[:19] if ts is not None else ""
            lines.append(
                f"  – {ts_s} | {cname} | {et} | ${amt_f:,.2f}"
            )

    lines.append(
        "To record a payment, add debt, check one balance, list debtors, undo, or add a customer, "
        "the user should say it in the chat in natural language (English, Arabic, or Arabizi); "
        "this snapshot is for your answers only — you do not execute those actions."
    )
    return "\n".join(lines)


def _build_pharmacy_data_snapshot_light() -> str:
    """Tiny snapshot for greetings — keeps prompts short and responses fast."""
    try:
        rows = db.get_customers_with_debt() or []
    except Exception as e:
        logger.warning("snapshot light: %s", e)
        return ""

    def _fdebt(r) -> float:
        try:
            return float(r.get("debt") or 0)
        except (TypeError, ValueError):
            return 0.0

    active = [r for r in rows if r.get("is_active", 1)]
    owing = [r for r in active if _fdebt(r) > 0.005]
    total_out = sum(_fdebt(r) for r in owing)
    return (
        f"Quick context only: {len(active)} customers on file; {len(owing)} owe money "
        f"(≈ ${total_out:,.2f} outstanding). Reply briefly; no name list in this turn."
    )


def _build_chat_context(session_id: str, limit: int = 6) -> list:
    """Load recent chat history from DB for LLM context."""
    try:
        history = db.get_chat_history(session_id, limit=limit)
        return [{"role": m.get("role", "user"), "message": m.get("message", "")} for m in history]
    except Exception:
        return []


def _conversational_reply(text: str, session_id: str, ctx: dict, intent: str) -> dict:
    """Generate a conversational LLM response for non-action intents (non-streaming)."""
    context = _build_chat_context(session_id)
    language_hint = ctx.get('language_hint', 'en')
    if intent in ('greeting', 'thanks', 'farewell'):
        snapshot = _build_pharmacy_data_snapshot_light()
        np = 72
    else:
        snapshot = _build_pharmacy_data_snapshot()
        np = None
    response = ollama_client.get_conversational_response(
        text, context, language_hint=language_hint, data_context=snapshot, num_predict=np,
    )
    if response:
        response = ollama_client.polish_chat_reply(response)
    if not response:
        response = _conversational_fallback_text()
    return _r(response, session_id=session_id, ctx=ctx, intent=intent)


def _execute_turn_impl(text: str, session_id: str, ctx: dict) -> dict:
    """
    Core routing for one user turn. ctx['language_hint'] must be set.
    When ctx['__stream__'] is True, skip inline LLM for conversational + rephrase
    (caller streams via _stream spec instead).
    """
    stream = ctx.get('__stream__', False)
    need = ctx.get('needs')
    text_lower = text.strip().lower()

    if text_lower in ('undo', 'تراجع', 'راجع', 'reverse', 'cancel last'):
        ar = action_executor.undo_last_action(ctx)
        _clear(ctx)
        return _from_action_result(ar, session_id, ctx, 'undo')

    if need == 'pick':
        return _on_pick(text, session_id, ctx)
    if need == 'confirm':
        return _on_confirm(text, session_id, ctx)
    if need == 'amount':
        return _on_amount(text, session_id, ctx)
    if need == 'name':
        return _on_name(text, session_id, ctx)

    norm = arabizi_normalizer.normalize(text)
    parsed = intent_parser.parse(text, norm.normalized)
    intent = parsed.intent
    name = parsed.customer_name
    amount = parsed.amount

    if intent == 'help':
        return _do_help_streaming(session_id, ctx, text, stream)

    if intent == 'list_debtors':
        tn = _top_debtors_limit_from_message(text, amount, intent)
        return _do_list(session_id, ctx, top_n=tn)

    if intent == 'unknown':
        tn = _top_debtors_limit_from_message(text, amount, intent)
        if tn is not None:
            return _do_list(session_id, ctx, top_n=tn)

    if intent == 'undo':
        ar = action_executor.undo_last_action(ctx)
        _clear(ctx)
        return _from_action_result(ar, session_id, ctx, 'undo')

    if intent == 'add_customer':
        if name:
            ctx.update(action='add_customer', customer={'name': name, 'id': None}, needs='confirm')
            return _r(
                f"Add new customer **{name}**? (Yes / No)",
                needs='confirm_customer',
                session_id=session_id, ctx=ctx, intent='add_customer',
            )
        ctx.update(action='add_customer', needs='name')
        return _r("What is the customer's name?", needs='name',
                  session_id=session_id, ctx=ctx, intent='add_customer')

    if intent in ('greeting', 'thanks', 'farewell', 'unknown'):
        if stream:
            context = _build_chat_context(session_id)
            lang = ctx.get('language_hint', 'en')
            if intent in ('greeting', 'thanks', 'farewell'):
                snap = _build_pharmacy_data_snapshot_light()
                spec_np, spec_temp = 72, 0.42
            else:
                snap = _build_pharmacy_data_snapshot()
                spec_np, spec_temp = None, 0.55
            result = _r('', session_id=session_id, ctx=ctx, intent=intent, success=True)
            result['_stream'] = {
                'kind': 'conversational',
                'user_text': text,
                'context': context,
                'language_hint': lang,
                'data_snapshot': snap,
                'num_predict': spec_np,
                'temperature': spec_temp,
                'fallback': _conversational_fallback_text(),
            }
            return result
        return _conversational_reply(text, session_id, ctx, intent)

    if not name:
        ctx.update(action=intent, amount=amount, needs='name')
        return _r("Which customer?", needs='name', success=False,
                  session_id=session_id, ctx=ctx, intent=intent)

    if intent in ('add_payment', 'add_debt') and not amount:
        ctx.update(action=intent, name=name, needs='amount')
        return _r("How much?", needs='amount', success=False,
                  session_id=session_id, ctx=ctx, intent=intent)

    return _resolve_and_confirm(intent, name, amount, session_id, ctx)


# ─── Main entry point ─────────────────────────────────────────────────────────
def process_message(text: str, session_id: Optional[str] = None,
                    language_hint: str = 'en') -> dict:
    """
    Process a chat message and return a response dict.

    Args:
        text: User message text
        session_id: Session identifier (generated if None)
        language_hint: 'en' or 'ar' (from browser language toggle)

    Returns:
        {
            'response': str,
            'success': bool,
            'needs': str|None,          # 'confirm_customer'|'clarification'|'amount'|'name'
            'candidates': list,
            'intent': str,
            'undo_available': bool,
            'action_preview': dict|None, # For UI confirm cards
            'session_id': str,
        }
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    try:
        db.save_chat_message(session_id, 'user', text, language=language_hint)
    except Exception:
        pass

    ctx = _ctx(session_id)
    ctx['language_hint'] = language_hint
    ctx['__stream__'] = False
    try:
        result = _execute_turn_impl(text, session_id, ctx)
    finally:
        ctx.pop('__stream__', None)

    try:
        db.save_chat_message(
            session_id, 'assistant',
            result.get('response', ''),
            intent=result.get('intent', ''),
            language=language_hint,
        )
    except Exception:
        pass

    result['session_id'] = session_id
    return {k: v for k, v in result.items() if k != '_stream'}


def iter_chat_sse_events(text: str, session_id: Optional[str] = None,
                          language_hint: str = 'en'
                          ) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """
    Run one chat turn for SSE: persist user message, yield (event, payload) tuples:
    ('meta', {...}), ('token', {'text': chunk}), ..., ('done', {'full_response': ...}).
    Persists the assistant message after streaming completes.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    try:
        db.save_chat_message(session_id, 'user', text, language=language_hint)
    except Exception:
        pass

    ctx = _ctx(session_id)
    ctx['language_hint'] = language_hint
    ctx['__stream__'] = True
    try:
        result = _execute_turn_impl(text, session_id, ctx)
    finally:
        ctx.pop('__stream__', None)

    result['session_id'] = session_id
    meta = {k: v for k, v in result.items() if not k.startswith('_')}
    yield 'meta', meta

    full_response = ''
    spec = result.get('_stream')
    if spec:
        if spec['kind'] == 'conversational':
            pieces = []
            for chunk in ollama_client.stream_conversational_response(
                spec['user_text'], spec['context'], language_hint=spec['language_hint'],
                data_context=spec.get('data_snapshot'),
                num_predict=spec.get('num_predict'),
                temperature=spec.get('temperature', 0.55),
            ):
                pieces.append(chunk)
                yield 'token', {'text': chunk}
            full_response = ollama_client.polish_chat_reply(''.join(pieces))
            if not full_response:
                full_response = spec['fallback']
                yield 'token', {'text': full_response}
        elif spec['kind'] == 'rephrase':
            pieces = []
            for chunk in ollama_client.stream_rephrase_response(
                spec['action_type'], spec['data'],
                context=spec['context'], language_hint=spec['language_hint'],
            ):
                pieces.append(chunk)
                yield 'token', {'text': chunk}
            streamed = ''.join(pieces).strip()
            if not streamed:
                full_response = spec['fallback']
                yield 'token', {'text': full_response}
            else:
                full_response = streamed
                suf = spec.get('suffix')
                if suf:
                    full_response += suf
                    yield 'token', {'text': suf}
    else:
        full_response = (result.get('response') or '').strip()
        if full_response:
            yield 'token', {'text': full_response}

    done_payload: Dict[str, Any] = {'full_response': full_response}
    for _k in (
        'ledger_changed', 'updated_customer_id', 'updated_customer_name',
        'updated_balance', 'success', 'intent', 'needs', 'candidates',
    ):
        if _k in result:
            done_payload[_k] = result[_k]
    yield 'done', done_payload

    try:
        db.save_chat_message(
            session_id, 'assistant', full_response,
            intent=result.get('intent', ''),
            language=language_hint,
        )
    except Exception:
        pass
