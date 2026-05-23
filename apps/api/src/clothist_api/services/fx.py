"""FX snapshot loader and conversion helpers.

Convention: rates are stored as units-per-USD (matches open.er-api.com). To
convert a native amount to USD: `amount_usd = amount / rates[ccy]`. Example:
4300 TRY at 32.20 = 4300 / 32.20 ≈ 133.54 USD.

Snapshot is loaded once per process from `data/fx/rates.json`. Restart to
refresh; we are explicitly trading "live rates" for "deterministic, no API key,
no quota risk, comparable prices across re-renders."
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

# Resolve from this file: /apps/api/src/clothist_api/services/fx.py
# parents: [0]=services [1]=clothist_api [2]=src [3]=api [4]=apps [5]=repo-root
RATES_PATH = Path(__file__).resolve().parents[5] / "data" / "fx" / "rates.json"


class UnknownCurrencyError(LookupError):
    """Raised when a currency code has no rate in the snapshot."""


@dataclass(frozen=True, slots=True)
class FXSnapshot:
    base: str
    date: str
    rates: dict[str, Decimal]


@lru_cache(maxsize=1)
def get_snapshot() -> FXSnapshot:
    if not RATES_PATH.exists():
        raise FileNotFoundError(f"FX snapshot missing: {RATES_PATH}")
    raw = json.loads(RATES_PATH.read_text())
    if raw.get("denomination") != "units_per_usd":
        raise ValueError(
            f"FX snapshot denomination must be 'units_per_usd', got {raw.get('denomination')!r}"
        )
    rates = {code.upper(): Decimal(str(rate)) for code, rate in raw["rates"].items()}
    return FXSnapshot(base=raw["base"].upper(), date=raw["date"], rates=rates)


def rate_for(ccy: str) -> Decimal:
    snap = get_snapshot()
    code = ccy.upper()
    if code not in snap.rates:
        raise UnknownCurrencyError(code)
    return snap.rates[code]


def to_usd(amount: Decimal, ccy: str) -> Decimal:
    """Convert `amount` in `ccy` to USD using the snapshot. Returns a Decimal
    rounded to 2 places. Raises `UnknownCurrencyError` if the code is unmapped.
    """
    rate = rate_for(ccy)
    return (amount / rate).quantize(Decimal("0.01"))


def supported_currencies() -> list[str]:
    return sorted(get_snapshot().rates.keys())


def snapshot_date() -> str:
    return get_snapshot().date
