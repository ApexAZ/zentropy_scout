"""Tests for voice application rules.

REQ-010 §3.2: Voice Application Rules
Rule 1: Avoid blacklisted terms absolutely — validate_no_blacklist.

The validate_no_blacklist function checks generated text against a user's
things_to_avoid list and returns any violations found.
"""

from app.services.voice_validation import validate_no_blacklist

# =============================================================================
# Basic Behavior Tests
# =============================================================================


class TestValidateNoBlacklist:
    """Tests for validate_no_blacklist per REQ-010 §3.2 Rule 1."""

    def test_returns_empty_list_when_no_violations(self) -> None:
        """No violations should return an empty list."""
        result = validate_no_blacklist(
            text="I led the cloud migration project.",
            things_to_avoid=["synergy", "leverage"],
        )
        assert result == []

    def test_detects_single_blacklisted_term(self) -> None:
        """Should detect a single blacklisted term in the text."""
        result = validate_no_blacklist(
            text="I leveraged my expertise in cloud computing.",
            things_to_avoid=["leveraged"],
        )
        assert len(result) == 1
        assert "leveraged" in result[0].lower()

    def test_detects_multiple_blacklisted_terms(self) -> None:
        """Should detect all blacklisted terms present."""
        result = validate_no_blacklist(
            text="I leveraged synergy to drive results.",
            things_to_avoid=["leveraged", "synergy", "paradigm"],
        )
        assert len(result) == 2

    def test_case_insensitive_matching(self) -> None:
        """Matching must be case-insensitive per REQ-010 §3.2."""
        result = validate_no_blacklist(
            text="I LEVERAGED my expertise.",
            things_to_avoid=["leveraged"],
        )
        assert len(result) == 1

    def test_case_insensitive_blacklist_term(self) -> None:
        """Blacklist terms themselves should match case-insensitively."""
        result = validate_no_blacklist(
            text="I leveraged my expertise.",
            things_to_avoid=["LEVERAGED"],
        )
        assert len(result) == 1

    def test_substring_matching(self) -> None:
        """Should match blacklisted terms as substrings."""
        result = validate_no_blacklist(
            text="This is a team-player mentality.",
            things_to_avoid=["team-player"],
        )
        assert len(result) == 1

    def test_violation_message_includes_term(self) -> None:
        """Each violation message must include the original blacklisted term."""
        result = validate_no_blacklist(
            text="We created synergy across departments.",
            things_to_avoid=["synergy"],
        )
        assert len(result) == 1
        assert "synergy" in result[0]


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestValidateNoBlacklistEdgeCases:
    """Edge cases for validate_no_blacklist."""

    def test_empty_text(self) -> None:
        """Empty text should return no violations."""
        result = validate_no_blacklist(
            text="",
            things_to_avoid=["synergy"],
        )
        assert result == []

    def test_empty_blacklist(self) -> None:
        """Empty blacklist should return no violations."""
        result = validate_no_blacklist(
            text="I leveraged synergy to drive results.",
            things_to_avoid=[],
        )
        assert result == []

    def test_both_empty(self) -> None:
        """Both empty should return no violations."""
        result = validate_no_blacklist(text="", things_to_avoid=[])
        assert result == []

    def test_whitespace_only_text(self) -> None:
        """Whitespace-only text should return no violations."""
        result = validate_no_blacklist(
            text="   \n\t  ",
            things_to_avoid=["synergy"],
        )
        assert result == []

    def test_multi_word_blacklist_phrase(self) -> None:
        """Should match multi-word blacklisted phrases."""
        result = validate_no_blacklist(
            text="I was responsible for leading the team.",
            things_to_avoid=["responsible for"],
        )
        assert len(result) == 1

    def test_duplicate_blacklist_terms_not_double_counted(self) -> None:
        """Same term appearing twice in blacklist should only report once."""
        result = validate_no_blacklist(
            text="I leveraged my expertise.",
            things_to_avoid=["leveraged", "leveraged"],
        )
        assert len(result) == 1

    def test_case_variant_duplicates_not_double_counted(self) -> None:
        """Same term in different cases should only report once."""
        result = validate_no_blacklist(
            text="I leveraged my expertise.",
            things_to_avoid=["leveraged", "LEVERAGED", "Leveraged"],
        )
        assert len(result) == 1

    def test_whitespace_padded_term_still_matches(self) -> None:
        """Terms with leading/trailing whitespace should be stripped and matched."""
        result = validate_no_blacklist(
            text="We created synergy across departments.",
            things_to_avoid=["  synergy  "],
        )
        assert len(result) == 1
        assert "synergy" in result[0]

    def test_violation_message_preserves_original_term_casing(self) -> None:
        """Violation message should use the original blacklist term casing."""
        result = validate_no_blacklist(
            text="we created synergy.",
            things_to_avoid=["Synergy"],
        )
        assert "Synergy" in result[0]

    def test_term_appears_multiple_times_in_text(self) -> None:
        """Term appearing multiple times in text should still be one violation."""
        result = validate_no_blacklist(
            text="Synergy drives synergy which creates more synergy.",
            things_to_avoid=["synergy"],
        )
        assert len(result) == 1

    def test_empty_string_in_blacklist_ignored(self) -> None:
        """Empty strings in the blacklist should be ignored."""
        result = validate_no_blacklist(
            text="I led the project.",
            things_to_avoid=["", "  "],
        )
        assert result == []

    def test_returns_list_type(self) -> None:
        """Should always return a list."""
        result = validate_no_blacklist(text="Hello.", things_to_avoid=[])
        assert isinstance(result, list)
