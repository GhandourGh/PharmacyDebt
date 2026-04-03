"""
Hybrid intent parser: Ollama LLM + rule-based fallback.

Decision logic:
  1. If Ollama is available → parse_intent() → use if confidence > 0.7
  2. Otherwise → rule-based keyword detection (fast, offline)

The rule-based engine is the same keyword logic from the original bot.py,
extracted here so it can be maintained independently.
"""

import os
import re
import logging
from dataclasses import dataclass
from typing import Optional

from chatbot import ollama_client
from chatbot.ollama_client import OllamaUnavailableError

logger = logging.getLogger(__name__)

OLLAMA_CONFIDENCE_THRESHOLD = 0.70

# If true: try fast keyword rules first; skip Ollama /api/generate when rules are confident enough.
OLLAMA_RULES_FIRST = os.environ.get("OLLAMA_RULES_FIRST", "true").strip().lower() in (
    "1", "true", "yes", "",
)


# ---------------------------------------------------------------------------
# Intent result dataclass
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    intent: str                    # check_balance|add_payment|add_debt|list_debtors|add_customer|undo|help|unknown
    customer_name: Optional[str]
    amount: Optional[float]
    payment_method: Optional[str]
    confidence: float
    language_detected: str         # en|ar|arabizi|mixed
    source: str                    # 'ollama' | 'rules'

    @classmethod
    def unknown(cls) -> 'IntentResult':
        return cls(intent='unknown', customer_name=None, amount=None,
                   payment_method=None, confidence=0.0,
                   language_detected='en', source='rules')


# ---------------------------------------------------------------------------
# Rule-based keyword sets (ported from bot.py + enhanced)
# ---------------------------------------------------------------------------

_KW_BALANCE = frozenset([
    'balance', 'check', 'how much', 'owe', 'hisab', 'shou', 'shoo',
    'ma3o', 'ma3oh', 'blance', 'ballance', 'choufle', 'choufleh', 'adeh', 'addeh',
    '3leh', '3leha', 'adaysh', 'addaysh',
    'حساب', 'رصيد', 'كم', 'شو', 'شوفلي', 'أديش', 'عليه', 'عليها',
])

_KW_PAYMENT = frozenset([
    'paid', 'pay', 'payment', 'dafa3', 'dafaa', 'dafaa3', 'dfaa3', 'defaa',
    'wdaa3', 'wadaa3', 'daf3', 'daf3a', 'wdaf3',
    'دفع', 'دفعة', 'سدد', 'سداد',
])

_KW_DEBT = frozenset([
    'owes', 'debt', 'owe', '3ndo', '3ando', '3indo', 'ando', 'aando',
    '3nde', 'dayn', 'deyn', 'dein', 'indo', 'indha',
    'عنده', 'دين', 'يدين', 'مديون',
])

_KW_LIST = frozenset([
    'all', 'list', 'show', 'debtors', 'everyone', 'kell', 'kull', 'kullon',
    'mdyouneen', 'medyouneen', 'mdyounin', 'madyouneen',
    'كل', 'الكل', 'مديونين', 'جميع',
])

_KW_ADD_CUSTOMER = frozenset([
    'add customer', 'new customer', 'register', 'create customer',
    'zid customer', 'add ziboun', 'ziboun jdid',
    'اضف زبون', 'زبون جديد', 'سجل زبون',
])

_KW_UNDO = frozenset([
    'undo', 'cancel', 'reverse', 'mistake', 'wrong',
    'تراجع', 'الغ', 'خطأ', 'راجع',
])

_KW_HELP = frozenset([
    'help', 'msa3de', 'saedni', '?', 'what can', 'commands',
    'مساعدة', 'ساعدني', 'ايش تعرف', 'شو بتعمل',
])

_KW_YES = frozenset([
    'yes', 'y', 'ok', 'okay', 'confirm', 'sure', 'correct', 'right',
    'yeh', 'aywa', 'aywah', 'mashi', 'tayeb', 'yalla',
    'نعم', 'ايوا', 'صح', 'ماشي', 'طيب', 'يلا', 'موافق',
])

_KW_NO = frozenset([
    'no', 'n', 'nope', 'cancel', 'stop', 'wrong', 'la2', 'la',
    'لا', 'لأ', 'خطأ',
])

