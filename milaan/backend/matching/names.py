"""
names.py – Multi-signal name similarity engine.

Returns a NameScores dataclass with individual sub-scores so the ML
model can use each as an independent feature.  The combined() helper
returns a single weighted score for rule-based use.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import jellyfish          # pip install jellyfish
from rapidfuzz import fuzz  # pip install rapidfuzz

from matching.preprocess import normalize_name, name_tokens


# ─────────────────────────────────────────────
# Output dataclass
# ─────────────────────────────────────────────

@dataclass
class NameScores:
    token_set_ratio:  float   # order-insensitive token similarity  (0-1)
    token_sort_ratio: float   # sorted-token similarity             (0-1)
    jaro_winkler:     float   # character-level similarity          (0-1)
    levenshtein_norm: float   # 1 – normalized edit distance        (0-1)
    prefix_match:     float   # longest common prefix on tokens     (0-1)
    phonetic_match:   float   # soundex key equality                (0-1)
    initial_match:    float   # initials vs full name match         (0-1)
    subset_match:     float   # one name's tokens ⊆ other's tokens  (0-1)

    def combined(self) -> float:
        """
        Weighted combination used by the rule engine.
        Weights reflect which signals are most reliable for South-Asian names.
        ML model uses raw sub-scores instead of this combined value.
        """
        return (
            0.30 * self.token_set_ratio  +
            0.20 * self.token_sort_ratio +
            0.15 * self.jaro_winkler     +
            0.10 * self.levenshtein_norm +
            0.10 * self.prefix_match     +
            0.05 * self.phonetic_match   +
            0.05 * self.initial_match    +
            0.05 * self.subset_match
        )

    def as_dict(self) -> dict[str, float]:
        return {
            "name_token_set":  self.token_set_ratio,
            "name_token_sort": self.token_sort_ratio,
            "name_jaro":       self.jaro_winkler,
            "name_lev_norm":   self.levenshtein_norm,
            "name_prefix":     self.prefix_match,
            "name_phonetic":   self.phonetic_match,
            "name_initial":    self.initial_match,
            "name_subset":     self.subset_match,
            "name_combined":   self.combined(),
        }


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _levenshtein_norm(a: str, b: str) -> float:
    """Normalized Levenshtein: 1 – (distance / max_len)."""
    if not a and not b:
        return 1.0
    dist = jellyfish.levenshtein_distance(a, b)
    max_len = max(len(a), len(b), 1)
    return 1.0 - dist / max_len


def _prefix_match(a: str, b: str) -> float:
    """
    Token-level prefix match.
    Banks cut names at fixed lengths, either spaced ("MUHAMMAD ALI AHME") or
    as a single fused string ("MUHAMMADALIAHME"). Both cases are handled.
    """
    if not a or not b:
        return 0.0
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)

    # Case 1: direct string prefix
    if long_.startswith(short):
        return 1.0

    # Case 2: spaceless-fused comparison
    # e.g. short="muhammadaliahme" vs long_="muhammad ali ahmed"
    long_fused  = "".join(long_.split())
    short_fused = "".join(short.split())
    if long_fused.startswith(short_fused) or short_fused.startswith(long_fused):
        return min(len(short_fused), len(long_fused)) / max(len(long_fused), 1)

    # Case 3: token-level prefix (spaced truncation like "MUHAMMAD ALI AHME")
    toks_s = short.split()
    toks_l = long_.split()
    matches = sum(
        1 for ts, tl in zip(toks_s, toks_l)
        if tl.startswith(ts)
    )
    return matches / max(len(toks_s), 1)


def _phonetic_match(a: str, b: str) -> float:
    """
    Compare Soundex codes for each token pair.
    Returns fraction of token pairs whose codes match.
    """
    ta = a.split() or [""]
    tb = b.split() or [""]
    if not ta or not tb:
        return 0.0
    # Compare all-pairs; take the best alignment fraction
    matches = 0
    for tok_a in ta:
        for tok_b in tb:
            try:
                if jellyfish.soundex(tok_a) == jellyfish.soundex(tok_b):
                    matches += 1
                    break
            except Exception:
                pass
    return matches / max(len(ta), 1)


def _initials_match(a: str, b: str) -> float:
    """
    Match 'M. Ali' against 'Muhammad Ali'.
    IMPORTANT: operates on raw lowercased+punctuation-stripped tokens BEFORE
    variant normalization, so that 'M.' stays as a single char 'm' rather than
    being expanded to 'muhammad' by the variant map.
    Returns 1.0 if all initials match a token on the other side, partial otherwise.
    """
    import re as _re
    def _raw_tokens(s: str) -> list[str]:
        s = s.lower()
        s = _re.sub(r"[^a-z0-9\s]", " ", s)
        return [t for t in s.split() if t]

    ta = _raw_tokens(a)
    tb = _raw_tokens(b)

    def _score(initials_side: list[str], full_side: list[str]) -> float:
        # initials_side: single-char tokens are treated as initials
        full_firsts = {t[0] for t in full_side if t}
        init_chars  = [t for t in initials_side if len(t) == 1]
        if not init_chars:
            return 0.0
        hits = sum(1 for c in init_chars if c in full_firsts)
        return hits / len(init_chars)

    score_ab = _score(ta, tb)
    score_ba = _score(tb, ta)
    return max(score_ab, score_ba)


def _subset_match(a: str, b: str) -> float:
    """
    Return 1.0 if one name's token-set is a subset of the other's.
    Handles 'Ali Ahmed' matching 'Ali Ahmed Khan'.
    """
    sa = name_tokens(a)
    sb = name_tokens(b)
    if not sa or not sb:
        return 0.0
    if sa <= sb or sb <= sa:
        return 1.0
    # Partial: Jaccard-like score
    return len(sa & sb) / len(sa | sb)


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def name_similarity(raw_a: str, raw_b: str) -> NameScores:
    """
    Compute multi-signal name similarity between two raw name strings.

    Parameters
    ----------
    raw_a : str
        Customer name from the order (as entered by the seller / customer).
    raw_b : str
        Sender name from the bank statement (as printed by the bank).

    Returns
    -------
    NameScores
        Individual sub-scores, plus a combined() weighted score.
    """
    a = normalize_name(raw_a)
    b = normalize_name(raw_b)

    if not a and not b:
        return NameScores(1, 1, 1, 1, 1, 1, 1, 1)
    if not a or not b:
        return NameScores(0, 0, 0, 0, 0, 0, 0, 0)

    tsr  = fuzz.token_set_ratio(a, b)  / 100.0
    tsor = fuzz.token_sort_ratio(a, b) / 100.0
    jw   = jellyfish.jaro_winkler_similarity(a, b)
    lev  = _levenshtein_norm(a, b)
    pfx  = _prefix_match(a, b)
    phn  = _phonetic_match(a, b)
    ini  = _initials_match(raw_a, raw_b)   # raw: so "M." stays as "m" (1 char)
    sub  = _subset_match(a, b)

    return NameScores(
        token_set_ratio  = tsr,
        token_sort_ratio = tsor,
        jaro_winkler     = jw,
        levenshtein_norm = lev,
        prefix_match     = pfx,
        phonetic_match   = phn,
        initial_match    = ini,
        subset_match     = sub,
    )
