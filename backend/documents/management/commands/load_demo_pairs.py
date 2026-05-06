from __future__ import annotations

from .load_demo_corpus import Command as LoadDemoCorpusCommand


class Command(LoadDemoCorpusCommand):
    help = (
        "Compatibility alias for load_demo_corpus. "
        "Loads the file-backed Phase 12 demo corpus."
    )
