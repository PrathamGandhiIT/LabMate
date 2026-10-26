"""
Code Lab service — AI-powered code analysis, debugging, dry-run, and optimization.

Uses GeminiService to analyze programming code across languages
and produce structured, academic-grade responses for engineering students.
"""

import logging
from typing import Any

from app.schemas import CodeLabRequest
from app.services.gemini_service import (
    GeminiError,
    GeminiGenerationError,
    GeminiService,
)

logger = logging.getLogger("labmate.codelab")


class CodeLabService:
    """Handles code analysis workflows via Gemini."""

    def __init__(self, gemini: GeminiService):
        self.gemini = gemini

    async def process_code(self, req: CodeLabRequest) -> dict[str, Any]:
        """
        Process code according to the requested mode:
        explain, dryrun, debug, optimize, or viva.
        """
        prompt = self._build_prompt(req)
        system_instruction = self._get_system_instruction(req.mode, req.language)

        try:
            raw_response = await self.gemini.chat(
                messages=[{"role": "user", "content": prompt}],
                system_instruction=system_instruction,
                temperature=0.2,  # Low temperature for technical precision
            )
            return {
                "mode": req.mode,
                "language": req.language,
                "content": raw_response.strip(),
            }
        except GeminiError:
            raise
        except Exception as exc:
            logger.error("Code Lab generation failed: %s", exc)
            raise GeminiGenerationError(f"Failed to process code: {exc}") from exc

    def _get_system_instruction(self, mode: str, language: str) -> str:
        base = (
            f"You are a Distinguished Professor of Computer Science & Engineering "
            f"and an expert in {language}. "
            "Your output must be technically rigorous, concise, beautifully formatted in Markdown, "
            "and tailored for engineering students preparing for laboratory journals and viva examinations."
        )
        return base

    def _build_prompt(self, req: CodeLabRequest) -> str:
        if req.mode == "explain":
            return self._build_explain_prompt(req)
        elif req.mode == "dryrun":
            return self._build_dryrun_prompt(req)
        elif req.mode == "debug":
            return self._build_debug_prompt(req)
        elif req.mode == "optimize":
            return self._build_optimize_prompt(req)
        elif req.mode == "viva":
            return self._build_viva_prompt(req)
        else:
            return self._build_explain_prompt(req)

    def _build_explain_prompt(self, req: CodeLabRequest) -> str:
        notes = f"\nAdditional Student Notes: {req.additional_notes}" if req.additional_notes else ""
        return f"""Analyze and explain the following {req.language} code in depth:

```{req.language}
{req.code}
```{notes}

Provide your response strictly structured with the following markdown headings:

### 🎯 High-Level Overview
- What problem does this program solve?
- What are the core inputs and expected outputs?
- Key architectural / algorithmic paradigm used (e.g. Greedy, Divide & Conquer, OOP, Procedural).

### 🔍 Logical Walkthrough
Explain the code in logical sequence or block-by-block. Break down:
- Data structures and variables declared and their roles.
- Control flow, looping mechanics, and termination invariants.
- Critical function calls, pointer operations, or memory handling.

### ⏱️ Time & Space Complexity Analysis
- **Best Case Time Complexity**: $O(...)$ with clear derivation.
- **Average Case Time Complexity**: $O(...)$ with mathematical reason.
- **Worst Case Time Complexity**: $O(...)$ and the scenario that triggers it.
- **Auxiliary Space Complexity**: $O(...)$ (memory allocated excluding input).
- **Total Space Complexity**: $O(...)$ (including call stack frames and input storage).

### 💡 Engineering Notes & Edge Cases
Highlight 2-4 critical edge cases (e.g., empty input, overflow, off-by-one, null pointers) and how this code handles (or fails to handle) them.
"""

    def _build_dryrun_prompt(self, req: CodeLabRequest) -> str:
        sample_input = req.sample_input or "Use a small, interesting sample input (e.g. an array of 4-5 elements or small inputs) that demonstrates all loop iterations and conditional branches."
        return f"""Perform a comprehensive, step-by-step Dry Run and Variable Trace on the following {req.language} code:

```{req.language}
{req.code}
```

Sample Input:
{sample_input}

Provide your response strictly structured with the following markdown headings:

### 📥 Initial State & Setup
- Initial variable values upon input ingestion.
- Pre-conditions and memory state before main execution loops.

### 📊 Step-by-Step Variable Trace Table
Construct a detailed markdown table tracing state changes across each iteration.
Use the format:
| Step # | Line # | Loop / Scope | Variable States | Condition Evaluated | Output / Action |
Trace through every meaningful step until termination.

### 🏁 Final Execution Result & State
- Exact console output produced.
- Final state of variables/pointers/data structures in memory.
- Total iterations/steps taken.
"""

    def _build_debug_prompt(self, req: CodeLabRequest) -> str:
        err = f"\nReported Error / Bug:\n{req.error_message}" if req.error_message else "\nNo error message provided. Inspect for syntax errors, logical bugs, edge cases, and undefined behavior."
        expected = f"\nExpected Behavior:\n{req.expected_behavior}" if req.expected_behavior else ""
        return f"""Debug and repair the following {req.language} code:

```{req.language}
{req.code}
```{err}{expected}

Provide your response strictly structured with the following markdown headings:

### 🚨 Issues Detected
List each syntax error, logical flaw, boundary bug, memory leak, or undefined behavior found with line numbers and severity (Critical, Warning, Style).

### 🔬 Root Cause Analysis
Explain clearly WHY each bug occurs and how it breaks execution or causes incorrect results.

### ✅ Corrected Code
Provide the complete, corrected, and clean {req.language} code block. Include clear inline comments highlighting what was corrected.
```{req.language}
// Corrected code here
```

### 📝 Summary of Fixes & Verification
Summarize each modification made and how it solves the issue.
"""

    def _build_optimize_prompt(self, req: CodeLabRequest) -> str:
        goal = f"\nOptimization Goal: {req.additional_notes}" if req.additional_notes else "\nOptimization Goal: Minimize time complexity and memory overhead while maintaining clean, idiomatic code."
        return f"""Analyze and optimize the following {req.language} code:

```{req.language}
{req.code}
```{goal}

Provide your response strictly structured with the following markdown headings:

### 📊 Complexity Comparison
| Metric | Original Code | Optimized Code | Reason for Improvement |
|---|---|---|---|
| Time Complexity | $O(...)$ | $O(...)$ | ... |
| Auxiliary Space | $O(...)$ | $O(...)$ | ... |
| Readability / Idiomatic Score | ... | ... | ... |

### 🚀 Optimized Implementation
Provide the fully optimized, production-ready {req.language} code block with comments explaining the algorithmic improvements.
```{req.language}
// Optimized code here
```

### 🛠️ Key Optimizations Applied
Explain the algorithmic or data structure changes made (e.g. replaced nested loops with hash map, used two pointers, reduced allocations).
"""

    def _build_viva_prompt(self, req: CodeLabRequest) -> str:
        return f"""Generate oral examination (viva voce) questions specifically based on this {req.language} code implementation:

```{req.language}
{req.code}
```

Provide 6 to 8 rigorous viva questions across 4 categories:
1. **Fundamental Concepts** (2 questions on language features / data structures used)
2. **Implementation Details** (2 questions on specific lines / algorithm logic)
3. **Edge Cases & Failure Points** (2 questions on stress-testing the code)
4. **Alternative Approaches & Complexity** (1-2 questions on trade-offs)

For EVERY question, format strictly as:
#### Q[number]: [The Question]
- **Ideal Answer**: Clear, confident, technical answer the student should recite.
- **Examiner Trap / Tip**: What the examiner is really testing, or common mistakes to avoid.
"""
