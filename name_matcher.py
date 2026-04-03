"""
Name matching module for Arabic speech → English customer name resolution.

Provides:
- Arabic-to-English phonetic transliteration
- Name normalization (lowercase, strip accents/diacritics, trim)
- Confidence-scored fuzzy matching
- Disambiguation for partial/ambiguous matches
- Debug logging for all matching decisions
"""

import logging
import re
import unicodedata
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Arabic → Latin character-level transliteration map
# ---------------------------------------------------------------------------
_ARABIC_TO_LATIN = {
    'ا': 'a', 'أ': 'a', 'إ': 'i', 'آ': 'aa', 'ء': '',
    'ب': 'b', 'ت': 't', 'ث': 'th',
    'ج': 'j', 'ح': 'h', 'خ': 'kh',
    'د': 'd', 'ذ': 'dh',
    'ر': 'r', 'ز': 'z',
    'س': 's', 'ش': 'sh',
    'ص': 's', 'ض': 'd',
    'ط': 't', 'ظ': 'z',
    'ع': 'a', 'غ': 'gh',
    'ف': 'f', 'ق': 'q',
    'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
    'ه': 'h', 'ة': 'a',
    'و': 'w', 'ي': 'y', 'ى': 'a',
    # Common ligatures / presentation forms
    'لا': 'la',
    # Diacritics (tashkeel) — strip them
    '\u064B': '', '\u064C': '', '\u064D': '', '\u064E': '',
    '\u064F': '', '\u0650': '', '\u0651': '', '\u0652': '',
}

# ---------------------------------------------------------------------------
# Common Arabic name → English spelling variants
# This lookup catches names where simple transliteration diverges from the
# conventional English spelling stored in the database.
# ---------------------------------------------------------------------------
_COMMON_NAME_VARIANTS = {
    # Arabic form (transliterated key) → list of likely English spellings
    'ahmd': ['ahmad', 'ahmed'],
    'ahmad': ['ahmad', 'ahmed'],
    'ahmed': ['ahmad', 'ahmed'],
    'mhmd': ['mohammad', 'mohammed', 'muhammad', 'muhammed', 'mohamad'],
    'mohammad': ['mohammad', 'mohammed', 'muhammad'],
    'mohammed': ['mohammad', 'mohammed', 'muhammad'],
    'muhammad': ['mohammad', 'mohammed', 'muhammad'],
    'hsn': ['hassan', 'hasan'],
    'hassan': ['hassan', 'hasan'],
    'hasan': ['hassan', 'hasan'],
    'hsyn': ['hussein', 'husain', 'hussain'],
    'hussein': ['hussein', 'husain', 'hussain'],
    'aly': ['ali'],
    'ali': ['ali'],
    'amr': ['amr', 'amer', 'amir', 'omar', 'umar'],
    'amir': ['amir', 'amer'],
    'ibrahym': ['ibrahim', 'ebrahim'],
    'ibrahim': ['ibrahim', 'ebrahim'],
    'yusf': ['youssef', 'yousef', 'yusuf', 'joseph'],
    'youssef': ['youssef', 'yousef', 'yusuf'],
    'amr': ['amr', 'amer', 'omar', 'umar'],
    'umar': ['omar', 'umar'],
    'omar': ['omar', 'umar'],
    'uthman': ['othman', 'osman', 'uthman'],
    'othman': ['othman', 'osman', 'uthman'],
    'abd': ['abd', 'abdul', 'abdel'],
    'abdul': ['abd', 'abdul', 'abdel'],
    'abdel': ['abd', 'abdul', 'abdel'],
    'khald': ['khaled', 'khalid'],
    'khaled': ['khaled', 'khalid'],
    'khalid': ['khaled', 'khalid'],
    'thabt': ['thabet', 'thabit'],
    'thabet': ['thabet', 'thabit'],
    'tarq': ['tariq', 'tarek'],
    'tariq': ['tariq', 'tarek'],
    'tarek': ['tariq', 'tarek'],
    'salm': ['salem', 'salim'],
    'salem': ['salem', 'salim'],
    'mstfa': ['mustafa', 'mostafa'],
    'mustafa': ['mustafa', 'mostafa'],
    'mostafa': ['mustafa', 'mostafa'],
    'hmd': ['hamad', 'hamed', 'hamid'],
    'hamad': ['hamad', 'hamed'],
    'slam': ['salam', 'salaam', 'islam'],
    'islam': ['islam'],
    'fhd': ['fahad', 'fahd'],
    'fahad': ['fahad', 'fahd'],
    'rshd': ['rashid', 'rashed', 'rasheed'],
    'rashid': ['rashid', 'rashed'],
    'nsr': ['nasser', 'nasir', 'nasr'],
    'nasser': ['nasser', 'nasir'],
    'sd': ['saad', 'saeed', 'said'],
    'saad': ['saad'],
    'saeed': ['saeed', 'said'],
    'jmal': ['jamal', 'gamal'],
    'jamal': ['jamal', 'gamal'],
    'zyd': ['zaid', 'zayed', 'ziad'],
    'zaid': ['zaid', 'zayed'],
    'mhsn': ['mohsen', 'muhsin'],
    'mohsen': ['mohsen', 'muhsin'],
    'mnsur': ['mansour', 'mansur'],
    'mansour': ['mansour', 'mansur'],
}

