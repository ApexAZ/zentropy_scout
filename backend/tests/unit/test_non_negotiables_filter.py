"""Tests for non-negotiables filter.

REQ-008 §3: Non-Negotiables Pre-Filter.

Tests cover:
- Remote preference filtering (§3.1)
- Minimum salary filtering (§3.1)
- Commutable cities filtering (§3.1)
- Industry exclusions filtering (§3.1)
- Undisclosed data handling (§3.2)
- Filter result structure (§3.3)
"""

from app.services.non_negotiables_filter import (
    NonNegotiablesResult,
    check_commutable_cities,
    check_industry_exclusions,
    check_minimum_salary,
    check_remote_preference,
    check_visa_sponsorship,
)

# =============================================================================
# NonNegotiablesResult Tests
# =============================================================================


class TestNonNegotiablesResult:
    """Tests for NonNegotiablesResult dataclass."""

    def test_passed_result_has_no_failed_reasons(self) -> None:
        """A passed result has empty failed_reasons list."""
        result = NonNegotiablesResult(
            passed=True,
            failed_reasons=[],
            warnings=[],
        )

        assert result.passed is True
        assert result.failed_reasons == []

    def test_failed_result_has_reasons(self) -> None:
        """A failed result contains failure reasons."""
        result = NonNegotiablesResult(
            passed=False,
            failed_reasons=["Remote only, job is Onsite"],
            warnings=[],
        )

        assert result.passed is False
        assert len(result.failed_reasons) == 1

    def test_warnings_can_exist_with_passed_result(self) -> None:
        """Warnings don't cause failure (e.g., undisclosed salary)."""
        result = NonNegotiablesResult(
            passed=True,
            failed_reasons=[],
            warnings=["Salary not disclosed"],
        )

        assert result.passed is True
        assert len(result.warnings) == 1


# =============================================================================
# Remote Preference Tests (§3.1)
# =============================================================================


class TestCheckRemotePreference:
    """Tests for remote preference filter rule."""

    # Remote Only preference
    def test_remote_only_passes_for_remote_job(self) -> None:
        """Remote Only preference passes for Remote jobs."""
        result = check_remote_preference(
            remote_preference="Remote Only",
            job_work_model="Remote",
        )

        assert result.passed is True
        assert result.failed_reasons == []

    def test_remote_only_fails_for_hybrid_job(self) -> None:
        """Remote Only preference fails for Hybrid jobs."""
        result = check_remote_preference(
            remote_preference="Remote Only",
            job_work_model="Hybrid",
        )

        assert result.passed is False
        assert "Remote Only" in result.failed_reasons[0]
        assert "Hybrid" in result.failed_reasons[0]

    def test_remote_only_fails_for_onsite_job(self) -> None:
        """Remote Only preference fails for Onsite jobs."""
        result = check_remote_preference(
            remote_preference="Remote Only",
            job_work_model="Onsite",
        )

        assert result.passed is False
        assert "Onsite" in result.failed_reasons[0]

    # Hybrid OK preference
    def test_hybrid_ok_passes_for_remote_job(self) -> None:
        """Hybrid OK preference passes for Remote jobs."""
        result = check_remote_preference(
            remote_preference="Hybrid OK",
            job_work_model="Remote",
        )

        assert result.passed is True

    def test_hybrid_ok_passes_for_hybrid_job(self) -> None:
        """Hybrid OK preference passes for Hybrid jobs."""
        result = check_remote_preference(
            remote_preference="Hybrid OK",
            job_work_model="Hybrid",
        )

        assert result.passed is True

    def test_hybrid_ok_fails_for_onsite_job(self) -> None:
        """Hybrid OK preference fails for Onsite jobs."""
        result = check_remote_preference(
            remote_preference="Hybrid OK",
            job_work_model="Onsite",
        )

        assert result.passed is False
        assert "Onsite" in result.failed_reasons[0]

    # Onsite OK preference
    def test_onsite_ok_always_passes(self) -> None:
        """Onsite OK preference passes for any work model."""
        for work_model in ["Remote", "Hybrid", "Onsite"]:
            result = check_remote_preference(
                remote_preference="Onsite OK",
                job_work_model=work_model,
            )
            assert result.passed is True

    # No Preference
    def test_no_preference_always_passes(self) -> None:
        """No Preference passes for any work model."""
        for work_model in ["Remote", "Hybrid", "Onsite", None]:
            result = check_remote_preference(
                remote_preference="No Preference",
                job_work_model=work_model,
            )
            assert result.passed is True

    # Undisclosed work model (§3.2)
    def test_remote_only_fails_when_work_model_unknown(self) -> None:
        """Remote Only fails when work model undisclosed (assume Onsite)."""
        result = check_remote_preference(
            remote_preference="Remote Only",
            job_work_model=None,
        )

        assert result.passed is False
        assert "undisclosed" in result.failed_reasons[0].lower()


