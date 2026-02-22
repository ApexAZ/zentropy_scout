"""Tests for cover letter validation.

REQ-010 §5.4: Cover Letter Validation.

Five validation rules:
    1. Word count bounds (250-350): error if <250, warning if >350
    2. Blacklisted phrases: error for each match (case-insensitive)
    3. Company name in opening: warning if missing
    4. Metric accuracy: error for metrics not from stories
    5. Skills fabrication: warning if >3 unknown skills

Pass/fail: passed = True only when there are zero error-severity issues.
Warnings are shown but do not block.
"""

from dataclasses import replace

import pytest

from app.services.cover_letter_validation import (
    CoverLetterValidation,
    ValidationIssue,
    extract_draft_metrics,
    validate_cover_letter,
)

# =============================================================================
# Helpers
# =============================================================================


def _draft(n_words: int = 300, company: str = "Acme Corp") -> str:
    """Create a draft with approximately n words, company in first paragraph."""
    opening = f"Dear {company} team I am writing"
    count = len(opening.split())
    body = " ".join(["lorem"] * max(0, n_words - count))
    return f"{opening}\n\n{body}"


def _validate(**kwargs) -> CoverLetterValidation:
    """Call validate_cover_letter with sensible defaults."""
    defaults: dict = {
        "draft_text": _draft(),
        "things_to_avoid": [],
        "company_name": "Acme Corp",
        "story_metrics": set(),
        "story_skills": set(),
        "draft_skills": None,
    }
    defaults.update(kwargs)
    return validate_cover_letter(**defaults)


# =============================================================================
# Data Structure Tests
# =============================================================================


class TestValidationIssue:
    """ValidationIssue is a frozen dataclass with severity, rule, message."""

    def test_preserves_original_values(self) -> None:
        """Modifying a copy preserves the original issue values."""
        issue = ValidationIssue(severity="error", rule="test", message="msg")
        updated = replace(issue, severity="warning")
        assert issue.severity == "error"
        assert updated.severity == "warning"

    def test_has_required_fields(self) -> None:
        issue = ValidationIssue(
            severity="error", rule="length_min", message="Too short"
        )
        assert issue.severity == "error"
        assert issue.rule == "length_min"
        assert issue.message == "Too short"


class TestCoverLetterValidation:
    """CoverLetterValidation is a frozen dataclass with passed, issues, word_count."""

    def test_preserves_original_values(self) -> None:
        """Modifying a copy preserves the original validation values."""
        result = CoverLetterValidation(passed=True, issues=(), word_count=300)
        updated = replace(result, passed=False)
        assert result.passed is True
        assert updated.passed is False

    def test_has_required_fields(self) -> None:
        result = CoverLetterValidation(passed=True, issues=(), word_count=300)
        assert result.passed is True
        assert result.issues == ()
        assert result.word_count == 300


# =============================================================================
# Rule 1: Word Count (250-350)
# =============================================================================


class TestWordCountValidation:
    """REQ-010 §5.4 Rule 1: Length check."""

    def test_below_minimum_is_error(self) -> None:
        result = _validate(draft_text=_draft(100))
        assert not result.passed
        errors = [i for i in result.issues if i.rule == "length_min"]
        assert len(errors) == 1
        assert errors[0].severity == "error"

    def test_below_minimum_message_includes_count(self) -> None:
        result = _validate(draft_text=_draft(100))
        errors = [i for i in result.issues if i.rule == "length_min"]
        assert "100" in errors[0].message

    def test_at_minimum_passes(self) -> None:
        result = _validate(draft_text=_draft(250))
        length_issues = [i for i in result.issues if i.rule.startswith("length")]
        assert len(length_issues) == 0

    def test_in_range_no_length_issues(self) -> None:
        result = _validate(draft_text=_draft(300))
        length_issues = [i for i in result.issues if i.rule.startswith("length")]
        assert len(length_issues) == 0

    def test_at_maximum_passes(self) -> None:
        result = _validate(draft_text=_draft(350))
        length_issues = [i for i in result.issues if i.rule.startswith("length")]
        assert len(length_issues) == 0

    def test_above_maximum_is_warning(self) -> None:
        result = _validate(draft_text=_draft(400))
        warnings = [i for i in result.issues if i.rule == "length_max"]
        assert len(warnings) == 1
        assert warnings[0].severity == "warning"

    def test_above_maximum_still_passes(self) -> None:
        """Warnings don't block passage."""
        result = _validate(draft_text=_draft(400))
        assert result.passed

    def test_word_count_in_result(self) -> None:
        result = _validate(draft_text=_draft(300))
        assert result.word_count == 300


