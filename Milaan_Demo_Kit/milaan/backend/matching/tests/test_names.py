"""
tests/test_names.py – Unit tests for name similarity functions.

Run with:  python -m pytest matching/tests/ -v
"""
import pytest
from matching.preprocess import normalize_name
from matching.names import name_similarity


# ─────────────────────────────────────────────
# normalize_name
# ─────────────────────────────────────────────

class TestNormalizeName:
    def test_lowercase(self):
        assert normalize_name("ALI KHAN") == "ali khan"

    def test_strips_honorifics(self):
        assert "mr" not in normalize_name("Mr Ali Khan")
        assert "haji" not in normalize_name("Haji Muhammad Ali")

    def test_urdu_variant_muhammad(self):
        assert normalize_name("Mohammed Ali") == normalize_name("Muhammad Ali")
        assert normalize_name("Mohammad Ali") == normalize_name("Muhammad Ali")

    def test_urdu_variant_hussain(self):
        assert normalize_name("Hussein Khan") == normalize_name("Hussain Khan")

    def test_removes_punctuation(self):
        result = normalize_name("Ali-Khan.")
        assert "-" not in result
        assert "." not in result

    def test_empty_string(self):
        assert normalize_name("") == ""


# ─────────────────────────────────────────────
# name_similarity
# ─────────────────────────────────────────────

class TestNameSimilarity:
    def _scores(self, a, b):
        return name_similarity(a, b)

    def test_exact_match_high_score(self):
        s = self._scores("Ali Khan", "Ali Khan")
        assert s.combined() > 0.95

    def test_reordered_tokens(self):
        s = self._scores("Ali Ahmed Khan", "Khan Ali Ahmed")
        assert s.token_set_ratio > 0.9

    def test_transliteration_variant(self):
        s = self._scores("Muhammad Ali", "Mohammed Ali")
        assert s.combined() > 0.80, f"Expected > 0.80, got {s.combined():.3f}"

    def test_truncated_name(self):
        # Bank fuses the name without spaces and truncates mid-word:
        # "MUHAMMADALIAHME" from "Muhammad Ali Ahmed"
        # Jaro-Winkler is the right signal for this case (very high on similar strings).
        # prefix_match won't fire because after normalization "ahmad" ≠ "ahme".
        s = self._scores("Muhammad Ali Ahmed", "MUHAMMADALIAHME")
        assert s.jaro_winkler > 0.90, f"Expected jaro_winkler > 0.90, got {s.jaro_winkler:.3f}"

    def test_completely_different_names(self):
        s = self._scores("Ali Khan", "Fatima Sheikh")
        assert s.combined() < 0.50

    def test_subset_match(self):
        s = self._scores("Ali Ahmed", "Ali Ahmed Khan")
        assert s.subset_match == 1.0

    def test_initial_match(self):
        s = self._scores("M. Ali", "Muhammad Ali")
        assert s.initial_match > 0.5

    def test_phonetic_match(self):
        # Soundex: Hussain ~ Hussein
        s = self._scores("Hussain Khan", "Hussein Khan")
        assert s.phonetic_match > 0.5

    def test_returns_all_sub_scores(self):
        s = self._scores("Ali Khan", "Ali Khan")
        d = s.as_dict()
        expected_keys = {
            "name_token_set", "name_token_sort", "name_jaro",
            "name_lev_norm", "name_prefix", "name_phonetic",
            "name_initial", "name_subset", "name_combined",
        }
        assert expected_keys == set(d.keys())

    def test_all_scores_in_0_1(self):
        s = self._scores("Muhammad Ahmed Khan", "MUHAMMADAHMEDKHA")
        for k, v in s.as_dict().items():
            assert 0.0 <= v <= 1.0, f"{k} = {v} out of range"
