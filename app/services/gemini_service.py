"""
Gemini AI Service — reusable client for all AI interactions.

Responsibilities:
- Check if the Gemini API is reachable and the key is valid
- Submit chat completion requests via Google's Gemini API
- Handle timeouts, connection errors, invalid keys
- Return normalized errors (never raw tracebacks to the user)

Design decisions:
- Uses the official `google-genai` SDK
- Semaphore limits concurrent generations to 2 (Gemini free tier rate limits)
- Non-streaming responses for simplicity in v1.0
"""

import asyncio
import json
import logging
from typing import Any

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger("labmate.gemini")


class GeminiError(Exception):
    """Base error for Gemini service issues."""
    pass


class GeminiUnreachableError(GeminiError):
    """Gemini API is not responding or API key is invalid."""
    pass


class GeminiModelMissingError(GeminiError):
    """Configured model is not available."""
    pass


class GeminiGenerationError(GeminiError):
    """Model generation failed or returned invalid data."""
    pass


class GeminiTimeoutError(GeminiError):
    """Request timed out waiting for model response."""
    pass


class GeminiService:
    """
    Manages all communication with the Google Gemini API.

    Usage:
        service = GeminiService()
        await service.start()       # Call once at app startup
        status = await service.health_check()
        response = await service.chat([{"role": "user", "content": "Hello"}])
        await service.stop()        # Call once at app shutdown
    """

    def __init__(self):
        self._client: genai.Client | None = None
        # Allow 2 concurrent generations (free tier allows ~15 RPM)
        self._semaphore = asyncio.Semaphore(2)

    async def start(self):
        """Create the Gemini client. Call once at app startup."""
        if not settings.gemini_api_key:
            logger.warning(
                "GEMINI_API_KEY is not set. AI features will not work."
            )
            return

        self._client = genai.Client(api_key=settings.gemini_api_key)
        logger.info(
            "Gemini service started — model=%s",
            settings.gemini_model,
        )

    async def stop(self):
        """Clean up resources. Call once at app shutdown."""
        self._client = None
        logger.info("Gemini service stopped")

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """
        Multi-level health check. Returns a dict with:
          - api_reachable: bool
          - model_available: bool
          - model_name: str
          - error: str | None
        """
        result = {
            "api_reachable": False,
            "model_available": False,
            "model_name": settings.gemini_model,
            "error": None,
        }

        if not self._client:
            result["error"] = (
                "Gemini API key is not configured. "
                "Add GEMINI_API_KEY to your .env file."
            )
            return result

        # Step 1: Can we reach the API and is the model available?
        try:
            loop = asyncio.get_event_loop()
            models_response = await loop.run_in_executor(
                None, lambda: list(self._client.models.list())
            )
            result["api_reachable"] = True

            model_names = [m.name for m in models_response]
            target = settings.gemini_model
            # Models are listed as "models/gemini-2.0-flash" etc.
            model_found = any(
                target in name or name.endswith(target)
                for name in model_names
            )
            result["model_available"] = model_found

            if not model_found:
                result["error"] = (
                    f"Model '{target}' is not available. "
                    f"Check your GEMINI_MODEL setting in .env"
                )
        except Exception as exc:
            error_str = str(exc).lower()
            if "api key" in error_str or "401" in error_str or "403" in error_str:
                result["error"] = (
                    "Invalid Gemini API key. "
                    "Check your GEMINI_API_KEY in the .env file."
                )
            else:
                result["error"] = f"Cannot reach Gemini API: {exc}"

        return result

    async def is_reachable(self) -> bool:
        """Quick connectivity check."""
        if not self._client:
            return False
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: list(self._client.models.list())
            )
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Chat completion
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: str | None = None,
    ) -> str:
        """
        Send a chat completion request to Gemini.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            system_prompt: Optional system message prepended to messages

        Returns:
            The assistant's response text.

        Raises:
            GeminiUnreachableError: Cannot connect to Gemini API
            GeminiModelMissingError: Model not found
            GeminiTimeoutError: Generation timed out
            GeminiGenerationError: Other generation failures
        """
        if not self._client:
            raise GeminiUnreachableError(
                "Gemini API key is not configured. Add GEMINI_API_KEY to .env"
            )

        # Build Gemini-compatible contents
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            # Gemini uses "user" and "model" (not "assistant")
            if role == "assistant":
                role = "model"
            elif role == "system":
                # System messages get merged into the system_instruction
                if not system_prompt:
                    system_prompt = msg["content"]
                else:
                    system_prompt = system_prompt + "\n\n" + msg["content"]
                continue
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])],
                )
            )

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system_prompt:
            config.system_instruction = system_prompt

        async with self._semaphore:
            try:
                logger.info(
                    "Gemini chat request — model=%s messages=%d max_tokens=%d",
                    settings.gemini_model,
                    len(contents),
                    max_tokens,
                )
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._client.models.generate_content(
                        model=settings.gemini_model,
                        contents=contents,
                        config=config,
                    ),
                )
            except asyncio.TimeoutError as exc:
                raise GeminiTimeoutError(
                    f"Generation timed out after {settings.gemini_timeout}s. "
                    "Try a shorter prompt."
                ) from exc
            except Exception as exc:
                error_str = str(exc).lower()
                if "api key" in error_str or "401" in error_str or "403" in error_str:
                    raise GeminiUnreachableError(
                        "Invalid Gemini API key. Check GEMINI_API_KEY in .env"
                    ) from exc
                if "not found" in error_str or "404" in error_str:
                    raise GeminiModelMissingError(
                        f"Model '{settings.gemini_model}' not found. "
                        "Check your GEMINI_MODEL setting."
                    ) from exc
                if "rate" in error_str or "429" in error_str or "quota" in error_str:
                    raise GeminiGenerationError(
                        "Gemini API rate limit exceeded. "
                        "Wait a minute and try again, or check your API quota."
                    ) from exc
                raise GeminiGenerationError(
                    f"Unexpected error during generation: {exc}"
                ) from exc

        # Parse response
        content = response.text if response.text else ""

        if not content.strip():
            raise GeminiGenerationError(
                "Gemini returned an empty response. "
                "The model may have had trouble with this prompt."
            )

        logger.info(
            "Gemini response received — length=%d chars",
            len(content),
        )
        return content

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 3000,
        system_prompt: str | None = None,
    ) -> dict:
        """
        Send a chat request expecting a JSON response.
        Attempts to parse the response as JSON; raises GeminiGenerationError
        if the model output is not valid JSON.
        """
        raw = await self.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
        )

        # Try to extract JSON from the response (model may wrap in markdown)
        text = raw.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last fence lines
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Failed to parse JSON from model response: %s...",
                text[:200],
            )
            raise GeminiGenerationError(
                "The AI model did not return valid JSON. "
                "This sometimes happens — please try again."
            ) from exc
