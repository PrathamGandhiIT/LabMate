"""
Tests for Practical Studio service, endpoints, and database operations.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.schemas import PracticalGenerateRequest, PracticalSectionRegenRequest
from app.services.gemini_service import GeminiUnreachableError
from app.services.practical_service import (
    PracticalService,
    parse_sections_from_response,
)


# ===========================================================================
# Unit Tests: Parser & Service Logic
# ===========================================================================

class TestPracticalParser:
    """Test response text parsing into section dictionaries."""

    def test_parse_standard_markers(self):
        sample_ai_text = """
### [AIM]
To implement a singly linked list in C++ with basic operations.

### [ALGORITHM]
Step 1: Start
Step 2: Define Node struct
Step 3: Stop

### [CODE]
```cpp
#include <iostream>
int main() { return 0; }
```

### [OUTPUT]
1. Insert
2. Display
Choice: 1

### [COMPLEXITY]
Time Complexity: O(1) for insertion at head.
Space Complexity: O(n).

### [VIVA_QUESTIONS]
Q1: What is a linked list?
A1: A linear dynamic data structure.

### [PRECAUTIONS]
1. Always check for NULL pointer before dereferencing.
"""
        sections = parse_sections_from_response(
            sample_ai_text,
            ["aim", "algorithm", "code", "output", "complexity", "viva_questions", "precautions"],
        )

        assert "aim" in sections
        assert "singly linked list" in sections["aim"]
        assert "algorithm" in sections
        assert "Step 1: Start" in sections["algorithm"]
        assert "code" in sections
        assert "#include <iostream>" in sections["code"]
        assert "output" in sections
        assert "complexity" in sections
        assert "viva_questions" in sections
        assert "precautions" in sections

    def test_parse_missing_sections_has_fallback(self):
        sample_ai_text = """
### [AIM]
To demonstrate quicksort algorithm.
"""
        sections = parse_sections_from_response(
            sample_ai_text,
            ["aim", "code"],
        )

        assert "aim" in sections
        assert "quicksort" in sections["aim"]
        assert "code" in sections
        assert "Regenerate" in sections["code"] or "No content" in sections["code"]


class TestPracticalServiceAsync:
    """Test PracticalService async methods with mock Ollama."""

    @pytest.mark.asyncio
    async def test_generate_practical_success(self):
        mock_ollama = AsyncMock()
        mock_ollama.chat.return_value = """
### [AIM]
To implement binary search.

### [CODE]
int binarySearch(int arr[], int x);
"""
        req = PracticalGenerateRequest(
            subject="Algorithms",
            practical_number="04",
            title="Binary Search",
            question="Write a program to perform binary search.",
            language="C++",
            sections=["aim", "code"],
            answer_length="medium",
        )

        res = await PracticalService.generate_practical(req, mock_ollama)
        assert "aim" in res
        assert "binary search" in res["aim"].lower()
        assert "code" in res
        assert "binarySearch" in res["code"]
        assert mock_ollama.chat.called

    @pytest.mark.asyncio
    async def test_regenerate_section_success(self):
        mock_ollama = AsyncMock()
        mock_ollama.chat.return_value = """### [AIM]\nTo study and implement BFS traversal on graph."""

        req = PracticalSectionRegenRequest(
            section_key="aim",
            subject="Algorithms",
            title="BFS Traversal",
            question="Implement BFS",
            language="Python",
            existing_sections={"code": "# BFS code"},
            additional_instructions="Make it concise",
        )

        content = await PracticalService.regenerate_section(req, mock_ollama)
        assert "BFS traversal" in content
        assert not content.startswith("### [AIM]")  # Header stripped


# ===========================================================================
# API Endpoint Integration Tests
# ===========================================================================

