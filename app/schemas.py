"""
Pydantic schemas for request/response validation.

These models define the shape of data flowing between
the frontend and backend. FastAPI uses them for automatic
validation and documentation.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Health / Status
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Response from the /api/health endpoint."""
    status: str = "ok"
    api_reachable: bool = False
    model_available: bool = False
    model_name: str = ""
    error: str | None = None


# ---------------------------------------------------------------------------
# Practical Studio (Milestone 2 — schema defined early for consistency)
# ---------------------------------------------------------------------------

class PracticalGenerateRequest(BaseModel):
    """Request to generate practical content."""
    subject: str = Field(..., min_length=1, max_length=200)
    practical_number: str | None = Field(None, max_length=20)
    title: str = Field(..., min_length=1, max_length=500)
    question: str = Field(..., min_length=1, max_length=5000)
    language: str | None = Field(None, max_length=50)
    sections: list[str] = Field(..., min_length=1)
    answer_length: str = Field(default="medium")  # short, medium, detailed
    additional_instructions: str | None = Field(None, max_length=2000)


class PracticalSectionRegenRequest(BaseModel):
    """Request to regenerate a single section."""
    section_key: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    language: str | None = None
    existing_sections: dict[str, str] = Field(default_factory=dict)
    additional_instructions: str | None = None


class PracticalSaveRequest(BaseModel):
    """Request to save a practical to the database."""
    subject: str = Field(..., min_length=1, max_length=200)
    practical_number: str | None = Field(None, max_length=20)
    title: str = Field(..., min_length=1, max_length=500)
    question: str = Field(..., min_length=1, max_length=5000)
    language: str | None = Field(None, max_length=50)
    sections: dict[str, str] = Field(default_factory=dict)


class PracticalResponse(BaseModel):
    """A saved practical returned from the API."""
    id: int
    subject: str
    practical_number: str | None
    title: str
    question: str
    language: str | None
    sections: dict[str, str]
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Code Lab (Milestone 3)
# ---------------------------------------------------------------------------

class CodeLabRequest(BaseModel):
    """Request for code analysis, explanation, debugging, or trace."""
    code: str = Field(..., min_length=1, max_length=20000)
    language: str = Field(default="python", max_length=50)
    mode: str = Field(..., pattern=r"^(explain|dryrun|debug|optimize|viva)$")
    sample_input: str | None = Field(None, max_length=2000)
    error_message: str | None = Field(None, max_length=2000)
    expected_behavior: str | None = Field(None, max_length=2000)
    additional_notes: str | None = Field(None, max_length=2000)


class CodeSnippetCreate(BaseModel):
    """Request to save a code snippet."""
    title: str = Field(..., min_length=1, max_length=300)
    language: str = Field(default="python", max_length=50)
    code: str = Field(..., min_length=1, max_length=20000)
    notes: str | None = Field(None, max_length=5000)


class CodeSnippetResponse(BaseModel):
    """Saved code snippet representation."""
    id: int
    title: str
    language: str
    code: str
    notes: str | None = None
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Viva Arena (Milestone 4)
# ---------------------------------------------------------------------------

class VivaRevisionRequest(BaseModel):
    """Request for quick revision content."""
    subject: str = Field(..., min_length=1, max_length=200)
    topic: str = Field(..., min_length=1, max_length=500)
    time_minutes: int = Field(default=10, ge=1, le=60)
    difficulty: str = Field(default="medium", pattern=r"^(easy|medium|hard)$")


class VivaQuestionRequest(BaseModel):
    """Request to start or continue a viva session."""
    subject: str = Field(..., min_length=1, max_length=200)
    topic: str = Field(..., min_length=1, max_length=500)
    mode: str = Field(..., pattern=r"^(rapid|mock)$")
    difficulty: str = Field(default="medium")
    session_history: list[dict] = Field(default_factory=list)


class VivaAnswerRequest(BaseModel):
    """Submit an answer to a viva question."""
    question: str = Field(..., min_length=1)
    answer: str = Field(default="")  # Empty = skip
    subject: str = Field(..., min_length=1)
    topic: str = Field(..., min_length=1)
    mode: str = Field(..., pattern=r"^(rapid|mock)$")
    session_history: list[dict] = Field(default_factory=list)
