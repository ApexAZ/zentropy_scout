"""Unit tests for Career Changer edge cases.

REQ-008 §9.2: Career Changers Edge Cases.

Tests verify that scoring handles career changers appropriately:
1. Career changers have low hard skills match (skills don't transfer to new field)
2. Career changers can have high Stretch Score (target role/skills alignment)
3. Soft skills may partially transfer between fields
4. System produces valid scores and explanations for career changers

Design note from REQ-008 §9.2:
"Users transitioning between fields may have low hard skills match but high
transferable skills."

The future "career_change_mode" enhancement (deferred) would adjust weights.
These tests document the CURRENT behavior without that mode.
"""

from dataclasses import dataclass

from app.services.explanation_generation import (
    generate_explanation,
    get_matched_skills,
    get_missing_skills,
    get_target_skill_matches,
)
from app.services.fit_score import (
    FIT_NEUTRAL_SCORE,
    FitScoreResult,
    calculate_fit_score,
)
from app.services.hard_skills_match import calculate_hard_skills_score
from app.services.soft_skills_match import calculate_soft_skills_score
from app.services.stretch_score import (
    StretchScoreResult,
    calculate_stretch_score,
    calculate_target_role_alignment,
    calculate_target_skills_exposure,
)

# =============================================================================
# Constants for Tests
# =============================================================================

# Default embedding dimension (OpenAI text-embedding-3-small)
EMBEDDING_DIM = 1536


# =============================================================================
# Helper: Create mock persona for career changers
# =============================================================================


@dataclass
class MockSkill:
    """Mock skill for testing."""

    skill_name: str
    skill_type: str  # "Hard" or "Soft"
    proficiency: str = "Proficient"


@dataclass
class MockExtractedSkill:
    """Mock extracted skill from job posting."""

    skill_name: str
    skill_type: str
    is_required: bool = True


@dataclass
class MockPersona:
    """Mock persona for career changers."""

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
# Career Changer Persona Factories
# =============================================================================


def make_software_engineer_to_pm_persona() -> MockPersona:
    """Create persona: Software Engineer transitioning to Product Manager.

    This represents a common career change scenario where:
    - Current skills: Python, SQL, FastAPI, Git (technical/Hard skills)
    - Soft skills: Problem Solving, Collaboration, Communication
    - Target role: Product Manager
    - Target skills: Product Strategy, Stakeholder Management, Roadmap Planning
    """
    return MockPersona(
        years_experience=5,
        current_role="Senior Software Engineer",
        target_roles=["Product Manager", "Technical Product Manager"],
        target_skills=[
            "Product Strategy",
            "Stakeholder Management",
            "Roadmap Planning",
        ],
        skills=[
            # Hard skills (won't match PM job requirements)
            MockSkill("Python", "Hard", "5+ years"),
            MockSkill("SQL", "Hard", "5+ years"),
            MockSkill("FastAPI", "Hard", "3-5 years"),
            MockSkill("Git", "Hard", "5+ years"),
            # Soft skills (may partially transfer)
            MockSkill("Problem Solving", "Soft", "Proficient"),
            MockSkill("Collaboration", "Soft", "Proficient"),
            MockSkill("Communication", "Soft", "Proficient"),
        ],
    )


def make_pm_job_posting() -> MockJobPosting:
    """Create PM job posting that a software engineer might apply to.

    Requirements are typical for Product Manager roles:
    - Hard skills: Product Strategy, Roadmap Planning, Agile/Scrum, SQL (nice-to-have)
    - Soft skills: Communication, Leadership, Stakeholder Management
    """
    return MockJobPosting(
        job_title="Product Manager",
        years_experience_min=3,
        years_experience_max=7,
        salary_max=150000,
        ghost_score=10,
        extracted_skills=[
            # Required hard skills for PM (software engineer won't have)
            MockExtractedSkill("Product Strategy", "Hard", is_required=True),
            MockExtractedSkill("Roadmap Planning", "Hard", is_required=True),
            MockExtractedSkill("Agile", "Hard", is_required=True),
            MockExtractedSkill("Scrum", "Hard", is_required=True),
            # Nice-to-have hard skills (software engineer has SQL)
            MockExtractedSkill("SQL", "Hard", is_required=False),
            MockExtractedSkill("Data Analysis", "Hard", is_required=False),
            # Soft skills (may partially match)
            MockExtractedSkill("Communication", "Soft", is_required=True),
            MockExtractedSkill("Leadership", "Soft", is_required=True),
            MockExtractedSkill("Stakeholder Management", "Soft", is_required=True),
        ],
    )


