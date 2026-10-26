"""
Practical Studio Router.

Handles:
- Rendering the Practical Studio workspace page
- AI practical generation and section regeneration
- Practical CRUD (save, load, list, update, delete)
- Exporting practical content as Markdown / Text
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from app.database import Practical
from app.schemas import (
    PracticalGenerateRequest,
    PracticalSaveRequest,
    PracticalSectionRegenRequest,
)
from app.services.gemini_service import (
    GeminiError,
    GeminiModelMissingError,
    GeminiTimeoutError,
    GeminiUnreachableError,
)
from app.services.practical_service import (
    SECTION_DEFINITIONS,
    PracticalService,
)

logger = logging.getLogger("labmate.practical_router")
router = APIRouter(tags=["practical"])
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# UI Page
# ---------------------------------------------------------------------------

@router.get("/practical-studio", response_class=HTMLResponse)
async def practical_studio_page(request: Request, edit_id: Optional[int] = Query(None)):
    """Render the Practical Studio interactive workspace."""
    practical_data = None
    if edit_id:
        SessionLocal = request.app.state.db_session_factory
        try:
            with SessionLocal() as session:
                row = session.query(Practical).filter(Practical.id == edit_id).first()
                if row:
                    practical_data = {
                        "id": row.id,
                        "subject": row.subject,
                        "practical_number": row.practical_number,
                        "title": row.title,
                        "question": row.question,
                        "language": row.language,
                        "sections": json.loads(row.sections_json or "{}"),
                    }
        except Exception as exc:
            logger.warning("Could not pre-load practical id=%s: %s", edit_id, exc)

    return templates.TemplateResponse(
        request,
        "practical_studio.html",
        {
            "page": "practical-studio",
            "section_definitions": SECTION_DEFINITIONS,
            "preloaded_practical": practical_data,
        },
    )


# ---------------------------------------------------------------------------
# AI Generation Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/practical/generate")
async def generate_practical(
    request: Request,
    payload: PracticalGenerateRequest,
):
    """
    Generate practical content sections via Ollama.
    """
    gemini = getattr(request.app.state, "gemini", None)
    if not gemini:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Service is not initialized. Please restart the application.",
        )

    try:
        sections = await PracticalService.generate_practical(payload, gemini)
        return {
            "success": True,
            "sections": sections,
        }
    except GeminiUnreachableError as exc:
        logger.error("Gemini API unreachable during practical generation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot connect to Gemini API. Check your API key in .env",
        ) from exc
    except GeminiModelMissingError as exc:
        logger.error("Gemini model missing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except GeminiTimeoutError as exc:
        logger.error("Gemini timed out during practical generation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI generation timed out. Try generating fewer sections or setting detail level to 'short'.",
        ) from exc
    except GeminiError as exc:
        logger.error("Gemini generation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in practical generation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {exc}",
        ) from exc


@router.post("/api/practical/regenerate-section")
async def regenerate_section(
    request: Request,
    payload: PracticalSectionRegenRequest,
):
    """
    Regenerate a single practical section with targeted instructions.
    """
    gemini = getattr(request.app.state, "gemini", None)
    if not gemini:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Service is not initialized.",
        )

    try:
        content = await PracticalService.regenerate_section(payload, gemini)
        return {
            "success": True,
            "section_key": payload.section_key,
            "content": content,
        }
    except GeminiUnreachableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot connect to Gemini API. Check your API key in .env",
        ) from exc
    except GeminiTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Regeneration timed out. Please try again with simpler instructions.",
        ) from exc
    except GeminiError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error regenerating section: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Database Persistence (CRUD)
# ---------------------------------------------------------------------------

@router.post("/api/practicals")
async def save_practical(request: Request, payload: PracticalSaveRequest):
    """Save a new practical to the SQLite database."""
    SessionLocal = request.app.state.db_session_factory
    try:
        with SessionLocal() as session:
            practical = Practical(
                subject=payload.subject.strip(),
                practical_number=payload.practical_number.strip() if payload.practical_number else None,
                title=payload.title.strip(),
                question=payload.question.strip(),
                language=payload.language.strip() if payload.language else None,
                sections_json=json.dumps(payload.sections),
            )
            session.add(practical)
            session.commit()
            session.refresh(practical)

            logger.info("Saved practical id=%d: '%s'", practical.id, practical.title)
            return {
                "success": True,
                "id": practical.id,
                "message": "Practical saved successfully!",
            }
    except Exception as exc:
        logger.exception("Failed to save practical: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving practical: {exc}",
        ) from exc


@router.get("/api/practicals")
async def list_practicals(
    request: Request,
    subject: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """List saved practicals with optional search and subject filter."""
    SessionLocal = request.app.state.db_session_factory
    try:
        with SessionLocal() as session:
            query = session.query(Practical)
            if subject:
                query = query.filter(Practical.subject.ilike(f"%{subject.strip()}%"))
            if search:
                search_term = f"%{search.strip()}%"
                query = query.filter(
                    (Practical.title.ilike(search_term))
                    | (Practical.question.ilike(search_term))
                    | (Practical.subject.ilike(search_term))
                )

            rows = query.order_by(Practical.updated_at.desc()).all()
            return [
                {
                    "id": p.id,
                    "subject": p.subject,
                    "practical_number": p.practical_number,
                    "title": p.title,
                    "language": p.language,
                    "created_at": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
                    "updated_at": p.updated_at.strftime("%Y-%m-%d %H:%M") if p.updated_at else "",
                }
                for p in rows
            ]
    except Exception as exc:
        logger.exception("Failed to list practicals: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query practicals: {exc}",
        ) from exc


@router.get("/api/practicals/{practical_id}")
async def get_practical(request: Request, practical_id: int):
    """Get full practical content by ID."""
    SessionLocal = request.app.state.db_session_factory
    try:
        with SessionLocal() as session:
            p = session.query(Practical).filter(Practical.id == practical_id).first()
            if not p:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Practical with ID {practical_id} not found.",
                )
            return {
                "id": p.id,
                "subject": p.subject,
                "practical_number": p.practical_number,
                "title": p.title,
                "question": p.question,
                "language": p.language,
                "sections": json.loads(p.sections_json or "{}"),
                "created_at": p.created_at.isoformat() if p.created_at else "",
                "updated_at": p.updated_at.isoformat() if p.updated_at else "",
            }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to retrieve practical %d: %s", practical_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.put("/api/practicals/{practical_id}")
async def update_practical(
    request: Request,
    practical_id: int,
    payload: PracticalSaveRequest,
):
    """Update an existing practical."""
    SessionLocal = request.app.state.db_session_factory
    try:
        with SessionLocal() as session:
            p = session.query(Practical).filter(Practical.id == practical_id).first()
            if not p:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Practical with ID {practical_id} not found.",
                )
            p.subject = payload.subject.strip()
            p.practical_number = payload.practical_number.strip() if payload.practical_number else None
            p.title = payload.title.strip()
            p.question = payload.question.strip()
            p.language = payload.language.strip() if payload.language else None
            p.sections_json = json.dumps(payload.sections)
            session.commit()

            return {
                "success": True,
                "id": p.id,
                "message": "Practical updated successfully!",
            }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to update practical %d: %s", practical_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.delete("/api/practicals/{practical_id}")
async def delete_practical(request: Request, practical_id: int):
    """Delete a practical by ID."""
    SessionLocal = request.app.state.db_session_factory
    try:
        with SessionLocal() as session:
            p = session.query(Practical).filter(Practical.id == practical_id).first()
            if not p:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Practical with ID {practical_id} not found.",
                )
            session.delete(p)
            session.commit()
            return {"success": True, "message": "Practical deleted successfully."}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete practical %d: %s", practical_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Exporting
# ---------------------------------------------------------------------------

@router.get("/api/practicals/{practical_id}/export")
async def export_practical(
    request: Request,
    practical_id: int,
    format: str = Query("markdown", pattern=r"^(markdown|txt)$"),
):
    """Export a practical as a downloadable Markdown or plain text file."""
    SessionLocal = request.app.state.db_session_factory
    try:
        with SessionLocal() as session:
            p = session.query(Practical).filter(Practical.id == practical_id).first()
            if not p:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Practical not found",
                )

            sections = json.loads(p.sections_json or "{}")

            lines = []
            if format == "markdown":
                title_prefix = f"Practical #{p.practical_number}: " if p.practical_number else ""
                lines.append(f"# {title_prefix}{p.title}\n")
                lines.append(f"**Subject:** {p.subject}  ")
                if p.language:
                    lines.append(f"**Language:** {p.language}  ")
                lines.append(f"\n### Problem Statement\n{p.question}\n\n---\n")

                for key, meta in SECTION_DEFINITIONS.items():
                    if key in sections and sections[key].strip():
                        lines.append(f"## {meta['title']}\n")
                        lines.append(f"{sections[key]}\n\n")

                content = "\n".join(lines)
                filename = f"Practical_{p.practical_number or p.id}_{p.subject.replace(' ', '_')}.md"
                media_type = "text/markdown; charset=utf-8"
            else:
                title_prefix = f"Practical #{p.practical_number}: " if p.practical_number else ""
                lines.append("=" * 60)
                lines.append(f"{title_prefix}{p.title}".center(60))
                lines.append("=" * 60)
                lines.append(f"Subject: {p.subject}")
                if p.language:
                    lines.append(f"Language: {p.language}")
                lines.append(f"\nProblem Statement:\n{p.question}\n")
                lines.append("-" * 60 + "\n")

                for key, meta in SECTION_DEFINITIONS.items():
                    if key in sections and sections[key].strip():
                        lines.append(f"[{meta['title'].upper()}]")
                        lines.append(sections[key])
                        lines.append("\n" + "-" * 40 + "\n")

                content = "\n".join(lines)
                filename = f"Practical_{p.practical_number or p.id}_{p.subject.replace(' ', '_')}.txt"
                media_type = "text/plain; charset=utf-8"

            return Response(
                content=content,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to export practical %d: %s", practical_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