_KW_GREETING = frozenset([
    'hi', 'hello', 'hey', 'hola', 'yo', 'sup',
    'marhaba', 'ahla', 'salam', 'hala',
    'kifak', 'kifek', 'kefak', 'shu akhbarak', 'keefak',
    'مرحبا', 'أهلا', 'هلا', 'كيفك', 'السلام عليكم', 'صباح الخير', 'مساء الخير',
])

_KW_GREETING_PHRASES = frozenset([
    'good morning', 'good evening', 'how are you',
    'sabah el kheir', 'masa el kheir', 'shu akhbarak',
    'صباح الخير', 'مساء الخير', 'السلام عليكم', 'كيف حالك',
])

_KW_THANKS = frozenset([
    'thanks', 'thank', 'thx', 'ty', 'mersi', 'yeslamo', 'yislamoh',
    'mashkour', 'mashkoure', 'teslam', 'teslameh',
    'شكرا', 'يسلمو', 'مشكور', 'تسلم',
])

_KW_FAREWELL = frozenset([
    'bye', 'goodbye', 'cya', 'see you', 'later',
    'yalla bye', 'bye bye', 'bbye',
    'مع السلامة', 'باي', 'يلا باي',
])


# Amount extraction pattern
_AMOUNT_RE = re.compile(
    r'(\d[\d,]*)(?:\.\d+)?'
    r'(?:\s*(?:dollar|dolar|دولار|lira|ليرة|lbp|\$|usd))?',
    re.IGNORECASE,
)


def _extract_amount(text: str) -> Optional[float]:
    """Extract first numerical amount from text."""
    match = _AMOUNT_RE.search(text)
    if match:
        try:
            return float(match.group(1).replace(',', ''))
        except ValueError:
            pass
    return None


def _extract_name(text: str) -> Optional[str]:
    """
    Extract customer name: remove intent keywords and amounts, return remainder.
    Best-effort — name resolution happens later in name_matcher.
    """
    # Remove intent keywords
    all_kw = (_KW_BALANCE | _KW_PAYMENT | _KW_DEBT | _KW_LIST |
              _KW_UNDO | _KW_HELP | _KW_YES | _KW_NO |
              _KW_GREETING | _KW_THANKS | _KW_FAREWELL)
    words = text.split()
    filtered = []
    for w in words:
        w_lower = w.lower().strip('.,!?؟')
        if w_lower in all_kw:
            continue
        if re.fullmatch(r'[\d,.]+', w):  # pure number
            continue
        filtered.append(w)
    name = ' '.join(filtered).strip()
    return name if len(name) >= 2 else None


