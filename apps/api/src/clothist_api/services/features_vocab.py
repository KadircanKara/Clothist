"""Locked feature vocabulary (25 tokens) loaded from data/taxonomy/features.json.

The LLM prompt advertises this list so it knows what tokens to emit; the
post-pass drops anything outside this list. Restart to pick up edits — no hot
reload (acceptable for single-worker MVP).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

FEATURES_PATH = Path(__file__).resolve().parents[5] / "data" / "taxonomy" / "features.json"
SYNONYMS_PATH = Path(__file__).resolve().parents[5] / "data" / "taxonomy" / "synonyms.json"


@lru_cache(maxsize=1)
def get_features_vocabulary() -> list[str]:
    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"Features taxonomy missing: {FEATURES_PATH}")
    raw = json.loads(FEATURES_PATH.read_text())
    vocab = list(raw["vocabulary"])
    if len(vocab) > 50:
        raise ValueError(
            f"Features vocabulary exceeds 50-token prompt budget cap (got {len(vocab)})."
        )
    return vocab


@lru_cache(maxsize=1)
def get_features_set() -> frozenset[str]:
    return frozenset(get_features_vocabulary())


@lru_cache(maxsize=1)
def get_synonyms() -> dict[str, dict[str, str]]:
    """Return synonyms map of shape {"en": {...}, "tr": {...}}."""
    if not SYNONYMS_PATH.exists():
        raise FileNotFoundError(f"Synonyms taxonomy missing: {SYNONYMS_PATH}")
    raw = json.loads(SYNONYMS_PATH.read_text())
    return {locale: dict(items) for locale, items in raw.items() if locale != "version"}
