from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings

DEMO_DOCUMENT_TITLE_PREFIX = "DEMO МФЦ:"
DEFAULT_OLD_FILE = "old.txt"
DEFAULT_NEW_FILE = "new.txt"


class DemoCorpusError(ValueError):
    """Raised when the file-backed demo corpus is missing or invalid."""


@dataclass(frozen=True)
class DemoVersionSpec:
    version_number: int
    source_filename: str
    text: str


@dataclass(frozen=True)
class DemoDocumentSpec:
    pair_id: str
    title: str
    description: str
    scenario: str
    metadata: dict[str, Any]
    versions: tuple[DemoVersionSpec, DemoVersionSpec]


def get_default_demo_corpus_dir() -> Path:
    return Path(settings.PROJECT_DIR) / "data" / "demo_corpus"


def _load_metadata(pair_dir: Path) -> dict[str, Any]:
    metadata_path = pair_dir / "metadata.json"
    if not metadata_path.exists():
        raise DemoCorpusError(f"Missing metadata.json in {pair_dir}")

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise DemoCorpusError(
            f"Invalid metadata.json in {pair_dir}: {error}"
        ) from error

    if not isinstance(metadata, dict):
        raise DemoCorpusError(f"metadata.json must contain an object in {pair_dir}")

    return metadata


def _read_version_text(pair_dir: Path, filename: str) -> str:
    path = pair_dir / filename
    if not path.exists():
        raise DemoCorpusError(f"Missing version file: {path}")
    if path.suffix.lower() != ".txt":
        raise DemoCorpusError(
            f"Only TXT files are supported by the file-backed demo loader: {path}"
        )

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise DemoCorpusError(f"Version file is empty: {path}")
    return text


def _build_description(metadata: dict[str, Any]) -> str:
    parts = []
    pair_id = str(metadata.get("pair_id") or "").strip()
    scenario = str(metadata.get("scenario") or "").strip()
    demo_goal = str(metadata.get("demo_goal") or "").strip()
    document_type = str(metadata.get("document_type") or "").strip()

    if demo_goal:
        parts.append(demo_goal)
    if scenario:
        parts.append(f"Demo scenario: {scenario}.")
    if pair_id:
        parts.append(f"Demo pair id: {pair_id}.")
    if document_type:
        parts.append(f"Document type: {document_type}.")
    parts.append("Synthetic demo corpus document; not an evaluation annotation.")
    return "\n".join(parts)


def _load_pair_spec(pair_dir: Path) -> DemoDocumentSpec:
    metadata = _load_metadata(pair_dir)
    pair_id = str(metadata.get("pair_id") or pair_dir.name).strip()
    title = str(metadata.get("title") or pair_id).strip()
    scenario = str(metadata.get("scenario") or pair_id).strip()

    if not title.startswith(DEMO_DOCUMENT_TITLE_PREFIX):
        title = f"{DEMO_DOCUMENT_TITLE_PREFIX} {title}"

    old_file = str(metadata.get("old_file") or DEFAULT_OLD_FILE).strip()
    new_file = str(metadata.get("new_file") or DEFAULT_NEW_FILE).strip()

    old_text = _read_version_text(pair_dir, old_file)
    new_text = _read_version_text(pair_dir, new_file)

    return DemoDocumentSpec(
        pair_id=pair_id,
        title=title,
        description=_build_description(metadata),
        scenario=scenario,
        metadata=metadata,
        versions=(
            DemoVersionSpec(
                version_number=1,
                source_filename=f"{pair_id}_old.txt",
                text=old_text,
            ),
            DemoVersionSpec(
                version_number=2,
                source_filename=f"{pair_id}_new.txt",
                text=new_text,
            ),
        ),
    )


def load_demo_document_specs(
    corpus_dir: Path | str | None = None,
) -> tuple[DemoDocumentSpec, ...]:
    root = Path(corpus_dir) if corpus_dir else get_default_demo_corpus_dir()
    if not root.exists():
        raise DemoCorpusError(f"Demo corpus directory does not exist: {root}")

    pair_dirs = [item for item in sorted(root.iterdir()) if item.is_dir()]
    if not pair_dirs:
        raise DemoCorpusError(
            f"Demo corpus directory does not contain pair directories: {root}"
        )

    specs = tuple(_load_pair_spec(pair_dir) for pair_dir in pair_dirs)
    pair_ids = [spec.pair_id for spec in specs]
    duplicates = sorted(
        {pair_id for pair_id in pair_ids if pair_ids.count(pair_id) > 1}
    )
    if duplicates:
        raise DemoCorpusError(f"Duplicate demo pair ids: {', '.join(duplicates)}")

    return specs
