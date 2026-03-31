"""Embedding type definitions for job-persona matching.

REQ-008 §6.1: What Gets Embedded.

Zentropy Scout uses five embedding types for semantic matching:

**Persona Embeddings:**
1. **hard_skills**: Concatenated skill names + proficiency levels
   from structured Skill records
2. **soft_skills**: Concatenated soft skill names from structured
   Skill records
3. **logistics**: Location preferences, work model, values from
   structured NonNegotiables fields

**Job Embeddings:**
4. **requirements**: Required + preferred skills, experience from
   structured ExtractedSkill records
5. **culture**: Company values, team description, benefits. CRITICAL:
   This requires LLM extraction from the raw description - NOT the entire
   description text (which would pollute the vector with technical keywords)

Key Principle (REQ-008 §6.1):
    Job culture embedding must be SEPARATED from requirements to avoid
    technical keywords polluting soft skill similarity matches.

Called by: Unit tests. Defines canonical embedding type enums for future use by embedding pipeline.
"""

from enum import Enum

# =============================================================================
# Embedding Type Enums (REQ-031 §6.2: Canonical definitions)
# =============================================================================


class PersonaEmbeddingType(str, Enum):
    """Persona-only embedding types.

    REQ-008 §6.1: Three persona embedding types from structured data.

    Values use unprefixed form for JSON serialization and DB storage
    (matches CHECK constraints on persona_embeddings.embedding_type).

    Values:
        HARD_SKILLS: Technical skills with proficiency levels.
        SOFT_SKILLS: Soft skills (names only, no proficiency).
        LOGISTICS: Location, remote preference, exclusions.
    """

    HARD_SKILLS = "hard_skills"
    SOFT_SKILLS = "soft_skills"
    LOGISTICS = "logistics"


class JobEmbeddingType(str, Enum):
    """Job-only embedding types.

    REQ-008 §6.1: Two job embedding types (structured + LLM-extracted).

    Values use unprefixed form for JSON serialization and DB storage
    (matches CHECK constraints on job_embeddings.embedding_type).

    Values:
        REQUIREMENTS: Required/preferred skills with experience levels.
        CULTURE: Company values and culture text.
    """

    REQUIREMENTS = "requirements"
    CULTURE = "culture"


# Union type for any embedding type (REQ-031 §6.2: Union alias)
EmbeddingType = PersonaEmbeddingType | JobEmbeddingType


# =============================================================================
# Embedding Configuration (REQ-008 §6.1)
# =============================================================================

# WHY dict of dicts: Configuration for each embedding type describing
# the source of data and what content gets embedded. Used by embedding
# generation functions to build appropriate text for vectorization.

EMBEDDING_CONFIGS: dict[EmbeddingType, dict[str, str]] = {
    PersonaEmbeddingType.HARD_SKILLS: {
        "source": "Structured Skill records (type=HARD)",
        "description": (
            "Concatenated skill names with proficiency levels. "
            "Example: 'Python (Expert), AWS (Intermediate), Docker (Beginner)'"
        ),
    },
    PersonaEmbeddingType.SOFT_SKILLS: {
        "source": "Structured Skill records (type=SOFT)",
        "description": (
            "Concatenated soft skill names. "
            "Example: 'Leadership, Communication, Problem Solving'"
        ),
    },
    PersonaEmbeddingType.LOGISTICS: {
        "source": "Structured NonNegotiables fields",
        "description": (
            "Location preferences, work model, values. "
            "Example: 'Remote, San Francisco Bay Area, work-life balance'"
        ),
    },
    JobEmbeddingType.REQUIREMENTS: {
        "source": "Structured ExtractedSkill records",
        "description": (
            "Required and preferred skills, experience level. "
            "Example: 'Python required, AWS preferred, 5+ years experience'"
        ),
    },
    JobEmbeddingType.CULTURE: {
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


def get_persona_embedding_types() -> list[PersonaEmbeddingType]:
    """Return all persona-related embedding types.

    Returns:
        List of PersonaEmbeddingType values.
    """
    return list(PersonaEmbeddingType)


def get_job_embedding_types() -> list[JobEmbeddingType]:
    """Return all job-related embedding types.

    Returns:
        List of JobEmbeddingType values.
    """
    return list(JobEmbeddingType)


def get_all_embedding_types() -> list[EmbeddingType]:
    """Return all embedding types (persona + job).

    Returns:
        List of all EmbeddingType values.
    """
    return [*PersonaEmbeddingType, *JobEmbeddingType]
