"""Unit tests for Entry-Level User edge cases.

REQ-008 §9.3: Entry-Level Users Edge Cases.

Tests verify that scoring handles entry-level users appropriately:
1. Users with <2 years experience applying to entry-level jobs
2. Users with <2 years experience applying to experienced roles (penalty)
3. Job title detection for entry-level roles (junior, intern, new grad)
4. Growth trajectory shows step-up potential for entry-level users
5. System produces valid scores and explanations for entry-level users

Design note from REQ-008 §9.3:
"Users with <2 years experience may score poorly on experience-heavy roles."

The future entry-level boost enhancement (deferred) would increase experience scores
for entry-level users applying to entry-level jobs. These tests document the
CURRENT behavior without that boost.
"""

from dataclasses import dataclass

from app.services.experience_level import calculate_experience_score
from app.services.explanation_generation import generate_explanation
from app.services.fit_score import (
    FIT_NEUTRAL_SCORE,
    FitScoreResult,
    calculate_fit_score,
)
from app.services.hard_skills_match import (
    JobSkillInput,
    PersonaSkillInput,
    calculate_hard_skills_score,
)
from app.services.stretch_score import (
    StretchScoreResult,
    calculate_growth_trajectory,
    calculate_stretch_score,
    calculate_target_skills_exposure,
    infer_level,
)

# =============================================================================
# Helper: Create mock objects for entry-level scenarios
# =============================================================================


@dataclass
class MockSkill:
    """Mock skill for testing."""

    skill_name: str
    skill_type: str  # "Hard" or "Soft"
    proficiency: str = "Learning"  # Entry-level users often "Learning"


@dataclass
class MockExtractedSkill:
    """Mock extracted skill from job posting."""

    skill_name: str
    skill_type: str
    is_required: bool = True


@dataclass
class MockPersona:
    """Mock persona for entry-level users."""

    years_experience: int | None
    current_role: str | None
    target_roles: list[str]
    target_skills: list[str]
    skills: list[MockSkill]


@dataclass
class MockJobPosting:
    """Mock job posting for testing."""

    job_title: str
    years_experience_min: int | None
    years_experience_max: int | None
    salary_max: int | None
    ghost_score: int
    extracted_skills: list[MockExtractedSkill]


# =============================================================================
# Entry-Level Persona Factories
# =============================================================================


def make_new_grad_developer_persona() -> MockPersona:
    """Create persona: New grad with CS degree seeking first developer job.

    This represents a common entry-level scenario where:
    - 0 years professional experience (recent graduate)
    - Skills from coursework/projects: Python, JavaScript, Git, SQL
    - Soft skills developed in school: Teamwork, Communication
    - Target role: Software Engineer / Junior Developer
    - Target skills: React, TypeScript (want to learn frontend)
    """
    return MockPersona(
        years_experience=0,
        current_role=None,  # No prior professional role
        target_roles=["Software Engineer", "Junior Developer"],
        target_skills=["React", "TypeScript", "Node.js"],
        skills=[
            # Hard skills from coursework (proficiency is "Learning")
            MockSkill("Python", "Hard", "Learning"),
            MockSkill("JavaScript", "Hard", "Learning"),
            MockSkill("Git", "Hard", "Learning"),
            MockSkill("SQL", "Hard", "Learning"),
            # Soft skills
            MockSkill("Teamwork", "Soft", "Learning"),
            MockSkill("Communication", "Soft", "Learning"),
        ],
    )


def make_bootcamp_grad_persona() -> MockPersona:
    """Create persona: Bootcamp graduate with ~1 year total (bootcamp + projects).

    This represents someone who:
    - Completed a 6-12 month coding bootcamp
    - Has ~1 year of experience (bootcamp duration + personal projects)
    - Strong in specific stack: JavaScript, React, Node.js
    - Looking for entry-level frontend/fullstack roles
    """
    return MockPersona(
        years_experience=1,
        current_role=None,  # Bootcamp, not employed
        target_roles=["Frontend Developer", "Full Stack Developer"],
        target_skills=["TypeScript", "Next.js", "AWS"],
        skills=[
            # Hard skills from bootcamp
            MockSkill("JavaScript", "Hard", "1-3 years"),
            MockSkill("React", "Hard", "1-3 years"),
            MockSkill("Node.js", "Hard", "1-3 years"),
            MockSkill("HTML", "Hard", "1-3 years"),
            MockSkill("CSS", "Hard", "1-3 years"),
            MockSkill("Git", "Hard", "1-3 years"),
            # Soft skills
            MockSkill("Problem Solving", "Soft", "Proficient"),
            MockSkill("Collaboration", "Soft", "Proficient"),
        ],
    )


