# 🎓 PNU Smart Educational Assistant

A **production-ready, RAG-based AI chat application** for university students (PNU). The system answers student questions grounded in uploaded course resources (PDFs), using a **Hybrid Expert Pedagogical RAG** approach — the LLM acts as an expert professor, solving problems step-by-step while citing the exact document chunks it used.

Built with a strict engineering mindset: **no vibe coding**. Clean architecture, SOLID principles, dependency injection, structured logging, and deliberate design patterns throughout.

---

## ✨ Key Features

### 🧠 Hybrid Expert Pedagogical RAG
- The LLM is prompted as an **expert University Professor**, solving problems step-by-step rather than strictly refusing when context is thin.
- **Zero-retrieval fallback:** if no chunks match, the model still answers from expertise and bridges the topic back to the course — never a dead-end error.
- **Query rewriting:** ambiguous follow-ups ("بیشتر توضیح بده") are rewritten into standalone vector queries using conversation memory.

### 📐 RTL KaTeX Engine (Bidi-Safe Math)
- A strictly isolated KaTeX/Markdown renderer that handles **bidirectional (Bidi) text and math formulas** correctly.
- Inline math (`$A$`) and block equations (`$$...$$`) are forced to LTR with `unicodeBidi: isolate` so Persian text and LaTeX never corrupt each other.
- **Interactive citation badges** map `[n]` references in the answer to the exact document chunk, with hover tooltips showing filename, page, and snippet.

### 🔄 Smart API Key Rotation (Round-Robin)
- Multiple Gemini API keys are rotated **proactively** before every request.
- A 429 marks the offending key as "burned" for a cooldown window; the same batch is immediately retried with the next available key.
- Exponential backoff when all keys are cooling — the system never hard-fails on rate limits.

### 💸 Token-Efficient Caching
- **LRU cache** for query embeddings (keyed by `(model, query)` hash) — repeated questions never re-bill.
- **Single-flight coalescing** — a burst of identical concurrent queries debounce to ONE upstream Gemini call.
- **OCR result cache** (keyed by SHA-256 of image bytes) — the same screenshot is only sent to the Vision model once.

### 🖼️ Multimodal Image Support
- Paste or upload a screenshot of an exam question.
- **Gemini OCR** extracts the text → drives the vector search → the raw image is also passed to the final generation call for visual analysis.
- OCR text is extracted **once** and reused for both the dynamic chat title and the RAG pipeline.

### 🛡️ Production Hardening
- **Per-user in-flight guard** — concurrent sends from the same user return HTTP 429 instead of corrupting conversation memory.
- **Structured logging** (`app/core/logging.py`) with rotating file handler.
- **Standardized exception handlers** — every error returns a consistent `{detail: str}` envelope.
- **Startup diagnostics banner** — DB, storage, cache, and key-count summary at boot (credentials masked).
- **Thread-safe ChromaDB singleton** — one persistent client for the process lifetime.
- **Connection pooling** — `pool_pre_ping`, `StaticPool` for SQLite, tunable pool for PostgreSQL/MySQL.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (React + Vite)                     │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────────┐  │
│  │  RTL UI     │  │  KaTeX Renderer  │  │  Citation Badges       │  │
│  │  (Persian)  │  │  (Bidi-safe)     │  │  (chunk tooltips)      │  │
│  └──────┬──────┘  └──────────────────┘  └────────────────────────┘  │
│         │  Axios (JWT interceptor, 401 → /login)                    │
└─────────┼───────────────────────────────────────────────────────────┘
          │  /api (Vite proxy → :8000)
┌─────────▼───────────────────────────────────────────────────────────┐
│                        Backend (FastAPI)                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  API Routers (auth, users, courses, chat, requests, admin)   │   │
│  │  • Standardized exception handlers                           │   │
│  │  • Per-user in-flight guard (429 on concurrent sends)        │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │  RAG Pipeline (services/)                                    │   │
│  │  Image → OCR → Title → Query Rewrite → Embed → Retrieve →    │   │
│  │  Generate (Professor-mode system prompt)                     │   │
│  │  • SmartKeyManager (round-robin + 429 cooldown)              │   │
│  │  • LRUCache + Singleflight (token savings)                   │   │
│  └──────┬──────────────────────────────┬────────────────────────┘   │
│         │                              │                            │
│  ┌──────▼──────────┐          ┌────────▼──────────┐                 │
│  │  SQLAlchemy     │          │  ChromaDB         │                 │
│  │  (SQLite/Postgres)         │  (persistent,     │                 │
│  │  users, courses, │         │   thread-safe     │                 │
│  │  chats, resources│         │   singleton)      │                 │
│  └─────────────────┘          └───────────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow (Student Question)

