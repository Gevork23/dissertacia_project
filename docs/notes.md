# Dissertation Project — Working Notes

This file is a living document for ideas, decisions, experiments, and thesis preparation.

---

## Project info

**Repository:** dissertacia_project  
**Type:** Master thesis + internal system for MFC  
**Topic (RU):**
Исследование и разработка методов интеллектуального анализа нормативно-правовых документов с автоматизированной генерацией тестовых материалов.

**Topic (EN):**
Research and development of intelligent analysis methods for regulatory documents with automated test generation.

---

## Goals

- Build a local system for:
  - document versioning
  - change detection
  - summarization (RAG)
  - quiz generation
- Use the system as:
  - real internal tool
  - experimental platform for thesis

---

## Architecture (draft)

- Backend: Django + DRF
- DB: PostgreSQL
- Vector DB: Qdrant
- NLP:
  - embeddings (sentence-transformers)
  - LLM (local or API)
  - LangGraph (agent orchestration)
- Deployment:
  - Docker Compose
  - Local network access

---

## Data pipeline (draft)

1. Upload document file
2. Extract text
3. Normalize text
4. Chunk into blocks
5. Store chunks in DB
6. Embed chunks
7. Index in Qdrant
8. Compare versions
9. Generate change summary
10. Generate quiz
11. User passes quiz

---

## Research part ideas

### Chunking strategies
- By paragraphs
- By legal structure (article / clause)
- Hybrid approach

### Diff strategies
- Raw text diff
- Chunk-based diff
- Semantic diff (optional)

### RAG evaluation
- Precision@k
- Human expert scoring

### Quiz quality
- correctness
- coverage of changes
- difficulty level

---

## Risks & constraints

- Legal sensitivity of documents
- No external legal DB integration
- Possible restriction on internet access
- Limited GPU / CPU

---

## Decisions log

| Date | Decision |
|------|----------|
| 2026-01-23 | Use local document versioning only |
| 2026-01-23 | Use Django + Qdrant |

---

## Thesis structure (draft)

1. Introduction
2. Analysis of existing solutions
3. Problem statement
4. System architecture
5. Document processing methods
6. Change detection methods
7. Test generation methods
8. Experiments and evaluation
9. Implementation details
10. Conclusion

---

## Commands cheat sheet (later)

(To be filled)

---

## Notes

- Always store document sources locally
- Prefer reproducible experiments
- Save dataset snapshots for thesis

---
