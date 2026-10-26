"""
Code Lab Router — Web pages and API endpoints for code analysis, debugging, and snippets.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import CodeSnippet
from app.schemas import CodeLabRequest, CodeSnippetCreate, CodeSnippetResponse
from app.services.codelab_service import CodeLabService
from app.services.gemini_service import (
    GeminiError,
    GeminiModelMissingError,
    GeminiTimeoutError,
    GeminiUnreachableError,
)

logger = logging.getLogger("labmate.codelab")
router = APIRouter(tags=["codelab"])
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Database Session Dependency
# ---------------------------------------------------------------------------

def get_db(request: Request) -> Session:
    """Yield a database session from the app's session factory."""
    factory = getattr(request.app.state, "db_session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not initialized",
        )
    db = factory()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pre-built Algorithm Templates
# ---------------------------------------------------------------------------

CODE_PRESETS = [
    {
        "id": "c-bubble-sort",
        "title": "Bubble Sort with Swap Flag",
        "language": "c",
        "category": "Sorting",
        "code": """#include <stdio.h>
#include <stdbool.h>

void bubbleSort(int arr[], int n) {
    for (int i = 0; i < n - 1; i++) {
        bool swapped = false;
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
                swapped = true;
            }
        }
        if (!swapped) break;
    }
}

int main() {
    int arr[] = {64, 34, 25, 12, 22, 11, 90};
    int n = sizeof(arr) / sizeof(arr[0]);
    bubbleSort(arr, n);
    printf("Sorted array: ");
    for (int i = 0; i < n; i++) printf("%d ", arr[i]);
    printf("\\n");
    return 0;
}"""
    },
    {
        "id": "cpp-binary-search",
        "title": "Binary Search (Recursive)",
        "language": "cpp",
        "category": "Searching",
        "code": """#include <iostream>
#include <vector>

int binarySearch(const std::vector<int>& arr, int low, int high, int target) {
    if (low > high) return -1;
    int mid = low + (high - low) / 2;
    if (arr[mid] == target) return mid;
    if (arr[mid] > target) return binarySearch(arr, low, mid - 1, target);
    return binarySearch(arr, mid + 1, high, target);
}

int main() {
    std::vector<int> data = {2, 5, 8, 12, 16, 23, 38, 56, 72, 91};
    int target = 23;
    int idx = binarySearch(data, 0, data.size() - 1, target);
    if (idx != -1)
        std::cout << "Element found at index: " << idx << std::endl;
    else
        std::cout << "Element not found" << std::endl;
    return 0;
}"""
    },
    {
        "id": "py-lru-cache",
        "title": "LRU Cache Implementation",
        "language": "python",
        "category": "Data Structures",
        "code": """class Node:
    def __init__(self, key: int, val: int):
        self.key = key
        self.val = val
        self.prev = None
        self.next = None

class LRUCache:
    def __init__(self, capacity: int):
        self.cap = capacity
        self.cache = {}
        self.head = Node(0, 0)
        self.tail = Node(0, 0)
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: Node):
        p, n = node.prev, node.next
        p.next, n.prev = n, p

    def _add(self, node: Node):
        p, n = self.head, self.head.next
        p.next = n.prev = node
        node.prev, node.next = p, n

    def get(self, key: int) -> int:
        if key in self.cache:
            node = self.cache[key]
            self._remove(node)
            self._add(node)
            return node.val
        return -1

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self._remove(self.cache[key])
        node = Node(key, value)
        self.cache[key] = node
        self._add(node)
        if len(self.cache) > self.cap:
            lru = self.tail.prev
            self._remove(lru)
            del self.cache[lru.key]"""
    },
    {
        "id": "java-linked-list-reverse",
        "title": "Singly Linked List Reversal",
        "language": "java",
        "category": "Linked Lists",
        "code": """class ListNode {
    int val;
    ListNode next;
    ListNode(int val) { this.val = val; }
}

public class Solution {
    public ListNode reverseList(ListNode head) {
        ListNode prev = null;
        ListNode curr = head;
        while (curr != null) {
            ListNode nextTemp = curr.next;
            curr.next = prev;
            prev = curr;
            curr = nextTemp;
        }
        return prev;
    }
}"""
    }
]


