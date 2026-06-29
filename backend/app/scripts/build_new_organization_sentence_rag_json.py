from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, NamedTuple


DEFAULT_INPUT_DIR = Path(__file__).resolve().parents[1] / "assets" / "resources" / "new_organization"
DEFAULT_OUTPUT_FILE = Path(__file__).resolve().parents[1] / "assets" / "resources" / "new_organization_sentence_rag.json"

_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ0-9“\"'(\[])")
_WS = re.compile(r"\s+")


class SectionCandidate(NamedTuple):
    section: dict[str, Any]
    normalized_texts: tuple[str, ...]


def normalize_ws(text: str) -> str:
    return _WS.sub(" ", text or "").strip()


def normalize_for_match(text: str) -> str:
    text = normalize_ws(text).casefold()
    text = re.sub(r"\s+", "", text)
    return text


def split_sentences(text: str) -> list[str]:
    text = normalize_ws(text)
    if not text:
        return []
    return [sent.strip() for sent in _SENT_SPLIT.split(text) if sent.strip()]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def commodity_metadata(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    names: list[str] = []
    terms: list[str] = []

    for commodity in data.get("commodities") or []:
        if not isinstance(commodity, dict):
            continue
        name = normalize_ws(str(commodity.get("name") or ""))
        if name and name not in names:
            names.append(name)

        for term in commodity.get("terms") or []:
            term_text = normalize_ws(str(term or ""))
            if term_text and term_text not in terms:
                terms.append(term_text)

    return names, terms


def section_title(section: dict[str, Any]) -> str:
    path_titles = [
        normalize_ws(str(title or ""))
        for title in section.get("path_titles") or []
        if normalize_ws(str(title or ""))
    ]
    if path_titles:
        return " > ".join(path_titles)
    return normalize_ws(str(section.get("title") or ""))


def page_bounds(section: dict[str, Any]) -> tuple[Any, Any]:
    pages = section.get("pages") or {}
    return pages.get("start") or "", pages.get("end") or ""


def build_section_candidates(sections: list[dict[str, Any]]) -> list[SectionCandidate]:
    candidates: list[SectionCandidate] = []
    for section in sections:
        section_texts = [str(section.get("text") or "")]
        section_texts.extend(str(span.get("text") or "") for span in section.get("page_spans") or [])

        normalized_texts = tuple(
            normalized
            for text in section_texts
            if (normalized := normalize_for_match(text))
        )
        if normalized_texts:
            candidates.append(SectionCandidate(section=section, normalized_texts=normalized_texts))

    return candidates


def find_section_for_sentence(
    sentence: str,
    candidates: list[SectionCandidate],
) -> dict[str, Any] | None:
    sentence_key = normalize_for_match(sentence)
    if not sentence_key:
        return None

    for candidate in candidates:
        for section_text in candidate.normalized_texts:
            if sentence_key in section_text:
                return candidate.section

    return None


def sentence_text(sentence_obj: dict[str, Any]) -> str:
    classification = sentence_obj.get("classification") or {}
    return normalize_ws(
        str(
            sentence_obj.get("original")
            or classification.get("sentence")
            or sentence_obj.get("rewrite")
            or ""
        )
    )


def sentence_modality(sentence_obj: dict[str, Any]) -> str:
    classification = sentence_obj.get("classification") or {}
    value = classification.get("modality")
    if value is None or value == "":
        value = sentence_obj.get("modality")
    return "" if value is None else normalize_ws(str(value))


def sentence_function(sentence_obj: dict[str, Any]) -> str:
    classification = sentence_obj.get("classification") or {}
    value = classification.get("function")
    if value is None or value == "":
        value = sentence_obj.get("function")
    return "" if value is None else normalize_ws(str(value))


def embedding_text(sentence: str, section_name: str, include_section_title: bool) -> str:
    if include_section_title and section_name:
        return f"{section_name}\n{sentence}"
    return sentence


def make_item(
    *,
    sentence: str,
    document_id: str,
    section: dict[str, Any] | None,
    modality: str,
    function: str,
    commodities: list[str],
    commodity_terms: list[str],
    include_section_title: bool,
) -> dict[str, Any]:
    section_name = section_title(section or {})
    page_start, page_end = page_bounds(section or {})

    return {
        "text": embedding_text(sentence, section_name, include_section_title),
        "metadata": {
            "document_id": document_id,
            "section_title": section_name,
            "page_start": page_start,
            "page_end": page_end,
            "sentence": sentence,
            "modality": modality,
            "function": function,
            "commodities": commodities,
            "commodity_terms": commodity_terms,
        },
    }


def extract_structured_items(
    data: dict[str, Any],
    *,
    include_section_title: bool,
) -> tuple[list[dict[str, Any]], Counter]:
    document = data.get("document") or {}
    document_id = normalize_ws(str(document.get("id") or ""))
    commodities, commodity_terms = commodity_metadata(data)
    sections = data.get("sections") or []
    candidates = build_section_candidates(sections)
    stats: Counter = Counter()
    items: list[dict[str, Any]] = []

    for source_section in sections:
        for sentence_obj in source_section.get("sentences") or []:
            if not isinstance(sentence_obj, dict):
                continue

            sentence = sentence_text(sentence_obj)
            if not sentence:
                stats["structured_empty_sentence"] += 1
                continue

            mapped_section = find_section_for_sentence(sentence, candidates) or source_section
            if not section_title(mapped_section) or page_bounds(mapped_section) == ("", ""):
                stats["unmapped_structured_sentence"] += 1

            items.append(
                make_item(
                    sentence=sentence,
                    document_id=document_id,
                    section=mapped_section,
                    modality=sentence_modality(sentence_obj),
                    function=sentence_function(sentence_obj),
                    commodities=commodities,
                    commodity_terms=commodity_terms,
                    include_section_title=include_section_title,
                )
            )
            stats["structured_sentence"] += 1

    return items, stats


def extract_fallback_items(
    data: dict[str, Any],
    *,
    include_section_title: bool,
) -> tuple[list[dict[str, Any]], Counter]:
    document = data.get("document") or {}
    document_id = normalize_ws(str(document.get("id") or ""))
    commodities, commodity_terms = commodity_metadata(data)
    stats: Counter = Counter()
    items: list[dict[str, Any]] = []

    for section in data.get("sections") or []:
        section_text = normalize_ws(str(section.get("text") or ""))
        if not section_text:
            continue

        for sentence in split_sentences(section_text):
            items.append(
                make_item(
                    sentence=sentence,
                    document_id=document_id,
                    section=section,
                    modality="",
                    function="",
                    commodities=commodities,
                    commodity_terms=commodity_terms,
                    include_section_title=include_section_title,
                )
            )
            stats["fallback_sentence"] += 1

    return items, stats


def extract_document_items(
    path: Path,
    *,
    include_section_title: bool,
) -> tuple[list[dict[str, Any]], Counter]:
    data = load_json(path)
    stats: Counter = Counter(files=1)

    structured_items, structured_stats = extract_structured_items(
        data,
        include_section_title=include_section_title,
    )
    stats.update(structured_stats)

    if structured_items:
        return structured_items, stats

    fallback_items, fallback_stats = extract_fallback_items(
        data,
        include_section_title=include_section_title,
    )
    stats.update(fallback_stats)
    if not fallback_items:
        stats["documents_without_sentences"] += 1

    return fallback_items, stats


def build_dataset(
    input_dir: Path,
    *,
    include_section_title: bool,
) -> tuple[list[dict[str, Any]], Counter]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    all_items: list[dict[str, Any]] = []
    stats: Counter = Counter()
    documents_with_structured = 0
    documents_without_structured = 0

    for path in sorted(input_dir.glob("*.json")):
        items, document_stats = extract_document_items(
            path,
            include_section_title=include_section_title,
        )
        all_items.extend(items)
        stats.update(document_stats)
        if document_stats.get("structured_sentence", 0):
            documents_with_structured += 1
        else:
            documents_without_structured += 1

    stats["total_items"] = len(all_items)
    stats["documents_with_structured_sentences"] = documents_with_structured
    stats["documents_without_structured_sentences"] = documents_without_structured
    return all_items, stats


def deduplicate_exact_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    deduplicated: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)

    return deduplicated, len(items) - len(deduplicated)


