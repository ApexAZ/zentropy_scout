"""Tests for modification_limits.py — Resume modification guardrails.

REQ-010 §4.4: Modification Limits (Guardrails).

Three automated checks prevent the Ghostwriter from overstepping:
1. Bullet ID subset — variant bullets must exist in the base resume
2. Summary length ±20% — prevents complete rewrites
3. No new skills — variant summary skills must exist in the persona

Pattern follows test_bullet_reordering.py: helper factory, keyword-only args.
"""

import logging

import pytest

from app.services.modification_limits import (
    VariantValidationData,
    validate_variant_modifications,
)

# =============================================================================
# Helpers
# =============================================================================


def _make_data(
    *,
    base_bullet_ids: set[str] | None = None,
    variant_bullet_ids: set[str] | None = None,
    base_summary: str = "experienced software engineer with python and java skills",
    variant_summary: str = "experienced software engineer with python and java skills",
    variant_summary_skills: set[str] | None = None,
    persona_skill_names: set[str] | None = None,
) -> VariantValidationData:
    """Build VariantValidationData with sensible defaults."""
    return VariantValidationData(
        base_bullet_ids={"b1", "b2", "b3"}
        if base_bullet_ids is None
        else base_bullet_ids,
        variant_bullet_ids={"b1", "b2", "b3"}
        if variant_bullet_ids is None
        else variant_bullet_ids,
        base_summary=base_summary,
        variant_summary=variant_summary,
        variant_summary_skills={"python", "java"}
        if variant_summary_skills is None
        else variant_summary_skills,
        persona_skill_names={"python", "java", "sql"}
        if persona_skill_names is None
        else persona_skill_names,
    )


# =============================================================================
# Test: Check 1 — Bullet ID Subset
# =============================================================================


class TestBulletIdSubset:
    """Check 1: All variant bullet IDs must exist in the base resume."""

    def test_valid_subset(self) -> None:
        """Variant uses a subset of base bullets — no violation."""
        data = _make_data(
            base_bullet_ids={"b1", "b2", "b3"},
            variant_bullet_ids={"b1", "b2"},
        )
        violations = validate_variant_modifications(data=data)
        assert violations == []

    def test_exact_match(self) -> None:
        """Variant uses same bullets as base — no violation."""
        data = _make_data(
            base_bullet_ids={"b1", "b2", "b3"},
            variant_bullet_ids={"b1", "b2", "b3"},
        )
        violations = validate_variant_modifications(data=data)
        assert violations == []

    def test_new_bullet_detected(self) -> None:
        """Variant contains a bullet not in the base resume — violation."""
        data = _make_data(
            base_bullet_ids={"b1", "b2"},
            variant_bullet_ids={"b1", "b2", "b99"},
        )
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1
        assert "b99" in violations[0]

    def test_multiple_new_bullets(self) -> None:
        """Multiple new bullets produce a single violation message listing all."""
        data = _make_data(
            base_bullet_ids={"b1"},
            variant_bullet_ids={"b1", "b88", "b99"},
        )
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1
        assert "b88" in violations[0]
        assert "b99" in violations[0]

    def test_empty_variant_bullets_valid(self) -> None:
        """Empty variant (no bullets selected) is valid — subset of anything."""
        data = _make_data(
            base_bullet_ids={"b1", "b2"},
            variant_bullet_ids=set(),
        )
        violations = validate_variant_modifications(data=data)
        assert violations == []

    def test_empty_base_with_variant_bullets(self) -> None:
        """Base has no bullets but variant does — violation."""
        data = _make_data(
            base_bullet_ids=set(),
            variant_bullet_ids={"b1"},
        )
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1
        assert "b1" in violations[0]


# =============================================================================
# Test: Check 2 — Summary Length (±20%)
# =============================================================================


