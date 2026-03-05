"""Tests for resume_generation_service — deterministic template fill.

REQ-026 §3.4: Template fill gathers persona data via
gather_base_resume_content() and mechanically slots it into
template {placeholder} markers. No LLM involved.

Tests verify:
- All placeholders replaced with persona data
- Multiple jobs rendered with correct formatting
- Multiple education entries rendered
- Multiple certifications rendered
- Skills formatted as comma-separated list
- Empty sections handled gracefully (omitted, not left as placeholders)
- Optional fields (linkedin_url) handled when None
- Date formatting matches "Mon YYYY" convention
- Security: regex back-reference injection blocked
- Security: cascading placeholder substitution blocked
"""

import re
from datetime import date
from unittest.mock import AsyncMock, patch

from app.services.pdf_generation import (
    ResumeCertificationEntry,
    ResumeContactInfo,
    ResumeContent,
    ResumeEducationEntry,
    ResumeJobEntry,
    ResumeSkillEntry,
)
from app.services.resume_generation_service import template_fill

# Module path for patching
_MODULE = "app.services.resume_generation_service"
_GATHER_TARGET = f"{_MODULE}.gather_base_resume_content"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEMPLATE_MARKDOWN = """\
# {full_name}

{email} | {phone} | {location} | {linkedin_url}

---

## Professional Summary

{summary}

---

## Experience

### {job_title} — {company_name}
*{start_date} – {end_date}*

- {bullet_1}
- {bullet_2}

---

## Education

### {degree} — {institution}
*{graduation_date}*

---

## Skills

{skills_list}

---

## Certifications

- {certification_1}
- {certification_2}
"""


def _make_content(
    *,
    full_name: str = "Jane Doe",
    email: str = "jane@example.com",
    phone: str = "555-0100",
    city: str = "Denver",
    state: str = "CO",
    linkedin_url: str | None = "linkedin.com/in/janedoe",
    portfolio_url: str | None = None,
    summary: str = "Experienced software engineer.",
    jobs: list[ResumeJobEntry] | None = None,
    education: list[ResumeEducationEntry] | None = None,
    certifications: list[ResumeCertificationEntry] | None = None,
    skills: list[ResumeSkillEntry] | None = None,
) -> ResumeContent:
    """Build a ResumeContent with sensible defaults."""
    if jobs is None:
        jobs = [
            ResumeJobEntry(
                job_title="Senior Engineer",
                company_name="Acme Corp",
                location="Denver, CO",
                start_date=date(2020, 3, 1),
                end_date=None,
                is_current=True,
                bullets=["Led backend migration", "Improved API latency by 40%"],
            ),
        ]
    if education is None:
        education = [
            ResumeEducationEntry(
                degree="B.S. Computer Science",
                institution="State University",
                field_of_study="Computer Science",
                graduation_year=2018,
            ),
        ]
    if certifications is None:
        certifications = [
            ResumeCertificationEntry(
                certification_name="AWS Solutions Architect",
                issuing_organization="Amazon",
                date_obtained=date(2021, 6, 15),
            ),
        ]
    if skills is None:
        skills = [
            ResumeSkillEntry(
                skill_name="Python", skill_type="technical", category="Languages"
            ),
            ResumeSkillEntry(
                skill_name="PostgreSQL", skill_type="technical", category="Databases"
            ),
        ]
    return ResumeContent(
        contact=ResumeContactInfo(
            full_name=full_name,
            email=email,
            phone=phone,
            city=city,
            state=state,
            linkedin_url=linkedin_url,
            portfolio_url=portfolio_url,
        ),
        summary=summary,
        jobs=jobs,
        education=education,
        certifications=certifications,
        skills=skills,
    )


def _make_template(markdown: str = _TEMPLATE_MARKDOWN) -> AsyncMock:
    """Build a mock ResumeTemplate with given markdown content."""
    template = AsyncMock()
    template.markdown_content = markdown
    return template


