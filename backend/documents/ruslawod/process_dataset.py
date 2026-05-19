from __future__ import annotations

from pathlib import Path

from documents.models import RusLawODDocument

from .data_loader import download_ruslawod, extract_metadata_and_text


def import_ruslawod_documents(
    *,
    cache_dir: str | Path | None = None,
    limit: int | None = None,
    force_download: bool = False,
) -> dict[str, int]:
    xml_paths = download_ruslawod(
        cache_dir=cache_dir,
        limit=limit,
        force=force_download,
    )
    created = 0
    updated = 0

    for xml_path in xml_paths:
        payload = extract_metadata_and_text(xml_path)
        if not payload.get("cleaned_text", "").strip():
            print(f"Warning: No text in {xml_path.name}, skipping.")
            continue
        _, was_created = RusLawODDocument.objects.update_or_create(
            pravo_gov_ru_nd=payload["pravo_gov_ru_nd"],
            defaults=payload,
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return {
        "processed": len(xml_paths),
        "created": created,
        "updated": updated,
    }