def make_intern_persona() -> MockPersona:
    """Create persona: Current intern looking for full-time conversion.

    This represents someone who:
    - Is currently an intern (0 years full-time experience)
    - Current role is "Software Engineering Intern"
    - Has intern-level skills in Python, SQL, Git
    - Looking to convert to full-time Junior/Associate role
    """
    return MockPersona(
        years_experience=0,
        current_role="Software Engineering Intern",
        target_roles=["Software Engineer", "Associate Software Engineer"],
        target_skills=["FastAPI", "Docker", "CI/CD"],
        skills=[
            MockSkill("Python", "Hard", "Learning"),
            MockSkill("SQL", "Hard", "Learning"),
            MockSkill("Git", "Hard", "Learning"),
            MockSkill("Testing", "Hard", "Learning"),
            # Soft skills
            MockSkill("Communication", "Soft", "Learning"),
            MockSkill("Teamwork", "Soft", "Learning"),
        ],
    )


# =============================================================================
# Entry-Level Job Posting Factories
# =============================================================================


def make_junior_developer_job() -> MockJobPosting:
    """Create junior developer job posting (0-2 years experience).

    Entry-level job with explicit "Junior" title and low experience requirement.
    """
    return MockJobPosting(
        job_title="Junior Software Developer",
        years_experience_min=0,
        years_experience_max=2,
        salary_max=65000,
        ghost_score=5,
        extracted_skills=[
            MockExtractedSkill("JavaScript", "Hard", is_required=True),
            MockExtractedSkill("Python", "Hard", is_required=True),
            MockExtractedSkill("Git", "Hard", is_required=True),
            MockExtractedSkill("SQL", "Hard", is_required=False),
            # Soft skills
            MockExtractedSkill("Communication", "Soft", is_required=True),
            MockExtractedSkill("Teamwork", "Soft", is_required=True),
        ],
    )


def make_new_grad_job() -> MockJobPosting:
    """Create 'New Grad' role (common in tech companies).

    Explicitly targets recent graduates with 0-1 years experience.
    """
    return MockJobPosting(
        job_title="Software Engineer - New Grad",
        years_experience_min=0,
        years_experience_max=1,
        salary_max=80000,
        ghost_score=10,
        extracted_skills=[
            MockExtractedSkill("Python", "Hard", is_required=True),
            MockExtractedSkill("Data Structures", "Hard", is_required=True),
            MockExtractedSkill("Algorithms", "Hard", is_required=True),
            MockExtractedSkill("Git", "Hard", is_required=False),
            # Soft skills
            MockExtractedSkill("Problem Solving", "Soft", is_required=True),
            MockExtractedSkill("Communication", "Soft", is_required=True),
        ],
    )


def make_intern_job() -> MockJobPosting:
    """Create internship posting (0 years experience, explicit intern title)."""
    return MockJobPosting(
        job_title="Software Engineering Intern",
        years_experience_min=0,
        years_experience_max=0,
        salary_max=40000,  # Intern salary
        ghost_score=5,
        extracted_skills=[
            MockExtractedSkill("Python", "Hard", is_required=True),
            MockExtractedSkill("Git", "Hard", is_required=False),
            # Soft skills
            MockExtractedSkill("Communication", "Soft", is_required=True),
            MockExtractedSkill("Eagerness to Learn", "Soft", is_required=True),
        ],
    )


def make_entry_level_job() -> MockJobPosting:
    """Create job with 'Entry Level' in title (1-2 years experience)."""
    return MockJobPosting(
        job_title="Entry-Level Backend Developer",
        years_experience_min=1,
        years_experience_max=2,
        salary_max=70000,
        ghost_score=8,
        extracted_skills=[
            MockExtractedSkill("Python", "Hard", is_required=True),
            MockExtractedSkill("REST APIs", "Hard", is_required=True),
            MockExtractedSkill("SQL", "Hard", is_required=True),
            MockExtractedSkill("Docker", "Hard", is_required=False),
            # Soft skills
            MockExtractedSkill("Problem Solving", "Soft", is_required=True),
        ],
    )


def make_mid_level_job() -> MockJobPosting:
    """Create mid-level job posting (3-5 years experience).

    Entry-level users applying here will be penalized for under-qualification.
    """
    return MockJobPosting(
        job_title="Software Engineer",
        years_experience_min=3,
        years_experience_max=5,
        salary_max=120000,
        ghost_score=15,
        extracted_skills=[
            MockExtractedSkill("Python", "Hard", is_required=True),
            MockExtractedSkill("FastAPI", "Hard", is_required=True),
            MockExtractedSkill("PostgreSQL", "Hard", is_required=True),
            MockExtractedSkill("Docker", "Hard", is_required=True),
            MockExtractedSkill("Kubernetes", "Hard", is_required=False),
            # Soft skills
            MockExtractedSkill("Leadership", "Soft", is_required=False),
            MockExtractedSkill("Mentoring", "Soft", is_required=False),
        ],
    )