def _make_resume() -> AsyncMock:
    """Build a mock BaseResume."""
    resume = AsyncMock()
    resume.id = "resume-1"
    return resume


async def _fill_with_content(
    content: ResumeContent,
    markdown: str = _TEMPLATE_MARKDOWN,
) -> str:
    """Run template_fill with mocked gather_base_resume_content."""
    with patch(_GATHER_TARGET, return_value=content):
        return await template_fill(
            _make_resume(), _make_template(markdown), AsyncMock()
        )


# ---------------------------------------------------------------------------
# Header & Contact Info
# ---------------------------------------------------------------------------


class TestHeaderPlaceholders:
    """Verify header/contact info placeholders are replaced."""

    async def test_full_name_replaced(self) -> None:
        result = await _fill_with_content(_make_content(full_name="Alice Smith"))
        assert "# Alice Smith" in result
        assert "{full_name}" not in result

    async def test_contact_info_replaced(self) -> None:
        result = await _fill_with_content(
            _make_content(
                email="alice@test.com", phone="555-1234", city="Austin", state="TX"
            )
        )
        assert "alice@test.com" in result
        assert "555-1234" in result
        assert "Austin, TX" in result

    async def test_linkedin_url_replaced(self) -> None:
        result = await _fill_with_content(
            _make_content(linkedin_url="linkedin.com/in/alice")
        )
        assert "linkedin.com/in/alice" in result
        assert "{linkedin_url}" not in result

    async def test_linkedin_url_none_removes_placeholder(self) -> None:
        result = await _fill_with_content(_make_content(linkedin_url=None))
        assert "{linkedin_url}" not in result


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestSummary:
    """Verify summary placeholder is replaced."""

    async def test_summary_replaced(self) -> None:
        result = await _fill_with_content(
            _make_content(summary="10 years of Python expertise.")
        )
        assert "10 years of Python expertise." in result
        assert "{summary}" not in result

    async def test_empty_summary_handled(self) -> None:
        result = await _fill_with_content(_make_content(summary=""))
        assert "{summary}" not in result


# ---------------------------------------------------------------------------
# Experience Section
# ---------------------------------------------------------------------------


class TestExperienceSection:
    """Verify experience section renders all jobs correctly."""

    async def test_single_job_rendered(self) -> None:
        jobs = [
            ResumeJobEntry(
                job_title="Backend Developer",
                company_name="TechCo",
                location="Remote",
                start_date=date(2021, 1, 1),
                end_date=None,
                is_current=True,
                bullets=["Built REST APIs", "Managed deployments"],
            ),
        ]
        result = await _fill_with_content(_make_content(jobs=jobs))
        assert "### Backend Developer" in result
        assert "TechCo" in result
        assert "Jan 2021" in result
        assert "Present" in result
        assert "- Built REST APIs" in result
        assert "- Managed deployments" in result
        assert "{job_title}" not in result
        assert "{bullet_1}" not in result

    async def test_multiple_jobs_rendered(self) -> None:
        jobs = [
            ResumeJobEntry(
                job_title="Senior Engineer",
                company_name="BigCorp",
                location="NYC",
                start_date=date(2022, 6, 1),
                end_date=None,
                is_current=True,
                bullets=["Led team of 5"],
            ),
            ResumeJobEntry(
                job_title="Junior Engineer",
                company_name="StartupInc",
                location="SF",
                start_date=date(2019, 3, 1),
                end_date=date(2022, 5, 31),
                is_current=False,
                bullets=["Shipped v1.0", "Wrote unit tests"],
            ),
        ]
        result = await _fill_with_content(_make_content(jobs=jobs))
        assert "### Senior Engineer" in result
        assert "BigCorp" in result
        assert "### Junior Engineer" in result
        assert "StartupInc" in result
        assert "- Led team of 5" in result
        assert "- Shipped v1.0" in result
        assert "- Wrote unit tests" in result

    async def test_job_with_end_date_formatted(self) -> None:
        jobs = [
            ResumeJobEntry(
                job_title="Analyst",
                company_name="DataCo",
                location="Boston",
                start_date=date(2018, 9, 1),
                end_date=date(2020, 12, 31),
                is_current=False,
                bullets=["Analyzed data"],
            ),
        ]
        result = await _fill_with_content(_make_content(jobs=jobs))
        assert "Sep 2018" in result
        assert "Dec 2020" in result

    async def test_job_not_current_no_end_date_shows_start_only(self) -> None:
        """Exercise _format_date_range branch: is_current=False, end_date=None."""
        jobs = [
            ResumeJobEntry(
                job_title="Contractor",
                company_name="FreelanceCo",
                location="Remote",
                start_date=date(2017, 4, 1),
                end_date=None,
                is_current=False,
                bullets=["Freelance work"],
            ),
        ]
        result = await _fill_with_content(_make_content(jobs=jobs))
        assert "Apr 2017" in result
        # Should NOT show "Present" since is_current is False
        assert "Present" not in result

    async def test_empty_jobs_removes_section_content(self) -> None:
        result = await _fill_with_content(_make_content(jobs=[]))
        assert "## Experience" in result
        assert "{job_title}" not in result
        assert "{bullet_1}" not in result