# =============================================================================
# Minimum Salary Tests (§3.1)
# =============================================================================


class TestCheckMinimumSalary:
    """Tests for minimum salary filter rule."""

    def test_passes_when_job_salary_meets_minimum(self) -> None:
        """Passes when job's max salary >= minimum requirement."""
        result = check_minimum_salary(
            minimum_base_salary=120000,
            job_salary_max=150000,
        )

        assert result.passed is True
        assert result.failed_reasons == []

    def test_passes_when_job_salary_equals_minimum(self) -> None:
        """Passes when job's max salary equals minimum exactly."""
        result = check_minimum_salary(
            minimum_base_salary=120000,
            job_salary_max=120000,
        )

        assert result.passed is True

    def test_fails_when_job_salary_below_minimum(self) -> None:
        """Fails when job's max salary is below minimum."""
        result = check_minimum_salary(
            minimum_base_salary=120000,
            job_salary_max=90000,
        )

        assert result.passed is False
        assert "$90,000" in result.failed_reasons[0]
        assert "$120,000" in result.failed_reasons[0]

    def test_passes_when_salary_undisclosed(self) -> None:
        """Passes when salary not disclosed (benefit of doubt per §3.2)."""
        result = check_minimum_salary(
            minimum_base_salary=120000,
            job_salary_max=None,
        )

        assert result.passed is True
        assert len(result.warnings) == 1
        assert "not disclosed" in result.warnings[0].lower()

    def test_passes_when_no_minimum_set(self) -> None:
        """Passes when user hasn't set a minimum salary."""
        result = check_minimum_salary(
            minimum_base_salary=None,
            job_salary_max=50000,
        )

        assert result.passed is True
        assert result.failed_reasons == []
        assert result.warnings == []


# =============================================================================
# Commutable Cities Tests (§3.1)
# =============================================================================


class TestCheckCommutableCities:
    """Tests for commutable cities filter rule."""

    def test_passes_when_location_in_commutable_list(self) -> None:
        """Passes when job location is in user's commutable cities."""
        result = check_commutable_cities(
            commutable_cities=["San Francisco, CA", "Oakland, CA"],
            job_location="San Francisco, CA",
            job_work_model="Onsite",
        )

        assert result.passed is True

    def test_fails_when_location_not_in_commutable_list(self) -> None:
        """Fails when job location is not commutable."""
        result = check_commutable_cities(
            commutable_cities=["San Francisco, CA", "Oakland, CA"],
            job_location="Seattle, WA",
            job_work_model="Onsite",
        )

        assert result.passed is False
        assert "Seattle, WA" in result.failed_reasons[0]

    def test_passes_for_remote_job_regardless_of_location(self) -> None:
        """Remote jobs pass regardless of location (commuting not needed)."""
        result = check_commutable_cities(
            commutable_cities=["San Francisco, CA"],
            job_location="New York, NY",
            job_work_model="Remote",
        )

        assert result.passed is True

    def test_passes_when_no_commutable_cities_set(self) -> None:
        """Passes when user hasn't set commutable cities (no restriction)."""
        result = check_commutable_cities(
            commutable_cities=[],
            job_location="Anywhere, USA",
            job_work_model="Onsite",
        )

        assert result.passed is True

    def test_location_matching_is_case_insensitive(self) -> None:
        """Location matching should be case-insensitive."""
        result = check_commutable_cities(
            commutable_cities=["San Francisco, CA"],
            job_location="san francisco, ca",
            job_work_model="Onsite",
        )

        assert result.passed is True

    def test_fails_when_location_undisclosed_for_onsite(self) -> None:
        """Fails for onsite job when location is undisclosed (can't verify)."""
        result = check_commutable_cities(
            commutable_cities=["San Francisco, CA"],
            job_location=None,
            job_work_model="Onsite",
        )

        assert result.passed is False
        assert "not disclosed" in result.failed_reasons[0].lower()


