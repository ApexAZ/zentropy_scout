"""Parameter objects for prompt builder functions.

Bundles related parameters into frozen dataclasses to reduce function
parameter counts (SonarCloud S107: max 13 parameters).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceProfileData:
    """Voice profile settings for content generation prompts.

    Groups the 7 voice-related parameters that always travel together
    when building cover letter or tailoring prompts.
    """

    tone: str
    sentence_style: str
    vocabulary_level: str
    personality_markers: str
    preferred_phrases: str
    things_to_avoid: str
    writing_sample: str


@dataclass(frozen=True)
class JobContext:
    """Job posting context for content generation prompts.

    Groups the 5 job-related parameters used in cover letter and
    tailoring prompts.
    """

    job_title: str
    company_name: str
    top_skills: str
    culture_signals: str
    description_excerpt: str


@dataclass(frozen=True)
class ScoreData:
    """Score breakdown data for rationale generation prompts.

    Groups the 14 score-related parameters for the strategist's
    score rationale prompt builder.
    """

    fit_score: int
    hard_skills_pct: int
    matched_hard_skills: int
    required_hard_skills: int
    soft_skills_pct: int
    experience_match: str
    job_years: str
    persona_years: str
    logistics_match: str
    stretch_score: int
    role_alignment_pct: int
    target_skills_found: str
    missing_skills: str
    bonus_skills: str
