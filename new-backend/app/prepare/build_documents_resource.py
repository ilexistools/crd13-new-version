from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = ROOT_DIR / "app" / "raw" / "new_organization"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "app" / "assets" / "resources" / "documents.json"


DOCUMENT_FIELDS = (
    "id",
    "type",
    "document_type",
    "reference",
    "year",
    "title",
    "label",
    "committee",
    "last_modified",
    "url",
    "processes",
)


def compact_section(section: dict[str, Any]) -> dict[str, Any]:
    pages = section.get("pages") or {}

    return {
        "section_title": section.get("title"),
        "section_page_start": pages.get("start"),
        "section_page_end": pages.get("end"),
    }


def compact_document(data: dict[str, Any]) -> dict[str, Any]:
    document = data.get("document") or {}
    compacted = {field: document.get(field) for field in DOCUMENT_FIELDS}
    compacted["commodities"] = data.get("commodities") or []
    compacted["sections"] = [
        compact_section(section)
        for section in data.get("sections") or []
        if isinstance(section, dict)
    ]

    return {"document": compacted}


def build_documents(input_dir: Path) -> list[dict[str, Any]]:
    documents = []

    for path in sorted(input_dir.glob("*.json")):
        with path.open(encoding="utf-8") as file:
            data = json.load(file)

        documents.append(compact_document(data))

    return documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a consolidated documents resource from app/raw/new_organization."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing source JSON files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output JSON path. Default: {DEFAULT_OUTPUT_PATH}",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    documents = build_documents(args.input_dir)
    output = {"documents": documents}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print(f"Wrote {len(documents)} documents to {args.output}")


if __name__ == "__main__":
    main()