# =============================================================================
# Industry Exclusions Tests (§3.1)
# =============================================================================


class TestCheckIndustryExclusions:
    """Tests for industry exclusions filter rule."""

    def test_passes_when_industry_not_excluded(self) -> None:
        """Passes when job industry is not in exclusion list."""
        result = check_industry_exclusions(
            industry_exclusions=["Gambling", "Tobacco"],
            job_industry="Technology",
        )

        assert result.passed is True

    def test_fails_when_industry_is_excluded(self) -> None:
        """Fails when job industry is in exclusion list."""
        result = check_industry_exclusions(
            industry_exclusions=["Gambling", "Tobacco", "Weapons"],
            job_industry="Gambling",
        )

        assert result.passed is False
        assert "Gambling" in result.failed_reasons[0]

    def test_passes_when_industry_undisclosed(self) -> None:
        """Passes when industry not disclosed (can't verify, pass per §3.2)."""
        result = check_industry_exclusions(
            industry_exclusions=["Gambling", "Tobacco"],
            job_industry=None,
        )

        assert result.passed is True
        assert len(result.warnings) == 1
        assert "not disclosed" in result.warnings[0].lower()

    def test_passes_when_no_exclusions_set(self) -> None:
        """Passes when user hasn't set any exclusions."""
        result = check_industry_exclusions(
            industry_exclusions=[],
            job_industry="Any Industry",
        )

        assert result.passed is True

    def test_industry_matching_is_case_insensitive(self) -> None:
        """Industry matching should be case-insensitive."""
        result = check_industry_exclusions(
            industry_exclusions=["Gambling"],
            job_industry="gambling",
        )

        assert result.passed is False
        assert "Gambling" in result.failed_reasons[0]


# =============================================================================
# Visa Sponsorship Tests (§3.1, §3.2)
# =============================================================================


class TestCheckVisaSponsorship:
    """Tests for visa sponsorship filter rule.

    REQ-008 §3.1: visa_sponsorship_required passes if job offers sponsorship OR unknown.
    REQ-008 §3.2: Unknown sponsorship passes with warning.
    """

    def test_passes_when_sponsorship_not_required(self) -> None:
        """Passes when user doesn't require visa sponsorship."""
        result = check_visa_sponsorship(
            visa_sponsorship_required=False,
            job_visa_sponsorship=False,
        )

        assert result.passed is True
        assert result.failed_reasons == []
        assert result.warnings == []

    def test_passes_when_job_offers_sponsorship(self) -> None:
        """Passes when user requires sponsorship and job offers it."""
        result = check_visa_sponsorship(
            visa_sponsorship_required=True,
            job_visa_sponsorship=True,
        )

        assert result.passed is True
        assert result.failed_reasons == []

    def test_fails_when_job_explicitly_no_sponsorship(self) -> None:
        """Fails when user requires sponsorship but job explicitly says no."""
        result = check_visa_sponsorship(
            visa_sponsorship_required=True,
            job_visa_sponsorship=False,
        )

        assert result.passed is False
        assert "sponsorship" in result.failed_reasons[0].lower()
        assert "no" in result.failed_reasons[0].lower()

    def test_passes_when_sponsorship_undisclosed(self) -> None:
        """Passes when sponsorship not disclosed (benefit of doubt per §3.2)."""
        result = check_visa_sponsorship(
            visa_sponsorship_required=True,
            job_visa_sponsorship=None,
        )

        assert result.passed is True
        assert len(result.warnings) == 1
        assert "not disclosed" in result.warnings[0].lower()

    def test_passes_when_not_required_and_undisclosed(self) -> None:
        """Passes without warning when not required and undisclosed."""
        result = check_visa_sponsorship(
            visa_sponsorship_required=False,
            job_visa_sponsorship=None,
        )

        assert result.passed is True
        assert result.warnings == []