# Confidence thresholds
MATCH_THRESHOLD = 0.55       # Minimum to consider a candidate at all
CONFIDENT_THRESHOLD = 0.82   # Auto-select if single match >= this
AMBIGUOUS_GAP = 0.10         # If top two scores are within this gap → ambiguous


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transliterate_arabic(text: str) -> str:
    """Convert Arabic text to a rough Latin phonetic form."""
    if not text:
        return ''
    result = []
    for ch in text:
        if ch in _ARABIC_TO_LATIN:
            result.append(_ARABIC_TO_LATIN[ch])
        elif ch.isascii():
            result.append(ch)
        elif '\u0600' <= ch <= '\u06FF':
            # Unknown Arabic char — skip
            continue
        else:
            result.append(ch)
    return ''.join(result)


def normalize_name(text: str) -> str:
    """Normalize a name: transliterate Arabic, strip accents, lowercase, collapse whitespace."""
    if not text:
        return ''
    # Transliterate any Arabic characters
    text = transliterate_arabic(text)
    # Decompose unicode and strip combining marks (accents)
    text = unicodedata.normalize('NFD', text)
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    # Lowercase and collapse whitespace
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    # Remove non-alphanumeric except spaces, hyphens, apostrophes
    text = re.sub(r"[^a-z0-9 '\-]", '', text)
    return text.strip()


def _expand_variants(name_normalized: str) -> list[str]:
    """Expand a normalized name into variant spellings using the common-names table."""
    words = name_normalized.split()
    if not words:
        return [name_normalized]
    # Build all variant combos for each word
    word_variants = []
    for w in words:
        variants = _COMMON_NAME_VARIANTS.get(w, [w])
        # Always include the original
        if w not in variants:
            variants = [w] + list(variants)
        word_variants.append(variants)

    # Generate combinations (limit to avoid explosion with many words)
    results = ['']
    for wv in word_variants:
        new_results = []
        for prefix in results:
            for v in wv:
                new_results.append((prefix + ' ' + v).strip())
        results = new_results
        if len(results) > 50:
            break
    return results


