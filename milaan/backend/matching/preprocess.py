"""
preprocess.py – Name and amount normalization utilities.
All other modules import from here to guarantee consistency.
"""
from __future__ import annotations

import re
import unicodedata

from matching.config import HONORIFICS

# ─────────────────────────────────────────────
# Transliteration variant map  (Urdu/Arabic → canonical Latin token)
# Keys are variants; values are the canonical form.
# Extend this map as new variants are discovered.
# ─────────────────────────────────────────────
_VARIANT_MAP: dict[str, str] = {
    # Muhammad variants
    "muhammad": "muhammad", "mohammed": "muhammad", "mohammad": "muhammad",
    "muhammed": "muhammad", "md":       "muhammad", "mhd":      "muhammad",
    "m":        "muhammad",   # single initial handled separately

    # Ahmed/Ahmad
    "ahmed":  "ahmad", "ahmad": "ahmad", "ahmd": "ahmad",

    # Hussein variants
    "hussain": "hussain", "hussein": "hussain", "husain": "hussain",
    "husein":  "hussain",

    # Ali
    "ali": "ali", "aly": "ali",

    # Khan variants
    "khan": "khan", "khaan": "khan",

    # Common first-name nicknames
    "fahad": "fahad", "fahd": "fahad",
    "bilal": "bilal", "billu": "bilal",
    "usman": "usman", "osman": "usman",
    "zubair": "zubair", "zubayr": "zubair",
    "hasan":  "hasan",  "hassan": "hasan",
}


def normalize_name(name: str) -> str:
    """
    Return a lowercase, punctuation-stripped, de-honorificed,
    transliteration-normalized name suitable for similarity comparison.

    Steps
    -----
    1. Unicode NFKD + ASCII fold (handles diacritics)
    2. Lowercase
    3. Remove punctuation and extra whitespace
    4. Strip honorifics
    5. Map variant tokens to canonical forms
    """
    if not name:
        return ""

    # 1. Unicode fold
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")

    # 2. Lowercase
    name = name.lower()

    # 3. Remove punctuation; keep letters, digits, spaces
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    # 4. Remove honorifics
    tokens = [t for t in name.split() if t not in HONORIFICS]

    # 5. Map variants to canonical forms
    tokens = [_VARIANT_MAP.get(t, t) for t in tokens]

    return " ".join(tokens)


def normalize_amount(amount: float | str) -> float:
    """
    Parse and return a float amount, stripping currency symbols and commas.
    Raises ValueError for un-parseable input.
    """
    if isinstance(amount, (int, float)):
        return float(amount)
    cleaned = re.sub(r"[^\d.]", "", str(amount).replace(",", ""))
    return float(cleaned)


def name_tokens(name: str) -> set[str]:
    """Return the set of normalized tokens from a name."""
    return set(normalize_name(name).split())
