"""
Practical Studio Service — engineering lab practical generation and editing.

Generates structured practical file content following standard university
engineering formats:
1. Aim
2. Algorithm / Procedure
3. Source Code (well-commented)
4. Expected Output / Test Run
5. Complexity Analysis (Time & Space)
6. Viva Questions & Answers
7. Precautions & Best Practices
"""

import json
import logging
import re
from typing import Any

from app.schemas import PracticalGenerateRequest, PracticalSectionRegenRequest
from app.services.gemini_service import (
    GeminiError,
    GeminiGenerationError,
    GeminiService,
)

logger = logging.getLogger("labmate.practical")

# Standard section display metadata
SECTION_DEFINITIONS = {
    "aim": {
        "title": "Aim / Objective",
        "icon": "🎯",
        "description": "Clear and formal statement of what the experiment achieves",
    },
    "algorithm": {
        "title": "Algorithm / Procedure",
        "icon": "📋",
        "description": "Step-by-step procedure from Start to Stop",
    },
    "code": {
        "title": "Source Code",
        "icon": "💻",
        "description": "Clean, syntactically correct, well-commented implementation",
    },
    "output": {
        "title": "Expected Output",
        "icon": "🖥️",
        "description": "Console output, sample input/output execution trace",
    },
    "complexity": {
        "title": "Complexity Analysis",
        "icon": "⚡",
        "description": "Time and Space complexity with Big-O notation and explanation",
    },
    "viva_questions": {
        "title": "Viva Questions & Answers",
        "icon": "💡",
        "description": "Top high-yield practical exam viva questions with precise answers",
    },
    "precautions": {
        "title": "Precautions & Notes",
        "icon": "⚠️",
        "description": "Important precautions, common pitfalls, and edge cases",
    },
}

SECTION_KEYS = list(SECTION_DEFINITIONS.keys())

SYSTEM_PROMPT = """You are AI LabMate, an expert engineering professor and lab mentor for B.Tech Information Technology / Computer Science students.
Your job is to generate high-quality, academic-standard practical file content for engineering lab submissions.

Follow these strict rules:
1. Format each section clearly under its corresponding header marker:
   ### [AIM]
   ### [ALGORITHM]
   ### [CODE]
   ### [OUTPUT]
   ### [COMPLEXITY]
   ### [VIVA_QUESTIONS]
   ### [PRECAUTIONS]
2. Under ### [AIM], write a formal, concise statement: "To implement/study/analyze..."
3. Under ### [ALGORITHM], write numbered steps: "Step 1: Start", "Step 2: ...", ending with "Step N: Stop".
4. Under ### [CODE], provide complete, clean, working code in the specified language with informative comments. Use markdown code fences ```language ... ```.
5. Under ### [OUTPUT], provide realistic console input and execution output showing successful test cases.
6. Under ### [COMPLEXITY], specify Time Complexity (Best, Average, Worst) and Auxiliary Space Complexity with Big-O notation and brief rationale.
7. Under ### [VIVA_QUESTIONS], provide 4-6 high-yield viva questions with clear, accurate answers.
8. Under ### [PRECAUTIONS], provide 3-5 practical precautions or edge cases to consider.
9. Do not include conversational filler (e.g. "Sure, here is your practical", "Hope this helps"). Only output the requested sections.
"""


def _build_generation_prompt(request: PracticalGenerateRequest) -> str:
    """Construct the user prompt for generating practical content."""
    requested_sections_str = ", ".join(
        f"{key} ({SECTION_DEFINITIONS.get(key, {}).get('title', key)})"
        for key in request.sections
        if key in SECTION_DEFINITIONS
    )

    prompt_parts = [
        f"Generate practical file content for the following engineering experiment:",
        f"- Subject: {request.subject}",
    ]
    if request.practical_number:
        prompt_parts.append(f"- Practical Number: {request.practical_number}")
    prompt_parts.append(f"- Title: {request.title}")
    prompt_parts.append(f"- Problem Statement / Question:\n{request.question}")

    if request.language and request.language.lower() not in ("none", "theory"):
        prompt_parts.append(f"- Programming Language: {request.language}")

    prompt_parts.append(f"- Detail Level: {request.answer_length} (short = concise essentials, medium = standard lab manual depth, detailed = comprehensive with deep comments)")
    prompt_parts.append(f"- Required Sections to include:\n{requested_sections_str}")

    if request.additional_instructions:
        prompt_parts.append(f"- Additional Requirements:\n{request.additional_instructions}")

    prompt_parts.append(
        "\nIMPORTANT: Only generate the sections listed above. "
        "Precede each section with its exact marker header: "
        + " ".join(f"### [{s.upper()}]" for s in request.sections if s in SECTION_DEFINITIONS)
    )

    return "\n".join(prompt_parts)


