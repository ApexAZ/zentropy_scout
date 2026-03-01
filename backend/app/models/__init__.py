"""SQLAlchemy ORM models for Zentropy Scout.

All models are exported from this module for convenient imports:
    from app.models import User, Persona, JobPosting, ...

Models are organized by domain:
- user.py: User (Tier 0)
- account.py: Account (Tier 1 - auth)
- session.py: Session (Tier 1 - auth)
- verification_token.py: VerificationToken (Tier 0 - auth, composite PK)
- job_source.py: JobSource, UserSourcePreference, PollingConfiguration
- persona.py: Persona (Tier 1)
- persona_content.py: WorkHistory, Bullet, Skill, Education, Certification, AchievementStory
- persona_settings.py: VoiceProfile, CustomNonNegotiable, PersonaEmbedding, PersonaChangeFlag
- persona_job.py: PersonaJob (Tier 2 - per-user job relationship)
- resume.py: ResumeFile, BaseResume, JobVariant, SubmittedResumePDF
- job_posting.py: JobPosting, ExtractedSkill
- cover_letter.py: CoverLetter, SubmittedCoverLetterPDF
- application.py: Application, TimelineEvent
- usage.py: LLMUsageRecord, CreditTransaction (Tier 2 - metering)
- admin_config.py: ModelRegistry, PricingConfig, TaskRoutingConfig, CreditPack, SystemConfig
"""

from app.models.account import Account
from app.models.admin_config import (
    CreditPack,
    ModelRegistry,
    PricingConfig,
    SystemConfig,
    TaskRoutingConfig,
)
from app.models.application import Application, TimelineEvent
from app.models.base import Base, EmbeddingColumnsMixin, SoftDeleteMixin, TimestampMixin
from app.models.cover_letter import CoverLetter, SubmittedCoverLetterPDF
from app.models.job_posting import ExtractedSkill, JobEmbedding, JobPosting
from app.models.job_source import JobSource, PollingConfiguration, UserSourcePreference
from app.models.persona import Persona
from app.models.persona_content import (
    AchievementStory,
    Bullet,
    Certification,
    Education,
    Skill,
    WorkHistory,
)
from app.models.persona_job import PersonaJob
from app.models.persona_settings import (
    CustomNonNegotiable,
    PersonaChangeFlag,
    PersonaEmbedding,
    VoiceProfile,
)
from app.models.resume import BaseResume, JobVariant, ResumeFile, SubmittedResumePDF
from app.models.session import Session
from app.models.usage import CreditTransaction, LLMUsageRecord
from app.models.user import User
from app.models.verification_token import VerificationToken

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    "EmbeddingColumnsMixin",
    # Tier 0
    "User",
    "VerificationToken",
    "JobSource",
    # Tier 1 - Auth
    "Account",
    "Session",
    # Tier 1
    "Persona",
    # Tier 2 - Persona content
    "WorkHistory",
    "Skill",
    "Education",
    "Certification",
    "AchievementStory",
    # Tier 2 - Persona settings
    "VoiceProfile",
    "CustomNonNegotiable",
    "PersonaEmbedding",
    "PersonaChangeFlag",
    # Tier 2 - Resume domain
    "ResumeFile",
    "BaseResume",
    # Tier 2 - Job source preferences
    "UserSourcePreference",
    "PollingConfiguration",
    # Tier 2 - Job posting
    "JobPosting",
    # Tier 2 - Per-user job relationship
    "PersonaJob",
    # Tier 2 - Metering
    "LLMUsageRecord",
    "CreditTransaction",
    # Tier 2 - Admin config
    "ModelRegistry",
    "PricingConfig",
    "TaskRoutingConfig",
    "CreditPack",
    "SystemConfig",
    # Tier 3
    "Bullet",
    "JobVariant",
    "ExtractedSkill",
    "JobEmbedding",
    "CoverLetter",
    # Tier 4
    "Application",
    "SubmittedResumePDF",
    "SubmittedCoverLetterPDF",
    # Tier 5
    "TimelineEvent",
]