1. **Student** sends a message (text and/or image) in a course-scoped chat.
2. **OCR** (if image): Gemini extracts the text — cached by image hash.
3. **Title** (first message): dynamic Persian chat title generated from the prompt/OCR text.
4. **Query Rewrite**: ambiguous follow-ups expanded into standalone search queries.
5. **Embed**: query vector generated via the LRU-cached, single-flight-coalesced path.
6. **Retrieve**: top-k chunks from the course's ChromaDB collection (cosine similarity).
7. **Generate**: Gemini receives the professor-mode system prompt + retrieved chunks + conversation history + image (if any).
8. **Persist**: assistant message + citation sources stored; returned to the frontend with interactive citation badges.

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18 (Vite 6) + Tailwind CSS + react-markdown + KaTeX + Floating UI |
| **Backend** | Python 3.10–3.13 + FastAPI + Uvicorn |
| **Relational DB** | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy 2.0 |
| **Vector DB** | ChromaDB (persistent, local) |
| **AI / LLM** | Google Gemini (raw REST via `requests` — no SDK wrapper) |
| **Auth** | JWT (HS256) + bcrypt password hashing |
| **PDF Parsing** | PyMuPDF (RTL-aware text extraction) |

> **Note:** The codebase deliberately uses **raw `requests`** against the Gemini REST API instead of the LangChain/Google SDK. This gives full control over key rotation, per-request headers, and 429 handling — no hidden transport caching.

---

## 📁 Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (auth, users, courses, chat, requests, admin)
│   │   ├── core/           # logging, exceptions, security, deps
│   │   ├── models/         # SQLAlchemy models (User, Course, ChatSession, Resource, ...)
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # RAG pipeline (rag, chat_manager, embedding_manager,
│   │   │                   #   vector_store, document_service, conversation_memory,
│   │   │                   #   cache, llm_service, log_service)
│   │   ├── config.py       # Pydantic settings (env-driven)
│   │   ├── database.py     # Engine + session factory (pooled)
│   │   └── main.py         # App factory, migrations, startup diagnostics
│   ├── requirements.txt
│   ├── seed_admin.py       # Create initial admin + demo course
│   ├── reset_admin_password.py
│   └── run.py              # Uvicorn launcher
├── frontend/
│   ├── src/
│   │   ├── api/            # Axios client (JWT interceptor, 401 handling)
│   │   ├── components/     # Layout, ProtectedRoute, Spinner, MarkdownRenderer
│   │   ├── context/        # AuthContext, ThemeContext
│   │   ├── pages/          # Student + admin pages
│   │   └── utils/          # Shared helpers (chat.js)
│   ├── package.json
│   └── vite.config.js      # /api proxy → localhost:8000
└── chroma_db/              # ChromaDB persistence (gitignored)
```

---

## 🔐 Environment Variables (`.env`)

Copy `backend/.env.example` → `backend/.env` and fill in the values.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | `sqlite:///./pnu_assistant.db` | SQLAlchemy URL. Use `postgresql+psycopg2://...` for production. |
| `JWT_SECRET_KEY` | ✅ | `change-this...` | **Change in production** to a long random string. |
| `JWT_ALGORITHM` | — | `HS256` | JWT signing algorithm. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | — | `1440` | Token lifetime (minutes). |
| `GEMINI_API_KEY` | ✅ | — | Single key **or** comma/newline-separated list for multi-key round-robin. |
| `GEMINI_EMBEDDING_MODEL` | — | `models/gemini-embedding-2` | Embedding model. |
| `GEMINI_CHAT_MODEL` | — | `gemini-3.5-flash-lite` | RAG answer generation model. |
| `GEMINI_REWRITE_MODEL` | — | `gemini-3.5-flash-lite` | Query-rewrite + title model. |
| `GEMINI_OCR_MODEL` | — | `gemini-3.5-flash-lite` | Image OCR model. |
| `EMBEDDING_BATCH_SIZE` | — | `20` | Chunks per embedding API call. |
| `EMBEDDING_KEY_COOLDOWN` | — | `60` | Seconds a key is "burned" after a 429. |
| `EMBEDDING_BACKOFF_BASE` | — | `10.0` | Base delay (s) for exponential backoff. |
| `EMBEDDING_MAX_RETRIES` | — | `5` | Max retries per embedding batch. |
| `EMBEDDING_INTER_BATCH_DELAY` | — | `0.5` | Sleep (s) between batches to avoid RPM spikes. |
| `CACHE_ENABLED` | — | `true` | Master switch for LRU caches. |
| `EMBEDDING_CACHE_SIZE` | — | `512` | Max entries in the embedding LRU cache. |
| `OCR_CACHE_SIZE` | — | `128` | Max entries in the OCR LRU cache. |
| `CHROMA_PERSIST_DIR` | — | `./chroma_db` | ChromaDB persistence directory. |
| `UPLOAD_DIR` | — | `./uploads` | Uploaded PDF storage directory. |
| `CORS_ORIGINS` | — | `http://localhost:5173` | Comma-separated allowed origins. |
| `HOST` / `PORT` | — | `0.0.0.0` / `8000` | Server bind address. |

