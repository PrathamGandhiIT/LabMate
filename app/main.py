"""
AI LabMate — Main FastAPI Application

This is the entry point. It:
1. Creates the FastAPI app with lifespan management
2. Starts/stops the shared Ollama HTTP client
3. Initializes the SQLite database
4. Mounts static files and template engine
5. Includes all routers
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import create_db_engine, get_session_factory, init_db
from app.services.gemini_service import GeminiService

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO if settings.app_debug else logging.WARNING,
    format="%(asctime)s  %(name)-24s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("labmate")


# ---------------------------------------------------------------------------
# Lifespan — runs once at startup and once at shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: create DB, start Gemini client.
    Shutdown: close Gemini client.
    """
    # Database
    engine = create_db_engine()
    init_db(engine)
    app.state.db_engine = engine
    app.state.db_session_factory = get_session_factory(engine)
    logger.info("Database initialized at %s", settings.database_path)

    # Gemini service
    gemini = GeminiService()
    await gemini.start()
    app.state.gemini = gemini

    logger.info(
        "AI LabMate ready — http://%s:%s",
        settings.app_host,
        settings.app_port,
    )

    yield  # App is running

    # Shutdown
    await gemini.stop()
    engine.dispose()
    logger.info("AI LabMate shutdown complete")


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI LabMate",
    description="Private, local-first AI assistant for engineering students",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files (CSS, JS, icons)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------

from app.routers import api, dashboard, practical  # noqa: E402

app.include_router(api.router)
app.include_router(dashboard.router)
app.include_router(practical.router)


# ---------------------------------------------------------------------------
# Stub page routes (Milestones 3-4 — placeholder pages for navigation)
# ---------------------------------------------------------------------------


@app.get("/code-lab", response_class=HTMLResponse)
async def code_lab_page(request: Request):
    return templates.TemplateResponse(
        request, "codelab.html", {"page": "code-lab"}
    )


@app.get("/viva-arena", response_class=HTMLResponse)
async def viva_arena_page(request: Request):
    return templates.TemplateResponse(
        request, "viva_arena.html", {"page": "viva-arena"}
    )


@app.get("/my-practicals", response_class=HTMLResponse)
async def my_practicals_page(request: Request):
    return templates.TemplateResponse(
        request, "my_practicals.html", {"page": "my-practicals"}
    )


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(
        request,
        "base.html",
        {
            "page": "error",
            "error_title": "Page Not Found",
            "error_message": "The page you're looking for doesn't exist.",
        },
        status_code=404,
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.error("Internal server error: %s", exc)
    return templates.TemplateResponse(
        request,
        "base.html",
        {
            "page": "error",
            "error_title": "Server Error",
            "error_message": "Something went wrong. Check the console for details.",
        },
        status_code=500,
    )
