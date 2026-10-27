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
    BatchDeleteRequest,
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


@router.get("/my-practicals", response_class=HTMLResponse)
async def my_practicals_page(
    request: Request,
    subject: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """Render the My Practicals management and library page."""
    SessionLocal = request.app.state.db_session_factory
    practicals_list = []
    subjects_list = []
    languages_list = []
    try:
        with SessionLocal() as session:
            # Query distinct subjects
            subj_rows = session.query(Practical.subject).distinct().all()
            subjects_list = sorted([s[0] for s in subj_rows if s[0]])

            # Query distinct languages
            lang_rows = session.query(Practical.language).distinct().all()
            languages_list = sorted([l[0] for l in lang_rows if l[0]])

            query = session.query(Practical)
            if subject and subject.strip():
                query = query.filter(Practical.subject.ilike(f"%{subject.strip()}%"))
            if language and language.strip() and language.lower() != "all":
                query = query.filter(Practical.language.ilike(f"%{language.strip()}%"))
            if search and search.strip():
                term = f"%{search.strip()}%"
                query = query.filter(
                    (Practical.title.ilike(term))
                    | (Practical.question.ilike(term))
                    | (Practical.subject.ilike(term))
                    | (Practical.language.ilike(term))
                )

            rows = query.order_by(Practical.updated_at.desc()).all()
            for p in rows:
                try:
                    sections = json.loads(p.sections_json or "{}")
                except Exception:
                    sections = {}
                practicals_list.append({
                    "id": p.id,
                    "subject": p.subject,
                    "practical_number": p.practical_number,
                    "title": p.title,
                    "question": (p.question[:180] + "...") if p.question and len(p.question) > 180 else (p.question or ""),
                    "language": p.language,
                    "section_keys": list(sections.keys()),
                    "section_count": len(sections),
                    "created_at": p.created_at.strftime("%b %d, %Y") if p.created_at else "",
                    "updated_at": p.updated_at.strftime("%b %d, %Y") if p.updated_at else "",
                })
    except Exception as exc:
        logger.warning("Could not load practicals for library page: %s", exc)

    return templates.TemplateResponse(
        request,
        "my_practicals.html",
        {
            "page": "my-practicals",
            "practicals": practicals_list,
            "subjects": subjects_list,
            "languages": languages_list,
            "active_subject": subject or "",
            "active_language": language or "",
            "search_query": search or "",
            "total_count": len(practicals_list),
            "section_definitions": SECTION_DEFINITIONS,
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
    language: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("updated_desc"),
):
    """List saved practicals with optional search, subject, language, and sorting."""
    SessionLocal = request.app.state.db_session_factory
    try:
        with SessionLocal() as session:
            query = session.query(Practical)
            if subject and subject.strip():
                query = query.filter(Practical.subject.ilike(f"%{subject.strip()}%"))
            if language and language.strip() and language.lower() != "all":
                query = query.filter(Practical.language.ilike(f"%{language.strip()}%"))
            if search and search.strip():
                search_term = f"%{search.strip()}%"
                query = query.filter(
                    (Practical.title.ilike(search_term))
                    | (Practical.question.ilike(search_term))
                    | (Practical.subject.ilike(search_term))
                    | (Practical.language.ilike(search_term))
                )

            # Sort
            if sort == "updated_asc":
                query = query.order_by(Practical.updated_at.asc())
            elif sort == "created_desc":
                query = query.order_by(Practical.created_at.desc())
            elif sort == "created_asc":
                query = query.order_by(Practical.created_at.asc())
            elif sort == "title_asc":
                query = query.order_by(Practical.title.asc())
            elif sort == "subject_asc":
                query = query.order_by(Practical.subject.asc())
            elif sort == "number_asc":
                query = query.order_by(Practical.practical_number.asc())
            else:
                query = query.order_by(Practical.updated_at.desc())

            rows = query.all()
            results = []
            for p in rows:
                try:
                    sections = json.loads(p.sections_json or "{}")
                except Exception:
                    sections = {}
                results.append({
                    "id": p.id,
                    "subject": p.subject,
                    "practical_number": p.practical_number,
                    "title": p.title,
                    "question": (p.question[:180] + "...") if p.question and len(p.question) > 180 else (p.question or ""),
                    "language": p.language,
                    "section_keys": list(sections.keys()),
                    "section_count": len(sections),
                    "created_at": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
                    "updated_at": p.updated_at.strftime("%Y-%m-%d %H:%M") if p.updated_at else "",
                })
            return results
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


@router.post("/api/practicals/{practical_id}/duplicate")
async def duplicate_practical(request: Request, practical_id: int):
    """Duplicate an existing practical as a new draft."""
    SessionLocal = request.app.state.db_session_factory
    try:
        with SessionLocal() as session:
            p = session.query(Practical).filter(Practical.id == practical_id).first()
            if not p:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Practical with ID {practical_id} not found.",
                )
            copy_num = f"{p.practical_number} (Copy)" if p.practical_number else None
            copy_p = Practical(
                subject=p.subject,
                practical_number=copy_num,
                title=f"{p.title} (Copy)",
                question=p.question,
                language=p.language,
                sections_json=p.sections_json,
            )
            session.add(copy_p)
            session.commit()
            session.refresh(copy_p)
            return {
                "success": True,
                "id": copy_p.id,
                "title": copy_p.title,
                "message": f"Successfully duplicated '{p.title}'!",
            }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to duplicate practical %d: %s", practical_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/api/practicals/batch-delete")