# =============================================================================
# REQ-008 §9.2: Career Changers — Hard Skills Match
# =============================================================================


class TestCareerChangerHardSkillsMatch:
    """Career changers typically have low hard skills match."""

    def test_career_changer_has_low_hard_skills_match(self) -> None:
        """REQ-008 §9.2: Career changer has mismatched hard skills."""
        # Software engineer applying to PM role
        persona_skills = [
            # Technical skills that don't transfer to PM
            {"skill_name": "Python", "skill_type": "Hard", "proficiency": "5+ years"},
            {"skill_name": "FastAPI", "skill_type": "Hard", "proficiency": "3-5 years"},
            {
                "skill_name": "PostgreSQL",
                "skill_type": "Hard",
                "proficiency": "3-5 years",
            },
            {"skill_name": "Git", "skill_type": "Hard", "proficiency": "5+ years"},
        ]

        job_skills = [
            # PM requirements (software engineer doesn't have these)
            {
                "skill_name": "Product Strategy",
                "skill_type": "Hard",
                "is_required": True,
            },
            {
                "skill_name": "Roadmap Planning",
                "skill_type": "Hard",
                "is_required": True,
            },
            {"skill_name": "Agile", "skill_type": "Hard", "is_required": True},
        ]

        result = calculate_hard_skills_score(persona_skills, job_skills)

        # Career changer has 0% hard skill match
        # Formula: (required_score × 0.80) + (nice_score × 0.20)
        # = (0 × 0.80) + (0 × 0.20) = 0
        assert result == 0.0

    def test_career_changer_partial_hard_skills_overlap(self) -> None:
        """REQ-008 §9.2: Some technical skills may overlap (e.g., SQL for PM)."""
        # Software engineer with SQL (which PM role also wants)
        persona_skills = [
            {"skill_name": "Python", "skill_type": "Hard", "proficiency": "5+ years"},
            {"skill_name": "SQL", "skill_type": "Hard", "proficiency": "5+ years"},
        ]

        job_skills = [
            # PM requirements
            {
                "skill_name": "Product Strategy",
                "skill_type": "Hard",
                "is_required": True,
            },
            {
                "skill_name": "SQL",
                "skill_type": "Hard",
                "is_required": False,
            },  # nice-to-have
            {"skill_name": "Data Analysis", "skill_type": "Hard", "is_required": False},
        ]

        result = calculate_hard_skills_score(persona_skills, job_skills)

        # 0/1 required skills matched (Product Strategy not matched)
        # 1/2 nice-to-have skills matched (SQL matched, Data Analysis not)
        # Formula:
        # - required_score = (0 / 1) * 80 = 0
        # - nice_score = (1.0 / 2) * 20 = 10  # Divides by TOTAL nice-to-have count
        # Total = 0 + 10 = 10.0
        assert result == 10.0


# =============================================================================
# REQ-008 §9.2: Career Changers — Stretch Score
# =============================================================================


