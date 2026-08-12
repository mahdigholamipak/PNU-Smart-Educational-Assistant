# PNU Smart Educational Assistant 🎓

A production-ready RAG-based AI chat application for university students (PNU). The system answers student questions strictly based on uploaded course resources (PDFs), using retrieval-augmented generation to mitigate AI hallucinations.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React.js (Vite) + Tailwind CSS (Persian RTL UI) |
| Backend | Python + FastAPI |
| Relational DB | SQLite + SQLAlchemy |
| Vector DB | ChromaDB (Local) |
| AI / LLM | Google Gemini (LangChain integration) |

## Features

### Student
- Register / Login (JWT authentication)
- Profile editing + password change
- Course selection to scope chat context
- RAG-based chat grounded in course materials
- Chat history (view, continue, delete)
- Course request submission

### Admin
- Secure admin dashboard
- Resource management: upload PDFs → parse → embed into ChromaDB
- Course management (create, activate/deactivate, delete)
- User management (activate/deactivate, change role)
- Course request approval/rejection (auto-creates course on approval)
- Gemini API key & model settings management

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (auth, users, courses, chat, requests, admin)
│   │   ├── core/         # JWT security + auth dependencies
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # RAG pipeline (vector store, LLM, document parsing)
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── requirements.txt
│   ├── seed_admin.py     # Create initial admin + demo course
│   └── run.py            # uvicorn launcher
└── frontend/
    ├── src/
    │   ├── api/          # Axios client with JWT interceptor
    │   ├── components/   # Layout, ProtectedRoute, Spinner
    │   ├── context/      # AuthContext
    │   └── pages/        # All pages (student + admin)
    └── ...config files
```

---

## Setup & Run

### 1. Backend

> **Requires Python 3.10–3.13** (ChromaDB does not yet ship wheels for Python 3.14 on Windows).

```bash
cd backend

# Create virtual environment (optional but recommended)
py -3.13 -m venv venv           # Windows (use your installed 3.x version)
venv\Scripts\activate           # Windows
source venv/bin/activate        # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/macOS
# Then edit .env: set JWT_SECRET_KEY and optionally GEMINI_API_KEY

# Create initial admin + demo course
python seed_admin.py

# Start the API server
python run.py
```

Backend runs at **http://localhost:8000** — API docs at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend

npm install
npm run dev
```

Frontend runs at **http://localhost:5173** (Vite proxies `/api` → `localhost:8000`).

---

## RAG Pipeline

1. **Ingestion:** Admin uploads a PDF → backend extracts text → splits into overlapping chunks → embeds via Gemini → stores in a **ChromaDB collection scoped to the course**.
2. **Query:** Student sends a message in a course-scoped chat → query is embedded → top-k similar chunks retrieved from **that course only** → chunks injected into a strict system prompt ("answer ONLY from provided context; if unknown, say so") → Gemini returns the answer with cited source filenames.
3. **Transparency:** Each assistant message persists its cited sources (filename + chunk + score) and displays them in the UI.

## Gemini API Key

Two ways to configure:

1. **Environment variable** in `backend/.env`:
   ```
   GEMINI_API_KEY=your_key_here
   ```
2. **Admin Settings page** (`/admin/settings`) — stored in the `settings` table. The admin UI takes precedence at runtime for both the chat model and embedding model.

## Default Admin

Run `python seed_admin.py` and follow the prompts. You'll create an admin account and a demo course automatically.

---

## Notes

- All frontend UI text is in **Persian (Farsi)** with full **RTL** support (Vazirmatn font).
- Backend code/comments are in English; user-facing API error messages are localized in Persian.
- Uses bcrypt password hashing + JWT (HS256) authentication.
- SQLite database, uploaded PDFs, and ChromaDB persistence all live under `backend/` and are gitignored.