def make_senior_job() -> MockJobPosting:
    """Create senior job posting (5-8 years experience).

    Entry-level users applying here will be heavily penalized.
    """
    return MockJobPosting(
        job_title="Senior Software Engineer",
        years_experience_min=5,
        years_experience_max=8,
        salary_max=180000,
        ghost_score=20,
        extracted_skills=[
            MockExtractedSkill("Python", "Hard", is_required=True),
            MockExtractedSkill("System Design", "Hard", is_required=True),
            MockExtractedSkill("Architecture", "Hard", is_required=True),
            MockExtractedSkill("Kubernetes", "Hard", is_required=True),
            MockExtractedSkill("Leadership", "Soft", is_required=True),
            MockExtractedSkill("Mentoring", "Soft", is_required=True),
        ],
    )


# =============================================================================
# Tests: Job Title Level Detection (REQ-008 §9.3)
# =============================================================================


class TestEntryLevelJobTitleDetection:
    """Tests for detecting entry-level jobs from titles."""

    def test_junior_title_detected_as_junior_level(self) -> None:
        """Titles with 'Junior' map to junior level."""
        assert infer_level("Junior Software Developer") == "junior"
        assert infer_level("Junior Engineer") == "junior"
        assert infer_level("Junior Data Analyst") == "junior"

    def test_jr_abbreviation_detected_as_junior_level(self) -> None:
        """Titles with 'Jr.' abbreviation map to junior level."""
        assert infer_level("Jr. Developer") == "junior"
        assert infer_level("Jr Software Engineer") == "junior"

    def test_intern_detected_as_junior_level(self) -> None:
        """Intern titles map to junior level."""
        assert infer_level("Software Engineering Intern") == "junior"
        assert infer_level("Data Science Intern") == "junior"
        assert infer_level("Intern - Engineering") == "junior"

    def test_entry_level_keyword_detected_as_junior_level(self) -> None:
        """Titles with 'entry-level' map to junior level."""
        assert infer_level("Entry-Level Backend Developer") == "junior"
        assert infer_level("entry-level engineer") == "junior"

    def test_associate_detected_as_junior_level(self) -> None:
        """Titles with 'Associate' map to junior level."""
        assert infer_level("Associate Software Engineer") == "junior"
        assert infer_level("Associate Developer") == "junior"

    def test_new_grad_not_explicitly_detected(self) -> None:
        """'New Grad' is not explicitly detected - defaults to mid.

        Note: This documents current behavior. The title 'Software Engineer - New Grad'
        contains no explicit level keyword so defaults to 'mid' even though it's
        semantically an entry-level role. A future enhancement could detect 'new grad'.
        """
        # "New Grad" alone defaults to mid (no explicit junior keyword)
        result = infer_level("Software Engineer - New Grad")
        assert result == "mid"

    def test_no_title_returns_none(self) -> None:
        """None or empty title returns None."""
        assert infer_level(None) is None
        assert infer_level("") is None
        assert infer_level("   ") is None


# =============================================================================
# Tests: Experience Score Calculation (REQ-008 §4.4)
# =============================================================================