def parse_sections_from_response(raw_text: str, requested_sections: list[str]) -> dict[str, str]:
    """
    Parse section text delimited by '### [SECTION_NAME]' markers.
    Handles variations in casing, brackets, and markdown headers.
    """
    result: dict[str, str] = {}
    normalized_keys = [k.lower() for k in requested_sections]

    # Pattern matches headers like:
    # ### [AIM] or ## [AIM] or ### AIM or ## Aim: or **AIM**
    pattern = re.compile(
        r"(?:^|\n)(?:#{1,4}\s*(?:\[(?P<tag_bracket>[A-Za-z_]+)\]|(?P<tag_plain>[A-Za-z_\s]+?):?))\s*(?:\n|$)",
        re.MULTILINE,
    )

    matches = list(pattern.finditer(raw_text))

    if matches:
        for i, match in enumerate(matches):
            raw_tag = (match.group("tag_bracket") or match.group("tag_plain") or "").strip().lower()
            cleaned_tag = raw_tag.replace(" ", "_")

            if "aim" in cleaned_tag or "objective" in cleaned_tag:
                key = "aim"
            elif "algo" in cleaned_tag or "procedure" in cleaned_tag:
                key = "algorithm"
            elif "code" in cleaned_tag or "program" in cleaned_tag or "source" in cleaned_tag:
                key = "code"
            elif "output" in cleaned_tag or "result" in cleaned_tag:
                key = "output"
            elif "complexity" in cleaned_tag:
                key = "complexity"
            elif "viva" in cleaned_tag:
                key = "viva_questions"
            elif "precaution" in cleaned_tag or "note" in cleaned_tag:
                key = "precautions"
            else:
                key = cleaned_tag

            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
            content = raw_text[start_pos:end_pos].strip()

            if key in normalized_keys and content:
                result[key] = content

    # If parsing found fewer than requested sections, check for fallback regex for each missing key
    for key in normalized_keys:
        if key not in result or not result[key]:
            escaped_key = re.escape(key.upper())
            direct_pattern = re.compile(
                rf"(?:###?\s*\[?{escaped_key}\]?[:\s]*\n)(.*?)(?=(?:###?\s*\[?[A-Z_]+\]?)|$)",
                re.DOTALL | re.IGNORECASE,
            )
            direct_match = direct_pattern.search(raw_text)
            if direct_match and direct_match.group(1).strip():
                result[key] = direct_match.group(1).strip()

    # If still empty for all requested sections, place all text into first requested section or aim/code
    if not any(result.values()) and raw_text.strip():
        primary_key = "code" if "code" in normalized_keys else normalized_keys[0]
        result[primary_key] = raw_text.strip()

    # Ensure every requested section has at least an empty string or fallback note
    for key in normalized_keys:
        if key not in result or not result[key].strip():
            result[key] = f"*(No content generated for {SECTION_DEFINITIONS.get(key, {}).get('title', key)}. Click 'Regenerate' to try again.)*"

    return result


class PracticalService:
    """Service handling practical file generation and section editing."""

    @staticmethod
    async def generate_practical(
        request: PracticalGenerateRequest,
        gemini: GeminiService,
    ) -> dict[str, str]:
        """
        Generate practical content for all requested sections.
        Returns a dict mapping section keys to content strings.
        """
        logger.info(
            "Generating practical — subject='%s' title='%s' sections=%d",
            request.subject,
            request.title,
            len(request.sections),
        )

        user_prompt = _build_generation_prompt(request)
        max_tokens = min(4096, 700 * max(1, len(request.sections)))

        raw_response = await gemini.chat(
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.4,
            max_tokens=max_tokens,
            system_prompt=SYSTEM_PROMPT,
        )

        sections = parse_sections_from_response(raw_response, request.sections)
        return sections

    @staticmethod
    async def regenerate_section(
        request: PracticalSectionRegenRequest,
        gemini: GeminiService,
    ) -> str:
        """
        Regenerate a single practical section with custom guidance and context.
        """
        key = request.section_key.lower()
        sec_info = SECTION_DEFINITIONS.get(key, {"title": key, "description": ""})

        logger.info(
            "Regenerating section '%s' for practical '%s'",
            key,
            request.title,
        )

        context_snippets = []
        if key in ("output", "complexity", "algorithm") and "code" in request.existing_sections:
            context_snippets.append(f"Relevant Source Code:\n```\n{request.existing_sections['code']}\n```")
        elif key == "code" and "algorithm" in request.existing_sections:
            context_snippets.append(f"Algorithm:\n{request.existing_sections['algorithm']}")

        context_str = "\n\n".join(context_snippets)

        prompt_parts = [
            f"You are regenerating ONLY the '{sec_info['title']}' section for this practical:",
            f"- Subject: {request.subject}",
            f"- Title: {request.title}",
            f"- Problem Statement: {request.question}",
        ]
        if request.language:
            prompt_parts.append(f"- Programming Language: {request.language}")
        if context_str:
            prompt_parts.append(f"\nContext from other sections:\n{context_str}")
        if request.additional_instructions:
            prompt_parts.append(f"\nUser instructions for this regeneration:\n{request.additional_instructions}")

        prompt_parts.append(
            f"\nStrict requirements:\n"
            f"- Output ONLY the content for the '{sec_info['title']}' section.\n"
            f"- Do NOT wrap with markers like '### [{key.upper()}]' or conversational introductions.\n"
            f"- Make it clean, academic-standard, and immediately ready to copy into an engineering practical file."
        )

        user_prompt = "\n".join(prompt_parts)

        raw_response = await gemini.chat(
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.5,
            max_tokens=2048,
            system_prompt=SYSTEM_PROMPT,
        )

        # Strip any accidental header markers like ### [AIM] or ## Aim
        cleaned = re.sub(
            r"^\s*#{1,4}\s*(?:\[?[\w\s/]+\]?)\s*[:\n]*",
            "",
            raw_response.strip(),
            flags=re.IGNORECASE,
        )

        return cleaned.strip()