class TestPracticalAPI:
    """Test Practical Studio API endpoints."""

    def test_practical_studio_page_loads(self, client):
        resp = client.get("/practical-studio")
        assert resp.status_code == 200
        assert "Practical Studio" in resp.text
        assert "Experiment Details" in resp.text
        assert "Generate Practical" in resp.text

    def test_generate_endpoint_success(self, client, monkeypatch):
        from app.services.gemini_service import GeminiService

        async def mock_chat(self, messages, **kwargs):
            return """
### [AIM]
To implement stack using array.

### [CODE]
class Stack { int top; };
"""

        monkeypatch.setattr(GeminiService, "chat", mock_chat)

        payload = {
            "subject": "Data Structures",
            "practical_number": "01",
            "title": "Stack using Array",
            "question": "Implement push and pop operations on stack",
            "language": "C++",
            "sections": ["aim", "code"],
            "answer_length": "medium",
        }

        resp = client.post("/api/practical/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "sections" in data
        assert "aim" in data["sections"]
        assert "code" in data["sections"]

    def test_generate_endpoint_validation_error(self, client):
        # Missing required fields
        resp = client.post("/api/practical/generate", json={"subject": ""})
        assert resp.status_code == 422

    def test_generate_endpoint_ollama_unreachable(self, client, monkeypatch):
        from app.services.gemini_service import GeminiService

        async def mock_chat_fail(self, messages, **kwargs):
            raise GeminiUnreachableError("Cannot connect to Gemini API.")

        monkeypatch.setattr(GeminiService, "chat", mock_chat_fail)

        payload = {
            "subject": "Data Structures",
            "title": "Stack",
            "question": "Implement stack",
            "sections": ["aim"],
        }
        resp = client.post("/api/practical/generate", json=payload)
        assert resp.status_code == 503
        assert "Cannot connect to Gemini" in resp.json()["detail"]

    def test_regenerate_endpoint_success(self, client, monkeypatch):
        from app.services.gemini_service import GeminiService

        async def mock_chat(self, messages, **kwargs):
            return "Step 1: Initialize top = -1\nStep 2: Check overflow"

        monkeypatch.setattr(GeminiService, "chat", mock_chat)

        payload = {
            "section_key": "algorithm",
            "subject": "DSA",
            "title": "Stack Operations",
            "question": "Implement push and pop",
            "language": "C",
            "existing_sections": {},
            "additional_instructions": "Make it 5 steps",
        }
        resp = client.post("/api/practical/regenerate-section", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "content" in data
        assert "Initialize top" in data["content"]


# ===========================================================================
# Database CRUD & Export Tests
# ===========================================================================

class TestPracticalCRUD:
    """Test saving, listing, retrieving, updating, deleting, and exporting practicals."""

    def test_full_crud_lifecycle(self, client):
        # 1. Save practical
        save_payload = {
            "subject": "Database Management Systems",
            "practical_number": "05",
            "title": "SQL Join Queries",
            "question": "Write queries demonstrating INNER, LEFT, and RIGHT joins.",
            "language": "SQL",
            "sections": {
                "aim": "To execute SQL Join operations.",
                "code": "SELECT * FROM emp INNER JOIN dept ON emp.dept_id = dept.id;",
            },
        }

        create_resp = client.post("/api/practicals", json=save_payload)
        assert create_resp.status_code == 200
        created_data = create_resp.json()
        assert created_data["success"] is True
        practical_id = created_data["id"]
        assert practical_id > 0

        # 2. Get practical by ID
        get_resp = client.get(f"/api/practicals/{practical_id}")
        assert get_resp.status_code == 200
        item = get_resp.json()
        assert item["title"] == "SQL Join Queries"
        assert item["subject"] == "Database Management Systems"
        assert "aim" in item["sections"]
        assert "code" in item["sections"]

        # 3. List practicals (with search/filter)
        list_resp = client.get("/api/practicals?subject=Database")
        assert list_resp.status_code == 200
        rows = list_resp.json()
        assert len(rows) >= 1
        assert any(r["id"] == practical_id for r in rows)

        # 4. Update practical
        update_payload = dict(save_payload)
        update_payload["title"] = "Advanced SQL Join Queries"
        update_payload["sections"]["output"] = "10 rows returned."

        update_resp = client.put(f"/api/practicals/{practical_id}", json=update_payload)
        assert update_resp.status_code == 200

        # Verify update
        get_updated = client.get(f"/api/practicals/{practical_id}").json()
        assert get_updated["title"] == "Advanced SQL Join Queries"
        assert "output" in get_updated["sections"]

        # 5. Export practical as Markdown
        md_resp = client.get(f"/api/practicals/{practical_id}/export?format=markdown")
        assert md_resp.status_code == 200
        assert "text/markdown" in md_resp.headers["content-type"]
        assert "Advanced SQL Join Queries" in md_resp.text
        assert "Database Management Systems" in md_resp.text

        # 6. Export practical as plain text
        txt_resp = client.get(f"/api/practicals/{practical_id}/export?format=txt")
        assert txt_resp.status_code == 200
        assert "text/plain" in txt_resp.headers["content-type"]
        assert "Advanced SQL Join Queries" in txt_resp.text

        # 7. Delete practical
        del_resp = client.delete(f"/api/practicals/{practical_id}")
        assert del_resp.status_code == 200

        # 8. Verify 404 after delete
        get_deleted = client.get(f"/api/practicals/{practical_id}")
        assert get_deleted.status_code == 404
