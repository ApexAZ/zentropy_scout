"""Embedding type definitions for job-persona matching.

REQ-008 §6.1: What Gets Embedded.

Zentropy Scout uses five embedding types for semantic matching:

**Persona Embeddings:**
1. **persona_hard_skills**: Concatenated skill names + proficiency levels
   from structured Skill records
2. **persona_soft_skills**: Concatenated soft skill names from structured
   Skill records
3. **persona_logistics**: Location preferences, work model, values from
   structured NonNegotiables fields

**Job Embeddings:**
4. **job_requirements**: Required + preferred skills, experience from
   structured ExtractedSkill records
5. **job_culture**: Company values, team description, benefits. CRITICAL:
   This requires LLM extraction from the raw description - NOT the entire
   description text (which would pollute the vector with technical keywords)

Key Principle (REQ-008 §6.1):
    Job culture embedding must be SEPARATED from requirements to avoid
    technical keywords polluting soft skill similarity matches.
"""

from enum import Enum

# =============================================================================
# Embedding Type Enums
# =============================================================================


class EmbeddingType(Enum):
    """All embedding types used in job-persona matching.

    REQ-008 §6.1: Five embedding types total.

    Persona embeddings come from structured data (Skill, NonNegotiables).
    Job embeddings come from ExtractedSkill records and LLM-extracted culture.
    """

    # Persona embeddings (3 types)
    PERSONA_HARD_SKILLS = "persona_hard_skills"
    PERSONA_SOFT_SKILLS = "persona_soft_skills"
    PERSONA_LOGISTICS = "persona_logistics"

    # Job embeddings (2 types)
    JOB_REQUIREMENTS = "job_requirements"
    JOB_CULTURE = "job_culture"


class PersonaEmbeddingType(Enum):
    """Persona-only embedding types.

    REQ-008 §6.1: Three persona embedding types from structured data.
    """

    HARD_SKILLS = "hard_skills"
    SOFT_SKILLS = "soft_skills"
    LOGISTICS = "logistics"


class JobEmbeddingType(Enum):
    """Job-only embedding types.

    REQ-008 §6.1: Two job embedding types (structured + LLM-extracted).
    """

    REQUIREMENTS = "requirements"
    CULTURE = "culture"


# =============================================================================
# Embedding Configuration (REQ-008 §6.1)
# =============================================================================

# WHY dict of dicts: Configuration for each embedding type describing
# the source of data and what content gets embedded. Used by embedding
# generation functions to build appropriate text for vectorization.

EMBEDDING_CONFIGS: dict[EmbeddingType, dict[str, str]] = {
    EmbeddingType.PERSONA_HARD_SKILLS: {
        "source": "Structured Skill records (type=HARD)",
        "description": (
            "Concatenated skill names with proficiency levels. "
            "Example: 'Python (Expert), AWS (Intermediate), Docker (Beginner)'"
        ),
    },
    EmbeddingType.PERSONA_SOFT_SKILLS: {
        "source": "Structured Skill records (type=SOFT)",
        "description": (
            "Concatenated soft skill names. "
            "Example: 'Leadership, Communication, Problem Solving'"
        ),
    },
    EmbeddingType.PERSONA_LOGISTICS: {
        "source": "Structured NonNegotiables fields",
        "description": (
            "Location preferences, work model, values. "
            "Example: 'Remote, San Francisco Bay Area, work-life balance'"
        ),
    },
    EmbeddingType.JOB_REQUIREMENTS: {
        "source": "Structured ExtractedSkill records",
        "description": (
            "Required and preferred skills, experience level. "
            "Example: 'Python required, AWS preferred, 5+ years experience'"
        ),
    },
    EmbeddingType.JOB_CULTURE: {
        "source": "LLM-extracted culture_text from description",
        "description": (
            "Company values, team environment, benefits. "
            "CRITICAL: Must be extracted separately from technical requirements "
            "to avoid keyword pollution. See REQ-007 §6.4 for extraction logic."
        ),
    },
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_persona_embedding_types() -> list[EmbeddingType]:
    """Return all persona-related embedding types.

    Returns:
        List of EmbeddingType values for persona embeddings.
    """
    return [
        EmbeddingType.PERSONA_HARD_SKILLS,
        EmbeddingType.PERSONA_SOFT_SKILLS,
        EmbeddingType.PERSONA_LOGISTICS,
    ]


def get_job_embedding_types() -> list[EmbeddingType]:
    """Return all job-related embedding types.

    Returns:
        List of EmbeddingType values for job embeddings.
    """
    return [
        EmbeddingType.JOB_REQUIREMENTS,
        EmbeddingType.JOB_CULTURE,
    ]