---

## 🚀 Local Setup & Run

### Prerequisites
- **Python 3.10–3.13** (ChromaDB does not yet ship wheels for Python 3.14 on Windows)
- **Node.js 18+** and npm
- A **Google Gemini API key** (or several for rotation)

### 1. Backend

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
# Then edit .env: set JWT_SECRET_KEY and GEMINI_API_KEY

# Create initial admin + demo course
python seed_admin.py

# Start the API server
python run.py
```

Backend runs at **http://localhost:8000** — interactive API docs at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend

npm install
npm run dev
```

Frontend runs at **http://localhost:5173** (Vite proxies `/api` → `localhost:8000`).

### 3. First Login

1. Open `http://localhost:5173`
2. Log in with the admin account created by `seed_admin.py`
3. Go to **Admin → Settings** → paste your Gemini API key(s) → save
4. Go to **Admin → Resources** → upload a course PDF → wait for status `ready`
5. Start chatting in the course!

---

## 🐳 Docker (Coming Soon)

Dockerfiles for the backend and frontend are planned. Until then, the manual setup above is fully supported. The backend is a standard FastAPI app (`uvicorn app.main:app`) and the frontend is a standard Vite build (`npm run build` → serve `dist/`).

---

## 🔧 Admin Capabilities

| Feature | Endpoint |
|---|---|
| Upload PDF → parse → embed | `POST /api/admin/resources/upload` |
| Reprocess a resource (background) | `POST /api/admin/resources/{id}/reprocess` |
| View/edit vector chunks | `GET/PUT /api/admin/resources/chunks/{chunk_id}` |
| Course CRUD | `GET/POST/PUT/DELETE /api/admin/courses` |
| User management | `GET/PATCH /api/admin/users` |
| Course request approval | `PATCH /api/admin/requests/{id}` |
| Gemini settings | `GET/PUT /api/admin/settings` |
| API usage monitoring | `GET /api/admin/api-usage` |
| System logs | `GET/DELETE /api/admin/logs` |
| Gemini model list + test connection | `GET /api/admin/gemini/models`, `POST /api/admin/gemini/test-connection` |

---

## 🧪 Testing

```bash
# Backend: compile-check all modules
cd backend
python -m py_compile app/main.py app/database.py app/config.py \
  app/core/logging.py app/core/exceptions.py \
  app/services/*.py app/api/*.py

# Frontend: production build
cd frontend
npm run build
```

---

## 📝 Notes

- All frontend UI text is in **Persian (Farsi)** with full **RTL** support (Vazirmatn font).
- Backend code/comments are in English; user-facing API error messages are localized in Persian.
- Uses bcrypt password hashing + JWT (HS256) authentication.
- SQLite database, uploaded PDFs, and ChromaDB persistence all live under `backend/` and are gitignored.
- The `SmartKeyManager` rotates keys **proactively** (before every batch) and tracks per-key cooldowns — adding more keys to `GEMINI_API_KEY` (comma-separated) instantly increases throughput.

---

## 📄 License

Private / internal project. All rights reserved.