def summarize_items(items: list[dict[str, Any]], stats: Counter) -> dict[str, Any]:
    documents = {item["metadata"]["document_id"] for item in items}
    commodity_values = {
        commodity
        for item in items
        for commodity in item["metadata"].get("commodities", [])
    }

    summary = dict(stats)
    summary["unique_documents_in_output"] = len(documents)
    summary["unique_commodities_in_output"] = len(commodity_values)
    summary["items_missing_section_title"] = sum(
        1 for item in items if not item["metadata"].get("section_title")
    )
    summary["items_missing_page"] = sum(
        1
        for item in items
        if item["metadata"].get("page_start") == "" or item["metadata"].get("page_end") == ""
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build sentence-level RAG JSON items from new_organization resources."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=None,
        help="Defaults to '<output>.summary.json'.",
    )
    parser.add_argument(
        "--no-section-title-in-text",
        action="store_true",
        help="Use only the sentence as embedding text.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include_section_title = not args.no_section_title_in_text
    summary_output = args.summary_output or args.output.with_suffix(".summary.json")

    items, stats = build_dataset(args.input, include_section_title=include_section_title)
    items, exact_duplicates_removed = deduplicate_exact_items(items)
    stats["exact_duplicates_removed"] = exact_duplicates_removed
    stats["total_items"] = len(items)
    summary = summarize_items(items, stats)

    write_json(args.output, items)
    write_json(summary_output, summary)

    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Summary: {summary_output}")
    print(f"Files read: {summary.get('files', 0)}")
    print(f"Items written: {summary.get('total_items', 0)}")
    print(f"Structured sentences: {summary.get('structured_sentence', 0)}")
    print(f"Fallback sentences: {summary.get('fallback_sentence', 0)}")
    print(f"Items missing section title: {summary.get('items_missing_section_title', 0)}")
    print(f"Items missing page: {summary.get('items_missing_page', 0)}")


if __name__ == "__main__":
    main()