# ---------------------------------------------------------------------------
# Education Section
# ---------------------------------------------------------------------------


class TestEducationSection:
    """Verify education section renders all entries."""

    async def test_single_education_rendered(self) -> None:
        education = [
            ResumeEducationEntry(
                degree="M.S. Data Science",
                institution="MIT",
                field_of_study="Data Science",
                graduation_year=2020,
            ),
        ]
        result = await _fill_with_content(_make_content(education=education))
        assert "### M.S. Data Science" in result
        assert "MIT" in result
        assert "2020" in result
        assert "{degree}" not in result

    async def test_multiple_education_rendered(self) -> None:
        education = [
            ResumeEducationEntry(
                degree="Ph.D. Physics",
                institution="Stanford",
                field_of_study="Physics",
                graduation_year=2022,
            ),
            ResumeEducationEntry(
                degree="B.S. Math",
                institution="UCLA",
                field_of_study="Mathematics",
                graduation_year=2016,
            ),
        ]
        result = await _fill_with_content(_make_content(education=education))
        assert "### Ph.D. Physics" in result
        assert "Stanford" in result
        assert "### B.S. Math" in result
        assert "UCLA" in result

    async def test_empty_education_removes_section_content(self) -> None:
        result = await _fill_with_content(_make_content(education=[]))
        assert "## Education" in result
        assert "{degree}" not in result


# ---------------------------------------------------------------------------
# Skills Section
# ---------------------------------------------------------------------------


class TestSkillsSection:
    """Verify skills are rendered as a comma-separated list."""

    async def test_skills_rendered_as_list(self) -> None:
        skills = [
            ResumeSkillEntry(
                skill_name="Python", skill_type="technical", category="Languages"
            ),
            ResumeSkillEntry(
                skill_name="React", skill_type="technical", category="Frameworks"
            ),
            ResumeSkillEntry(
                skill_name="Leadership", skill_type="soft", category="Soft Skills"
            ),
        ]
        result = await _fill_with_content(_make_content(skills=skills))
        assert "Python" in result
        assert "React" in result
        assert "Leadership" in result
        assert "{skills_list}" not in result

    async def test_empty_skills_removes_placeholder(self) -> None:
        result = await _fill_with_content(_make_content(skills=[]))
        assert "{skills_list}" not in result


# ---------------------------------------------------------------------------
# Certifications Section
# ---------------------------------------------------------------------------


