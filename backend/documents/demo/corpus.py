from __future__ import annotations

from .file_corpus import (
    DemoCorpusError,
    DemoDocumentSpec,
    DemoVersionSpec,
    get_default_demo_corpus_dir,
    load_demo_document_specs,
)

try:
    DEMO_DOCUMENTS = load_demo_document_specs()
except DemoCorpusError:
    DEMO_DOCUMENTS: tuple[DemoDocumentSpec, ...] = ()

__all__ = [
    "DEMO_DOCUMENTS",
    "DemoCorpusError",
    "DemoDocumentSpec",
    "DemoVersionSpec",
    "get_default_demo_corpus_dir",
    "load_demo_document_specs",
]