async def batch_delete_practicals(request: Request, payload: BatchDeleteRequest):
    """Delete multiple practicals in one transaction."""
    if not payload.ids:
        return {"success": True, "deleted_count": 0}
    SessionLocal = request.app.state.db_session_factory
    try:
        with SessionLocal() as session:
            count = (
                session.query(Practical)
                .filter(Practical.id.in_(payload.ids))
                .delete(synchronize_session=False)
            )
            session.commit()
            return {
                "success": True,
                "deleted_count": count,
                "message": f"Successfully deleted {count} practical(s).",
            }
    except Exception as exc:
        logger.exception("Failed to batch delete practicals: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Exporting & Academic Print View
# ---------------------------------------------------------------------------

@router.get("/api/practicals/{practical_id}/export")
async def export_practical(
    request: Request,
    practical_id: int,
    format: str = Query("markdown", pattern=r"^(markdown|txt|json)$"),
):
    """Export a practical as a downloadable Markdown, plain text, or JSON file."""
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

            if format == "json":
                export_data = {
                    "id": p.id,
                    "subject": p.subject,
                    "practical_number": p.practical_number,
                    "title": p.title,
                    "question": p.question,
                    "language": p.language,
                    "sections": sections,
                    "created_at": p.created_at.isoformat() if p.created_at else "",
                    "updated_at": p.updated_at.isoformat() if p.updated_at else "",
                }
                content = json.dumps(export_data, indent=2)
                filename = f"Practical_{p.practical_number or p.id}_{p.subject.replace(' ', '_')}.json"
                media_type = "application/json; charset=utf-8"
            elif format == "markdown":
                title_prefix = f"Practical #{p.practical_number}: " if p.practical_number else ""
                lines = [
                    f"# {title_prefix}{p.title}\n",
                    f"**Subject:** {p.subject}  ",
                ]
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
                lines = [
                    "=" * 60,
                    f"{title_prefix}{p.title}".center(60),
                    "=" * 60,
                    f"Subject: {p.subject}",
                ]
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


@router.get("/practicals/{practical_id}/print", response_class=HTMLResponse)
async def print_practical_view(request: Request, practical_id: int):
    """Render a formal academic laboratory record for clean printing / PDF export."""
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
            return templates.TemplateResponse(
                request,
                "practical_print.html",
                {
                    "practical": p,
                    "sections": sections,
                    "section_definitions": SECTION_DEFINITIONS,
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to render print view for %d: %s", practical_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
