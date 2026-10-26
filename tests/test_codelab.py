"""
Tests for Code Lab — page loading, AI analysis modes, and snippet CRUD.
"""

import pytest


class TestCodeLabPage:
    """Test that Code Lab workbench page loads properly."""

    def test_codelab_page_loads(self, client):
        resp = client.get("/code-lab")
        assert resp.status_code == 200
        assert "Code Lab" in resp.text
        assert "Explain Code" in resp.text
        assert "Dry Run Trace" in resp.text
        assert "Debug &amp; Fix" in resp.text or "Debug & Fix" in resp.text


class TestCodeLabAnalysis:
    """Test AI analysis across all 5 modes."""

    def test_explain_code_success(self, client, mock_gemini_success):
        payload = {
            "code": "def add(a, b): return a + b",
            "language": "python",
            "mode": "explain",
        }
        resp = client.post("/api/codelab/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["mode"] == "explain"
        assert len(data["data"]["content"]) > 0

    def test_dryrun_code_success(self, client, mock_gemini_success):
        payload = {
            "code": "for i in range(3): print(i)",
            "language": "python",
            "mode": "dryrun",
            "sample_input": "n = 3",
        }
        resp = client.post("/api/codelab/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["mode"] == "dryrun"

    def test_debug_code_success(self, client, mock_gemini_success):
        payload = {
            "code": "int main() { printf('hello') }",
            "language": "c",
            "mode": "debug",
            "error_message": "error: expected ';' before '}'",
        }
        resp = client.post("/api/codelab/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["mode"] == "debug"

    def test_optimize_code_success(self, client, mock_gemini_success):
        payload = {
            "code": "def fib(n): return fib(n-1) + fib(n-2) if n > 1 else n",
            "language": "python",
            "mode": "optimize",
        }
        resp = client.post("/api/codelab/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["mode"] == "optimize"

    def test_viva_code_success(self, client, mock_gemini_success):
        payload = {
            "code": "void swap(int *a, int *b) { int t = *a; *a = *b; *b = t; }",
            "language": "c",
            "mode": "viva",
        }
        resp = client.post("/api/codelab/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["mode"] == "viva"

    def test_validation_error_empty_code(self, client, mock_gemini_success):
        payload = {
            "code": "",
            "language": "python",
            "mode": "explain",
        }
        resp = client.post("/api/codelab/analyze", json=payload)
        assert resp.status_code == 422

    def test_validation_error_invalid_mode(self, client, mock_gemini_success):
        payload = {
            "code": "print('hello')",
            "language": "python",
            "mode": "invalid_mode",
        }
        resp = client.post("/api/codelab/analyze", json=payload)
        assert resp.status_code == 422

    def test_analysis_when_gemini_down(self, client, monkeypatch):
        from app.services.gemini_service import GeminiService, GeminiUnreachableError

        async def mock_chat_down(self, messages, **kwargs):
            raise GeminiUnreachableError("Gemini API connection failed")

        monkeypatch.setattr(GeminiService, "chat", mock_chat_down)

        payload = {
            "code": "def test(): pass",
            "language": "python",
            "mode": "explain",
        }
        resp = client.post("/api/codelab/analyze", json=payload)
        assert resp.status_code == 503
        assert "unreachable" in resp.json()["detail"].lower()


class TestCodeSnippetCRUD:
    """Test saving, retrieving, and deleting code snippets."""

    def test_snippet_crud_lifecycle(self, client):
        # 1. Create snippet
        payload = {
            "title": "Merge Sort in C++",
            "language": "cpp",
            "code": "void mergeSort() {}",
            "notes": "Classic divide and conquer experiment",
        }
        resp = client.post("/api/codelab/snippets", json=payload)
        assert resp.status_code == 200
        snippet = resp.json()
        assert snippet["id"] is not None
        assert snippet["title"] == "Merge Sort in C++"
        snippet_id = snippet["id"]

        # 2. List snippets
        list_resp = client.get("/api/codelab/snippets")
        assert list_resp.status_code == 200
        items = list_resp.json()["snippets"]
        assert any(s["id"] == snippet_id for s in items)

        # 3. Get single snippet
        get_resp = client.get(f"/api/codelab/snippets/{snippet_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "Merge Sort in C++"

        # 4. Delete snippet
        del_resp = client.delete(f"/api/codelab/snippets/{snippet_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

        # 5. Verify deleted (404)
        not_found_resp = client.get(f"/api/codelab/snippets/{snippet_id}")
        assert not_found_resp.status_code == 404