# ---------------------------------------------------------------------------
# HTML Page Endpoint
# ---------------------------------------------------------------------------

@router.get("/code-lab", response_class=HTMLResponse)
async def code_lab_page(request: Request, db: Session = Depends(get_db)):
    """Render the main Code Lab studio workbench."""
    snippets = (
        db.execute(select(CodeSnippet).order_by(desc(CodeSnippet.updated_at)).limit(20))
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request,
        "codelab.html",
        {
            "page": "code-lab",
            "presets": CODE_PRESETS,
            "snippets": snippets,
        },
    )


# ---------------------------------------------------------------------------
# AI Analysis Endpoint
# ---------------------------------------------------------------------------

@router.post("/api/codelab/analyze")
async def analyze_code(request: Request, req: CodeLabRequest) -> dict[str, Any]:
    """Execute AI code analysis for explain, dryrun, debug, optimize, or viva."""
    gemini = getattr(request.app.state, "gemini", None)
    if not gemini:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not initialized",
        )

    service = CodeLabService(gemini)
    try:
        result = await service.process_code(req)
        return {"success": True, "data": result}
    except GeminiUnreachableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Gemini API is unreachable. Check your internet connection or API key.",
        ) from exc
    except GeminiModelMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except GeminiTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI generation timed out. Try with a smaller code block.",
        ) from exc
    except GeminiError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI service error: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in Code Lab analysis: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Snippet CRUD Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/codelab/snippets")
async def list_snippets(db: Session = Depends(get_db)):
    """List all saved code snippets."""
    snippets = (
        db.execute(select(CodeSnippet).order_by(desc(CodeSnippet.updated_at)))
        .scalars()
        .all()
    )
    return {
        "success": True,
        "snippets": [
            {
                "id": s.id,
                "title": s.title,
                "language": s.language,
                "code": s.code,
                "notes": s.notes,
                "created_at": s.created_at.isoformat() if s.created_at else "",
                "updated_at": s.updated_at.isoformat() if s.updated_at else "",
            }
            for s in snippets
        ],
    }


@router.post("/api/codelab/snippets", response_model=CodeSnippetResponse)
async def save_snippet(req: CodeSnippetCreate, db: Session = Depends(get_db)):
    """Save or create a new code snippet."""
    snippet = CodeSnippet(
        title=req.title,
        language=req.language,
        code=req.code,
        notes=req.notes,
    )
    db.add(snippet)
    db.commit()
    db.refresh(snippet)
    return CodeSnippetResponse(
        id=snippet.id,
        title=snippet.title,
        language=snippet.language,
        code=snippet.code,
        notes=snippet.notes,
        created_at=snippet.created_at.isoformat() if snippet.created_at else "",
        updated_at=snippet.updated_at.isoformat() if snippet.updated_at else "",
    )


@router.get("/api/codelab/snippets/{snippet_id}", response_model=CodeSnippetResponse)
async def get_snippet(snippet_id: int, db: Session = Depends(get_db)):
    """Get a saved snippet by id."""
    snippet = db.get(CodeSnippet, snippet_id)
    if not snippet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snippet #{snippet_id} not found",
        )
    return CodeSnippetResponse(
        id=snippet.id,
        title=snippet.title,
        language=snippet.language,
        code=snippet.code,
        notes=snippet.notes,
        created_at=snippet.created_at.isoformat() if snippet.created_at else "",
        updated_at=snippet.updated_at.isoformat() if snippet.updated_at else "",
    )


@router.delete("/api/codelab/snippets/{snippet_id}")
async def delete_snippet(snippet_id: int, db: Session = Depends(get_db)):
    """Delete a snippet by id."""
    snippet = db.get(CodeSnippet, snippet_id)
    if not snippet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snippet #{snippet_id} not found",
        )
    db.delete(snippet)
    db.commit()
    return {"success": True, "message": f"Snippet #{snippet_id} deleted"}
