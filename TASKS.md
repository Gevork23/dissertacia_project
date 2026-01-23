# TASKS — Dissertation Project (MVP → Defense)

Этот файл — список задач проекта. Мы двигаемся сверху вниз.
Формат статусов:
- [ ] todo
- [x] done

---

## Stage 0 — Planning & Repo
- [x] Create `PROJECT_SCOPE.md`
- [x] Create `README.md`
- [x] Create `ERD.md`
- [ ] Add `.gitignore` (Python + Django + env + media)
- [ ] Add `LICENSE` (temporary: Private/Thesis or MIT later)
- [ ] Create `/docs` folder and add `docs/notes.md`

---

## Stage 1 — Infrastructure (Docker)
- [ ] Create `docker-compose.yml` for: postgres + qdrant + backend
- [ ] Create `infra/.env.example` (DB creds, secret key, ports)
- [ ] Add `Makefile` (optional) with shortcuts: up/down/logs/migrate
- [ ] Verify:
  - [ ] Postgres is reachable
  - [ ] Qdrant is reachable (web UI or health endpoint)
  - [ ] Backend container starts

---

## Stage 2 — Backend skeleton (Django + DRF)
- [ ] Create Django project (`backend/`)
- [ ] Install dependencies (Django, DRF, psycopg, etc.)
- [ ] Configure settings for Docker (DB, allowed hosts, media)
- [ ] Create base app `core` (or `documents`)
- [ ] Add Django admin
- [ ] Add health endpoint `/api/health`

---

## Stage 3 — Data models & migrations
- [ ] Implement models:
  - [ ] Document
  - [ ] DocumentVersion
  - [ ] Chunk
  - [ ] Test
  - [ ] Question
  - [ ] Choice
  - [ ] Attempt
  - [ ] Answer
- [ ] Create and apply migrations
- [ ] Register models in Django Admin
- [ ] Create superuser

---

## Stage 4 — File upload & text extraction
- [ ] Endpoint: create Document
- [ ] Endpoint: upload DocumentVersion (file)
- [ ] Save uploaded file to `/media`
- [ ] Extract text from:
  - [ ] DOCX
  - [ ] TXT
- [ ] Store `extracted_text` in DocumentVersion

---

## Stage 5 — Chunking (split into blocks)
- [ ] Implement normalizer (spaces, hyphens, newlines)
- [ ] Implement chunking:
  - [ ] Structure-aware (sections/articles/clauses heuristics)
  - [ ] Fallback: paragraphs
- [ ] Create chunks in DB after upload
- [ ] Add basic tests for chunking

---

## Stage 6 — Embeddings & Qdrant indexing
- [ ] Choose embeddings method (local sentence-transformers for MVP)
- [ ] Add Qdrant client integration
- [ ] Create Qdrant collection on startup (if missing)
- [ ] Index chunks in Qdrant (point_id = chunk_id)
- [ ] Endpoint: `/api/search` (top-k chunks + metadata)

---

## Stage 7 — RAG (Q&A + summaries)
- [ ] Endpoint: `/api/chat`
  - [ ] Retrieve top-k chunks
  - [ ] Build context
  - [ ] Generate answer via LLM
  - [ ] Return citations (chunk ids + quotes)
- [ ] Endpoint: `/api/summarize` (summary of a document/version)

> Note: LLM mode decision:
> - local (Ollama/vLLM) OR
> - API (if allowed)

---

## Stage 8 — Version diff & “what changed”
- [ ] Implement diff between versions:
  - [ ] quick text diff (fallback)
  - [ ] chunk-based diff (main)
- [ ] Endpoint: `/api/compare` (from_version, to_version)
- [ ] Generate “what changed” briefing via LLM
- [ ] (Optional) persist VersionComparison + VersionChangeItem

---

## Stage 9 — Quiz generation & passing
- [ ] Generate quiz from changes:
  - [ ] question types: single_choice, true_false
  - [ ] store correct answers
  - [ ] store question sources (chunk citations)
- [ ] Publish quiz
- [ ] Employee can take quiz:
  - [ ] create Attempt
  - [ ] submit answers
  - [ ] compute score
  - [ ] show results

---

## Stage 10 — UI (local web)
- [ ] Minimal UI pages:
  - [ ] Login
  - [ ] Documents list
  - [ ] Upload version
  - [ ] View changes
  - [ ] Generate quiz
  - [ ] Take quiz
  - [ ] Results
- [ ] Roles/permissions (admin vs employee)
- [ ] Basic statistics dashboard

---

## Stage 11 — Defense packaging (thesis materials)
- [ ] Architecture diagram
- [ ] Experiments plan:
  - [ ] chunking strategies
  - [ ] retrieval quality
  - [ ] quiz quality
- [ ] Metrics & tables
- [ ] User manual (install/run/use)
- [ ] Results section + conclusions
