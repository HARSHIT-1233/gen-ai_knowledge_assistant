# GenAI Knowledge & Research Assistant

A local, document-grounded AI research assistant. Upload PDF/TXT documents,
index them with local embeddings, and chat with a local LLM that can answer
questions grounded in your own knowledge base — with source references.

Everything runs locally through [Ollama](https://ollama.com). No paid APIs,
no cloud GPUs, no secrets.

- **Backend:** FastAPI (Python 3.12), JSON-file storage
- **Frontend:** Next.js App Router + React + TypeScript + Tailwind CSS
- **LLM:** `qwen2.5:1.5b` (configurable)
- **Embeddings:** `nomic-embed-text` (configurable)
- **Tests:** pytest

---

## Overview

The app has two chat modes:

- **General chat** — plain conversation with the local LLM. No documents needed.
- **Knowledge mode** — the question is embedded, the most similar document
  chunks are retrieved, and only those excerpts are given to the model as
  grounding context. The response returns the actual chunks that were used,
  so citations are real (never fabricated).

Documents and conversations are persisted as JSON files under `backend/data/`,
which is git-ignored.

---

## Architecture

```
frontend (Next.js, localhost:3000)
        |  fetch / FormData  (NEXT_PUBLIC_API_BASE_URL)
        v
backend (FastAPI, localhost:8000)  ──> Ollama (localhost:11434)
  ├── /api/v1/chat
  ├── /api/v1/documents      (upload / list / get / delete)
  ├── /api/v1/knowledge      (index / ask)
  └── /api/v1/conversations  (create / list / get / messages / delete)
        |
        v
backend/data/
  ├── ingested/<document_id>.json   (chunked document text)
  ├── conversations/<id>.json       (message history)
  └── vector_index.json             (chunk embeddings + metadata)
```

Key backend modules:

| Path | Responsibility |
| --- | --- |
| `backend/app/api/routes/` | HTTP routes (chat, documents, knowledge, conversations, health) |
| `backend/app/services/document_ingestion.py` | PDF/TXT extraction + chunking |
| `backend/app/services/knowledge.py` | Embedding, vector index, similarity search |
| `backend/app/services/ollama.py` | Ollama chat client |
| `backend/app/services/conversation_store.py` | Conversation persistence |
| `backend/app/schemas/` | Pydantic request/response models |

---

## Prerequisites

- **Python 3.12** (3.12.8 recommended)
- **Node.js 20+** and npm
- **Ollama** installed and running

---

## 1. Ollama setup

Install Ollama from https://ollama.com/download, then start it and pull the
two models:

```powershell
ollama serve                 # if not already running as a service
ollama pull qwen2.5:1.5b     # chat model
ollama pull nomic-embed-text # embedding model
```

Verify:

```powershell
ollama list
Invoke-WebRequest http://localhost:11434/api/tags -UseBasicParsing
```

---

## 2. Backend setup

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create your local environment file from the example and adjust if needed:

```powershell
Copy-Item .env.example .env
```

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- API root: http://localhost:8000
- Interactive docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## 3. Frontend setup

In a second terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local   # optional; defaults to http://localhost:8000
npm run dev
```

Open http://localhost:3000.

Production build:

```powershell
npm run build
npm run start
```

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `GenAI Knowledge & Research Assistant` | Display name |
| `APP_VERSION` | `0.1.0` | Version string |
| `ENVIRONMENT` | `development` | Environment label |
| `LOG_LEVEL` | `INFO` | Python log level |
| `API_V1_PREFIX` | `/api/v1` | API route prefix |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5:1.5b` | Chat model |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `KNOWLEDGE_SIMILARITY_THRESHOLD` | `0.35` | Minimum cosine similarity for a chunk to count as relevant |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Allowed browser origins (comma-separated) |

### Frontend (`frontend/.env.local`)

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend base URL (no `/api/v1` suffix) |

`NEXT_PUBLIC_API_URL` is also accepted as a fallback.

---

## API documentation

Base prefix: `/api/v1` (except `/` and `/health`).

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Health/version info |
| POST | `/api/v1/chat` | General chat (`{ "messages": [...] }`) |
| POST | `/api/v1/documents/upload` | Upload a PDF/TXT (`multipart/form-data`, field `file`) |
| GET | `/api/v1/documents` | List documents with chunk + indexing counts |
| GET | `/api/v1/documents/{document_id}` | Retrieve one stored document |
| DELETE | `/api/v1/documents/{document_id}` | Delete document **and** its vectors |
| POST | `/api/v1/knowledge/index/{document_id}` | Embed + index a document's chunks |
| POST | `/api/v1/knowledge/ask` | One-shot RAG question (`question`, `top_k`) |
| POST | `/api/v1/conversations` | Create a conversation (`title`) |
| GET | `/api/v1/conversations` | List conversations |
| GET | `/api/v1/conversations/{id}` | Get a conversation with messages |
| POST | `/api/v1/conversations/{id}/messages` | Send a message (`content`, `use_knowledge`) |
| DELETE | `/api/v1/conversations/{id}` | Delete a conversation |

---

## Running the tests

The backend suite uses temporary directories and mocks Ollama/embeddings, so
it never touches your real documents:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend checks:

```powershell
cd frontend
npx tsc --noEmit
npm run lint
npm run build
```

---

## Typical workflow

1. Start Ollama, then the backend, then the frontend.
2. Open http://localhost:3000.
3. Upload a PDF or TXT in the **Knowledge Library**.
4. Click **Index** on the document (status becomes "Indexed").
5. Create a chat, toggle **Knowledge mode** on, and ask a question about the
   document. The answer cites the retrieved chunks under **Sources used**.
6. Delete documents/conversations as needed; deleting a document also removes
   its vectors.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "Backend offline" in the header | Start the backend on port 8000; check `CORS_ORIGINS` matches the frontend origin. |
| 503 when chatting or indexing | Ollama is not running or the model is missing. Run `ollama serve` and `ollama pull qwen2.5:1.5b` / `ollama pull nomic-embed-text`. |
| 415 on upload | Only `.pdf` and `.txt` are supported. |
| 422 on upload | File is empty, exceeds 10 MiB, or a TXT file is not UTF-8. |
| Scanned PDF returns "No extractable text" | OCR is not supported; use a text-based PDF. |
| Knowledge answers say no relevant info | Lower `KNOWLEDGE_SIMILARITY_THRESHOLD`, re-index, or ask with closer wording. |
| `ResponseValidationError` on `/documents/...` | Fixed: route ordering + UUID validation; regression tests in `tests/test_documents.py`. |

---

## Known limitations

- **JSON storage, no concurrency control.** Documents, the vector index, and
  conversations are single JSON files written atomically via a temp file +
  rename. A single writer is assumed; simultaneous writes to the same file
  from multiple processes could race. Suitable for a single local user.
- **Vector search is a full scan** of `vector_index.json` using cosine
  similarity. Fine for hundreds of chunks; not designed for large corpora.
- **No OCR.** Image-only/scanned PDFs yield no text.
- **Conversation context is windowed** to the most recent 10 messages.
- **No authentication / multi-user support.** Intended for local use.
- **Uploads are limited to 10 MiB** per file.
- **Re-indexing replaces** a document's existing vectors; the same file
  uploaded multiple times is treated as multiple independent documents.
- **Retrieved document text is treated as untrusted** and is never allowed to
  override system instructions, but prompt-injection resistance of small local
  models is not guaranteed.
