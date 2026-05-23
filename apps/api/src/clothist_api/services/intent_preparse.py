"""Deterministic, locale-aware pre-parser.

Runs before the LLM call. Pulls out price/currency tokens, operator
(under/over/between), sort intent, locale, and negation tokens — and strips
them from the text the LLM sees so it can focus on the descriptive parts.

Decimal/thousands rules:
  - EUR, TRY: dot is thousands, comma is decimal.
  - USD, GBP, JPY, CAD, AUD: comma is thousands, dot is decimal.
  - "Step 3.5" override: when the number contains exactly one separator and
    1-2 digits follow it, treat that separator as the decimal point
    regardless of currency convention. Handles Anglo-typed continental
    prices like "€100.50".

Ambiguity hint is emitted only for the narrow `\\d\\.\\d{3}` European case
(e.g. "€1.000") where the user could realistically have meant 1.00. The
frontend surfaces a one-click override; backend stays deterministic.

Spec: plans/senior_dev_v3.md §1c.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from clothist_api.schemas.intent import AmbiguityHint, SortKey
from clothist_api.services.fx import UnknownCurrencyError, to_usd

# Order matters: multi-char and ISO codes first so the alternation prefers
# them over the bare $ symbol.
CURRENCY_PATTERNS: list[tuple[str, str]] = [
    (r"C\$", "CAD"),
    (r"A\$", "AUD"),
    (r"\$", "USD"),
    (r"€", "EUR"),
    (r"£", "GBP"),
    (r"₺", "TRY"),
    (r"¥", "JPY"),
    (r"\bUSD\b", "USD"),
    (r"\bEUR\b", "EUR"),
    (r"\bGBP\b", "GBP"),
    (r"\bTRY\b", "TRY"),
    (r"\bTL\b", "TRY"),
    (r"\bJPY\b", "JPY"),
    (r"\bCAD\b", "CAD"),
    (r"\bAUD\b", "AUD"),
]
EUROPEAN_CONVENTION = frozenset({"EUR", "TRY"})

NUMBER = r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+"
_SYMS = "|".join(p for p, _ in CURRENCY_PATTERNS)
PRE_SYM_RE = re.compile(rf"(?P<sym>{_SYMS})\s*(?P<num>{NUMBER})", re.IGNORECASE)
POST_SYM_RE = re.compile(rf"(?P<num>{NUMBER})\s*(?P<sym>{_SYMS})", re.IGNORECASE)

# Multi-word phrases first within each list so they take precedence.
_OP_BEFORE = [
    (re.compile(r"\bless\s+than\s*$", re.IGNORECASE), "max"),
    (re.compile(r"\bmore\s+than\s*$", re.IGNORECASE), "min"),
    (re.compile(r"\bat\s+least\s*$", re.IGNORECASE), "min"),
    (re.compile(r"\bunder\s*$", re.IGNORECASE), "max"),
    (re.compile(r"\bbelow\s*$", re.IGNORECASE), "max"),
    (re.compile(r"\bover\s*$", re.IGNORECASE), "min"),
    (re.compile(r"\babove\s*$", re.IGNORECASE), "min"),
    (re.compile(r"<\s*$"), "max"),
    (re.compile(r">\s*$"), "min"),
]
_OP_AFTER = [
    (re.compile(r"^\s*altında\b", re.IGNORECASE), "max"),
    (re.compile(r"^\s*altinda\b", re.IGNORECASE), "max"),
    (re.compile(r"^\s*aşağı\b", re.IGNORECASE), "max"),
    (re.compile(r"^\s*asagi\b", re.IGNORECASE), "max"),
    (re.compile(r"^\s*üstünde\b", re.IGNORECASE), "min"),
    (re.compile(r"^\s*ustunde\b", re.IGNORECASE), "min"),
    (re.compile(r"^\s*üzeri(?:nde)?\b", re.IGNORECASE), "min"),
    (re.compile(r"^\s*uzeri(?:nde)?\b", re.IGNORECASE), "min"),
]

_SORT_PATTERNS: list[tuple[re.Pattern[str], SortKey]] = [
    (re.compile(r"\b(?:cheapest|lowest\s+price)\b", re.IGNORECASE), "price_asc"),
    (re.compile(r"\b(?:most\s+expensive|highest\s+price|priciest|premium)\b", re.IGNORECASE), "price_desc"),
    (re.compile(r"\b(?:newest|latest|new\s+arrivals?)\b", re.IGNORECASE), "newest"),
    (re.compile(r"\b(?:highest\s+rated|best\s+reviewed|top\s+rated)\b", re.IGNORECASE), "highest_rated"),
]

_NEGATION_RE = re.compile(r"\b(?:no|without|not)\s+([a-zA-Z][a-zA-Z_\-]+)\b")
_TR_HINTS = re.compile(
    r"\b(?:altında|altinda|aşağı|asagi|üstünde|ustunde|üzeri(?:nde)?|kapüşonlu|kapusonlu|"
    r"pantolon|tişört|tisort|şort|sort|ayakkabı|ayakkabi)\b|[şğçöü]",
    re.IGNORECASE,
)

_AMBIGUOUS_EUR_RE = re.compile(r"^\d\.\d{3}$")
_STOPWORD_STRIP = re.compile(
    r"\b(?:under|less\s+than|more\s+than|at\s+least|over|above|below|between|and|"
    r"altında|altinda|aşağı|asagi|üstünde|ustunde|üzeri(?:nde)?|uzeri(?:nde)?)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class _Detection:
    currency: str
    amount_native: Decimal
    span_start: int
    span_end: int
    raw_token: str


@dataclass(slots=True)
class PrePassResult:
    detected_currency: str | None = None
    detected_amount_native: Decimal | None = None
    min_price_usd: Decimal | None = None
    max_price_usd: Decimal | None = None
    stripped_query: str = ""
    locale: Literal["en", "tr"] = "en"
    sort: SortKey | None = None
    negation_tokens: list[str] = field(default_factory=list)
    ui_hints: list[str] = field(default_factory=list)
    ambiguity_hint: AmbiguityHint | None = None


def _resolve_currency(symbol: str) -> str | None:
    s = symbol.strip()
    for pat, code in CURRENCY_PATTERNS:
        if re.fullmatch(pat, s, re.IGNORECASE):
            return code
    return None


def _parse_number(text: str, currency: str) -> tuple[Decimal, bool]:
    """Returns (amount_decimal, ambiguity_present).

    Ambiguity is True only for the European 1-digit + dot + 3-trailing-digits
    case ("€1.000") where the user might have meant 1.00 as a typo.
    """
    sep_count = text.count(".") + text.count(",")

    # Step 3.5: one separator, 1-2 trailing digits → always decimal.
    if sep_count == 1:
        trailing_match = re.search(r"[.,](\d+)$", text)
        if trailing_match and 1 <= len(trailing_match.group(1)) <= 2:
            return Decimal(text.replace(",", ".")), False

    european = currency in EUROPEAN_CONVENTION
    if european:
        cleaned = text.replace(".", "").replace(",", ".")
        ambiguity = bool(_AMBIGUOUS_EUR_RE.fullmatch(text))
        return Decimal(cleaned), ambiguity
    cleaned = text.replace(",", "")
    return Decimal(cleaned), False


def _detect_locale(q: str, currencies: list[str]) -> Literal["en", "tr"]:
    if "TRY" in currencies:
        return "tr"
    if _TR_HINTS.search(q):
        return "tr"
    return "en"


def _find_operator(
    q: str,
    det: _Detection,
    all_dets: list[_Detection],
) -> Literal["min", "max", "between_low", "between_high"] | None:
    between_match = re.search(r"\bbetween\b", q, re.IGNORECASE)
    if between_match and len(all_dets) >= 2 and between_match.start() < det.span_start:
        ordered = sorted(all_dets, key=lambda d: d.span_start)
        if det is ordered[0]:
            return "between_low"
        if det is ordered[1]:
            return "between_high"

    before = q[max(0, det.span_start - 25):det.span_start]
    for pat, op in _OP_BEFORE:
        if pat.search(before):
            return "min" if op == "min" else "max"

    after = q[det.span_end:det.span_end + 25]
    for pat, op in _OP_AFTER:
        if pat.search(after):
            return "min" if op == "min" else "max"
    return None


def run(q: str) -> PrePassResult:
    """Run the full deterministic pre-pass over `q`."""
    result = PrePassResult(stripped_query=q.strip() if q else "")
    if not result.stripped_query:
        return result

    # 1. Sort intent.
    for sort_re, sort_key in _SORT_PATTERNS:
        if sort_re.search(q):
            if sort_key == "highest_rated":
                result.sort = "relevance"
                result.ui_hints.append("reviews coming soon")
            else:
                result.sort = sort_key
            break

    # 2. Find currency-amount pairs (symbol-before, then symbol-after).
    detections: list[_Detection] = []
    seen_spans: list[tuple[int, int]] = []

    def _record(m: re.Match[str]) -> None:
        ccy = _resolve_currency(m.group("sym"))
        if ccy is None:
            return
        amount, ambiguity = _parse_number(m.group("num"), ccy)
        det = _Detection(
            currency=ccy,
            amount_native=amount,
            span_start=m.start(),
            span_end=m.end(),
            raw_token=m.group(0),
        )
        detections.append(det)
        seen_spans.append((m.start(), m.end()))
        if ambiguity and result.ambiguity_hint is None:
            parsed_as = f"{int(amount):,}"
            alternative = format(amount / Decimal(1000), "f").rstrip("0").rstrip(".") or "0"
            # Always display alternative as two-decimal form (the design's "1.00" framing).
            try:
                alternative = f"{(amount / Decimal(1000)).quantize(Decimal('0.01'))}"
            except Exception:
                pass
            result.ambiguity_hint = AmbiguityHint(
                token=det.raw_token,
                parsed_as=parsed_as,
                alternative=alternative,
            )

    for m in PRE_SYM_RE.finditer(q):
        _record(m)
    for m in POST_SYM_RE.finditer(q):
        if any(s <= m.start() < e or s < m.end() <= e for s, e in seen_spans):
            continue
        _record(m)

    detections.sort(key=lambda d: d.span_start)

    # 3. Apply operators per detection, converting to USD.
    for det in detections:
        op = _find_operator(q, det, detections)
        try:
            usd = to_usd(det.amount_native, det.currency)
        except UnknownCurrencyError:
            continue
        if op == "between_low" or op == "min":
            result.min_price_usd = usd
        elif op == "between_high" or op == "max":
            result.max_price_usd = usd

    # 4. Surface the first-detected native amount/currency for the UI chip.
    if detections:
        first = detections[0]
        result.detected_currency = first.currency
        result.detected_amount_native = first.amount_native

    # 5. Locale.
    result.locale = _detect_locale(q, [d.currency for d in detections])

    # 6. Negation tokens (raw; post-pass maps them to canonical features).
    for nm in _NEGATION_RE.finditer(q):
        token = nm.group(1).lower().strip("-_")
        if token and len(token) > 1 and token not in {"the", "a", "an"}:
            result.negation_tokens.append(token)

    # 7. Strip matched price spans + operator stopwords for the LLM.
    chars = list(q)
    for s, e in seen_spans:
        for i in range(s, e):
            chars[i] = " "
    stripped = "".join(chars)
    stripped = _STOPWORD_STRIP.sub(" ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    result.stripped_query = stripped

    return result
