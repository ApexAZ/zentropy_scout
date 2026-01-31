"""Persona embedding generation service.

REQ-008 §6.3: Generate embeddings for persona data.

Generates three embedding types from persona data:
1. hard_skills: Skill names with proficiency levels
2. soft_skills: Skill names only (no proficiency)
3. logistics: Location, remote preference, commutable cities, exclusions

Called on: Persona creation, Persona update (REQ-007 §7.1).
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# =============================================================================
# Type Definitions
# =============================================================================


class SkillLike(Protocol):
    """Protocol for skill objects (avoids tight coupling to ORM model)."""

    skill_name: str
    skill_type: str
    proficiency: str


class PersonaLike(Protocol):
    """Protocol for persona objects (avoids tight coupling to ORM model)."""

    id: uuid.UUID
    skills: list[SkillLike]
    home_city: str
    home_state: str
    home_country: str
    remote_preference: str
    commutable_cities: list[str]
    industry_exclusions: list[str]
    updated_at: datetime


# Type alias for embedding function signature
EmbedFunction = Callable[[str], Awaitable[list[list[float]]]]


# =============================================================================
# Result Dataclasses
# =============================================================================


@dataclass
class PersonaEmbeddingData:
    """Single embedding with its source text.

    Attributes:
        vector: The 1536-dimensional embedding vector.
        source_text: The text that was embedded (for debugging/auditing).
    """

    vector: list[float]
    source_text: str


@dataclass
class PersonaEmbeddingsResult:
    """Result of generating all persona embeddings.

    REQ-008 §6.3: Three embedding types per persona.

    Attributes:
        persona_id: UUID of the persona these embeddings belong to.
        hard_skills: Embedding for technical skills with proficiency.
        soft_skills: Embedding for soft skills (names only).
        logistics: Embedding for location/preference data.
        version: Timestamp for staleness detection (from persona.updated_at).
        model_name: Name of the embedding model used.
    """

    persona_id: uuid.UUID
    hard_skills: PersonaEmbeddingData
    soft_skills: PersonaEmbeddingData
    logistics: PersonaEmbeddingData
    version: datetime
    model_name: str


# =============================================================================
# Text Building Functions
# =============================================================================


def build_hard_skills_text(skills: list[SkillLike]) -> str:
    """Build embedding text from hard skills.

    REQ-008 §6.3: Format is "{skill_name} ({proficiency})" joined by " | ".

    Args:
        skills: List of skill objects (filters to type="Hard").

    Returns:
        Formatted text for embedding, e.g., "Python (Expert) | AWS (Proficient)".
    """
    hard_skills = [s for s in skills if s.skill_type == "Hard"]
    if not hard_skills:
        return ""

    return " | ".join(f"{s.skill_name} ({s.proficiency})" for s in hard_skills)


def build_soft_skills_text(skills: list[SkillLike]) -> str:
    """Build embedding text from soft skills.

    REQ-008 §6.3: Format is "{skill_name}" joined by " | " (no proficiency).

    Args:
        skills: List of skill objects (filters to type="Soft").

    Returns:
        Formatted text for embedding, e.g., "Leadership | Communication".
    """
    soft_skills = [s for s in skills if s.skill_type == "Soft"]
    if not soft_skills:
        return ""

    return " | ".join(s.skill_name for s in soft_skills)


def build_logistics_text(persona: PersonaLike) -> str:
    """Build embedding text from persona logistics.

    REQ-008 §6.3: Combines remote preference, location, commutable cities,
    and industry exclusions into a single text block.

    Args:
        persona: Persona object with location/preference fields.

    Returns:
        Multi-line text for embedding.
    """
    location = f"{persona.home_city}, {persona.home_state}, {persona.home_country}"
    commutable = (
        ", ".join(persona.commutable_cities) if persona.commutable_cities else "None"
    )
    exclusions = (
        ", ".join(persona.industry_exclusions)
        if persona.industry_exclusions
        else "None"
    )

    return f"""Remote preference: {persona.remote_preference}
Location: {location}
Commutable cities: {commutable}
Industry exclusions: {exclusions}"""


# =============================================================================
# Main Generation Function
# =============================================================================


async def generate_persona_embeddings(
    persona: PersonaLike,
    embed_fn: EmbedFunction,
    model_name: str = "text-embedding-3-small",
) -> PersonaEmbeddingsResult:
    """Generate all embeddings for a persona.

    REQ-008 §6.3: Called on persona creation and update.

    Args:
        persona: Persona object with skills and preferences.
        embed_fn: Async function that takes text and returns embedding vector.
                  Signature: async def embed(text: str) -> list[list[float]]
        model_name: Name of embedding model (for tracking).

    Returns:
        PersonaEmbeddingsResult with all three embedding types.
    """
    # Build text for each embedding type
    hard_skills_text = build_hard_skills_text(persona.skills)
    soft_skills_text = build_soft_skills_text(persona.skills)
    logistics_text = build_logistics_text(persona)

    # Generate embeddings
    # WHY SEPARATE CALLS: Each embedding type has distinct semantic content.
    # Combining them would pollute the vector space (REQ-008 §6.1 principle).
    hard_result = await embed_fn(hard_skills_text)
    soft_result = await embed_fn(soft_skills_text)
    logistics_result = await embed_fn(logistics_text)

    return PersonaEmbeddingsResult(
        persona_id=persona.id,
        hard_skills=PersonaEmbeddingData(
            vector=hard_result[0],
            source_text=hard_skills_text,
        ),
        soft_skills=PersonaEmbeddingData(
            vector=soft_result[0],
            source_text=soft_skills_text,
        ),
        logistics=PersonaEmbeddingData(
            vector=logistics_result[0],
            source_text=logistics_text,
        ),
        version=persona.updated_at,
        model_name=model_name,
    )
