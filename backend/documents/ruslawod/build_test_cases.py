from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from documents.models import RusLawODDocument


def group_ruslawod_documents(
    documents: Iterable[RusLawODDocument],
) -> dict[str, list[RusLawODDocument]]:
    by_identifier: dict[str, list[RusLawODDocument]] = defaultdict(list)
    for document in documents:
        by_identifier[document.pravo_gov_ru_nd].append(document)

    if any(len(items) > 1 for items in by_identifier.values()):
        return by_identifier

    by_family_key: dict[str, list[RusLawODDocument]] = defaultdict(list)
    for document in documents:
        key = document.version_family_key or document.pravo_gov_ru_nd
        by_family_key[key].append(document)
    return by_family_key


def build_regression_pairs(
    *,
    limit: int = 50,
    output_path: str | Path,
    export_dir: str | Path,
) -> list[dict[str, object]]:
    documents = list(
        RusLawODDocument.objects.exclude(version_family_key="")
        .order_by("version_family_key", "document_date", "pravo_gov_ru_nd")
    )
    groups = group_ruslawod_documents(documents)
    output = Path(output_path)
    export_root = Path(export_dir)
    export_root.mkdir(parents=True, exist_ok=True)

    pairs: list[dict[str, object]] = []
    pair_index = 0
    for group_key, group_documents in groups.items():
        ordered_group = sorted(
            group_documents,
            key=lambda item: (
                item.document_date.isoformat() if item.document_date else "",
                item.pravo_gov_ru_nd,
            ),
        )
        if len(ordered_group) < 2:
            continue

        for old_document, new_document in zip(ordered_group, ordered_group[1:]):
            pair_index += 1
            pair_dir = export_root / f"pair_{pair_index:04d}"
            pair_dir.mkdir(parents=True, exist_ok=True)
            old_path = pair_dir / "old.txt"
            new_path = pair_dir / "new.txt"
            old_path.write_text(old_document.cleaned_text + "\n", encoding="utf-8")
            new_path.write_text(new_document.cleaned_text + "\n", encoding="utf-8")
            pairs.append(
                {
                    "id": f"ruslawod_pair_{pair_index:04d}",
                    "name": old_document.heading or old_document.pravo_gov_ru_nd,
                    "group_key": group_key,
                    "v1_document_id": old_document.id,
                    "v2_document_id": new_document.id,
                    "v1_path": str(old_path),
                    "v2_path": str(new_path),
                    "expected_significance_label": None,
                    "annotation_status": "pending",
                }
            )
            if len(pairs) >= limit:
                break
        if len(pairs) >= limit:
            break

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(pairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pairs