def _score_pair(input_norm: str, candidate_norm: str) -> float:
    """Score how well input matches a candidate name. Returns 0.0–1.0."""
    if not input_norm or not candidate_norm:
        return 0.0

    # Exact match
    if input_norm == candidate_norm:
        return 1.0

    scores = []

    # Direct SequenceMatcher ratio
    scores.append(SequenceMatcher(None, input_norm, candidate_norm).ratio())

    # Word-level checks
    input_words = input_norm.split()
    candidate_words = candidate_norm.split()

    # Prefix matching: every input word starts some candidate word
    prefix_match = all(
        any(cw.startswith(iw) or iw.startswith(cw) for cw in candidate_words)
        for iw in input_words
    )
    if prefix_match and input_words:
        scores.append(0.78)

    # Word overlap ratio
    overlap = sum(1 for w in input_words if w in candidate_words)
    if candidate_words:
        scores.append(overlap / len(candidate_words))

    # Containment: candidate name fully within input or vice-versa
    if candidate_norm in input_norm or input_norm in candidate_norm:
        length_ratio = min(len(input_norm), len(candidate_norm)) / max(len(input_norm), len(candidate_norm))
        scores.append(0.6 + 0.4 * length_ratio)

    return max(scores)


def partial_token_candidates(input_name: str, customers: list[dict]) -> list[dict]:
    """
    Find customers whose name matches the query by word-level prefix / equality.

    - Each query token (length ≥ 2) must match at least one word in the customer
      name: same word, or customer word starts with the token (e.g. "alex" →
      "Alex", "Alexander").
    - Multi-word queries require ALL tokens to match (e.g. "alex mark" → "Alex Mark").

    Used so "alex" surfaces every "Alex …" customer for disambiguation instead of
    fuzzy-picking a single winner.
    """
    input_norm = normalize_name(input_name)
    if not input_norm:
        return []

    tokens = [t for t in input_norm.split() if len(t) >= 2]
    if not tokens:
        return []

    def name_matches(cname_norm: str) -> bool:
        cwords = cname_norm.split()
        if not cwords:
            return False
        for t in tokens:
            if not any(cw == t or cw.startswith(t) for cw in cwords):
                return False
        return True

    hits: list[dict] = []
    seen_keys: set = set()
    for c in customers:
        cid = c.get('id')
        cname = (c.get('name') or '').strip()
        key = cid if cid is not None else cname.casefold()
        if not cname or key in seen_keys:
            continue
        if name_matches(normalize_name(cname)):
            hits.append(c)
            seen_keys.add(key)

    return hits