class TestSummaryLength:
    """Check 2: Variant summary word count within ±20% of base."""

    def test_same_length_valid(self) -> None:
        """Identical word count — no violation."""
        data = _make_data(
            base_summary="one two three four five six seven eight nine ten",
            variant_summary="alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        violations = validate_variant_modifications(data=data)
        assert violations == []

    def test_within_20_percent_shorter(self) -> None:
        """Variant is 20% shorter — still valid (boundary)."""
        # 10 words base, 8 words variant = 80% = exactly at boundary
        base = " ".join(f"word{i}" for i in range(10))
        variant = " ".join(f"word{i}" for i in range(8))
        data = _make_data(base_summary=base, variant_summary=variant)
        violations = validate_variant_modifications(data=data)
        assert violations == []

    def test_within_20_percent_longer(self) -> None:
        """Variant is 20% longer — still valid (boundary)."""
        # 10 words base, 12 words variant = 120% = exactly at boundary
        base = " ".join(f"word{i}" for i in range(10))
        variant = " ".join(f"word{i}" for i in range(12))
        data = _make_data(base_summary=base, variant_summary=variant)
        violations = validate_variant_modifications(data=data)
        assert violations == []

    def test_too_short_violation(self) -> None:
        """Variant is more than 20% shorter — violation."""
        # 10 words base, 7 words variant = 70% < 80%
        base = " ".join(f"word{i}" for i in range(10))
        variant = " ".join(f"word{i}" for i in range(7))
        data = _make_data(base_summary=base, variant_summary=variant)
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1
        assert "10" in violations[0]
        assert "7" in violations[0]

    def test_too_long_violation(self) -> None:
        """Variant is more than 20% longer — violation."""
        # 10 words base, 13 words variant = 130% > 120%
        base = " ".join(f"word{i}" for i in range(10))
        variant = " ".join(f"word{i}" for i in range(13))
        data = _make_data(base_summary=base, variant_summary=variant)
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1
        assert "10" in violations[0]
        assert "13" in violations[0]

    def test_empty_base_empty_variant_valid(self) -> None:
        """Both summaries empty — no violation."""
        data = _make_data(base_summary="", variant_summary="")
        violations = validate_variant_modifications(data=data)
        assert violations == []

    def test_empty_base_nonempty_variant_violation(self) -> None:
        """Base empty but variant has words — violation (added content from nothing)."""
        data = _make_data(base_summary="", variant_summary="new content added")
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1

    def test_nonempty_base_empty_variant_violation(self) -> None:
        """Base has words but variant is empty — violation (deleted summary)."""
        data = _make_data(base_summary="original summary here", variant_summary="")
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1


# =============================================================================
# Test: Check 3 — No New Skills
# =============================================================================


class TestNoNewSkills:
    """Check 3: Skills in variant summary must exist in the persona."""

    def test_valid_subset(self) -> None:
        """Variant skills are a subset of persona skills — no violation."""
        data = _make_data(
            variant_summary_skills={"python", "java"},
            persona_skill_names={"python", "java", "sql", "docker"},
        )
        violations = validate_variant_modifications(data=data)
        assert violations == []

    def test_exact_match(self) -> None:
        """Variant skills exactly match persona skills — no violation."""
        data = _make_data(
            variant_summary_skills={"python", "java"},
            persona_skill_names={"python", "java"},
        )
        violations = validate_variant_modifications(data=data)
        assert violations == []

    def test_new_skill_detected(self) -> None:
        """Variant has a skill not in persona — violation."""
        data = _make_data(
            variant_summary_skills={"python", "java", "kubernetes"},
            persona_skill_names={"python", "java"},
        )
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1
        assert "kubernetes" in violations[0]

    def test_multiple_new_skills(self) -> None:
        """Multiple new skills produce one violation listing all."""
        data = _make_data(
            variant_summary_skills={"python", "rust", "go"},
            persona_skill_names={"python"},
        )
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1
        assert "go" in violations[0]
        assert "rust" in violations[0]

    def test_empty_variant_skills_valid(self) -> None:
        """No skills in variant — no violation."""
        data = _make_data(
            variant_summary_skills=set(),
            persona_skill_names={"python"},
        )
        violations = validate_variant_modifications(data=data)
        assert violations == []

    def test_empty_persona_skills_with_variant_skills(self) -> None:
        """Persona has no skills but variant does — violation."""
        data = _make_data(
            variant_summary_skills={"python"},
            persona_skill_names=set(),
        )
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1
        assert "python" in violations[0]


# =============================================================================
# Test: Combined Checks (Multiple Violations)
# =============================================================================


class TestCombinedViolations:
    """Multiple checks can fail simultaneously."""

    def test_all_three_violations(self) -> None:
        """All three checks fail — three violation messages."""
        data = _make_data(
            base_bullet_ids={"b1"},
            variant_bullet_ids={"b1", "b99"},  # Check 1 fail
            base_summary=" ".join(f"w{i}" for i in range(10)),
            variant_summary=" ".join(f"w{i}" for i in range(20)),  # Check 2 fail
            variant_summary_skills={"python", "haskell"},
            persona_skill_names={"python"},  # Check 3 fail
        )
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 3

    def test_two_violations(self) -> None:
        """Two checks fail — bullets and skills."""
        data = _make_data(
            base_bullet_ids={"b1"},
            variant_bullet_ids={"b1", "b99"},  # Check 1 fail
            variant_summary_skills={"python", "haskell"},
            persona_skill_names={"python"},  # Check 3 fail
        )
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 2

    def test_no_violations(self) -> None:
        """All checks pass — empty violation list."""
        data = _make_data()
        violations = validate_variant_modifications(data=data)
        assert violations == []


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Boundary and unusual inputs."""

    def test_whitespace_only_summary_treated_as_empty(self) -> None:
        """Whitespace-only summaries treated as zero words."""
        data = _make_data(base_summary="   ", variant_summary="   ")
        violations = validate_variant_modifications(data=data)
        # Both empty after split → 0 words each → valid
        assert violations == []

    def test_whitespace_only_base_nonempty_variant_violation(self) -> None:
        """Whitespace-only base with real variant — treated as empty base violation."""
        data = _make_data(base_summary="  \t\n  ", variant_summary="real words here")
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1
        assert "0" in violations[0]

    def test_single_word_summary_boundary(self) -> None:
        """1-word base: variant must also be 1 word (0.8-1.2 range)."""
        data = _make_data(base_summary="engineer", variant_summary="developer")
        violations = validate_variant_modifications(data=data)
        assert violations == []

    def test_single_word_base_two_word_variant(self) -> None:
        """1-word base, 2-word variant = 200% — violation."""
        data = _make_data(base_summary="engineer", variant_summary="software engineer")
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 1

    def test_violation_messages_are_human_readable(self) -> None:
        """Violation messages should contain enough context for debugging."""
        data = _make_data(
            base_bullet_ids={"b1"},
            variant_bullet_ids={"b1", "fabricated-id"},
            base_summary=" ".join(f"w{i}" for i in range(10)),
            variant_summary=" ".join(f"w{i}" for i in range(2)),
            variant_summary_skills={"python", "cobol"},
            persona_skill_names={"python"},
        )
        violations = validate_variant_modifications(data=data)
        assert len(violations) == 3
        # Check that violations reference the specific issues
        bullet_violation = [v for v in violations if "fabricated-id" in v]
        assert len(bullet_violation) == 1
        length_violation = [v for v in violations if "10" in v and "2" in v]
        assert len(length_violation) == 1
        skill_violation = [v for v in violations if "cobol" in v]
        assert len(skill_violation) == 1


# =============================================================================
# Test: Safety Bounds
# =============================================================================


class TestSafetyBounds:
    """Safety bounds prevent resource exhaustion."""

    def test_too_many_base_bullet_ids(self) -> None:
        """Exceeding max base bullet IDs raises ValueError."""
        data = _make_data(
            base_bullet_ids={f"b{i}" for i in range(5001)},
        )
        with pytest.raises(ValueError, match="base_bullet_ids"):
            validate_variant_modifications(data=data)

    def test_too_many_variant_bullet_ids(self) -> None:
        """Exceeding max variant bullet IDs raises ValueError."""
        data = _make_data(
            variant_bullet_ids={f"b{i}" for i in range(5001)},
        )
        with pytest.raises(ValueError, match="variant_bullet_ids"):
            validate_variant_modifications(data=data)

    def test_too_many_variant_skills(self) -> None:
        """Exceeding max variant skills raises ValueError."""
        data = _make_data(
            variant_summary_skills={f"skill{i}" for i in range(1001)},
        )
        with pytest.raises(ValueError, match="variant_summary_skills"):
            validate_variant_modifications(data=data)

    def test_too_many_persona_skills(self) -> None:
        """Exceeding max persona skills raises ValueError."""
        data = _make_data(
            persona_skill_names={f"skill{i}" for i in range(1001)},
        )
        with pytest.raises(ValueError, match="persona_skill_names"):
            validate_variant_modifications(data=data)

    def test_too_long_base_summary(self) -> None:
        """Exceeding max base summary length raises ValueError."""
        data = _make_data(base_summary="x" * 50_001)
        with pytest.raises(ValueError, match="base_summary"):
            validate_variant_modifications(data=data)

    def test_too_long_variant_summary(self) -> None:
        """Exceeding max variant summary length raises ValueError."""
        data = _make_data(variant_summary="x" * 50_001)
        with pytest.raises(ValueError, match="variant_summary"):
            validate_variant_modifications(data=data)

    def test_at_boundary_passes(self) -> None:
        """Exactly at max limits — no ValueError."""
        data = _make_data(
            base_bullet_ids={f"b{i}" for i in range(5000)},
            variant_bullet_ids={f"b{i}" for i in range(5000)},
            variant_summary_skills={f"s{i}" for i in range(1000)},
            persona_skill_names={f"s{i}" for i in range(1000)},
            base_summary="x" * 50_000,
            variant_summary="x" * 50_000,
        )
        # Should not raise
        validate_variant_modifications(data=data)


# =============================================================================
# Test: Logging
# =============================================================================


class TestLogging:
    """Validation results are logged."""

    def test_logs_validation_result(self, caplog: pytest.LogCaptureFixture) -> None:
        """Successful validation logs a debug message."""
        data = _make_data()
        with caplog.at_level(logging.DEBUG):
            validate_variant_modifications(data=data)
        assert any("0 violation" in r.message for r in caplog.records)

    def test_logs_violation_count(self, caplog: pytest.LogCaptureFixture) -> None:
        """Violations are logged with count."""
        data = _make_data(
            base_bullet_ids={"b1"},
            variant_bullet_ids={"b1", "b99"},
        )
        with caplog.at_level(logging.DEBUG):
            validate_variant_modifications(data=data)
        assert any("1 violation" in r.message for r in caplog.records)
