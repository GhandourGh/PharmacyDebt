"""
Arabizi / Lebanese Arabic normalizer.

Three-pass preprocessing pipeline that runs before both Ollama AND rule-based
intent detection:

  Pass 1 — Arabizi digit substitution (3→ع, 7→ح, etc.)
  Pass 2 — Lebanese phrase dictionary (pharmacy-domain vocab)
  Pass 3 — Number phrase normalization ("50 alf" → "50000")

The goal is NOT to translate everything to pure Arabic — the output is intentionally
mixed so that names like "Ahmad" survive and the LLM sees consistent tokens.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pass 1: Arabizi digit-to-letter substitution
# ---------------------------------------------------------------------------

# These apply only inside words (not to standalone digits like amounts)
_ARABIZI_DIGITS = {
    '2': 'ء',
    '3': 'ع',
    '5': 'خ',
    '6': 'ط',
    '7': 'ح',
    '8': 'غ',
    '9': 'ق',
}

# Pattern: digit surrounded by letters (i.e., part of an Arabizi word)
_ARABIZI_IN_WORD = re.compile(r'(?<=[a-zA-Z\u0600-\u06FF])([23567890])(?=[a-zA-Z\u0600-\u06FF])|^([23567890])(?=[a-zA-Z])|(?<=[a-zA-Z])([23567890])$')


def _substitute_arabizi_digits(text: str) -> str:
    """Replace Arabizi digits inside words only (preserve standalone numbers)."""
    result = []
    i = 0
    words = text.split()
    normalized_words = []
    for word in words:
        # If the word looks like a pure number or starts with digit then letter at end of word
        # check if it's an Arabizi word (contains letters alongside digits)
        has_letters = bool(re.search(r'[a-zA-Z\u0600-\u06FF]', word))
        has_arabizi_digit = bool(re.search(r'[23567890]', word))

        if has_letters and has_arabizi_digit:
            new_word = ''.join(_ARABIZI_DIGITS.get(c, c) for c in word)
            normalized_words.append(new_word)
        else:
            normalized_words.append(word)
    return ' '.join(normalized_words)


# ---------------------------------------------------------------------------
# Pass 2: Lebanese phrase dictionary
# ---------------------------------------------------------------------------

# Order matters: longer phrases first to avoid partial matches
_LEBANESE_PHRASES = [
    # ── Show/Check commands ──────────────────────────────────────────────────
    (r'\bchoufleh\b', 'شوفلي'),
    (r'\bchoufle\b',  'شوفلي'),
    (r'\bshufle\b',   'شوفلي'),
    (r'\bshufleh\b',  'شوفلي'),
    (r'\baddeh\b',    'أديش'),
    (r'\badeh\b',     'أديش'),
    (r'\baddaysh\b',  'أديش'),
    (r'\badaysh\b',   'أديش'),
    (r'\bkaddaysh\b', 'قديش'),
    (r'\bkadaysh\b',  'قديش'),

    # ── Debt/balance prepositions ────────────────────────────────────────────
    (r'\b3leha\b',    'عليها'),
    (r'\b3leh\b',     'عليه'),
    (r'\b3la\b',      'على'),
    (r'\bma3oh\b',    'معه'),
    (r'\bma3o\b',     'معه'),
    (r'\bma3ah\b',    'معها'),
    (r'\bma3a\b',     'معها'),
    (r'\bma3\b',      'مع'),

    # ── Possession / owes ───────────────────────────────────────────────────
    (r'\b3ndo\b',     'عنده'),
    (r'\b3ando\b',    'عنده'),
    (r'\b3indo\b',    'عنده'),
    (r'\b3nde\b',     'عنده'),
    (r'\b3inda\b',    'عنده'),
    (r'\bindo\b',     'عنده'),
    (r'\bindha\b',    'عندها'),
    (r'\bindon\b',    'عندهم'),
    (r'\bando\b',     'عنده'),
    (r'\baando\b',    'عنده'),

    # ── Payment ──────────────────────────────────────────────────────────────
    (r'\bdafaa3\b',   'دفع'),
    (r'\bdfaa3\b',    'دفع'),
    (r'\bdafa3\b',    'دفع'),
    (r'\bdafaa\b',    'دفع'),
    (r'\bdefaa\b',    'دفع'),
    (r'\bdaf3\b',     'دفع'),
    (r'\bwdaa3\b',    'دفع'),
    (r'\bwadaa3\b',   'دفع'),
    (r'\bdaf3a\b',    'دفعة'),

    # ── List / show all ──────────────────────────────────────────────────────
    (r'\bmdyouneen\b',  'مديونين'),
    (r'\bmedyouneen\b', 'مديونين'),
    (r'\bmdyounin\b',   'مديونين'),
    (r'\bmadyouneen\b', 'مديونين'),
    (r'\bkullon\b',   'كلهم'),
    (r'\bkull\b',     'كل'),
    (r'\bkell\b',     'كل'),

    # ── Common Lebanese greetings / fillers ──────────────────────────────────
    (r'\bkifak\b',    'كيف حالك'),
    (r'\bkefak\b',    'كيف حالك'),
    (r'\bkifek\b',    'كيف حالك'),
    (r'\bmnee7\b',    'منيح'),
    (r'\bmnih\b',     'منيح'),
    (r'\bshoo\b',     'شو'),
    (r'\bshou\b',     'شو'),
    (r'\bwlek\b',     'وليك'),
    (r'\byalla\b',    'يلا'),
    (r'\bmashi\b',    'ماشي'),
    (r'\btayeb\b',    'طيب'),
    (r'\bmersi\b',    'شكراً'),

    # ── Yes / No ────────────────────────────────────────────────────────────
    (r'\bla2\b',      'لا'),
    (r'\bla\b',       'لا'),
    (r'\baywa\b',     'نعم'),
    (r'\baywah\b',    'نعم'),
    (r'\byeh\b',      'نعم'),
    (r'\bok\b',       'نعم'),

    # ── Currency ────────────────────────────────────────────────────────────
    (r'\bdolar\b',    'دولار'),
    (r'\bdollar\b',   'دولار'),
    (r'\blira\b',     'ليرة'),
    (r'\blbp\b',      'ليرة لبنانية'),
    (r'\bnuss\b',     'نص'),
    (r'\bnus\b',      'نص'),

    # ── Thousand / amounts ───────────────────────────────────────────────────
    (r'\balef\b',     'ألف'),
    (r'\balf\b',      'ألف'),
]

# Compile patterns once
_COMPILED_PHRASES = [(re.compile(pat, re.IGNORECASE | re.UNICODE), repl)
                     for pat, repl in _LEBANESE_PHRASES]


def _apply_phrase_dict(text: str) -> tuple:
    """Apply Lebanese phrase dictionary. Returns (new_text, list_of_hits)."""
    hits = []
    for pattern, replacement in _COMPILED_PHRASES:
        new_text, n = pattern.subn(replacement, text)
        if n > 0:
            hits.append(pattern.pattern)
            text = new_text
    return text, hits


# ---------------------------------------------------------------------------
# Pass 3: Number phrase normalization
# ---------------------------------------------------------------------------

_NUMBER_PHRASES = [
    # "alf w nuss" → 1500, "alf" → 1000
    (re.compile(r'\b(\d+)\s*(?:ألف|alf|alef)\s+(?:w|و|wa)\s*(?:nuss|nss|نص)\b', re.IGNORECASE), lambda m: str(int(m.group(1)) * 1000 + 500)),
    (re.compile(r'\b(\d+)\s*(?:ألف|alf|alef)\b', re.IGNORECASE), lambda m: str(int(m.group(1)) * 1000)),
    # Standalone "alf" without preceding number → 1000
    (re.compile(r'\b(?:ألف|alf|alef)\b', re.IGNORECASE), lambda m: '1000'),
    # Arabic-Indic digits → Western digits
]

_ARABIC_INDIC = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def _normalize_numbers(text: str) -> str:
    """Convert Lebanese number phrases and Arabic-Indic digits."""
    # Arabic-Indic first
    text = text.translate(_ARABIC_INDIC)
    for pattern, repl in _NUMBER_PHRASES:
        text = pattern.sub(repl, text)
    return text


# ---------------------------------------------------------------------------
# Script detection
# ---------------------------------------------------------------------------

def _detect_script(text: str) -> str:
    """Classify the script of text."""
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', text))
    has_latin = bool(re.search(r'[a-zA-Z]', text))
    has_arabizi_digits = bool(re.search(r'\b[2357890][a-z]|[a-z][2357890]\b', text.lower()))

    if has_arabic and has_latin:
        return 'mixed'
    if has_arabic:
        return 'arabic'
    if has_arabizi_digits:
        return 'arabizi'
    if has_latin:
        return 'latin'
    return 'unknown'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class NormalizationResult:
    original: str
    normalized: str
    detected_script: str
    arabizi_hits: List[str] = field(default_factory=list)


def normalize(text: str) -> NormalizationResult:
    """
    Full normalization pipeline.

    Example:
        normalize("choufle adeh 3leh Ahmad")
        → NormalizationResult(
            original="choufle adeh 3leh Ahmad",
            normalized="شوفلي أديش عليه Ahmad",
            detected_script="arabizi",
            arabizi_hits=[...]
          )
    """
    if not text or not text.strip():
        return NormalizationResult(original=text, normalized=text, detected_script='unknown')

    original = text
    detected_script = _detect_script(text)

    # Pass 1: Lebanese phrase dictionary FIRST (must run before digit substitution
    # so that patterns like "3leh", "dafa3" are matched before '3' → 'ع')
    text, hits = _apply_phrase_dict(text)

    # Pass 2: Arabizi digit substitution (remaining digits in words not caught by phrases)
    if detected_script in ('arabizi', 'mixed', 'latin'):
        text = _substitute_arabizi_digits(text)

    # Pass 3: Number normalization
    text = _normalize_numbers(text)

    return NormalizationResult(
        original=original,
        normalized=text,
        detected_script=detected_script,
        arabizi_hits=hits,
    )


def is_arabic_input(text: str) -> bool:
    """Quick check — does this text contain Arabic or Arabizi?"""
    result = normalize(text)
    return result.detected_script in ('arabic', 'arabizi', 'mixed')


def get_language_hint(text: str) -> str:
    """
    Return language hint based on script detection.
    Returns 'ar' for Arabic/Arabizi, 'en' for Latin.
    """
    script = _detect_script(text)
    return 'ar' if script in ('arabic', 'arabizi', 'mixed') else 'en'