# =============================================================================
# Rule 2: Blacklisted Phrases
# =============================================================================


class TestBlacklistValidation:
    """REQ-010 §5.4 Rule 2: Voice adherence — blacklisted phrases."""

    def test_no_blacklist_passes(self) -> None:
        result = _validate(things_to_avoid=[])
        issues = [i for i in result.issues if i.rule == "blacklist_violation"]
        assert len(issues) == 0

    def test_phrase_present_is_error(self) -> None:
        draft = _draft(300).replace("lorem", "synergy lorem", 1)
        result = _validate(draft_text=draft, things_to_avoid=["synergy"])
        assert not result.passed
        errors = [i for i in result.issues if i.rule == "blacklist_violation"]
        assert len(errors) == 1

    def test_error_message_includes_phrase(self) -> None:
        draft = _draft(300).replace("lorem", "synergy lorem", 1)
        result = _validate(draft_text=draft, things_to_avoid=["synergy"])
        errors = [i for i in result.issues if i.rule == "blacklist_violation"]
        assert "synergy" in errors[0].message

    def test_case_insensitive(self) -> None:
        draft = _draft(300).replace("lorem", "SYNERGY lorem", 1)
        result = _validate(draft_text=draft, things_to_avoid=["synergy"])
        errors = [i for i in result.issues if i.rule == "blacklist_violation"]
        assert len(errors) == 1

    def test_multiple_violations_reported(self) -> None:
        draft = _draft(300)
        draft = draft.replace("lorem", "synergy", 1)
        draft = draft.replace("lorem", "leverage", 1)
        result = _validate(draft_text=draft, things_to_avoid=["synergy", "leverage"])
        errors = [i for i in result.issues if i.rule == "blacklist_violation"]
        assert len(errors) == 2

    def test_phrase_not_present_passes(self) -> None:
        result = _validate(things_to_avoid=["synergy", "leverage"])
        issues = [i for i in result.issues if i.rule == "blacklist_violation"]
        assert len(issues) == 0


# =============================================================================
# Rule 3: Company Specificity
# =============================================================================


class TestCompanySpecificityValidation:
    """REQ-010 §5.4 Rule 3: Company name in opening paragraph."""

    def test_company_in_first_paragraph_passes(self) -> None:
        result = _validate(
            draft_text=_draft(300, company="Acme Corp"),
            company_name="Acme Corp",
        )
        issues = [i for i in result.issues if i.rule == "company_specificity"]
        assert len(issues) == 0

    def test_company_missing_from_first_paragraph_is_warning(self) -> None:
        opening = "Dear team I am writing to apply for this role"
        body = " ".join(["lorem"] * 290)
        draft = f"{opening}\n\n{body}"
        result = _validate(draft_text=draft, company_name="Acme Corp")
        warnings = [i for i in result.issues if i.rule == "company_specificity"]
        assert len(warnings) == 1
        assert warnings[0].severity == "warning"

    def test_case_insensitive_match(self) -> None:
        opening = "Dear ACME CORP team I am writing"
        body = " ".join(["lorem"] * 293)
        draft = f"{opening}\n\n{body}"
        result = _validate(draft_text=draft, company_name="Acme Corp")
        issues = [i for i in result.issues if i.rule == "company_specificity"]
        assert len(issues) == 0

    def test_empty_company_name_skips_check(self) -> None:
        opening = "Dear team I am writing to apply for this role"
        body = " ".join(["lorem"] * 290)
        draft = f"{opening}\n\n{body}"
        result = _validate(draft_text=draft, company_name="")
        issues = [i for i in result.issues if i.rule == "company_specificity"]
        assert len(issues) == 0

    def test_warning_does_not_block_passing(self) -> None:
        opening = "Dear team I am writing to apply for this role"
        body = " ".join(["lorem"] * 290)
        draft = f"{opening}\n\n{body}"
        result = _validate(draft_text=draft, company_name="Acme Corp")
        assert result.passed

    def test_no_paragraph_break_uses_first_500_chars(self) -> None:
        """When no \\n\\n separator, use first 500 chars as opening."""
        draft = "Dear Acme Corp team " + " ".join(["lorem"] * 296)
        result = _validate(draft_text=draft, company_name="Acme Corp")
        issues = [i for i in result.issues if i.rule == "company_specificity"]
        assert len(issues) == 0


