from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_PATH = ROOT_DIR / "app" / "assets" / "resources" / "provisions.json"
DEFAULT_OUTPUT_PATH = (
    ROOT_DIR / "app" / "assets" / "resources" / "provisions_index_documents.json"
)

_SPACE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return _SPACE.sub(" ", value.strip())


def normalize_commodity(value: str) -> str:
    return normalize_text(value).lower()


def load_provisions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, dict):
        data = data.get("provisions") or data.get("sentences") or data.get("results")

    if not isinstance(data, list):
        raise ValueError(f"Expected a list of provisions in {path}")

    return [item for item in data if isinstance(item, dict)]


def provision_id(provision: dict[str, Any]) -> str:
    value = provision.get("sentence_id") or provision.get("id")
    if value is not None:
        return str(value)
    return normalize_text(str(provision.get("sentence", "")))


def build_metadata(provision: dict[str, Any], unit: str, unit_index: int) -> dict[str, Any]:
    commodities = [
        commodity
        for commodity in provision.get("commodities", [])
        if isinstance(commodity, str) and commodity.strip()
    ]

    return {
        "provision_id": provision_id(provision),
        "sentence_id": provision.get("sentence_id"),
        "document_id": provision.get("document_id"),
        "type": provision.get("type"),
        "commodities": commodities,
        "normalized_commodities": [normalize_commodity(commodity) for commodity in commodities],
        "section_title": provision.get("section_title"),
        "page_start": provision.get("page_start"),
        "page_end": provision.get("page_end"),
        "sentence": provision.get("sentence"),
        "category": provision.get("category"),
        "modality": provision.get("modality"),
        "function": provision.get("function"),
        "unit_index": unit_index,
        "unit": unit,
    }


def build_index_documents(provisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for provision in provisions:
        units = provision.get("units") or []
        if not isinstance(units, list):
            continue

        pid = provision_id(provision)
        for unit_index, raw_unit in enumerate(units):
            if not isinstance(raw_unit, str):
                continue

            unit = normalize_text(raw_unit)
            if not unit:
                continue

            dedupe_key = (pid, unit)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            documents.append(
                {
                    "id": f"{pid}#unit-{unit_index}",
                    "text": unit,
                    "metadata": build_metadata(provision, unit, unit_index),
                }
            )

    return documents


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create unit-level JSON documents ready for provisions RAG indexing."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"Input provisions JSON. Default: {DEFAULT_INPUT_PATH}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output index documents JSON. Default: {DEFAULT_OUTPUT_PATH}",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    provisions = load_provisions(args.input)
    documents = build_index_documents(provisions)
    write_json(args.output, documents)

    print(f"Read provisions: {len(provisions)}")
    print(f"Wrote index documents: {len(documents)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