class TestCareerChangerStretchScore:
    """Career changers can have high Stretch Score if role aligns with targets."""

    def test_career_changer_high_target_role_alignment_exact(self) -> None:
        """REQ-008 §9.2: Exact target role match gives 100."""
        target_roles = ["Product Manager", "Technical Product Manager"]
        job_title = "Product Manager"

        result = calculate_target_role_alignment(
            target_roles=target_roles,
            job_title=job_title,
            target_roles_embedding=None,  # Exact match, no embedding needed
            job_title_embedding=None,
        )

        # Exact match → 100
        assert result == 100.0

    def test_career_changer_high_target_skills_exposure(self) -> None:
        """REQ-008 §9.2: Career changer gains exposure to target skills."""
        # Software engineer wants to learn PM skills
        target_skills = [
            "Product Strategy",
            "Stakeholder Management",
            "Roadmap Planning",
        ]

        # PM job offers all these skills
        job_skills = [
            "Product Strategy",
            "Roadmap Planning",
            "Agile",
            "Stakeholder Management",
        ]

        result = calculate_target_skills_exposure(
            target_skills=target_skills,
            job_skills=job_skills,
        )

        # 3 matches = excellent exposure (100)
        assert result == 100.0

    def test_career_changer_partial_target_skills_exposure(self) -> None:
        """REQ-008 §9.2: Partial target skills exposure gives moderate score."""
        target_skills = [
            "Product Strategy",
            "Stakeholder Management",
            "User Research",  # Not in job
        ]

        job_skills = [
            "Product Strategy",
            "Roadmap Planning",
            "Agile",
        ]

        result = calculate_target_skills_exposure(
            target_skills=target_skills,
            job_skills=job_skills,
        )

        # 1 match = minimal exposure (50)
        assert result == 50.0

    def test_career_changer_no_target_skills_in_job(self) -> None:
        """REQ-008 §9.2: No target skills in job gives low score."""
        target_skills = ["Machine Learning", "Deep Learning", "MLOps"]

        job_skills = [
            "Product Strategy",
            "Roadmap Planning",
            "Agile",
        ]

        result = calculate_target_skills_exposure(
            target_skills=target_skills,
            job_skills=job_skills,
        )

        # 0 matches = no exposure (20)
        assert result == 20.0


# =============================================================================
# REQ-008 §9.2: Career Changers — Aggregate Scores
# =============================================================================


class TestCareerChangerAggregateScores:
    """Career changers: low Fit Score + high Stretch Score is valid outcome."""

    def test_career_changer_low_fit_high_stretch(self) -> None:
        """REQ-008 §9.2: Career changers have low Fit but can have high Stretch."""
        # Fit Score components for career changer:
        # - Hard skills: 0 (no overlap)
        # - Soft skills: 70 (neutral - embeddings not provided)
        # - Experience: 100 (5 years fits 3-7 range perfectly)
        # - Role title: 70 (neutral - current role doesn't match job title)
        # - Location: 70 (neutral)
        fit_result = calculate_fit_score(
            hard_skills=0.0,  # No hard skill overlap
            soft_skills=70.0,  # Neutral (embeddings not provided)
            experience_level=100.0,  # Experience fits range
            role_title=70.0,  # Neutral (current role different)
            location_logistics=70.0,  # Neutral
        )

        # Stretch Score components for career changer:
        # - Target role: 100 (exact match to target)
        # - Target skills: 100 (3+ skill matches)
        # - Growth trajectory: 70 (neutral - level inference)
        stretch_result = calculate_stretch_score(
            target_role=100.0,  # PM is their target
            target_skills=100.0,  # Job has their target skills
            growth_trajectory=70.0,  # Neutral
        )

        # Career changer profile:
        # - Low Fit Score (hard skills drag it down)
        # - High Stretch Score (job aligns with career goals)
        assert fit_result.total < 60  # Below "Low" threshold
        assert stretch_result.total >= 90  # In "High" range

    def test_career_changer_component_breakdown(self) -> None:
        """REQ-008 §9.2: Verify component weights affect career changer scores."""
        # Calculate Fit Score with 0 hard skills
        fit_result = calculate_fit_score(
            hard_skills=0.0,
            soft_skills=80.0,  # Good soft skills transfer
            experience_level=90.0,  # Good experience
            role_title=50.0,  # Poor role match
            location_logistics=100.0,  # Perfect location
        )

        # Fit calculation:
        # (0 × 0.40) + (80 × 0.15) + (90 × 0.25) + (50 × 0.10) + (100 × 0.10)
        # = 0 + 12 + 22.5 + 5 + 10 = 49.5 → rounds to 50
        assert fit_result.total == 50

        # Hard skills at 40% weight is the biggest drag
        assert fit_result.components["hard_skills"] == 0.0
        assert fit_result.weights["hard_skills"] == 0.40


# =============================================================================
# REQ-008 §9.2: Career Changers — Soft Skills Transfer
# =============================================================================


