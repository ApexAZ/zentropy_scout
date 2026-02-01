"""Non-negotiables filter for job matching.

REQ-008 §3: Non-Negotiables Pre-Filter.

Non-negotiables are hard requirements that jobs must meet before scoring.
Jobs that fail are stored but not scored (transparency without wasted effort).

Key principle: Jobs fail on disclosed violations, but undisclosed data often
passes (benefit of doubt) — see §3.2 for specific rules.
"""

from dataclasses import dataclass, field

# =============================================================================
# Result Dataclass
# =============================================================================


@dataclass
class NonNegotiablesResult:
    """Result of non-negotiables filter check.

    REQ-008 §3.3: Filter Output Structure.

    Attributes:
        passed: True if job passes all non-negotiable checks.
        failed_reasons: List of human-readable failure reasons.
        warnings: List of warnings (e.g., undisclosed data).
    """

    passed: bool
    failed_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# =============================================================================
# Remote Preference Check
# =============================================================================


def check_remote_preference(
    remote_preference: str,
    job_work_model: str | None,
) -> NonNegotiablesResult:
    """Check if job work model meets user's remote preference.

    REQ-008 §3.1: Remote Preference Filter Rules.

    | Preference | Pass Condition |
    |------------|----------------|
    | Remote Only | job.work_model == "Remote" |
    | Hybrid OK | job.work_model IN ("Remote", "Hybrid") |
    | Onsite OK | Always passes |
    | No Preference | Always passes |

    REQ-008 §3.2: If work_model is undisclosed, assume Onsite (conservative).

    Args:
        remote_preference: User's preference ("Remote Only", "Hybrid OK",
            "Onsite OK", or "No Preference").
        job_work_model: Job's work model ("Remote", "Hybrid", "Onsite", or None).

    Returns:
        NonNegotiablesResult with pass/fail status and reasons.
    """
    # Preferences that always pass
    if remote_preference in ("Onsite OK", "No Preference"):
        return NonNegotiablesResult(passed=True)

    # Handle undisclosed work model (§3.2: assume Onsite)
    effective_work_model = job_work_model if job_work_model else "Onsite"

    if remote_preference == "Remote Only":
        if effective_work_model == "Remote":
            return NonNegotiablesResult(passed=True)

        if job_work_model is None:
            return NonNegotiablesResult(
                passed=False,
                failed_reasons=[
                    "Remote Only required, but work model undisclosed (assumed Onsite)"
                ],
            )

        return NonNegotiablesResult(
            passed=False,
            failed_reasons=[f"Remote Only required, job is {effective_work_model}"],
        )

    if remote_preference == "Hybrid OK":
        if effective_work_model in ("Remote", "Hybrid"):
            return NonNegotiablesResult(passed=True)

        return NonNegotiablesResult(
            passed=False,
            failed_reasons=[
                f"Hybrid or Remote required, job is {effective_work_model}"
            ],
        )

    # Unknown preference — pass to be safe
    return NonNegotiablesResult(passed=True)


# =============================================================================
# Minimum Salary Check
# =============================================================================


def check_minimum_salary(
    minimum_base_salary: int | None,
    job_salary_max: int | None,
) -> NonNegotiablesResult:
    """Check if job salary meets user's minimum requirement.

    REQ-008 §3.1: Minimum Salary Filter Rule.

    Pass Condition: job.salary_max >= minimum OR salary undisclosed.

    REQ-008 §3.2: If salary is undisclosed, pass with warning (benefit of doubt).
    Many good jobs don't disclose salary upfront.

    Args:
        minimum_base_salary: User's minimum salary requirement (or None if not set).
        job_salary_max: Job's maximum salary (or None if undisclosed).

    Returns:
        NonNegotiablesResult with pass/fail status and reasons.
    """
    # No minimum set — always passes
    if minimum_base_salary is None:
        return NonNegotiablesResult(passed=True)

    # Salary undisclosed — pass with warning (§3.2)
    if job_salary_max is None:
        return NonNegotiablesResult(
            passed=True,
            warnings=["Salary not disclosed"],
        )

    # Check if salary meets minimum
    if job_salary_max >= minimum_base_salary:
        return NonNegotiablesResult(passed=True)

    # Failed — salary below minimum
    return NonNegotiablesResult(
        passed=False,
        failed_reasons=[
            f"Salary below minimum (${job_salary_max:,} < ${minimum_base_salary:,})"
        ],
    )