# =============================================================================
# Rule 4: Metric Accuracy
# =============================================================================


class TestMetricAccuracyValidation:
    """REQ-010 §5.4 Rule 4: Metrics must come from selected stories."""

    def test_draft_metric_from_stories_passes(self) -> None:
        draft = _draft(300).replace("lorem", "achieved 40% lorem", 1)
        result = _validate(draft_text=draft, story_metrics={"40%"})
        issues = [i for i in result.issues if i.rule == "metric_accuracy"]
        assert len(issues) == 0

    def test_fabricated_metric_is_error(self) -> None:
        draft = _draft(300).replace("lorem", "achieved 99% lorem", 1)
        result = _validate(draft_text=draft, story_metrics={"40%"})
        assert not result.passed
        errors = [i for i in result.issues if i.rule == "metric_accuracy"]
        assert len(errors) >= 1

    def test_error_message_includes_metric(self) -> None:
        draft = _draft(300).replace("lorem", "achieved 99% lorem", 1)
        result = _validate(draft_text=draft, story_metrics=set())
        errors = [i for i in result.issues if i.rule == "metric_accuracy"]
        assert "99%" in errors[0].message

    def test_no_metrics_in_draft_passes(self) -> None:
        result = _validate(story_metrics={"40%", "$2m"})
        issues = [i for i in result.issues if i.rule == "metric_accuracy"]
        assert len(issues) == 0

    def test_no_story_metrics_no_draft_metrics_passes(self) -> None:
        result = _validate(story_metrics=set())
        issues = [i for i in result.issues if i.rule == "metric_accuracy"]
        assert len(issues) == 0

    def test_dollar_amount_from_story_passes(self) -> None:
        draft = _draft(300).replace("lorem", "saved $2M lorem", 1)
        result = _validate(draft_text=draft, story_metrics={"$2M"})
        issues = [i for i in result.issues if i.rule == "metric_accuracy"]
        assert len(issues) == 0

    def test_multiplier_from_story_passes(self) -> None:
        draft = _draft(300).replace("lorem", "achieved 3x lorem", 1)
        result = _validate(draft_text=draft, story_metrics={"3x"})
        issues = [i for i in result.issues if i.rule == "metric_accuracy"]
        assert len(issues) == 0


# =============================================================================
# Rule 5: Fabrication Check (Skills)
# =============================================================================


class TestFabricationCheckValidation:
    """REQ-010 §5.4 Rule 5: Skills should come from selected stories."""

    def test_all_draft_skills_in_stories_passes(self) -> None:
        result = _validate(
            story_skills={"python", "fastapi", "docker"},
            draft_skills={"python", "fastapi"},
        )
        issues = [i for i in result.issues if i.rule == "potential_fabrication"]
        assert len(issues) == 0

    def test_few_unknown_skills_within_tolerance(self) -> None:
        """3 unknown skills is within threshold."""
        result = _validate(
            story_skills={"python"},
            draft_skills={"python", "rust", "go", "java"},
        )
        issues = [i for i in result.issues if i.rule == "potential_fabrication"]
        assert len(issues) == 0

    def test_many_unknown_skills_is_warning(self) -> None:
        """More than 3 unknown skills triggers warning."""
        result = _validate(
            story_skills={"python"},
            draft_skills={"python", "rust", "go", "java", "kotlin"},
        )
        warnings = [i for i in result.issues if i.rule == "potential_fabrication"]
        assert len(warnings) == 1
        assert warnings[0].severity == "warning"

    def test_no_draft_skills_skips_check(self) -> None:
        result = _validate(draft_skills=None)
        issues = [i for i in result.issues if i.rule == "potential_fabrication"]
        assert len(issues) == 0

    def test_warning_does_not_block_passing(self) -> None:
        result = _validate(
            story_skills=set(),
            draft_skills={"a", "b", "c", "d", "e"},
        )
        assert result.passed

    def test_case_insensitive_comparison(self) -> None:
        result = _validate(
            story_skills={"Python", "FastAPI"},
            draft_skills={"python", "fastapi"},
        )
        issues = [i for i in result.issues if i.rule == "potential_fabrication"]
        assert len(issues) == 0


