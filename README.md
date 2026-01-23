# dissertacia_project

Local web system for intelligent analysis of regulatory documents: version tracking, change detection, summarization (RAG), and automated quiz generation for staff assessment.

> RU: Локальный веб-сервис для интеллектуального анализа НПА/локальных актов: версионность, выявление изменений, выжимка (RAG) и генерация тестов для сотрудников.

---

## Project scope
Detailed scope and requirements: **[PROJECT_SCOPE.md](./PROJECT_SCOPE.md)**

---

## What this project does (MVP)
- Upload local documents (DOCX/TXT; PDF later)
- Store document versions
- Extract text and split into structured chunks
- Index chunks in Qdrant (vector DB)
- RAG-based Q&A and summaries with citations
- Compare versions and generate “what changed”
- Generate quizzes based on changes (single-choice + true/false)
- Save attempts and show results/statistics

## What it does NOT do (MVP)
- No integration with external legal databases (ConsultantPlus/Garant)
- No internet monitoring of document updates
- No OCR for scanned PDFs (optional later)

---

## Roadmap (we implement step by step)
### Stage 0 — Planning
- [x] Create project scope (`PROJECT_SCOPE.md`)
- [x] Create ERD schema (`ERD.md`)
- [x] Create tasks list (`TASKS.md`)

### Stage 1 — Infrastructure
- [ ] Docker Compose: PostgreSQL + Qdrant + Backend
- [ ] Backend skeleton (Django + DRF)
- [ ] File storage (media)

### Stage 2 — Documents & versions
- [ ] Models: Document / Version / Chunk
- [ ] Upload endpoints
- [ ] Text extraction (DOCX/TXT)
- [ ] Chunking (structure-aware + fallback)

### Stage 3 — Vector search & RAG
- [ ] Embeddings
- [ ] Index in Qdrant
- [ ] Search API
- [ ] RAG answer with citations

### Stage 4 — Changes & quizzes
- [ ] Version diff (by chunks)
- [ ] “What changed” summary
- [ ] Quiz generation from changes
- [ ] Attempts + scoring + statistics

### Stage 5 — UI
- [ ] Minimal web UI (local network)
- [ ] Auth + roles
- [ ] Admin: docs/tests management
- [ ] Employee: read + take quiz

---

## Repository structure (planned)
/backend # Django + DRF
/infra # docker-compose, configs
/docs # thesis notes, diagrams, experiments


---

## License
Private / for thesis (update later if needed).