def match_customers(input_name: str, customers: list[dict],
                    threshold: float = MATCH_THRESHOLD) -> list[tuple[float, dict]]:
    """
    Match an input name (possibly Arabic) against a list of customer dicts.

    Returns a list of (score, customer) tuples where score >= threshold,
    sorted best-first.  Each customer dict must have a 'name' key.
    """
    input_norm = normalize_name(input_name)
    if not input_norm:
        return []

    input_variants = _expand_variants(input_norm)
    logger.debug("match_customers | input=%r → norm=%r → variants=%s",
                 input_name, input_norm, input_variants[:5])

    scored: list[tuple[float, dict]] = []

    for customer in customers:
        cname = (customer.get('name') or '').strip()
        if not cname:
            continue
        cname_norm = normalize_name(cname)

        # Score input (and its variants) against candidate
        best = 0.0
        for variant in input_variants:
            s = _score_pair(variant, cname_norm)
            if s > best:
                best = s

        # Also score the raw normalized input (handles already-English input)
        direct = _score_pair(input_norm, cname_norm)
        if direct > best:
            best = direct

        if best >= threshold:
            scored.append((best, customer))
            logger.debug("  candidate %r (norm=%r) score=%.3f", cname, cname_norm, best)

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def resolve_customer(
    input_name: str,
    customers: list[dict],
    *,
    require_pick_for_fuzzy: bool = False,
) -> dict:
    """
    High-level resolver that returns one of:
      {"status": "matched",    "customer": {...}}
      {"status": "ambiguous",  "candidates": [{...}, ...], "message": "..."}
      {"status": "no_match",   "message": "..."}

    Logic:
    - Exact full-name case-insensitive match → matched.
    - Partial word match: if several customers share a token (e.g. "alex" → "Alex Mark",
      "Alex Robert") → ambiguous list for the UI picker (up to 12).
    - Single partial word match → matched (then tap-to-confirm in the bot).
    - Else fuzzy scores: confident single winner, or ambiguous / no match.

    require_pick_for_fuzzy: For chat add payment / debt — always show a pick list for
    fuzzy or partial matches (exact full name still matches immediately).
    """
    input_lower = input_name.strip().casefold()
    for c in customers:
        if (c.get('name') or '').strip().casefold() == input_lower:
            logger.info("resolve_customer | input=%r → EXACT match %r", input_name, c['name'])
            return {"status": "matched", "customer": c}

    partial_hits = partial_token_candidates(input_name, customers)
    if len(partial_hits) >= 2:
        partial_hits.sort(key=lambda x: (x.get('name') or '').casefold())
        cap = partial_hits[:12]
        names_str = ', '.join(c['name'] for c in cap[:4])
        logger.info("resolve_customer | input=%r → PARTIAL multi hit [%s]", input_name, names_str)
        return {
            "status": "ambiguous",
            "candidates": cap,
            "message": f"Multiple customers match '{input_name}'. Pick one: {names_str}",
        }
    if len(partial_hits) == 1:
        if require_pick_for_fuzzy:
            c0 = partial_hits[0]
            logger.info(
                "resolve_customer | input=%r → PARTIAL single → pick list %r",
                input_name, c0.get('name'),
            )
            return {
                "status": "ambiguous",
                "candidates": [c0],
                "message": f"Tap the customer for **{input_name.strip()}**:",
            }
        logger.info("resolve_customer | input=%r → PARTIAL single hit %r",
                    input_name, partial_hits[0].get('name'))
        return {"status": "matched", "customer": partial_hits[0]}

    scored = match_customers(input_name, customers)

    if not scored:
        logger.info("resolve_customer | input=%r → NO MATCH", input_name)
        return {"status": "no_match",
                "message": f"No customer found matching '{input_name}'."}

    top_score, top_customer = scored[0]

    for score, cust in scored:
        if cust['name'].strip().casefold() == input_lower:
            logger.info("resolve_customer | input=%r → EXACT match %r", input_name, cust['name'])
            return {"status": "matched", "customer": cust}

    if require_pick_for_fuzzy:
        candidates = [c for _, c in scored[:8]]
        names_str = ", ".join(c['name'] for c in candidates[:4])
        logger.info(
            "resolve_customer | input=%r → PICK list (fuzzy) [%s]",
            input_name, names_str,
        )
        return {
            "status": "ambiguous",
            "candidates": candidates,
            "message": f"Who did you mean? Pick one (matches **{input_name.strip()}**):",
        }

    # Single candidate
    if len(scored) == 1:
        if top_score >= CONFIDENT_THRESHOLD:
            logger.info("resolve_customer | input=%r → single confident match %r (%.3f)",
                        input_name, top_customer['name'], top_score)
            return {"status": "matched", "customer": top_customer}
        else:
            logger.info("resolve_customer | input=%r → single low-confidence match %r (%.3f)",
                        input_name, top_customer['name'], top_score)
            return {
                "status": "ambiguous",
                "candidates": [top_customer],
                "message": f"Did you mean '{top_customer['name']}'?"
            }

    # Multiple candidates
    second_score = scored[1][0]

    # Clear winner: top is confident and well above second place
    if top_score >= CONFIDENT_THRESHOLD and (top_score - second_score) >= AMBIGUOUS_GAP:
        logger.info("resolve_customer | input=%r → confident winner %r (%.3f vs %.3f)",
                     input_name, top_customer['name'], top_score, second_score)
        return {"status": "matched", "customer": top_customer}

    # Ambiguous — return disambiguation list
    candidates = [c for _, c in scored[:8]]
    names_str = ", ".join(c['name'] for c in candidates[:4])
    logger.info("resolve_customer | input=%r → AMBIGUOUS among [%s]", input_name, names_str)
    return {
        "status": "ambiguous",
        "candidates": candidates,
        "message": f"Multiple customers match '{input_name}'. Did you mean: {names_str}?"
    }
