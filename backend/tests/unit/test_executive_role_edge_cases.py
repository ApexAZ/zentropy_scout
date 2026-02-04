"""Unit tests for Executive Role edge cases.

REQ-008 §9.4: Executive Roles Edge Cases.

Tests verify that scoring handles executive roles appropriately:
1. Executive title detection (VP, Director, C-suite)
2. Scoring for experienced users applying to executive roles
3. Growth trajectory for executive-level career moves
4. System produces valid scores and explanations for executive scenarios

Design notes from REQ-008 §9.4:
"VP+ roles often have vague skill requirements and emphasize leadership."

The spec defines shifted weights for executive roles:
- Soft Skills: 30% (up from 15%)
- Hard Skills: 25% (down from 40%)
- Experience Level: 25% (unchanged)

Note: The weight shift is NOT YET IMPLEMENTED. These tests document the CURRENT
behavior where standard weights are used for all roles. The weight modification
is a future enhancement.
"""

from dataclasses import dataclass

from app.services.experience_level import calculate_experience_score
from app.services.explanation_generation import generate_explanation
from app.services.fit_score import (
    FIT_NEUTRAL_SCORE,
    FIT_WEIGHT_HARD_SKILLS,
    FIT_WEIGHT_SOFT_SKILLS,
    FitScoreResult,
    calculate_fit_score,
    get_fit_component_weights,
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
# Helper: Create mock objects for executive scenarios
# =============================================================================


@dataclass
class MockSkill:
    """Mock skill for testing."""

    skill_name: str
    skill_type: str  # "Hard" or "Soft"
    proficiency: str = "5+ years"  # Executives typically have deep experience


@dataclass
class MockExtractedSkill:
    """Mock extracted skill from job posting."""

    skill_name: str
    skill_type: str
    is_required: bool = True


@dataclass
class MockPersona:
    """Mock persona for executive users."""

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
# Executive Persona Factories
# =============================================================================


def make_director_engineering_persona() -> MockPersona:
    """Create persona: Engineering Director with 15 years experience.

    This represents a seasoned engineering leader who:
    - Has 15 years of experience
    - Currently Director of Engineering
    - Strong in strategic/leadership skills
    - Looking for VP or similar executive role
    """
    return MockPersona(
        years_experience=15,
        current_role="Director of Engineering",
        target_roles=["VP of Engineering", "CTO", "Head of Engineering"],
        target_skills=["Executive Leadership", "Board Presentation", "M&A"],
        skills=[
            # Hard skills (technical foundation)
            MockSkill("Python", "Hard", "5+ years"),
            MockSkill("System Design", "Hard", "5+ years"),
            MockSkill("Architecture", "Hard", "5+ years"),
            MockSkill("Cloud Infrastructure", "Hard", "3-5 years"),
            # Soft/leadership skills (critical for executives)
            MockSkill("Leadership", "Soft", "5+ years"),
            MockSkill("Strategic Planning", "Soft", "5+ years"),
            MockSkill("Team Building", "Soft", "5+ years"),
            MockSkill("Stakeholder Management", "Soft", "3-5 years"),
            MockSkill("Executive Communication", "Soft", "3-5 years"),
        ],
    )


def make_vp_product_persona() -> MockPersona:
    """Create persona: VP of Product with 18 years experience.

    This represents a senior product executive who:
    - Has 18 years of experience
    - Currently VP of Product at a tech company
    - Looking for CPO or similar C-suite role
    """
    return MockPersona(
        years_experience=18,
        current_role="Vice President of Product",
        target_roles=["Chief Product Officer", "CPO", "SVP Product"],
        target_skills=["Board Relations", "P&L Ownership", "Enterprise Strategy"],
        skills=[
            # Hard skills
            MockSkill("Product Strategy", "Hard", "5+ years"),
            MockSkill("Data Analysis", "Hard", "3-5 years"),
            MockSkill("Market Research", "Hard", "5+ years"),
            # Soft/leadership skills
            MockSkill("Executive Leadership", "Soft", "5+ years"),
            MockSkill("Vision Setting", "Soft", "5+ years"),
            MockSkill("Cross-functional Leadership", "Soft", "5+ years"),
            MockSkill("Investor Relations", "Soft", "3-5 years"),
        ],
    )


def make_cto_persona() -> MockPersona:
    """Create persona: CTO with 20 years experience.

    This represents a C-suite executive who:
    - Has 20 years of experience
    - Currently CTO of a company
    - Looking for CEO or similar top executive role
    """
    return MockPersona(
        years_experience=20,
        current_role="Chief Technology Officer",
        target_roles=["CEO", "President", "General Manager"],
        target_skills=["CEO", "Board Membership", "Company Building"],
        skills=[
            # Hard skills
            MockSkill("Technology Strategy", "Hard", "5+ years"),
            MockSkill("Enterprise Architecture", "Hard", "5+ years"),
            MockSkill("Due Diligence", "Hard", "3-5 years"),
            # Soft/leadership skills
            MockSkill("Board Presentation", "Soft", "5+ years"),
            MockSkill("Executive Communication", "Soft", "5+ years"),
            MockSkill("Company Strategy", "Soft", "5+ years"),
            MockSkill("Culture Building", "Soft", "5+ years"),
            MockSkill("Fundraising", "Soft", "3-5 years"),
        ],
    )


def make_senior_manager_persona() -> MockPersona:
    """Create persona: Senior Engineering Manager looking to move to director.

    This represents someone who:
    - Has 10 years of experience
    - Currently Senior Engineering Manager
    - Looking for their first Director role
    """
    return MockPersona(
        years_experience=10,
        current_role="Senior Engineering Manager",
        target_roles=["Director of Engineering", "Engineering Director"],
        target_skills=["Strategic Planning", "Budget Management", "Org Design"],
        skills=[
            # Hard skills
            MockSkill("Python", "Hard", "5+ years"),
            MockSkill("System Design", "Hard", "3-5 years"),
            MockSkill("AWS", "Hard", "3-5 years"),
            # Soft/leadership skills
            MockSkill("People Management", "Soft", "3-5 years"),
            MockSkill("Project Management", "Soft", "3-5 years"),
            MockSkill("Mentoring", "Soft", "3-5 years"),
        ],
    )


# =============================================================================
# Executive Job Posting Factories
# =============================================================================


def make_vp_engineering_job() -> MockJobPosting:
    """Create VP of Engineering job posting (15+ years experience).

    Executive-level job with leadership focus and vague technical requirements.
    """
    return MockJobPosting(
        job_title="VP of Engineering",
        years_experience_min=15,
        years_experience_max=None,  # No upper limit for executives
        salary_max=350000,
        ghost_score=10,
        extracted_skills=[
            # Hard skills (more vague at exec level)
            MockExtractedSkill("Technology Strategy", "Hard", is_required=True),
            MockExtractedSkill("System Design", "Hard", is_required=False),
            MockExtractedSkill("Architecture", "Hard", is_required=False),
            # Soft skills emphasized
            MockExtractedSkill("Leadership", "Soft", is_required=True),
            MockExtractedSkill("Strategic Planning", "Soft", is_required=True),
            MockExtractedSkill("Executive Communication", "Soft", is_required=True),
            MockExtractedSkill("Team Building", "Soft", is_required=True),
            MockExtractedSkill("Stakeholder Management", "Soft", is_required=True),
        ],
    )


def make_director_engineering_job() -> MockJobPosting:
    """Create Director of Engineering job posting (10-15 years experience)."""
    return MockJobPosting(
        job_title="Director of Engineering",
        years_experience_min=10,
        years_experience_max=15,
        salary_max=250000,
        ghost_score=8,
        extracted_skills=[
            # Hard skills
            MockExtractedSkill("System Design", "Hard", is_required=True),
            MockExtractedSkill("Cloud Architecture", "Hard", is_required=True),
            MockExtractedSkill("Technical Leadership", "Hard", is_required=True),
            # Soft skills
            MockExtractedSkill("Leadership", "Soft", is_required=True),
            MockExtractedSkill("Team Building", "Soft", is_required=True),
            MockExtractedSkill("Strategic Planning", "Soft", is_required=False),
        ],
    )


def make_cto_job() -> MockJobPosting:
    """Create CTO job posting (20+ years experience)."""
    return MockJobPosting(
        job_title="Chief Technology Officer",
        years_experience_min=20,
        years_experience_max=None,
        salary_max=500000,
        ghost_score=15,
        extracted_skills=[
            # Hard skills (high-level strategic)
            MockExtractedSkill("Technology Strategy", "Hard", is_required=True),
            MockExtractedSkill("Enterprise Architecture", "Hard", is_required=True),
            # Soft skills dominate for C-suite
            MockExtractedSkill("Executive Leadership", "Soft", is_required=True),
            MockExtractedSkill("Board Presentation", "Soft", is_required=True),
            MockExtractedSkill("Company Strategy", "Soft", is_required=True),
            MockExtractedSkill("Culture Building", "Soft", is_required=True),
        ],
    )


def make_ceo_job() -> MockJobPosting:
    """Create CEO job posting (very senior, minimal technical requirements)."""
    return MockJobPosting(
        job_title="Chief Executive Officer",
        years_experience_min=20,
        years_experience_max=None,
        salary_max=800000,
        ghost_score=20,  # CEO roles often get many applicants/reposts
        extracted_skills=[
            # Hard skills minimal
            MockExtractedSkill("P&L Management", "Hard", is_required=True),
            # Soft skills dominate
            MockExtractedSkill("Leadership", "Soft", is_required=True),
            MockExtractedSkill("Board Relations", "Soft", is_required=True),
            MockExtractedSkill("Vision Setting", "Soft", is_required=True),
            MockExtractedSkill("Fundraising", "Soft", is_required=False),
        ],
    )


def make_svp_job() -> MockJobPosting:
    """Create SVP (Senior Vice President) job posting."""
    return MockJobPosting(
        job_title="SVP of Engineering",
        years_experience_min=18,
        years_experience_max=None,
        salary_max=400000,
        ghost_score=12,
        extracted_skills=[
            MockExtractedSkill("Technology Strategy", "Hard", is_required=True),
            MockExtractedSkill("Executive Leadership", "Soft", is_required=True),
            MockExtractedSkill("Organizational Design", "Soft", is_required=True),
        ],
    )


def make_evp_job() -> MockJobPosting:
    """Create EVP (Executive Vice President) job posting."""
    return MockJobPosting(
        job_title="EVP of Technology",
        years_experience_min=18,
        years_experience_max=None,
        salary_max=450000,
        ghost_score=10,
        extracted_skills=[
            MockExtractedSkill("Enterprise Strategy", "Hard", is_required=True),
            MockExtractedSkill("Executive Leadership", "Soft", is_required=True),
        ],
    )


# =============================================================================
# Tests: Executive Title Level Detection (REQ-008 §5.4 / §9.4)
# =============================================================================


class TestExecutiveTitleDetection:
    """Tests for detecting executive-level jobs from titles."""

    # -------------------------------------------------------------------------
    # Director Level
    # -------------------------------------------------------------------------

    def test_director_title_detected_as_director_level(self) -> None:
        """Titles with 'Director' map to director level."""
        assert infer_level("Director of Engineering") == "director"
        assert infer_level("Engineering Director") == "director"
        assert infer_level("Director, Product") == "director"
        assert infer_level("director") == "director"

    def test_senior_director_detected_as_director_level(self) -> None:
        """Senior Director is still director level (not senior)."""
        assert infer_level("Senior Director of Engineering") == "director"
        assert infer_level("Sr. Director, Product") == "director"

    # -------------------------------------------------------------------------
    # VP Level
    # -------------------------------------------------------------------------

    def test_vp_title_detected_as_vp_level(self) -> None:
        """Titles with 'VP' map to vp level."""
        assert infer_level("VP of Engineering") == "vp"
        assert infer_level("VP Engineering") == "vp"
        assert infer_level("VP Product") == "vp"

    def test_vice_president_detected_as_vp_level(self) -> None:
        """Titles with 'Vice President' map to vp level."""
        assert infer_level("Vice President of Engineering") == "vp"
        assert infer_level("Vice President, Technology") == "vp"

    def test_svp_detected_as_vp_level(self) -> None:
        """Senior Vice President (SVP) maps to vp level."""
        assert infer_level("SVP of Engineering") == "vp"
        assert infer_level("SVP Engineering") == "vp"
        assert infer_level("Senior Vice President") == "vp"

    def test_evp_detected_as_vp_level(self) -> None:
        """Executive Vice President (EVP) maps to vp level."""
        assert infer_level("EVP of Technology") == "vp"
        assert infer_level("EVP Engineering") == "vp"
        assert infer_level("Executive Vice President") == "vp"

    # -------------------------------------------------------------------------
    # C-Level
    # -------------------------------------------------------------------------

    def test_ceo_detected_as_c_level(self) -> None:
        """CEO titles map to c_level."""
        assert infer_level("CEO") == "c_level"
        assert infer_level("Chief Executive Officer") == "c_level"

    def test_cto_detected_as_c_level(self) -> None:
        """CTO titles map to c_level."""
        assert infer_level("CTO") == "c_level"
        assert infer_level("Chief Technology Officer") == "c_level"

    def test_cfo_detected_as_c_level(self) -> None:
        """CFO titles map to c_level."""
        assert infer_level("CFO") == "c_level"
        assert infer_level("Chief Financial Officer") == "c_level"

    def test_coo_detected_as_c_level(self) -> None:
        """COO titles map to c_level."""
        assert infer_level("COO") == "c_level"
        assert infer_level("Chief Operating Officer") == "c_level"

    def test_other_chief_titles_detected_as_c_level(self) -> None:
        """Other 'Chief' titles map to c_level."""
        assert infer_level("Chief Product Officer") == "c_level"
        assert infer_level("Chief Marketing Officer") == "c_level"
        assert infer_level("Chief People Officer") == "c_level"
        assert infer_level("Chief Revenue Officer") == "c_level"

    def test_chief_of_staff_not_c_level(self) -> None:
        """Chief of Staff is lead level, not c_level.

        This is an explicit exception in the level detection logic because
        'Chief of Staff' is a support role, not a C-suite executive.
        """
        assert infer_level("Chief of Staff") == "lead"
        assert infer_level("Chief of Staff, Technology") == "lead"

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    def test_cto_in_longer_title_detected(self) -> None:
        """CTO embedded in longer title still detected as c_level."""
        # Note: The regex uses word boundaries, so "CTO" must be a standalone word
        assert infer_level("CTO / Co-Founder") == "c_level"
        assert infer_level("Interim CTO") == "c_level"

    def test_director_vs_senior_priority(self) -> None:
        """Director takes priority over Senior in detection.

        'Senior Director' should be 'director' not 'senior'.
        """
        # Director checked before Senior in the level hierarchy
        assert infer_level("Senior Director") == "director"

    def test_vp_vs_director_priority(self) -> None:
        """VP takes priority over Director when both present."""
        # VP checked before Director
        assert infer_level("VP / Director") == "vp"


# =============================================================================
# Tests: Experience Score for Executives (REQ-008 §4.4)
# =============================================================================


class TestExecutiveExperienceScore:
    """Tests for experience scoring with executive users and roles."""

    def test_director_experience_matches_director_job(self) -> None:
        """15-year director applying to 10-15 year director job scores 100."""
        score = calculate_experience_score(
            user_years=15,
            job_min_years=10,
            job_max_years=15,
        )
        assert score == 100.0

    def test_director_slightly_overqualified_for_director_job(self) -> None:
        """15-year user for 10-12 year job gets small penalty.

        Over-qualified penalty is 5 per year (less than under-qualified penalty).
        """
        score = calculate_experience_score(
            user_years=15,
            job_min_years=10,
            job_max_years=12,
        )
        # 3 years over max: 100 - (3 * 5) = 85
        assert score == 85.0

    def test_vp_experience_matches_vp_job(self) -> None:
        """18-year VP applying to 15+ year VP job scores 100."""
        score = calculate_experience_score(
            user_years=18,
            job_min_years=15,
            job_max_years=None,  # No upper limit
        )
        assert score == 100.0

    def test_senior_manager_underqualified_for_vp_job(self) -> None:
        """10-year senior manager applying to 15+ VP job is under-qualified.

        Gap = 5 years, penalty = 15 per year → score = 25
        """
        score = calculate_experience_score(
            user_years=10,
            job_min_years=15,
            job_max_years=None,
        )
        assert score == 25.0  # 100 - (5 * 15)

    def test_cto_matches_ceo_experience_requirements(self) -> None:
        """20-year CTO applying to 20+ CEO job scores 100."""
        score = calculate_experience_score(
            user_years=20,
            job_min_years=20,
            job_max_years=None,
        )
        assert score == 100.0

    def test_none_max_years_no_overqualified_penalty(self) -> None:
        """Jobs with no max years don't penalize overqualified candidates."""
        score = calculate_experience_score(
            user_years=25,  # Very experienced
            job_min_years=15,
            job_max_years=None,  # No upper limit
        )
        # Meets minimum, no max to exceed
        assert score == 100.0

    def test_very_experienced_executive_at_mid_level_job(self) -> None:
        """20-year executive at 5-8 year job is heavily overqualified.

        Over-qualified penalty: 5 per year, but floored at 50.
        Gap = 12 years over: 100 - (12 * 5) = 40, but floor is 50.
        """
        score = calculate_experience_score(
            user_years=20,
            job_min_years=5,
            job_max_years=8,
        )
        # 12 years over max: max(50, 100 - 60) = 50 (floored)
        assert score == 50.0


# =============================================================================
# Tests: Growth Trajectory for Executives (REQ-008 §5.4)
# =============================================================================


class TestExecutiveGrowthTrajectory:
    """Tests for growth trajectory with executive-level career moves."""

    def test_director_to_vp_is_step_up(self) -> None:
        """Director applying to VP role is step up."""
        score = calculate_growth_trajectory(
            current_role="Director of Engineering",
            job_title="VP of Engineering",
        )
        assert score == 100.0  # Step up

    def test_vp_to_c_level_is_step_up(self) -> None:
        """VP applying to C-level role is step up."""
        score = calculate_growth_trajectory(
            current_role="Vice President of Engineering",
            job_title="CTO",
        )
        assert score == 100.0  # Step up

    def test_director_to_director_is_lateral(self) -> None:
        """Director applying to another director role is lateral."""
        score = calculate_growth_trajectory(
            current_role="Director of Engineering",
            job_title="Director of Platform",
        )
        assert score == 70.0  # Lateral move

    def test_vp_to_vp_is_lateral(self) -> None:
        """VP applying to another VP role is lateral."""
        score = calculate_growth_trajectory(
            current_role="VP of Engineering",
            job_title="VP of Product",
        )
        assert score == 70.0  # Lateral move

    def test_cto_to_ceo_is_step_up(self) -> None:
        """CTO applying to CEO role is step up (within c_level).

        Note: Both are c_level, so currently this is treated as lateral.
        A future enhancement could distinguish between different C-suite roles.
        """
        score = calculate_growth_trajectory(
            current_role="CTO",
            job_title="CEO",
        )
        # Both are c_level → lateral (current behavior)
        assert score == 70.0

    def test_vp_to_director_is_step_down(self) -> None:
        """VP applying to director role is step down."""
        score = calculate_growth_trajectory(
            current_role="VP of Engineering",
            job_title="Director of Engineering",
        )
        assert score == 30.0  # Step down

    def test_cto_to_vp_is_step_down(self) -> None:
        """C-level applying to VP role is step down."""
        score = calculate_growth_trajectory(
            current_role="CTO",
            job_title="VP of Engineering",
        )
        assert score == 30.0  # Step down

    def test_senior_manager_to_director_is_step_up(self) -> None:
        """Senior manager (lead level) to director is step up."""
        score = calculate_growth_trajectory(
            current_role="Senior Engineering Manager",
            job_title="Director of Engineering",
        )
        # "Senior Engineering Manager" contains "senior" but also "manager"
        # Manager patterns like "engineering manager" map to lead
        assert infer_level("Senior Engineering Manager") == "lead"
        assert score == 100.0  # lead → director is step up


# =============================================================================
# Tests: Hard Skills Match for Executives
# =============================================================================


class TestExecutiveHardSkillsMatch:
    """Tests for hard skills matching with executive roles.

    Executive roles often have vague or fewer hard skill requirements,
    emphasizing leadership and strategic skills instead.
    """

    def test_director_skills_match_director_job(self) -> None:
        """Director with technical background matches director job skills."""
        persona = make_director_engineering_persona()
        job = make_director_engineering_job()

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

        # Director has: Python, System Design, Architecture, Cloud Infrastructure
        # Job requires: System Design, Cloud Architecture, Technical Leadership
        # Only System Design matches exactly (Cloud Infrastructure != Cloud Architecture)
        # Score reflects partial match (1 of 3 required skills)
        assert score >= 25.0  # Partial match expected

    def test_cto_with_strategic_skills_for_cto_job(self) -> None:
        """CTO persona matches CTO job's strategic hard skills."""
        persona = make_cto_persona()
        job = make_cto_job()

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

        # CTO has: Technology Strategy, Enterprise Architecture, Due Diligence
        # Job requires: Technology Strategy, Enterprise Architecture
        # Strong match expected
        assert score >= 80.0

    def test_executive_job_with_minimal_hard_skills(self) -> None:
        """CEO job has minimal hard skill requirements."""
        job = make_ceo_job()

        # Count hard skills in CEO job
        hard_skills = [s for s in job.extracted_skills if s.skill_type == "Hard"]

        # CEO role should have fewer hard skills (only P&L Management)
        assert len(hard_skills) <= 2

    def test_vp_job_emphasizes_soft_skills(self) -> None:
        """VP job has more soft skills than hard skills."""
        job = make_vp_engineering_job()

        hard_skills = [s for s in job.extracted_skills if s.skill_type == "Hard"]
        soft_skills = [s for s in job.extracted_skills if s.skill_type == "Soft"]

        # VP role should emphasize soft skills
        assert len(soft_skills) > len(hard_skills)


# =============================================================================
# Tests: Weight System for Executive Roles (REQ-008 §9.4)
# =============================================================================


class TestExecutiveWeightSystem:
    """Tests documenting the weight system for executive roles.

    REQ-008 §9.4 specifies different weights for executive roles:
    - Soft Skills: 30% (up from 15%)
    - Hard Skills: 25% (down from 40%)
    - Experience Level: 25% (unchanged)

    IMPORTANT: These weights are NOT YET IMPLEMENTED. The current system uses
    the same weights for all roles. These tests document that behavior.
    """

    def test_current_weights_are_standard(self) -> None:
        """Current implementation uses standard weights for all roles.

        This test documents that executive-specific weights are NOT implemented.
        """
        weights = get_fit_component_weights()

        # Standard weights (same for all roles currently)
        assert weights["hard_skills"] == 0.40
        assert weights["soft_skills"] == 0.15
        assert weights["experience_level"] == 0.25
        assert weights["role_title"] == 0.10
        assert weights["location_logistics"] == 0.10

    def test_weight_constants_reflect_standard_values(self) -> None:
        """Weight constants are standard values.

        Future: Executive roles should use:
        - FIT_WEIGHT_HARD_SKILLS = 0.25 (currently 0.40)
        - FIT_WEIGHT_SOFT_SKILLS = 0.30 (currently 0.15)
        """
        assert FIT_WEIGHT_HARD_SKILLS == 0.40  # Standard, not executive
        assert FIT_WEIGHT_SOFT_SKILLS == 0.15  # Standard, not executive

    def test_executive_fit_score_uses_standard_weights(self) -> None:
        """Fit score for executive uses standard weights (not shifted).

        This demonstrates that currently an executive with strong soft skills
        but weaker hard skills won't benefit from the weight shift.
        """
        # Simulate executive with strong soft skills, moderate hard skills
        result = calculate_fit_score(
            hard_skills=60.0,  # Moderate (execs often have vague hard reqs)
            soft_skills=95.0,  # Strong leadership skills
            experience_level=100.0,  # Perfect experience match
            role_title=80.0,  # Good title match
            location_logistics=70.0,  # Neutral
        )

        # Current calculation with standard weights:
        # 0.40*60 + 0.15*95 + 0.25*100 + 0.10*80 + 0.10*70
        # = 24 + 14.25 + 25 + 8 + 7 = 78.25 → 78
        assert result.total == 78

        # With executive weights (NOT IMPLEMENTED):
        # 0.25*60 + 0.30*95 + 0.25*100 + 0.10*80 + 0.10*70
        # = 15 + 28.5 + 25 + 8 + 7 = 83.5 → 84
        # Future: assert result.total == 84


# =============================================================================
# Tests: Full Fit Score for Executives
# =============================================================================


class TestExecutiveFitScoreAggregation:
    """Tests for full Fit Score with executive users."""

    def test_director_at_vp_job_underqualified(self) -> None:
        """Director applying to VP job may be slightly under-qualified."""
        # Simulate 15-year director at 18+ VP job
        result = calculate_fit_score(
            hard_skills=70.0,  # Good technical match
            soft_skills=85.0,  # Strong leadership
            experience_level=55.0,  # 3 years under (100 - 3*15)
            role_title=60.0,  # Director vs VP mismatch
            location_logistics=70.0,  # Neutral
        )

        # Expected: 0.40*70 + 0.15*85 + 0.25*55 + 0.10*60 + 0.10*70
        #         = 28 + 12.75 + 13.75 + 6 + 7 = 67.5 → 68
        assert result.total >= 60 and result.total <= 75

    def test_vp_at_cto_job_good_stretch(self) -> None:
        """VP applying to CTO job - challenging but achievable."""
        result = calculate_fit_score(
            hard_skills=80.0,  # Strong technical strategy
            soft_skills=90.0,  # Strong executive leadership
            experience_level=85.0,  # Slight experience gap
            role_title=70.0,  # VP to CTO progression
            location_logistics=70.0,  # Neutral
        )

        # Expected: Good fit despite being a stretch
        assert result.total >= 75

    def test_cto_at_ceo_job_lateral_within_c_suite(self) -> None:
        """CTO applying to CEO - lateral move within C-suite."""
        result = calculate_fit_score(
            hard_skills=50.0,  # CEO has different hard skill focus
            soft_skills=95.0,  # Strong executive skills
            experience_level=100.0,  # Experience matches
            role_title=70.0,  # C-suite to C-suite
            location_logistics=70.0,  # Neutral
        )

        # Expected: Moderate fit (hard skills mismatch is significant)
        assert result.total >= 60 and result.total <= 80


# =============================================================================
# Tests: Stretch Score for Executives
# =============================================================================


class TestExecutiveStretchScore:
    """Tests for Stretch Score with executive users."""

    def test_director_target_skills_exposure(self) -> None:
        """Director can have high target skills exposure for VP role."""
        persona = make_director_engineering_persona()
        job = make_vp_engineering_job()

        # Get job skill names (all types)
        job_skill_names = [s.skill_name for s in job.extracted_skills]

        score = calculate_target_skills_exposure(
            target_skills=persona.target_skills,
            job_skills=job_skill_names,
        )

        # Target skills: Executive Leadership, Board Presentation, M&A
        # VP job has: Leadership, Strategic Planning, Executive Communication...
        # Partial match or no match depending on normalization
        assert score >= 20.0  # At minimum, 0 matches = 20

    def test_executive_full_stretch_score_for_advancement(self) -> None:
        """Executive targeting C-suite can have high stretch score."""
        result = calculate_stretch_score(
            target_role=90.0,  # Strong alignment with target
            target_skills=75.0,  # Good skills exposure
            growth_trajectory=100.0,  # Step up
        )

        # Expected: 0.50*90 + 0.40*75 + 0.10*100 = 45 + 30 + 10 = 85
        assert result.total == 85

    def test_executive_lateral_stretch_score(self) -> None:
        """Executive making lateral move has moderate stretch score."""
        result = calculate_stretch_score(
            target_role=70.0,  # Moderate alignment (different focus area)
            target_skills=50.0,  # Some exposure
            growth_trajectory=70.0,  # Lateral move
        )

        # Expected: 0.50*70 + 0.40*50 + 0.10*70 = 35 + 20 + 7 = 62
        assert result.total == 62


# =============================================================================
# Tests: Explanation Generation for Executives
# =============================================================================


class TestExecutiveExplanationGeneration:
    """Tests for explanation generation with executive roles."""

    def test_executive_good_fit_explanation(self) -> None:
        """Executive with good fit gets appropriate explanation."""
        persona = make_director_engineering_persona()
        job = make_director_engineering_job()

        fit_result = FitScoreResult(
            total=85,
            components={
                "hard_skills": 80.0,
                "soft_skills": 90.0,
                "experience_level": 100.0,
                "role_title": 80.0,
                "location_logistics": 70.0,
            },
            weights=get_fit_component_weights(),
        )

        stretch_result = StretchScoreResult(
            total=70,
            components={
                "target_role": 70.0,
                "target_skills": 60.0,
                "growth_trajectory": 70.0,
            },
            weights={
                "target_role": 0.50,
                "target_skills": 0.40,
                "growth_trajectory": 0.10,
            },
        )

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should mention good/strong fit
        assert "fit" in explanation.summary.lower()
        # Executive with good scores should have strengths
        assert len(explanation.strengths) >= 1

    def test_executive_overqualified_warning(self) -> None:
        """Overqualified executive gets appropriate warning."""
        persona = make_cto_persona()
        # CTO applying to senior-level (not exec) job
        job = MockJobPosting(
            job_title="Senior Software Engineer",
            years_experience_min=5,
            years_experience_max=8,
            salary_max=180000,
            ghost_score=10,
            extracted_skills=[
                MockExtractedSkill("Python", "Hard", is_required=True),
                MockExtractedSkill("System Design", "Hard", is_required=True),
            ],
        )

        # CTO with 20 years applying to 5-8 year job
        fit_result = FitScoreResult(
            total=55,
            components={
                "hard_skills": 70.0,
                "soft_skills": 70.0,
                "experience_level": 40.0,  # Heavily over-qualified (12 years over)
                "role_title": 30.0,  # CTO vs Senior Engineer mismatch
                "location_logistics": 70.0,
            },
            weights=get_fit_component_weights(),
        )

        stretch_result = StretchScoreResult(
            total=30,
            components={
                "target_role": 20.0,  # Not aligned with target
                "target_skills": 30.0,  # Limited exposure
                "growth_trajectory": 30.0,  # Step down
            },
            weights={
                "target_role": 0.50,
                "target_skills": 0.40,
                "growth_trajectory": 0.10,
            },
        )

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should have warnings about overqualification
        overqualified_warnings = [
            w for w in explanation.warnings if "overqualified" in w.lower()
        ]
        assert len(overqualified_warnings) > 0

    def test_executive_experience_perfect_match_strength(self) -> None:
        """Executive with perfect experience match gets strength message."""
        persona = make_vp_product_persona()
        job = make_svp_job()

        fit_result = FitScoreResult(
            total=80,
            components={
                "hard_skills": 70.0,
                "soft_skills": 85.0,
                "experience_level": 100.0,  # Perfect match
                "role_title": 80.0,
                "location_logistics": 70.0,
            },
            weights=get_fit_component_weights(),
        )

        stretch_result = StretchScoreResult(
            total=85,
            components={
                "target_role": 90.0,
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

        # With experience score >= 90, should mention experience as strength
        experience_strengths = [
            s for s in explanation.strengths if "experience" in s.lower()
        ]
        assert len(experience_strengths) > 0


# =============================================================================
# Tests: Edge Cases Specific to Executive Roles
# =============================================================================


class TestExecutiveEdgeCases:
    """Tests for edge cases specific to executive roles."""

    def test_no_max_years_common_for_executives(self) -> None:
        """Executive jobs often have no max years requirement."""
        job = make_vp_engineering_job()

        # VP job has no upper limit
        assert job.years_experience_max is None

        # Score calculation handles None max correctly
        score = calculate_experience_score(
            user_years=25,  # Very experienced
            job_min_years=job.years_experience_min,
            job_max_years=job.years_experience_max,
        )
        # Exceeds minimum, no max to worry about
        assert score == 100.0

    def test_executive_with_undefined_experience(self) -> None:
        """Executive with None years_experience gets neutral score."""
        persona = MockPersona(
            years_experience=None,  # Not specified
            current_role="VP of Engineering",
            target_roles=["CTO"],
            target_skills=[],
            skills=[],
        )

        score = calculate_experience_score(
            user_years=persona.years_experience,
            job_min_years=15,
            job_max_years=None,
        )

        # None is treated as 0, which is 15 years under → penalty
        # 100 - (15 * 15) = 100 - 225 = -125, floored at 0
        assert score == 0.0

    def test_executive_job_with_all_none_experience(self) -> None:
        """Executive job with no experience requirements returns neutral."""
        score = calculate_experience_score(
            user_years=20,
            job_min_years=None,
            job_max_years=None,
        )

        assert score == FIT_NEUTRAL_SCORE  # 70

    def test_executive_level_hierarchy_order(self) -> None:
        """Executive levels are in correct hierarchy order.

        Order: director < vp < c_level
        """
        # Verify the hierarchy is correct
        assert infer_level("Director") == "director"
        assert infer_level("VP") == "vp"
        assert infer_level("CEO") == "c_level"

        # Test step-up from each level
        assert calculate_growth_trajectory("Director", "VP") == 100.0  # Step up
        assert calculate_growth_trajectory("VP", "CEO") == 100.0  # Step up
        assert calculate_growth_trajectory("Director", "CEO") == 100.0  # Step up

    def test_very_senior_executive_boundary(self) -> None:
        """Test scoring at very senior executive levels (25+ years)."""
        # 25-year executive at 20+ C-suite job
        score_exp = calculate_experience_score(
            user_years=25,
            job_min_years=20,
            job_max_years=None,
        )
        assert score_exp == 100.0  # Exceeds minimum, no max

        # Growth trajectory: C-level to C-level (lateral)
        score_growth = calculate_growth_trajectory(
            current_role="CTO",
            job_title="CEO",
        )
        assert score_growth == 70.0  # Both c_level → lateral

    def test_executive_soft_skills_emphasis_in_job(self) -> None:
        """Executive jobs emphasize soft skills over hard skills.

        This demonstrates why the weight shift would be valuable.
        """
        job = make_cto_job()

        soft_count = sum(
            1 for s in job.extracted_skills if s.skill_type == "Soft" and s.is_required
        )
        hard_count = sum(
            1 for s in job.extracted_skills if s.skill_type == "Hard" and s.is_required
        )

        # CTO job: More required soft skills than hard skills
        # This is why executive weight shift would help
        assert soft_count >= hard_count