# =============================================================================
# Commutable Cities Check
# =============================================================================


def check_commutable_cities(
    commutable_cities: list[str],
    job_location: str | None,
    job_work_model: str | None,
) -> NonNegotiablesResult:
    """Check if job location is commutable for the user.

    REQ-008 §3.1: Commutable Cities Filter Rule.

    Pass Condition: job.location IN cities OR job.work_model == "Remote".

    Remote jobs pass regardless of location (no commute needed).
    If location is undisclosed for an onsite job, fail (can't verify commutability).

    Args:
        commutable_cities: List of cities user can commute to.
        job_location: Job's location (or None if undisclosed).
        job_work_model: Job's work model ("Remote", "Hybrid", "Onsite", or None).

    Returns:
        NonNegotiablesResult with pass/fail status and reasons.
    """
    # No commutable cities set — no restriction
    if not commutable_cities:
        return NonNegotiablesResult(passed=True)

    # Remote jobs pass regardless of location
    if job_work_model == "Remote":
        return NonNegotiablesResult(passed=True)

    # Location undisclosed for non-remote job — fail
    if job_location is None:
        return NonNegotiablesResult(
            passed=False,
            failed_reasons=[
                "Location not disclosed for non-remote job (cannot verify commutability)"
            ],
        )

    # Check if location is in commutable list (case-insensitive)
    job_location_lower = job_location.lower()
    if any(city.lower() == job_location_lower for city in commutable_cities):
        return NonNegotiablesResult(passed=True)

    # Not in commutable cities
    return NonNegotiablesResult(
        passed=False,
        failed_reasons=[f"Location '{job_location}' not in commutable cities"],
    )


# =============================================================================
# Industry Exclusions Check
# =============================================================================


def check_industry_exclusions(
    industry_exclusions: list[str],
    job_industry: str | None,
) -> NonNegotiablesResult:
    """Check if job industry is excluded by user preferences.

    REQ-008 §3.1: Industry Exclusions Filter Rule.

    Pass Condition: job.industry NOT IN exclusions.

    REQ-008 §3.2: If industry is undisclosed, pass with warning (can't verify).

    Args:
        industry_exclusions: List of industries user wants to avoid.
        job_industry: Job's industry (or None if undisclosed).

    Returns:
        NonNegotiablesResult with pass/fail status and reasons.
    """
    # No exclusions set — always passes
    if not industry_exclusions:
        return NonNegotiablesResult(passed=True)

    # Industry undisclosed — pass with warning (§3.2)
    if job_industry is None:
        return NonNegotiablesResult(
            passed=True,
            warnings=["Industry not disclosed"],
        )

    # Check if industry is excluded (case-insensitive)
    job_industry_lower = job_industry.lower()
    for excluded in industry_exclusions:
        if excluded.lower() == job_industry_lower:
            return NonNegotiablesResult(
                passed=False,
                failed_reasons=[f"Industry '{excluded}' is in exclusion list"],
            )

    return NonNegotiablesResult(passed=True)


# =============================================================================
# Visa Sponsorship Check
# =============================================================================


def check_visa_sponsorship(
    visa_sponsorship_required: bool,
    job_visa_sponsorship: bool | None,
) -> NonNegotiablesResult:
    """Check if job visa sponsorship meets user's requirement.

    REQ-008 §3.1: Visa Sponsorship Filter Rule.

    Pass Condition: job.visa_sponsorship == true OR unknown.

    REQ-008 §3.2: If visa sponsorship is undisclosed, pass with warning.
    Only fail if job explicitly states "No sponsorship."

    Args:
        visa_sponsorship_required: Whether user requires visa sponsorship.
        job_visa_sponsorship: Whether job offers sponsorship (True/False/None).

    Returns:
        NonNegotiablesResult with pass/fail status and reasons.
    """
    # User doesn't require sponsorship — always passes
    if not visa_sponsorship_required:
        return NonNegotiablesResult(passed=True)

    # Job offers sponsorship — passes
    if job_visa_sponsorship is True:
        return NonNegotiablesResult(passed=True)

    # Sponsorship undisclosed — pass with warning (§3.2)
    if job_visa_sponsorship is None:
        return NonNegotiablesResult(
            passed=True,
            warnings=["Visa sponsorship not disclosed"],
        )

    # Job explicitly says no sponsorship — fail
    return NonNegotiablesResult(
        passed=False,
        failed_reasons=["Visa sponsorship required, but job offers no sponsorship"],
    )