class TestCareerChangerSoftSkillsTransfer:
    """Soft skills may partially transfer between fields."""

    def test_soft_skills_transfer_with_embeddings(self) -> None:
        """REQ-008 §9.2: Soft skills use embedding similarity for matching."""
        # Create mock embeddings that show high similarity
        # (Software engineer's communication ≈ PM's communication)
        # Using a simple high-similarity pattern
        persona_embedding = [0.8] * EMBEDDING_DIM
        job_embedding = [0.85] * EMBEDDING_DIM

        result = calculate_soft_skills_score(
            persona_soft_embedding=persona_embedding,
            job_soft_embedding=job_embedding,
        )

        # High cosine similarity → high score
        # These embeddings are very similar (both positive, similar magnitude)
        assert result > 90.0

    def test_soft_skills_no_embeddings_returns_neutral(self) -> None:
        """REQ-008 §9.2: No soft skills embeddings → neutral score."""
        result = calculate_soft_skills_score(
            persona_soft_embedding=None,
            job_soft_embedding=None,
        )

        assert result == FIT_NEUTRAL_SCORE  # 70


# =============================================================================
# REQ-008 §9.2: Career Changers — Explanation Generation
# =============================================================================


class TestCareerChangerExplanationGeneration:
    """Explanations should highlight career changer's gaps and opportunities."""

    def test_get_missing_skills_for_career_changer(self) -> None:
        """REQ-008 §9.2: Career changer is missing most required skills."""
        persona = make_software_engineer_to_pm_persona()
        job = make_pm_job_posting()

        missing = get_missing_skills(
            persona, job, skill_type="Hard", required_only=True
        )

        # Software engineer is missing PM hard skills
        # Required skills: Product Strategy, Roadmap Planning, Agile, Scrum
        # Software engineer has: Python, SQL, FastAPI, Git (none overlap)
        assert "Product Strategy" in missing
        assert "Roadmap Planning" in missing
        assert "Agile" in missing

    def test_get_matched_skills_for_career_changer_hard(self) -> None:
        """REQ-008 §9.2: Career changer has few matching hard skills."""
        persona = make_software_engineer_to_pm_persona()
        job = make_pm_job_posting()

        matched = get_matched_skills(persona, job, skill_type="Hard")

        # Software engineer has SQL which is a nice-to-have in PM job
        # Most other hard skills (Python, FastAPI, Git) don't match
        # Career changers typically have minimal hard skill overlap
        assert len(matched) == 1
        assert "SQL" in matched

    def test_get_matched_skills_for_career_changer_soft(self) -> None:
        """REQ-008 §9.2: Career changer may have matching soft skills."""
        persona = make_software_engineer_to_pm_persona()
        job = make_pm_job_posting()

        matched = get_matched_skills(persona, job, skill_type="Soft")

        # Software engineer has: Problem Solving, Collaboration, Communication
        # PM job wants: Communication, Leadership, Stakeholder Management
        # Overlap: Communication
        assert "Communication" in matched

    def test_get_target_skill_matches_for_career_changer(self) -> None:
        """REQ-008 §9.2: Career changer's target skills appear in job."""
        persona = make_software_engineer_to_pm_persona()
        job = make_pm_job_posting()

        matches = get_target_skill_matches(persona, job)

        # Target skills: Product Strategy, Stakeholder Management, Roadmap Planning
        # Job has: Product Strategy, Roadmap Planning, Stakeholder Management (as extracted skills)
        assert "Product Strategy" in matches
        assert "Stakeholder Management" in matches
        assert "Roadmap Planning" in matches

    def test_generate_explanation_for_career_changer(self) -> None:
        """REQ-008 §9.2: Full explanation for career changer scenario."""
        persona = make_software_engineer_to_pm_persona()
        job = make_pm_job_posting()

        # Create mock results (career changer profile)
        fit_result = FitScoreResult(
            total=45,  # Low Fit Score
            components={
                "hard_skills": 0.0,  # No hard skill overlap
                "soft_skills": 70.0,  # Neutral
                "experience_level": 100.0,  # Good experience
                "role_title": 30.0,  # Poor match (current != job)
                "location_logistics": 70.0,  # Neutral
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
            total=95,  # High Stretch Score
            components={
                "target_role": 100.0,  # Exact match to target
                "target_skills": 100.0,  # Has 3+ target skills
                "growth_trajectory": 70.0,  # Neutral
            },
            weights={
                "target_role": 0.50,
                "target_skills": 0.40,
                "growth_trajectory": 0.10,
            },
        )

        explanation = generate_explanation(
            fit_result=fit_result,
            stretch_result=stretch_result,
            persona=persona,
            job=job,
        )

        # Career changer should see:
        # 1. Summary mentioning "weak fit" (score < 55)
        assert "weak fit" in explanation.summary.lower()

        # 2. Gaps showing missing required skills
        assert len(explanation.gaps) > 0
        # Should mention missing skills like Product Strategy, Roadmap Planning
        gap_text = " ".join(explanation.gaps)
        assert "Missing required skills" in gap_text

        # 3. Stretch opportunities (target role/skills alignment)
        assert len(explanation.stretch_opportunities) > 0
        # Should mention alignment with target role or target skills
        stretch_text = " ".join(explanation.stretch_opportunities)
        # High stretch score should trigger stretch opportunities
        assert "target" in stretch_text.lower() or "Aligns" in stretch_text


# =============================================================================
# REQ-008 §9.2: Career Changers — Edge Cases Within Edge Case
# =============================================================================


class TestCareerChangerEdgeCases:
    """Edge cases specific to career changer scenarios."""

    def test_career_changer_with_no_target_roles_defined(self) -> None:
        """REQ-008 §9.2: Career changer without target roles gets neutral Stretch."""
        result = calculate_target_role_alignment(
            target_roles=None,  # No targets defined
            job_title="Product Manager",
            target_roles_embedding=None,
            job_title_embedding=None,
        )

        # No target roles → neutral score (50)
        assert result == 50.0

    def test_career_changer_with_empty_target_skills(self) -> None:
        """REQ-008 §9.2: Career changer without target skills gets neutral."""
        result = calculate_target_skills_exposure(
            target_skills=[],  # Empty list
            job_skills=["Product Strategy", "Roadmap Planning"],
        )

        # No target skills → neutral score (50)
        assert result == 50.0

    def test_career_changer_multiple_target_roles(self) -> None:
        """REQ-008 §9.2: Multiple target roles, one matches exactly."""
        target_roles = [
            "Data Scientist",  # Primary target
            "Machine Learning Engineer",  # Secondary
            "Product Manager",  # Tertiary
        ]

        result = calculate_target_role_alignment(
            target_roles=target_roles,
            job_title="Product Manager",
            target_roles_embedding=None,
            job_title_embedding=None,
        )

        # Any exact match → 100
        assert result == 100.0

    def test_career_changer_title_normalization(self) -> None:
        """REQ-008 §9.2: Title matching is case-insensitive."""
        target_roles = ["product manager"]  # lowercase
        job_title = "Product Manager"  # Title case

        result = calculate_target_role_alignment(
            target_roles=target_roles,
            job_title=job_title,
            target_roles_embedding=None,
            job_title_embedding=None,
        )

        # Case-insensitive match → 100
        assert result == 100.0

    def test_career_changer_full_scoring_flow(self) -> None:
        """REQ-008 §9.2: Complete scoring flow for career changer produces valid output."""
        # This test verifies the system doesn't crash and produces valid scores
        # for the career changer use case

        fit_result = calculate_fit_score(
            hard_skills=0.0,
            soft_skills=75.0,
            experience_level=85.0,
            role_title=40.0,
            location_logistics=100.0,
        )

        stretch_result = calculate_stretch_score(
            target_role=100.0,
            target_skills=100.0,
            growth_trajectory=80.0,
        )

        # All scores are in valid range 0-100
        assert 0 <= fit_result.total <= 100
        assert 0 <= stretch_result.total <= 100

        # Component breakdown is accessible
        assert "hard_skills" in fit_result.components
        assert "target_role" in stretch_result.components

        # Weights sum to 1.0
        assert abs(sum(fit_result.weights.values()) - 1.0) < 0.001
        assert abs(sum(stretch_result.weights.values()) - 1.0) < 0.001
