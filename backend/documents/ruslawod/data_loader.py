from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_DIR = Path("D:/dataset/RusLawOD/cache")
DEFAULT_XML_DIR = DEFAULT_CACHE_DIR / "xml"
DATASET_NAME = "irlspbru/RusLawOD"


def clean_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(clean_text(str(item)) for item in value if str(item).strip())
    return str(value)


def _append_value_node(parent: ET.Element, tag: str, value: Any) -> None:
    text = _safe_text(value)
    if not text:
        return
    node = ET.SubElement(parent, tag)
    if tag == "headingIPS":
        node.text = text
        return
    node.set("val", text)


def build_version_family_key(
    *,
    heading: str,
    issued_by: str = "",
    doc_number: str = "",
    doc_type: str = "",
) -> str:
    parts = [
        clean_text(doc_type).lower(),
        clean_text(issued_by).lower(),
        clean_text(doc_number).lower(),
        clean_text(heading).lower(),
    ]
    key = " | ".join(part for part in parts if part)
    return key[:255]


def row_to_xml_string(row: dict[str, Any]) -> str:
    root = ET.Element("act")
    meta = ET.SubElement(root, "meta")
    identification = ET.SubElement(meta, "identification")
    classification = ET.SubElement(meta, "classification")
    body = ET.SubElement(root, "text")
    keywords = ET.SubElement(root, "keywords")
    reference = ET.SubElement(root, "reference")

    for tag in (
        "pravogovruNd",
        "issuedByIPS",
        "doc_typeIPS",
        "doc_author_normal_formIPS",
        "docdateIPS",
        "docNumberIPS",
        "headingIPS",
        "signedIPS",
        "statusIPS",
        "actual_datetimeIPS",
        "actual_datetime_humanIPS",
        "is_widely_used",
    ):
        _append_value_node(identification, tag, row.get(tag))

    text_node = ET.SubElement(body, "textIPS")
    text_node.text = _safe_text(row.get("textIPS"))
    tagged_node = ET.SubElement(body, "taggedtextIPS")
    tagged_node.text = _safe_text(row.get("taggedtextIPS") or row.get("taggedtextips"))

    _append_value_node(classification, "classifierByIPS", row.get("classifierByIPS"))
    _append_value_node(keywords, "keywordsByIPS", row.get("keywordsByIPS"))
    _append_value_node(reference, "classifierByIPS", row.get("classifierByIPS"))

    return ET.tostring(root, encoding="unicode")


def _parse_iso_date(raw_value: str) -> date | None:
    normalized = clean_text(raw_value)
    if not normalized:
        return None
    for candidate in (normalized, ".".join(reversed(normalized.split(".")))):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            continue
    day, dot, remainder = normalized.partition(".")
    if dot and remainder.count(".") == 1:
        month, _, year = remainder.partition(".")
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            return None
    return None


def _node_value(root: ET.Element, tag: str) -> str:
    node = root.find(f".//{tag}")
    if node is None:
        return ""
    if "val" in node.attrib:
        return clean_text(node.attrib.get("val", ""))
    return clean_text("".join(node.itertext()))


def extract_metadata_and_text(xml_path: str | Path) -> dict[str, Any]:
    path = Path(xml_path)
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    heading = _node_value(root, "headingIPS")
    issued_by = _node_value(root, "issuedByIPS")
    doc_number = _node_value(root, "docNumberIPS")
    doc_type = _node_value(root, "doc_typeIPS")
    text_node = root.find(".//textIPS")
    cleaned = clean_text("".join(text_node.itertext()) if text_node is not None else "")
    pravo_gov_ru_nd = _node_value(root, "pravogovruNd")

    return {
        "pravo_gov_ru_nd": pravo_gov_ru_nd,
        "heading": heading,
        "document_date": _parse_iso_date(_node_value(root, "docdateIPS")),
        "cleaned_text": cleaned,
        "source_xml": path.read_text(encoding="utf-8"),
        "version_family_key": build_version_family_key(
            heading=heading,
            issued_by=issued_by,
            doc_number=doc_number,
            doc_type=doc_type,
        ),
        "metadata": {
            "issued_by": issued_by,
            "doc_number": doc_number,
            "doc_type": doc_type,
            "signed_by": _node_value(root, "signedIPS"),
            "status": _node_value(root, "statusIPS"),
            "classifier": _node_value(root, "classifierByIPS"),
            "keywords": _node_value(root, "keywordsByIPS"),
        },
    }


def download_ruslawod(
    *,
    cache_dir: str | Path | None = None,
    limit: int | None = None,
    force: bool = False,
) -> list[Path]:
    from datasets import load_dataset
    from tqdm import tqdm

    base_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
    xml_dir = base_dir / "xml"
    xml_dir.mkdir(parents=True, exist_ok=True)

    existing_paths = sorted(xml_dir.glob("*.xml"))
    if existing_paths and not force:
        return existing_paths[:limit] if limit else existing_paths

    dataset = load_dataset(DATASET_NAME, split="train", streaming=True, cache_dir=str(base_dir / "hf"))
    xml_paths: list[Path] = []
    total = 0
    iterator = dataset
    progress = tqdm(iterator, desc="Downloading RusLawOD", unit="doc")
    for row in progress:
        pravo_gov_ru_nd = clean_text(str(row.get("pravogovruNd") or ""))
        if not pravo_gov_ru_nd:
            continue
        xml_path = xml_dir / f"{pravo_gov_ru_nd}.xml"
        if force or not xml_path.exists():
            xml_path.write_text(row_to_xml_string(dict(row)), encoding="utf-8")
        xml_paths.append(xml_path)
        total += 1
        if limit and total >= limit:
            break

    manifest_path = base_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "dataset": DATASET_NAME,
                "count": len(xml_paths),
                "xml_dir": str(xml_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return xml_paths