class TestEntryLevelExperienceScore:
    """Tests for experience scoring with entry-level users."""

    def test_zero_years_at_zero_requirement_job(self) -> None:
        """0 years user applying to job with 0-2 year range scores 100 (perfect fit)."""
        # Junior job: 0-2 years
        score = calculate_experience_score(
            user_years=0,
            job_min_years=0,
            job_max_years=2,
        )
        assert score == 100.0

    def test_one_year_at_one_to_two_requirement(self) -> None:
        """1 year user applying to 1-2 year job scores 100."""
        score = calculate_experience_score(
            user_years=1,
            job_min_years=1,
            job_max_years=2,
        )
        assert score == 100.0

    def test_zero_years_at_one_year_min_requirement(self) -> None:
        """0 years user applying to 1+ year job is penalized.

        Gap = 1 year, penalty = 15 per year → score = 85
        """
        score = calculate_experience_score(
            user_years=0,
            job_min_years=1,
            job_max_years=2,
        )
        assert score == 85.0  # 100 - (1 * 15)

    def test_zero_years_at_three_year_min_requirement(self) -> None:
        """0 years user applying to 3+ year job is heavily penalized.

        Gap = 3 years, penalty = 15 per year → score = 55
        """
        score = calculate_experience_score(
            user_years=0,
            job_min_years=3,
            job_max_years=5,
        )
        assert score == 55.0  # 100 - (3 * 15)

    def test_zero_years_at_five_year_min_requirement(self) -> None:
        """0 years user applying to 5+ year senior job is very heavily penalized.

        Gap = 5 years, penalty = 15 per year → score = 25
        """
        score = calculate_experience_score(
            user_years=0,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == 25.0  # 100 - (5 * 15)

    def test_one_year_at_three_year_min_requirement(self) -> None:
        """1 year user applying to 3+ year job.

        Gap = 2 years, penalty = 15 per year → score = 70
        """
        score = calculate_experience_score(
            user_years=1,
            job_min_years=3,
            job_max_years=5,
        )
        assert score == 70.0  # 100 - (2 * 15)

    def test_zero_years_at_seven_year_min_floors_at_zero(self) -> None:
        """0 years user applying to 7+ year job floors at 0.

        Gap = 7 years, penalty = 7 * 15 = 105, but floor is 0
        """
        score = calculate_experience_score(
            user_years=0,
            job_min_years=7,
            job_max_years=10,
        )
        assert score == 0.0  # max(0, 100 - 105)

    def test_none_experience_treated_as_zero(self) -> None:
        """None years_experience is treated as 0 years."""
        score = calculate_experience_score(
            user_years=None,
            job_min_years=0,
            job_max_years=2,
        )
        assert score == 100.0  # Treated as 0, which is within 0-2 range

    def test_no_job_requirements_returns_neutral(self) -> None:
        """Job with no experience requirements returns neutral score."""
        score = calculate_experience_score(
            user_years=0,
            job_min_years=None,
            job_max_years=None,
        )
        assert score == FIT_NEUTRAL_SCORE  # 70


# =============================================================================
# Tests: Growth Trajectory for Entry-Level Users (REQ-008 §5.4)
# =============================================================================


class TestEntryLevelGrowthTrajectory:
    """Tests for growth trajectory calculation with entry-level users."""

    def test_no_current_role_to_junior_job(self) -> None:
        """User with no current role applying to junior job gets neutral score.

        Cannot determine level from None current role, so neutral (50).
        """
        score = calculate_growth_trajectory(
            current_role=None,
            job_title="Junior Software Developer",
        )
        assert score == 50.0  # Neutral - can't determine current level

    def test_intern_to_junior_is_lateral(self) -> None:
        """Intern applying to junior role is lateral (same level).

        Both intern and junior titles map to 'junior' level.
        """
        score = calculate_growth_trajectory(
            current_role="Software Engineering Intern",
            job_title="Junior Developer",
        )
        assert score == 70.0  # Lateral move

    def test_intern_to_mid_level_is_step_up(self) -> None:
        """Intern applying to mid-level role (no explicit level) is step up.

        Intern → 'junior', 'Software Engineer' (no level indicator) → 'mid'
        """
        score = calculate_growth_trajectory(
            current_role="Engineering Intern",
            job_title="Software Engineer",
        )
        assert score == 100.0  # Step up

    def test_junior_to_senior_is_step_up(self) -> None:
        """Junior applying to senior role is step up."""
        score = calculate_growth_trajectory(
            current_role="Junior Developer",
            job_title="Senior Software Engineer",
        )
        assert score == 100.0  # Step up

    def test_no_current_role_to_senior_job(self) -> None:
        """User with no current role applying to senior job gets neutral.

        Even though this is likely a step up, we can't determine without current role.
        """
        score = calculate_growth_trajectory(
            current_role=None,
            job_title="Senior Software Engineer",
        )
        assert score == 50.0  # Neutral - can't determine


# =============================================================================
# Tests: Hard Skills Match for Entry-Level Users
# =============================================================================


class TestEntryLevelHardSkillsMatch:
    """Tests for hard skills matching with entry-level users."""

    def test_new_grad_skills_match_junior_job(self) -> None:
        """New grad with coursework skills can match junior job requirements."""
        persona = make_new_grad_developer_persona()
        job = make_junior_developer_job()

        # New grad has: Python, JavaScript, Git, SQL
        # Junior job requires: JavaScript, Python, Git (required), SQL (nice-to-have)

        # Build skill lists for hard skills match using correct TypedDict format
        persona_skills: list[PersonaSkillInput] = [
            {
                "skill_name": s.skill_name,
                "skill_type": s.skill_type,
                "proficiency": s.proficiency,
            }
            for s in persona.skills
            if s.skill_type == "Hard"
        ]
        job_skills: list[JobSkillInput] = [
            {
                "skill_name": s.skill_name,
                "skill_type": s.skill_type,
                "is_required": s.is_required,
            }
            for s in job.extracted_skills
            if s.skill_type == "Hard"
        ]

        score = calculate_hard_skills_score(
            persona_skills=persona_skills,
            job_skills=job_skills,
        )

        # Expected: Matches JavaScript, Python, Git (all 3 required)
        # Also matches SQL (nice-to-have)
        # Score should be high (80-100 range) due to full match
        assert score >= 80.0

    def test_new_grad_skills_partial_match_mid_level_job(self) -> None:
        """New grad has some skills for mid-level job but missing key ones."""
        persona = make_new_grad_developer_persona()
        job = make_mid_level_job()

        # New grad has: Python, JavaScript, Git, SQL
        # Mid-level requires: Python, FastAPI, PostgreSQL, Docker (required), Kubernetes (nice)

        persona_skills: list[PersonaSkillInput] = [
            {
                "skill_name": s.skill_name,
                "skill_type": s.skill_type,
                "proficiency": s.proficiency,
            }
            for s in persona.skills
            if s.skill_type == "Hard"
        ]
        job_skills: list[JobSkillInput] = [
            {
                "skill_name": s.skill_name,
                "skill_type": s.skill_type,
                "is_required": s.is_required,
            }
            for s in job.extracted_skills
            if s.skill_type == "Hard"
        ]

        score = calculate_hard_skills_score(
            persona_skills=persona_skills,
            job_skills=job_skills,
        )

        # Matches: Python only (1/4 required)
        # Missing: FastAPI, PostgreSQL, Docker
        # Score should be low due to only 25% required match
        assert score < 40.0

    def test_bootcamp_grad_matches_frontend_skills(self) -> None:
        """Bootcamp grad with React/JS skills matches frontend job well."""
        persona = make_bootcamp_grad_persona()

        # Create frontend-focused entry-level job
        job = MockJobPosting(
            job_title="Junior Frontend Developer",
            years_experience_min=0,
            years_experience_max=2,
            salary_max=70000,
            ghost_score=5,
            extracted_skills=[
                MockExtractedSkill("JavaScript", "Hard", is_required=True),
                MockExtractedSkill("React", "Hard", is_required=True),
                MockExtractedSkill("HTML", "Hard", is_required=True),
                MockExtractedSkill("CSS", "Hard", is_required=True),
                MockExtractedSkill("TypeScript", "Hard", is_required=False),
            ],
        )

        persona_skills: list[PersonaSkillInput] = [
            {
                "skill_name": s.skill_name,
                "skill_type": s.skill_type,
                "proficiency": s.proficiency,
            }
            for s in persona.skills
            if s.skill_type == "Hard"
        ]
        job_skills: list[JobSkillInput] = [
            {
                "skill_name": s.skill_name,
                "skill_type": s.skill_type,
                "is_required": s.is_required,
            }
            for s in job.extracted_skills
            if s.skill_type == "Hard"
        ]

        score = calculate_hard_skills_score(
            persona_skills=persona_skills,
            job_skills=job_skills,
        )

        # Bootcamp grad has: JavaScript, React, HTML, CSS, Node.js, Git
        # Job requires: JavaScript, React, HTML, CSS (all match!)
        # Nice: TypeScript (no match)
        # Should score high (80-100)
        assert score >= 80.0


# =============================================================================
# Tests: Full Fit Score Aggregation for Entry-Level Users
# =============================================================================


class TestEntryLevelFitScoreAggregation:
    """Tests for full Fit Score with entry-level users."""

    def test_entry_level_user_at_entry_level_job_good_fit(self) -> None:
        """Entry-level user applying to entry-level job can achieve good fit.

        When skills match and experience is within range, overall fit is good.
        """
        # Simulate component scores for entry-level user at entry-level job
        result = calculate_fit_score(
            hard_skills=85.0,  # Good skill match
            soft_skills=70.0,  # Neutral soft skills
            experience_level=100.0,  # Perfect - 0 years for 0-2 range
            role_title=80.0,  # Title match (both developer roles)
            location_logistics=70.0,  # Neutral
        )

        # Expected: 0.40*85 + 0.15*70 + 0.25*100 + 0.10*80 + 0.10*70
        #         = 34 + 10.5 + 25 + 8 + 7 = 84.5 → 84
        assert result.total >= 80

    def test_entry_level_user_at_mid_level_job_poor_fit(self) -> None:
        """Entry-level user applying to mid-level job will have poor fit.

        Experience penalty dominates even with decent skill match.
        """
        # Simulate 0 years user at 3-5 year job
        # Experience score: 100 - (3 * 15) = 55
        result = calculate_fit_score(
            hard_skills=30.0,  # Low - missing key skills
            soft_skills=70.0,  # Neutral
            experience_level=55.0,  # 3-year gap penalty
            role_title=70.0,  # Neutral title match
            location_logistics=70.0,  # Neutral
        )

        # Expected: 0.40*30 + 0.15*70 + 0.25*55 + 0.10*70 + 0.10*70
        #         = 12 + 10.5 + 13.75 + 7 + 7 = 50.25 → 50
        assert result.total < 60  # Poor fit

    def test_entry_level_user_at_senior_job_very_poor_fit(self) -> None:
        """Entry-level user applying to senior job will have very poor fit."""
        # Simulate 0 years user at 5-8 year senior job
        # Experience score: 100 - (5 * 15) = 25
        result = calculate_fit_score(
            hard_skills=20.0,  # Very low - missing most senior skills
            soft_skills=50.0,  # Below neutral
            experience_level=25.0,  # 5-year gap penalty
            role_title=50.0,  # Junior vs Senior mismatch
            location_logistics=70.0,  # Neutral
        )

        # Expected: 0.40*20 + 0.15*50 + 0.25*25 + 0.10*50 + 0.10*70
        #         = 8 + 7.5 + 6.25 + 5 + 7 = 33.75 → 34
        assert result.total < 40  # Very poor fit


# =============================================================================
# Tests: Stretch Score for Entry-Level Users
# =============================================================================


class TestEntryLevelStretchScore:
    """Tests for Stretch Score with entry-level users."""

    def test_new_grad_target_skills_exposure(self) -> None:
        """New grad can have high target skills exposure even at entry level."""
        persona = make_new_grad_developer_persona()

        # Job that exposes target skills: React, TypeScript, Node.js
        job = MockJobPosting(
            job_title="Junior Full Stack Developer",
            years_experience_min=0,
            years_experience_max=2,
            salary_max=75000,
            ghost_score=5,
            extracted_skills=[
                MockExtractedSkill("React", "Hard", is_required=True),
                MockExtractedSkill("TypeScript", "Hard", is_required=True),
                MockExtractedSkill("Node.js", "Hard", is_required=True),
                MockExtractedSkill("JavaScript", "Hard", is_required=True),
            ],
        )

        # Get job skill names
        job_skill_names = [s.skill_name for s in job.extracted_skills]

        score = calculate_target_skills_exposure(
            target_skills=persona.target_skills,
            job_skills=job_skill_names,
        )

        # Target skills: React, TypeScript, Node.js
        # Job has: React, TypeScript, Node.js, JavaScript
        # All 3 target skills present → score = 100.0
        assert score == 100.0

    def test_new_grad_target_role_alignment_via_stretch_score(self) -> None:
        """New grad's target role can align with entry-level job.

        Note: calculate_target_role_alignment requires embeddings which need
        special setup. This test uses calculate_stretch_score directly with
        simulated component scores instead.
        """
        # Simulate perfect role alignment score (would come from embedding similarity)
        target_role_score = 100.0  # Perfect alignment

        result = calculate_stretch_score(
            target_role=target_role_score,
            target_skills=75.0,  # Good skills exposure
            growth_trajectory=70.0,  # Lateral or slight step up
        )

        # Perfect role alignment contributes heavily (50% weight)
        # Expected: 0.50*100 + 0.40*75 + 0.10*70 = 50 + 30 + 7 = 87
        assert result.total == 87

    def test_entry_level_full_stretch_score(self) -> None:
        """Entry-level user can have high stretch score when goals align."""
        result = calculate_stretch_score(
            target_role=100.0,  # Perfect role alignment
            target_skills=100.0,  # All target skills present
            growth_trajectory=100.0,  # Step up from intern to junior
        )

        # Weights: role 50%, skills 40%, growth 10%
        # Expected: 0.50*100 + 0.40*100 + 0.10*100 = 100
        assert result.total == 100


# =============================================================================
# Tests: Explanation Generation for Entry-Level Users
# =============================================================================


class TestEntryLevelExplanationGeneration:
    """Tests for explanation generation with entry-level users."""

    def test_entry_level_user_good_fit_explanation(self) -> None:
        """Entry-level user with good fit gets appropriate explanation."""
        persona = make_new_grad_developer_persona()
        job = make_junior_developer_job()

        fit_result = FitScoreResult(
            total=85,
            components={
                "hard_skills": 90.0,
                "soft_skills": 70.0,
                "experience_level": 100.0,
                "role_title": 80.0,
                "location_logistics": 70.0,
            },
            weights={
                "hard_skills": 0.40,
                "soft_skills": 0.15,
                "experience_level": 0.25,
                "role_title": 0.10,
                "location_logistics": 0.10,
            },
        )

        stretch_result = StretchScoreResult(
            total=80,
            components={
                "target_role": 80.0,
                "target_skills": 75.0,
                "growth_trajectory": 100.0,
            },
            weights={
                "target_role": 0.50,
                "target_skills": 0.40,
                "growth_trajectory": 0.10,
            },
        )

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should mention good fit
        assert "fit" in explanation.summary.lower()
        # Should have strengths (high hard skills)
        assert len(explanation.strengths) > 0

    def test_entry_level_user_experience_gap_explanation(self) -> None:
        """Entry-level user with experience gap gets gap explanation."""
        persona = make_new_grad_developer_persona()
        job = make_mid_level_job()

        # Low experience score triggers gap explanation
        fit_result = FitScoreResult(
            total=50,
            components={
                "hard_skills": 30.0,
                "soft_skills": 70.0,
                "experience_level": 55.0,  # Below 60 threshold
                "role_title": 70.0,
                "location_logistics": 70.0,
            },
            weights={
                "hard_skills": 0.40,
                "soft_skills": 0.15,
                "experience_level": 0.25,
                "role_title": 0.10,
                "location_logistics": 0.10,
            },
        )

        stretch_result = StretchScoreResult(
            total=60,
            components={
                "target_role": 60.0,
                "target_skills": 50.0,
                "growth_trajectory": 100.0,
            },
            weights={
                "target_role": 0.50,
                "target_skills": 0.40,
                "growth_trajectory": 0.10,
            },
        )

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should mention gaps or poor fit
        # Note: gaps list is populated when experience_level < 60 and under-qualified
        # New grad (0 years) vs mid-level (3-5 years) should produce gap
        assert "fit" in explanation.summary.lower()

    def test_explanation_includes_missing_skills_for_entry_level(self) -> None:
        """Entry-level user gets explanation about missing skills."""
        persona = make_new_grad_developer_persona()
        job = make_mid_level_job()

        # Very low hard skills score triggers gap explanation
        fit_result = FitScoreResult(
            total=45,
            components={
                "hard_skills": 20.0,  # Below 50 threshold → gap
                "soft_skills": 70.0,
                "experience_level": 55.0,
                "role_title": 70.0,
                "location_logistics": 70.0,
            },
            weights={
                "hard_skills": 0.40,
                "soft_skills": 0.15,
                "experience_level": 0.25,
                "role_title": 0.10,
                "location_logistics": 0.10,
            },
        )

        stretch_result = StretchScoreResult(
            total=50,
            components={
                "target_role": 50.0,
                "target_skills": 50.0,
                "growth_trajectory": 50.0,
            },
            weights={
                "target_role": 0.50,
                "target_skills": 0.40,
                "growth_trajectory": 0.10,
            },
        )

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should have gaps when hard_skills < 50
        assert len(explanation.gaps) > 0
        # Gap should mention missing skills
        missing_skills_gap = [g for g in explanation.gaps if "missing" in g.lower()]
        assert len(missing_skills_gap) > 0

    def test_entry_level_stretch_opportunity_explanation(self) -> None:
        """Entry-level user with stretch potential gets stretch opportunity."""
        persona = make_new_grad_developer_persona()

        # Job with target skills
        job = MockJobPosting(
            job_title="Junior Full Stack Developer",
            years_experience_min=0,
            years_experience_max=2,
            salary_max=75000,
            ghost_score=5,
            extracted_skills=[
                MockExtractedSkill("React", "Hard", is_required=True),
                MockExtractedSkill("TypeScript", "Hard", is_required=True),
                MockExtractedSkill("Node.js", "Hard", is_required=True),
                MockExtractedSkill("JavaScript", "Hard", is_required=True),
            ],
        )

        fit_result = FitScoreResult(
            total=75,
            components={
                "hard_skills": 70.0,
                "soft_skills": 70.0,
                "experience_level": 100.0,
                "role_title": 70.0,
                "location_logistics": 70.0,
            },
            weights={
                "hard_skills": 0.40,
                "soft_skills": 0.15,
                "experience_level": 0.25,
                "role_title": 0.10,
                "location_logistics": 0.10,
            },
        )

        stretch_result = StretchScoreResult(
            total=90,
            components={
                "target_role": 80.0,
                "target_skills": 100.0,  # ≥75 triggers stretch opportunity
                "growth_trajectory": 100.0,
            },
            weights={
                "target_role": 0.50,
                "target_skills": 0.40,
                "growth_trajectory": 0.10,
            },
        )

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should have stretch opportunities
        assert len(explanation.stretch_opportunities) > 0
        # Should mention target skills
        target_skill_opportunities = [
            o for o in explanation.stretch_opportunities if "target" in o.lower()
        ]
        assert len(target_skill_opportunities) > 0


# =============================================================================
# Tests: Edge Cases Specific to Entry-Level Users
# =============================================================================


class TestEntryLevelEdgeCases:
    """Tests for edge cases specific to entry-level users."""

    def test_none_years_experience_defaults_to_zero(self) -> None:
        """Persona with None years_experience is treated as 0."""
        persona = MockPersona(
            years_experience=None,  # Not set
            current_role=None,
            target_roles=["Developer"],
            target_skills=[],
            skills=[],
        )

        # Calculate experience score - None should be treated as 0
        score = calculate_experience_score(
            user_years=persona.years_experience,
            job_min_years=0,
            job_max_years=2,
        )

        # 0 is within 0-2 range → perfect score
        assert score == 100.0

    def test_new_grad_with_no_skills(self) -> None:
        """New grad with no skills yet gets zero hard skills score."""
        # Note: We don't need to create a full persona for this test -
        # we just test hard skills calculation with empty persona skills
        job = make_junior_developer_job()

        persona_skills: list[PersonaSkillInput] = []  # Empty
        job_skills: list[JobSkillInput] = [
            {
                "skill_name": s.skill_name,
                "skill_type": s.skill_type,
                "is_required": s.is_required,
            }
            for s in job.extracted_skills
            if s.skill_type == "Hard"
        ]

        score = calculate_hard_skills_score(
            persona_skills=persona_skills,
            job_skills=job_skills,
        )

        # No matches → 0 score
        assert score == 0.0

    def test_intern_converting_to_full_time(self) -> None:
        """Intern converting to full-time role at same company scenario."""
        persona = make_intern_persona()

        # Same company's entry-level full-time role
        job = MockJobPosting(
            job_title="Associate Software Engineer",
            years_experience_min=0,
            years_experience_max=1,
            salary_max=75000,
            ghost_score=0,  # Internal posting, low ghost risk
            extracted_skills=[
                # Same skills the intern learned
                MockExtractedSkill("Python", "Hard", is_required=True),
                MockExtractedSkill("SQL", "Hard", is_required=True),
                MockExtractedSkill("Git", "Hard", is_required=True),
                MockExtractedSkill("Communication", "Soft", is_required=True),
            ],
        )

        # Experience score: 0 years in 0-1 range → 100
        exp_score = calculate_experience_score(
            user_years=persona.years_experience,
            job_min_years=job.years_experience_min,
            job_max_years=job.years_experience_max,
        )
        assert exp_score == 100.0

        # Growth trajectory: intern → associate (both junior level) → lateral
        growth_score = calculate_growth_trajectory(
            current_role=persona.current_role,
            job_title=job.job_title,
        )
        assert growth_score == 70.0  # Lateral move

    def test_boundary_one_year_experience(self) -> None:
        """Test boundary at exactly 1 year experience."""
        # 1 year user at 1-3 year job → perfect fit
        score_1 = calculate_experience_score(
            user_years=1,
            job_min_years=1,
            job_max_years=3,
        )
        assert score_1 == 100.0

        # 1 year user at 2-4 year job → 1 year under, penalty 15
        score_2 = calculate_experience_score(
            user_years=1,
            job_min_years=2,
            job_max_years=4,
        )
        assert score_2 == 85.0  # 100 - 15

    def test_boundary_two_year_experience_threshold(self) -> None:
        """Test at the <2 years threshold mentioned in REQ-008 §9.3.

        Note: The current implementation doesn't have special handling for the
        '<2 years' threshold mentioned in REQ-008 §9.3. This documents that
        the future entry-level boost is not yet implemented.
        """
        # 1 year (under threshold) at 3+ job
        score_1yr = calculate_experience_score(
            user_years=1,
            job_min_years=3,
            job_max_years=5,
        )

        # 2 years (at threshold) at 3+ job
        score_2yr = calculate_experience_score(
            user_years=2,
            job_min_years=3,
            job_max_years=5,
        )

        # 3 years (above threshold, meets requirement)
        score_3yr = calculate_experience_score(
            user_years=3,
            job_min_years=3,
            job_max_years=5,
        )

        # Current behavior: standard penalty applies regardless of threshold
        # 1 year: 100 - (2 * 15) = 70
        # 2 years: 100 - (1 * 15) = 85
        # 3 years: 100 (meets minimum)
        assert score_1yr == 70.0
        assert score_2yr == 85.0
        assert score_3yr == 100.0
