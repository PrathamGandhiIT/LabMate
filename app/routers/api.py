"""
API router — health check, AI status, and utility endpoints.
"""

import logging

from fastapi import APIRouter, Request

from app.schemas import HealthResponse

logger = logging.getLogger("labmate.api")
router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """
    Multi-level health check:
    1. Is the Gemini API reachable?
    2. Is the configured model available?
    """
    gemini = request.app.state.gemini
    result = await gemini.health_check()

    return HealthResponse(
        status="ok" if result["model_available"] else "degraded",
        api_reachable=result["api_reachable"],
        model_available=result["model_available"],
        model_name=result["model_name"],
        error=result["error"],
    )


@router.get("/status")
async def quick_status(request: Request):
    """Quick connectivity check (no model test)."""
    gemini = request.app.state.gemini
    reachable = await gemini.is_reachable()
    return {
        "api_reachable": reachable,
        "model_name": "gemini" if reachable else "N/A",
    }
