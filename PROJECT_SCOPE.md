# Dissertation Project — Scope

## Title (RU)
Исследование и разработка методов интеллектуального анализа нормативно-правовых документов с автоматизированной генерацией тестовых материалов.

## Title (EN)
Research and development of intelligent analysis methods for regulatory documents with automated generation of training/assessment tests.

## Goal
Build a local web system that stores versions of regulatory documents, detects changes between versions, produces concise summaries, and generates quizzes for staff knowledge assessment.

## Users & Roles
- **Admin**: uploads documents/versions, generates tests, views statistics.
- **Employee**: reads summaries/changes, takes tests, views own results.

## Inputs
- Local files stored on a workstation/server.
- Supported formats for MVP: **DOCX, TXT**
- Later (optional): PDF (text-based first; OCR later).

## Core Features (MVP)
1. Upload a document and create a new version.
2. Extract text from files.
3. Split text into structured chunks (by sections/articles/clauses; fallback to paragraphs).
4. Store metadata and full text in relational DB (PostgreSQL).
5. Create embeddings and index chunks in **Qdrant**.
6. Search/Q&A over documents using **RAG** with source citations.
7. Compare two versions and list changes (added/removed/modified chunks).
8. Generate a short “what changed” briefing.
9. Generate a quiz based on the changes (at least: single-choice + true/false).
10. Save quiz attempts and show results.

## Non-goals (MVP)
- No external legal database integration (ConsultantPlus/Garant).
- No automatic monitoring of online updates.
- No OCR for scanned PDFs in MVP.
- No complex HR/LMS integration.

## Success Criteria
- A user can complete the full flow: upload → index → view changes → generate quiz → take quiz → see results.
- Answers/summaries include citations to document fragments.
- The system runs on one machine and is accessible in local network via browser.

## Tech Stack (planned)
- Backend: Django + Django REST Framework
- DB: PostgreSQL
- Vector DB: Qdrant (Docker)
- NLP/RAG: embeddings + LLM (local or API), LangGraph for orchestration
- Frontend: simple web UI (server-rendered or separate SPA; MVP can be minimal)

## Deliverables
- Working local web application (Docker Compose)
- Documentation: setup guide + user guide
- Thesis materials: architecture, experiments, results tables/plots
