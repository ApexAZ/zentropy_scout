"""API v1 router aggregator.

REQ-006 §5.1: URL structure with /api/v1 prefix.

All v1 endpoint routers are included here.
"""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    applications,
    auth,
    auth_magic_link,
    auth_oauth,
    base_resumes,
    chat,
    cover_letters,
    files,
    job_postings,
    job_sources,
    job_variants,
    onboarding,
    persona_change_flags,
    personas,
    refresh,
    usage,
    user_source_preferences,
)

router = APIRouter()

# =============================================================================
# Authentication (REQ-013)
# =============================================================================

_AUTH_PREFIX = "/auth"

router.include_router(auth.router, prefix=_AUTH_PREFIX, tags=["auth"])
router.include_router(auth_magic_link.router, prefix=_AUTH_PREFIX, tags=["auth"])
router.include_router(auth_oauth.router, prefix=_AUTH_PREFIX, tags=["auth"])

# =============================================================================
# Core Resource Routers
# =============================================================================

router.include_router(personas.router, prefix="/personas", tags=["personas"])
router.include_router(
    job_postings.router, prefix="/job-postings", tags=["job-postings"]
)
router.include_router(
    base_resumes.router, prefix="/base-resumes", tags=["base-resumes"]
)
router.include_router(
    job_variants.router, prefix="/job-variants", tags=["job-variants"]
)
router.include_router(
    applications.router, prefix="/applications", tags=["applications"]
)
router.include_router(
    cover_letters.router, prefix="/cover-letters", tags=["cover-letters"]
)

# =============================================================================
# Job Sources (read-only)
# =============================================================================

router.include_router(job_sources.router, prefix="/job-sources", tags=["job-sources"])
router.include_router(
    user_source_preferences.router,
    prefix="/user-source-preferences",
    tags=["user-source-preferences"],
)

# =============================================================================
# Chat (agent interaction)
# =============================================================================

router.include_router(chat.router, prefix="/chat", tags=["chat"])

# =============================================================================
# HITL Sync
# =============================================================================

router.include_router(
    persona_change_flags.router,
    prefix="/persona-change-flags",
    tags=["persona-change-flags"],
)

# =============================================================================
# File Upload/Download
# =============================================================================

router.include_router(files.resume_files_router, prefix="/resume-files", tags=["files"])
router.include_router(
    files.submitted_resume_pdfs_router,
    prefix="/submitted-resume-pdfs",
    tags=["files"],
)
router.include_router(
    files.submitted_cover_letter_pdfs_router,
    prefix="/submitted-cover-letter-pdfs",
    tags=["files"],
)

# =============================================================================
# Onboarding
# =============================================================================

router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])

# =============================================================================
# Action Endpoints
# =============================================================================

router.include_router(refresh.router, prefix="/refresh", tags=["actions"])

# =============================================================================
# Usage & Billing (REQ-020)
# =============================================================================

router.include_router(usage.router, prefix="/usage", tags=["usage"])

# =============================================================================
# Admin (REQ-022)
# =============================================================================

router.include_router(admin.router, prefix="/admin", tags=["admin"])