# =============================================================================
# Aggregate Filter Results Tests (§3.3)
# =============================================================================


class TestAggregateFilterResults:
    """Tests for aggregate_filter_results().

    REQ-008 §3.3: Combines individual filter results into a single output.
    """

    def test_empty_results_passes(self) -> None:
        """Empty results list passes (no filters = no failures)."""
        from app.services.non_negotiables_filter import aggregate_filter_results

        result = aggregate_filter_results([])

        assert result.passed is True
        assert result.failed_reasons == []
        assert result.warnings == []

    def test_all_passed_returns_passed(self) -> None:
        """When all individual results pass, aggregate passes."""
        from app.services.non_negotiables_filter import aggregate_filter_results

        results = [
            NonNegotiablesResult(passed=True),
            NonNegotiablesResult(passed=True),
            NonNegotiablesResult(passed=True),
        ]

        result = aggregate_filter_results(results)

        assert result.passed is True
        assert result.failed_reasons == []

    def test_one_failure_causes_aggregate_failure(self) -> None:
        """When any individual result fails, aggregate fails."""
        from app.services.non_negotiables_filter import aggregate_filter_results

        results = [
            NonNegotiablesResult(passed=True),
            NonNegotiablesResult(
                passed=False, failed_reasons=["Remote Only required, job is Onsite"]
            ),
            NonNegotiablesResult(passed=True),
        ]

        result = aggregate_filter_results(results)

        assert result.passed is False
        assert len(result.failed_reasons) == 1
        assert "Remote Only" in result.failed_reasons[0]

    def test_multiple_failures_aggregated(self) -> None:
        """Multiple failed reasons are combined in order."""
        from app.services.non_negotiables_filter import aggregate_filter_results

        results = [
            NonNegotiablesResult(
                passed=False, failed_reasons=["Remote Only required, job is Onsite"]
            ),
            NonNegotiablesResult(
                passed=False,
                failed_reasons=["Salary below minimum ($90,000 < $120,000)"],
            ),
        ]

        result = aggregate_filter_results(results)

        assert result.passed is False
        assert len(result.failed_reasons) == 2
        assert "Remote Only" in result.failed_reasons[0]
        assert "Salary" in result.failed_reasons[1]

    def test_warnings_aggregated_from_all_results(self) -> None:
        """Warnings from all results are combined."""
        from app.services.non_negotiables_filter import aggregate_filter_results

        results = [
            NonNegotiablesResult(passed=True, warnings=["Salary not disclosed"]),
            NonNegotiablesResult(passed=True, warnings=["Industry not disclosed"]),
        ]

        result = aggregate_filter_results(results)

        assert result.passed is True
        assert len(result.warnings) == 2
        assert "Salary" in result.warnings[0]
        assert "Industry" in result.warnings[1]

    def test_mixed_failures_and_warnings(self) -> None:
        """Failures and warnings from different results are both collected."""
        from app.services.non_negotiables_filter import aggregate_filter_results

        results = [
            NonNegotiablesResult(passed=True, warnings=["Salary not disclosed"]),
            NonNegotiablesResult(
                passed=False, failed_reasons=["Remote Only required, job is Onsite"]
            ),
            NonNegotiablesResult(
                passed=True, warnings=["Visa sponsorship not disclosed"]
            ),
        ]

        result = aggregate_filter_results(results)

        assert result.passed is False
        assert len(result.failed_reasons) == 1
        assert len(result.warnings) == 2

    def test_single_result_with_multiple_reasons(self) -> None:
        """Individual result with multiple reasons preserved."""
        from app.services.non_negotiables_filter import aggregate_filter_results

        results = [
            NonNegotiablesResult(
                passed=False,
                failed_reasons=["Reason 1", "Reason 2"],
                warnings=["Warning 1"],
            ),
        ]

        result = aggregate_filter_results(results)

        assert result.passed is False
        assert len(result.failed_reasons) == 2
        assert len(result.warnings) == 1
