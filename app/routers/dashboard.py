"""
Dashboard router — serves the main landing page.
"""

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger("labmate.dashboard")
router = APIRouter(tags=["dashboard"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Render the dashboard with real application state:
    - Recent practicals from the database
    - Ollama status (fetched async by the frontend)
    """
    # Get recent practicals from the database
    SessionLocal = request.app.state.db_session_factory
    recent_practicals = []
    try:
        with SessionLocal() as session:
            from app.database import Practical
            rows = (
                session.query(Practical)
                .order_by(Practical.updated_at.desc())
                .limit(5)
                .all()
            )
            for row in rows:
                recent_practicals.append({
                    "id": row.id,
                    "subject": row.subject,
                    "practical_number": row.practical_number,
                    "title": row.title,
                    "language": row.language,
                    "updated_at": row.updated_at.strftime("%b %d, %Y") if row.updated_at else "",
                })
    except Exception as exc:
        logger.warning("Could not load recent practicals: %s", exc)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "page": "dashboard",
            "recent_practicals": recent_practicals,
        },
    )