class TestCertificationsSection:
    """Verify certifications are rendered correctly."""

    async def test_single_certification_rendered(self) -> None:
        certs = [
            ResumeCertificationEntry(
                certification_name="PMP",
                issuing_organization="PMI",
                date_obtained=date(2023, 1, 15),
            ),
        ]
        result = await _fill_with_content(_make_content(certifications=certs))
        assert "PMP" in result
        assert "{certification_1}" not in result

    async def test_multiple_certifications_rendered(self) -> None:
        certs = [
            ResumeCertificationEntry(
                certification_name="AWS Solutions Architect",
                issuing_organization="Amazon",
                date_obtained=date(2021, 6, 15),
            ),
            ResumeCertificationEntry(
                certification_name="CKA",
                issuing_organization="CNCF",
                date_obtained=date(2022, 11, 1),
            ),
        ]
        result = await _fill_with_content(_make_content(certifications=certs))
        assert "AWS Solutions Architect" in result
        assert "CKA" in result

    async def test_empty_certifications_removes_section_content(self) -> None:
        result = await _fill_with_content(_make_content(certifications=[]))
        assert "## Certifications" in result
        assert "{certification_1}" not in result


# ---------------------------------------------------------------------------
# No Remaining Placeholders
# ---------------------------------------------------------------------------


class TestNoRemainingPlaceholders:
    """Verify the output contains no unreplaced {placeholder} markers."""

    async def test_no_placeholders_remain(self) -> None:
        result = await _fill_with_content(_make_content())
        remaining = re.findall(r"\{[a-z_]+\}", result)
        assert remaining == [], f"Unreplaced placeholders found: {remaining}"

    async def test_output_starts_with_heading(self) -> None:
        """Filled output preserves the template's heading structure."""
        result = await _fill_with_content(_make_content())
        assert result.startswith("# ")
        assert "## Professional Summary" in result
        assert "## Experience" in result


# ---------------------------------------------------------------------------
# Security: Regex back-reference injection
# ---------------------------------------------------------------------------


class TestRegexBackReferenceInjection:
    """Verify persona data with regex metacharacters is rendered safely."""

    async def test_backslash_g_in_job_title(self) -> None:
        r"""Job title containing \g<1> must appear literally, not as group ref."""
        jobs = [
            ResumeJobEntry(
                job_title=r"Senior \g<1> Engineer",
                company_name="Corp",
                location="NYC",
                start_date=date(2022, 1, 1),
                end_date=None,
                is_current=True,
                bullets=["Worked hard"],
            ),
        ]
        result = await _fill_with_content(_make_content(jobs=jobs))
        assert r"\g<1>" in result

    async def test_backslash_1_in_bullet(self) -> None:
        r"""Bullet containing \1 must appear literally."""
        jobs = [
            ResumeJobEntry(
                job_title="Engineer",
                company_name="Corp",
                location="NYC",
                start_date=date(2022, 1, 1),
                end_date=None,
                is_current=True,
                bullets=[r"Improved \1 metric by 50%"],
            ),
        ]
        result = await _fill_with_content(_make_content(jobs=jobs))
        assert r"\1" in result

    async def test_backslash_in_certification_name(self) -> None:
        r"""Certification with backslashes renders safely."""
        certs = [
            ResumeCertificationEntry(
                certification_name=r"Cert\g<2>Name",
                issuing_organization="Org",
                date_obtained=date(2023, 1, 1),
            ),
        ]
        result = await _fill_with_content(_make_content(certifications=certs))
        assert r"Cert\g<2>Name" in result


# ---------------------------------------------------------------------------
# Security: Cascading placeholder substitution
# ---------------------------------------------------------------------------


class TestCascadingPlaceholderSubstitution:
    """Verify persona values containing placeholder tokens are not double-substituted."""

    async def test_full_name_containing_placeholder_token(self) -> None:
        """A name like '{skills_list}' should appear literally in output."""
        result = await _fill_with_content(_make_content(full_name="{skills_list}"))
        assert "# {skills_list}" in result
        # Skills should still appear in the Skills section
        assert "Python" in result

    async def test_summary_containing_placeholder_token(self) -> None:
        """Summary text with '{full_name}' should not expand to the name."""
        result = await _fill_with_content(
            _make_content(full_name="Jane Doe", summary="Hello {full_name}")
        )
        # The summary should contain the literal placeholder, not "Jane Doe"
        assert "Hello {full_name}" in result
