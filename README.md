# 🧪 AI LabMate

<div align="center">

![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini-3.6%20Flash-4285F4.svg?style=for-the-badge&logo=google&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57.svg?style=for-the-badge&logo=sqlite&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-35%20Passing-success.svg?style=for-the-badge&logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)

<p align="center">
  <b>A modern, high-performance AI assistant built for engineering students.</b><br>
  Generate academic-grade practical records, analyze code, and prepare for viva exams — powered by <b>Google Gemini 3.6 Flash</b>.
</p>

[Key Features](#-key-features) •
[Quick Start](#-quick-start) •
[Architecture](#-architecture) •
[Project Structure](#-project-structure) •
[Configuration](#-configuration) •
[Roadmap](#-roadmap)

</div>

---

## 💡 Overview

**AI LabMate** is a purpose-built workspace that eliminates the repetitive busywork in engineering laboratory workflows. Instead of manually searching, formatting, and drafting laboratory journals, AI LabMate produces structured, technically accurate practical documentation adhering to academic standards — completely free with no expensive GPU or complex local model setups.

---

## ✨ Key Features

### 📋 Practical Studio (Completed ✅)
- **Structured 8-Section Generation**: Title, Aim, Apparatus, Theory, Step-by-step Procedure, Program / Code, Sample Input/Output, and Conclusion.
- **Section-Level Regeneration**: Re-prompt individual sections without re-generating the entire practical.
- **Live Markdown Editor**: Interactive editor with instant formatting, previewing, and text extraction.
- **Persistent Storage**: Save, browse, update, and manage practicals with local SQLite storage.
- **Export Options**: Export files directly to clean Markdown / Plain Text for submission.

### 📂 My Practicals & Library (Milestone 5 Completed ✅)
- **Interactive Library**: Searchable and filterable archive of all saved practical records.
- **Real-Time Filtering**: Instant search across titles, subjects, languages, problem statements, and practical numbers.
- **Rich Dual Views**: Grid card tiles with section chips or compact table list for fast browsing.
- **Quick Preview Modal**: Full-screen section viewer with copy-to-clipboard for code and text sections.
- **Academic Print & PDF View**: University-formatted laboratory record layout with metadata table, faculty evaluation blocks, and `@media print` optimization.
- **Multi-Format Export & Duplication**: Instant downloads in Markdown (`.md`), Plain Text (`.txt`), and JSON backup (`.json`), plus one-click practical duplication and batch deletion.

### 💻 Code Lab (Completed ✅)
- **Deep Code Analysis**: Line-by-line breakdown of logic, algorithms, and formal Time & Space Complexity derivations.
- **Step-by-Step Dry Run Trace**: Interactive iteration trace tables tracking variable states, conditions, and console output.
- **Automated Bug Fixing**: Identify syntax errors, logic flaws, memory leaks, and boundary bugs with ready-to-run fixes.
- **Code Optimization**: Algorithmic refactoring with side-by-side Big-O comparison tables.
- **Code-Specific Viva Prep**: Tailored viva questions with ideal answers and examiner traps to avoid.
- **Snippet Library**: Save, load, and manage code snippets locally with SQLite persistence.

### 🎯 Viva Arena (Milestone 4 🚧)
- **Viva Question Generator**: Tailored oral exam questions across basic, intermediate, and tricky edge-case categories.
- **Interactive Mock Viva**: Real-time simulated interrogation with adaptive follow-ups and scoring.

---

## 📊 Feature Status Matrix

| Component | Status | Details |
|---|:---:|---|
| **System Dashboard & AI Heartbeat** | ✅ Complete | Real-time connection checks to Gemini API & models |
| **Practical Studio CRUD** | ✅ Complete | Full generation, custom section regeneration, persistence |
| **My Practicals & Library (Milestone 5)** | ✅ Complete | Search, filtering, grid/table views, modal preview, academic print & batch actions |
| **Code Lab Workbench** | ✅ Complete | Explain, dry-run trace table, debug & fix, optimize, viva & snippets |
| **SQLite ORM Backend** | ✅ Complete | Async SQLAlchemy 2.0 with clean migrations |
| **Vanilla Design System** | ✅ Complete | Responsive dark-mode glassmorphism interface |
| **Automated Test Suite** | ✅ Complete | 35 Pytest unit & integration tests passing |
| **Viva Arena** | 🚧 Planned | Interactive oral exam prep simulator |

---

## 🚀 Quick Start

### Prerequisites
1. **Python 3.11+** installed ([python.org](https://python.org))
2. **Google Gemini API Key** (Free tier) — [Get one from Google AI Studio](https://aistudio.google.com/apikey)

### Option 1: One-Click Startup (Windows)
Double-click [`run.bat`](run.bat) or run in terminal:
```cmd
run.bat
```
*This automatically initializes the virtual environment, installs dependencies, verifies the environment, and launches the server.*

### Option 2: Manual Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/PrathamGandhiIT/LabMate.git
   cd "LAB MATE"
   ```

2. **Set up virtual environment**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   python -m pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   copy .env.example .env
   ```
   Open `.env` and set your API key:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   GEMINI_MODEL=gemini-3.6-flash
   ```

5. **Start the application**:
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser!

---

## ⚙️ Configuration

Settings are managed via Pydantic Settings in [`app/config.py`](app/config.py) and loaded from `.env`:

| Key | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(Required)* | Google Gemini API key from AI Studio |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Gemini model variant (`gemini-3.6-flash`, `gemini-2.5-flash`, etc.) |
| `GEMINI_TIMEOUT` | `120` | Request timeout in seconds |
| `APP_HOST` | `127.0.0.1` | Local host IP address |
| `APP_PORT` | `8000` | Port for the HTTP server |
| `APP_DEBUG` | `true` | Debug logging and hot-reload flag |
| `DATABASE_DIR` | `./data` | Directory for the SQLite database |

---

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────────┐
│                      Client Browser                       │
│     (Vanilla JS + CSS Design System + Jinja2 HTML)        │
└─────────────────────────────┬─────────────────────────────┘
                              │ HTTP / REST
┌─────────────────────────────▼─────────────────────────────┐
│                 FastAPI Application (ASGI)                │
│  ├── Routers: Dashboard, Practical Studio, Code Lab, Viva │
│  ├── Schemas: Pydantic v2 Request/Response Models         │
│  └── Services: PracticalService & GeminiService           │
└──────────────┬─────────────────────────────┬──────────────┘
               │                             │
┌──────────────▼─────────────┐ ┌─────────────▼──────────────┐
│       SQLite Database      │ │      Google Gemini API     │
│   (SQLAlchemy 2.0 ORM)     │ │   (gemini-3.6-flash Cloud) │
└────────────────────────────┘ └────────────────────────────┘
```

---

## 📁 Project Structure

```
LAB MATE/
├── app/
│   ├── main.py                 # FastAPI application & lifecycle entry
│   ├── config.py               # Pydantic configuration & env loader
│   ├── database.py             # SQLAlchemy models & SQLite session factory
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── routers/
│   │   ├── api.py              # Health check & AI status polling
│   │   ├── dashboard.py        # Dashboard view controller
│   │   └── practical.py        # Practical Studio generation & CRUD
│   ├── services/
│   │   ├── gemini_service.py   # Google GenAI client with concurrency lock
│   │   └── practical_service.py# AI prompt engineering & section parser
│   ├── static/
│   │   ├── css/style.css       # Complete modern CSS design tokens
│   │   └── js/app.js           # Vanilla JS helpers & status polling
│   └── templates/              # Jinja2 HTML layout & view templates
├── tests/
│   ├── conftest.py             # Pytest fixtures & mock AI services
│   ├── test_health.py          # Dashboard & health endpoint tests
│   └── test_practical.py       # Practical Studio CRUD & generation tests
├── .env.example                # Template for environment configuration
├── .gitignore                  # Git ignore rules (protects API keys)
├── requirements.txt            # Python dependencies
├── run.bat                     # Windows one-click startup script
└── README.md                   # Project documentation
```

---

## 🧪 Testing

The test suite runs with zero network dependencies using isolated mocks:

```bash
# Run all tests
venv\Scripts\python.exe -m pytest tests/ -v
```

```text
======================== 24 passed in 8.65s ========================
```

---

## 🛡️ Gemini API Rate Limits (Free Tier)

Google AI Studio provides a free tier suitable for student workloads:
- **15 Requests per Minute (RPM)**
- **1,500 Requests per Day (RPD)**
- **1,000,000 Tokens per Minute (TPM)**
- Concurrency bounded via `asyncio.Semaphore(2)` in `GeminiService` to prevent quota violations.

---

## 🗺️ Roadmap

- [x] Phase 1: Core Architecture, SQLite persistence, and UI Design System
- [x] Phase 2: Practical Studio with AI generation, live editing, and section regeneration
- [x] Phase 2.5: Google Gemini 3.6 Flash migration (zero local GPU overhead)
- [x] Phase 3: Code Lab — Code execution tracing, complexity visualizer, bug resolver & snippet library
- [ ] Phase 4: Viva Arena — Voice/text interactive oral viva interrogation
- [x] Phase 5: My Practicals Library, search/filtering, multi-format export & academic PDF/print journal

---

## 📄 License

This project is open-source under the [MIT License](LICENSE).

---

<div align="center">
  <sub>Developed with ❤️ for engineering students.</sub>
</div>
