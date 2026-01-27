"""API v1 router aggregator.

REQ-006 §5.1: URL structure with /api/v1 prefix.

All v1 endpoint routers are included here.
"""

from fastapi import APIRouter

router = APIRouter()

# Routers will be included here as they are implemented:
# router.include_router(personas.router, prefix="/personas", tags=["personas"])
# router.include_router(resumes.router, prefix="/base-resumes", tags=["resumes"])
# etc.