# =============================================================================
# Extract Draft Metrics
# =============================================================================


class TestExtractDraftMetrics:
    """Tests for the extract_draft_metrics utility function."""

    def test_extracts_percentages(self) -> None:
        metrics = extract_draft_metrics("Reduced costs by 40%")
        assert "40%" in metrics

    def test_extracts_decimal_percentages(self) -> None:
        metrics = extract_draft_metrics("Improved efficiency by 2.5%")
        assert "2.5%" in metrics

    def test_extracts_dollar_amounts(self) -> None:
        metrics = extract_draft_metrics("Saved $2.5M annually")
        assert "$2.5m" in metrics

    def test_extracts_dollar_with_commas(self) -> None:
        metrics = extract_draft_metrics("Saved $100,000 per year")
        assert "$100,000" in metrics

    def test_extracts_multipliers(self) -> None:
        metrics = extract_draft_metrics("Improved throughput by 3x")
        assert "3x" in metrics

    def test_empty_text_returns_empty(self) -> None:
        assert extract_draft_metrics("") == set()

    def test_no_metrics_returns_empty(self) -> None:
        assert extract_draft_metrics("No quantified outcomes here") == set()

    def test_returns_lowercased(self) -> None:
        metrics = extract_draft_metrics("Saved $5M")
        assert all(m == m.lower() for m in metrics)


# =============================================================================
# Pass/Fail Logic
# =============================================================================


class TestPassedLogic:
    """passed = not any(issue.severity == 'error' for issue in issues)."""

    def test_no_issues_passes(self) -> None:
        result = _validate()
        assert result.passed

    def test_only_warnings_passes(self) -> None:
        result = _validate(draft_text=_draft(400))
        assert result.passed

    def test_error_fails(self) -> None:
        result = _validate(draft_text=_draft(100))
        assert not result.passed

    def test_mixed_errors_and_warnings(self) -> None:
        """Both errors and warnings present — fails due to errors."""
        opening = "Dear team I am writing to apply"
        body = " ".join(["lorem"] * 90)
        draft = f"{opening}\n\n{body}"
        result = _validate(draft_text=draft, company_name="Acme Corp")
        assert not result.passed
        assert any(i.severity == "error" for i in result.issues)
        assert any(i.severity == "warning" for i in result.issues)


# =============================================================================
# Safety Bounds
# =============================================================================


class TestSafetyBounds:
    """Inputs exceeding safety limits should raise ValueError."""

    def test_oversized_draft_raises(self) -> None:
        with pytest.raises(ValueError, match="draft_text"):
            _validate(draft_text="x " * 50_001)

    def test_too_long_company_name_raises(self) -> None:
        with pytest.raises(ValueError, match="company_name"):
            _validate(company_name="x" * 501)

    def test_too_many_things_to_avoid_raises(self) -> None:
        with pytest.raises(ValueError, match="things_to_avoid"):
            _validate(things_to_avoid=[f"p{i}" for i in range(101)])

    def test_too_many_story_metrics_raises(self) -> None:
        with pytest.raises(ValueError, match="story_metrics"):
            _validate(story_metrics={f"{i}%" for i in range(201)})

    def test_too_many_story_skills_raises(self) -> None:
        with pytest.raises(ValueError, match="story_skills"):
            _validate(story_skills={f"s{i}" for i in range(501)})

    def test_too_many_draft_skills_raises(self) -> None:
        with pytest.raises(ValueError, match="draft_skills"):
            _validate(draft_skills={f"s{i}" for i in range(501)})

    def test_at_boundary_does_not_raise(self) -> None:
        """Inputs exactly at limits should be accepted."""
        result = _validate(
            things_to_avoid=[f"p{i}" for i in range(100)],
            company_name="x" * 500,
        )
        assert isinstance(result, CoverLetterValidation)


# =============================================================================
# Logging
# =============================================================================


class TestLogging:
    """Debug logging on validation results."""

    def test_logs_issue_count_on_pass(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("DEBUG", logger="app.services.cover_letter_validation"):
            _validate()
        assert "0 issue(s)" in caplog.text
        assert "passed=True" in caplog.text

    def test_logs_issue_count_on_fail(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("DEBUG", logger="app.services.cover_letter_validation"):
            _validate(draft_text=_draft(100))
        assert "1 issue(s)" in caplog.text
        assert "passed=False" in caplog.text