def _rule_based_detect(text: str) -> IntentResult:
    """Fast keyword-based intent detection (no network calls)."""
    lower = text.lower()
    tokens = set(re.findall(r"[\w']+", lower))

    # Check multi-word keywords first
    is_add_customer = any(kw in lower for kw in _KW_ADD_CUSTOMER)
    is_undo = any(kw in lower for kw in _KW_UNDO)
    is_yes = any(kw in tokens for kw in _KW_YES)
    is_no = any(kw in tokens for kw in _KW_NO)

    score_balance = len(tokens & _KW_BALANCE)
    score_payment = len(tokens & _KW_PAYMENT)
    score_debt = len(tokens & _KW_DEBT)
    score_list = len(tokens & _KW_LIST)
    score_help = len(tokens & _KW_HELP)

    amount = _extract_amount(text)
    name = _extract_name(text)

    # Detect language
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', text))
    has_arabizi = bool(re.search(r'\b[37][a-z]|[a-z][37]\b', lower))
    if has_arabic and (len(text.split()) > 2):
        lang = 'ar'
    elif has_arabizi:
        lang = 'arabizi'
    else:
        lang = 'en'

    # Special intents first
    if is_undo:
        return IntentResult('undo', None, None, None, 0.9, lang, 'rules')
    if is_add_customer:
        return IntentResult('add_customer', name, None, None, 0.88, lang, 'rules')
    if is_yes:
        return IntentResult('yes', None, None, None, 0.95, lang, 'rules')
    if is_no:
        return IntentResult('no', None, None, None, 0.95, lang, 'rules')

    is_greeting = any(kw in tokens for kw in _KW_GREETING) or any(kw in lower for kw in _KW_GREETING_PHRASES)
    is_thanks = any(kw in tokens for kw in _KW_THANKS)
    is_farewell = any(kw in lower for kw in _KW_FAREWELL)

    if is_thanks:
        return IntentResult('thanks', None, None, None, 0.95, lang, 'rules')
    if is_farewell:
        return IntentResult('farewell', None, None, None, 0.95, lang, 'rules')
    if is_greeting and not amount and not name:
        return IntentResult('greeting', None, None, None, 0.95, lang, 'rules')

    # Ranked intent detection
    scores = {
        'check_balance': score_balance,
        'add_payment': score_payment,
        'add_debt': score_debt,
        'list_debtors': score_list,
        'help': score_help,
    }
    best_intent, best_score = max(scores.items(), key=lambda x: x[1])

    if best_score == 0:
        # No keyword match — try heuristic: has amount + name → probably add_debt
        if amount and name:
            return IntentResult('add_debt', name, amount, None, 0.55, lang, 'rules')
        return IntentResult.unknown()

    # Confidence based on score
    confidence = min(0.5 + best_score * 0.15, 0.92)

    return IntentResult(
        intent=best_intent,
        customer_name=name,
        amount=amount,
        payment_method=None,
        confidence=confidence,
        language_detected=lang,
        source='rules',
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _rules_fast_path(rules: IntentResult, raw_text: str) -> bool:
    """True if we can skip Ollama intent JSON (saves one model round-trip)."""
    if rules.intent in ('greeting', 'thanks', 'farewell', 'undo'):
        return True
    if rules.intent in ('help', 'list_debtors') and rules.confidence >= 0.68:
        return True
    if rules.intent == 'help' and len(raw_text.strip()) < 48 and rules.confidence >= 0.60:
        return True
    if rules.intent != 'unknown' and rules.confidence >= 0.88:
        return True
    return False


def parse(text: str, normalized_text: str = '') -> IntentResult:
    """
    Hybrid intent parsing. With OLLAMA_RULES_FIRST (default), keyword rules run first
    when confident enough to avoid an extra Ollama /api/generate call. Otherwise tries
    Ollama first, then rules.

    Args:
        text: Original user message
        normalized_text: Arabizi-normalized version (from arabizi_normalizer)

    Returns:
        IntentResult
    """
    sample = normalized_text or text
    rules_first = _rule_based_detect(sample)

    if OLLAMA_RULES_FIRST and _rules_fast_path(rules_first, text):
        logger.debug("Rules-first intent (skip Ollama): %s", rules_first.intent)
        return rules_first

    # Try Ollama
    if ollama_client.is_available():
        try:
            raw = ollama_client.parse_intent(text, normalized_text)
            confidence = float(raw.get('confidence', 0))

            if confidence >= OLLAMA_CONFIDENCE_THRESHOLD:
                intent = raw.get('intent', 'unknown')
                result = IntentResult(
                    intent=intent,
                    customer_name=raw.get('customer_name'),
                    amount=raw.get('amount'),
                    payment_method=raw.get('payment_method'),
                    confidence=confidence,
                    language_detected=raw.get('language_detected', 'en'),
                    source='ollama',
                )
                logger.debug("Ollama intent: %s (%.2f)", intent, confidence)
                return result
            else:
                logger.debug("Ollama confidence too low (%.2f), falling back to rules", confidence)

        except OllamaUnavailableError:
            logger.debug("Ollama unavailable, using rule-based detection")
        except Exception as e:
            logger.warning("Ollama parse error: %s, using rules", e)

    # Rule-based fallback (reuse first pass if we already computed it)
    logger.debug("Rule-based intent: %s (%.2f)", rules_first.intent, rules_first.confidence)
    return rules_first


def is_confirmation(text: str) -> bool:
    """Quick check — is this a yes/no confirmation?"""
    result = _rule_based_detect(text)
    return result.intent in ('yes', 'no')


def is_yes(text: str) -> bool:
    lower = text.lower().strip()
    return any(kw in lower.split() for kw in _KW_YES) or lower in ('y', '1', 'yes')


def is_no(text: str) -> bool:
    lower = text.lower().strip()
    return any(kw in lower.split() for kw in _KW_NO) or lower in ('n', '0', 'no')
