from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = ROOT_DIR / "app" / "raw" / "new_organization"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "app" / "assets" / "resources" / "sentences.json"


def parse_page(value: Any) -> int | None:
    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.isdigit():
        return int(value)

    return None


def page_range(
    sentence: dict[str, Any], section: dict[str, Any]
) -> tuple[int | None, int | None]:
    source = sentence.get("source") or {}
    source_pages = [
        page
        for page in (parse_page(value) for value in source.get("pages") or [])
        if page is not None
    ]

    if source_pages:
        return min(source_pages), max(source_pages)

    source_page = parse_page(source.get("page"))
    if source_page is not None:
        return source_page, source_page

    section_pages = section.get("pages") or {}
    return parse_page(section_pages.get("start")), parse_page(section_pages.get("end"))


def commodity_names(commodities: list[Any]) -> list[str]:
    return [
        commodity.get("name")
        for commodity in commodities
        if isinstance(commodity, dict) and commodity.get("name")
    ]


def sentence_text(sentence: dict[str, Any]) -> str:
    classification = sentence.get("classification") or {}
    return classification.get("sentence") or sentence.get("original") or sentence.get("rewrite") or ""


def compact_sentence(
    document: dict[str, Any],
    commodities: list[str],
    section: dict[str, Any],
    sentence: dict[str, Any],
) -> dict[str, Any]:
    classification = sentence.get("classification") or {}
    source = sentence.get("source") or {}
    page_start, page_end = page_range(sentence, section)

    return {
        "document_id": document.get("id"),
        "type": document.get("type"),
        "commodities": commodities,
        "section_title": source.get("section_title") or section.get("title") or "",
        "page_start": page_start,
        "page_end": page_end,
        "sentence": sentence_text(sentence),
        "category": classification.get("category") or sentence.get("category") or "",
        "modality": classification.get("modality") or sentence.get("modality") or "",
        "function": classification.get("function") or sentence.get("function") or "",
    }


def is_productive_sentence(sentence: dict[str, Any]) -> bool:
    classification = sentence.get("classification") or {}
    category = classification.get("category") or sentence.get("category") or ""
    return category != "discarded_by_prefilter"


def iter_sentences(input_dir: Path):
    for path in sorted(input_dir.glob("*.json")):
        with path.open(encoding="utf-8") as file:
            data = json.load(file)

        document = data.get("document") or {}
        commodities = commodity_names(data.get("commodities") or [])

        for section in data.get("sections") or []:
            if not isinstance(section, dict):
                continue

            for sentence in section.get("sentences") or []:
                if isinstance(sentence, dict) and is_productive_sentence(sentence):
                    yield compact_sentence(document, commodities, section, sentence)


def write_sentences(input_dir: Path, output_path: Path) -> int:
    count = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        file.write('{\n  "sentences": [\n')

        for sentence in iter_sentences(input_dir):
            if count:
                file.write(",\n")

            sentence = {"sentence_id": count + 1, **sentence}
            encoded = json.dumps(sentence, ensure_ascii=False, indent=4)
            file.write("    " + encoded.replace("\n", "\n    "))
            count += 1

        file.write("\n  ]\n}\n")

    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a consolidated sentences resource from app/raw/new_organization."
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
    count = write_sentences(args.input_dir, args.output)
    print(f"Wrote {count} sentences to {args.output}")


if __name__ == "__main__":
    main()
