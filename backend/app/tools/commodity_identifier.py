from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - exercised only when dependency is absent.
    fuzz = None


RESOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "resources"
    / "crd13_commodities_with_related_terms.json"
)

FUZZY_STOPWORDS = {
    "and",
    "or",
    "of",
    "for",
    "from",
    "in",
    "to",
    "the",
    "with",
    "without",
    "human",
    "consumption",
    "product",
    "products",
    "quick",
    "frozen",
}


@dataclass(frozen=True)
class TermEntry:
    commodity: str
    term: str
    normalized_term: str
    source: str
    base_score: float
    word_count: int


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower()
    value = value.replace("&", " and ")
    value = re.sub(r"['’]", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.65:
        return "medium"
    if confidence >= 0.45:
        return "low"
    return "very_low"


def _specificity_bonus(entry: TermEntry) -> float:
    return min(0.16, (entry.word_count - 1) * 0.035 + len(entry.normalized_term) / 260)


def _plural_variants(normalized_term: str) -> set[str]:
    tokens = normalized_term.split()
    if len(tokens) != 1 or len(tokens[0]) < 4:
        return set()

    token = tokens[0]
    if token.endswith(("s", "x", "z", "ch", "sh")):
        return {f"{token}es"}
    if token.endswith("y") and token[-2] not in "aeiou":
        return {f"{token[:-1]}ies"}
    return {f"{token}s"}


@lru_cache(maxsize=1)
def _load_terms() -> tuple[list[TermEntry], dict[str, set[str]], int]:
    with RESOURCE_PATH.open(encoding="utf-8") as file:
        data = json.load(file)

    entries_by_key: dict[tuple[str, str], TermEntry] = {}
    term_to_commodities: dict[str, set[str]] = {}

    for item in data:
        commodity = item["commodity"]
        candidate_terms = [(commodity, "commodity", 0.92)]
        candidate_terms.extend((term, "related_term", 0.78) for term in item.get("related_terms", []))

        for term, source, base_score in candidate_terms:
            normalized = _normalize(term)
            if not normalized:
                continue
            word_count = len(normalized.split())
            if source == "related_term" and word_count == 1:
                base_score = 0.52

            entry = TermEntry(
                commodity=commodity,
                term=term,
                normalized_term=normalized,
                source=source,
                base_score=base_score,
                word_count=word_count,
            )
            key = (commodity, normalized)
            current = entries_by_key.get(key)
            if current is None or entry.base_score > current.base_score:
                entries_by_key[key] = entry
            term_to_commodities.setdefault(normalized, set()).add(commodity)

            for plural in _plural_variants(normalized):
                plural_entry = TermEntry(
                    commodity=commodity,
                    term=term,
                    normalized_term=plural,
                    source=source,
                    base_score=base_score * 0.96,
                    word_count=1,
                )
                plural_key = (commodity, plural)
                current = entries_by_key.get(plural_key)
                if current is None or plural_entry.base_score > current.base_score:
                    entries_by_key[plural_key] = plural_entry
                term_to_commodities.setdefault(plural, set()).add(commodity)

    entries = sorted(
        entries_by_key.values(),
        key=lambda entry: (entry.word_count, len(entry.normalized_term), entry.base_score),
        reverse=True,
    )
    return entries, term_to_commodities, len(data)


def _add_evidence(
    matches: dict[str, dict[str, Any]],
    entry: TermEntry,
    score: float,
    match_type: str,
    *,
    text_similarity: float | None = None,
) -> None:
    commodity_match = matches.setdefault(
        entry.commodity,
        {
            "commodity": entry.commodity,
            "evidence": [],
            "_scores": [],
        },
    )

    existing_terms = {
        (evidence["matched_term"], evidence["match_type"])
        for evidence in commodity_match["evidence"]
    }
    evidence_key = (entry.term, match_type)
    if evidence_key in existing_terms:
        return

    commodity_match["evidence"].append(
        {
            "matched_term": entry.term,
            "match_type": match_type,
            "source": entry.source,
            "score": round(score, 3),
            **({"text_similarity": round(text_similarity, 3)} if text_similarity is not None else {}),
        }
    )
    commodity_match["_scores"].append(score)


def _ngrams(tokens: list[str], size: int) -> set[str]:
    if size <= 0 or size > len(tokens):
        return set()
    return {" ".join(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def _content_tokens(value: str) -> set[str]:
    return {token for token in value.split() if token not in FUZZY_STOPWORDS and len(token) > 2}


def identify_commodities_from_text(
    text: str,
    top_k: int = 10,
    min_confidence: float = 0.25,
    include_evidence: bool = True,
    enable_fuzzy: bool = True,
) -> dict[str, Any]:
    """Identify possible CRD13 commodities in free text."""
    normalized_text = _normalize(text)
    entries, term_to_commodities, commodity_count = _load_terms()

    if not normalized_text:
        return {
            "matches": [],
            "metadata": {
                "commodity_count": commodity_count,
                "term_count": len(entries),
                "normalized_text_length": 0,
            },
        }

    padded_text = f" {normalized_text} "
    matches: dict[str, dict[str, Any]] = {}
    exact_normalized_terms: set[str] = set()
    normalized_tokens = normalized_text.split()
    fuzzy_windows_by_size: dict[int, set[str]] = {}

    for entry in entries:
        if f" {entry.normalized_term} " not in padded_text:
            continue

        exact_normalized_terms.add(entry.normalized_term)
        score = entry.base_score + _specificity_bonus(entry)
        if len(term_to_commodities.get(entry.normalized_term, set())) > 1:
            score *= 0.86
        _add_evidence(matches, entry, min(score, 0.97), "exact")

    if enable_fuzzy and fuzz is not None:
        for entry in entries:
            if entry.normalized_term in exact_normalized_terms:
                continue
            if entry.word_count == 1:
                continue
            if len(entry.normalized_term) < 12:
                continue

            candidate_windows: set[str] = set()
            for size in range(max(1, entry.word_count - 1), entry.word_count + 2):
                if size not in fuzzy_windows_by_size:
                    fuzzy_windows_by_size[size] = _ngrams(normalized_tokens, size)
                candidate_windows.update(fuzzy_windows_by_size[size])
            if not candidate_windows:
                continue

            entry_content_tokens = _content_tokens(entry.normalized_term)
            scored_windows = [
                fuzz.ratio(entry.normalized_term, window) / 100
                for window in candidate_windows
                if not entry_content_tokens
                or entry_content_tokens.intersection(_content_tokens(window))
            ]
            if not scored_windows:
                continue

            similarity = max(scored_windows)
            threshold = 0.93 if len(entry.normalized_term) < 18 else 0.88
            if similarity < threshold:
                continue

            score = (0.48 + _specificity_bonus(entry)) * similarity
            if len(term_to_commodities.get(entry.normalized_term, set())) > 1:
                score *= 0.8
            _add_evidence(matches, entry, min(score, 0.74), "fuzzy", text_similarity=similarity)

    results: list[dict[str, Any]] = []
    for commodity_match in matches.values():
        scores = sorted(commodity_match.pop("_scores"), reverse=True)
        confidence = 1.0
        for score in scores[:6]:
            confidence *= 1 - score
        confidence = 1 - confidence

        evidence = sorted(
            commodity_match["evidence"],
            key=lambda item: (item["score"], len(item["matched_term"])),
            reverse=True,
        )
        commodity_match["confidence"] = round(min(confidence, 0.99), 3)
        commodity_match["confidence_label"] = _confidence_label(commodity_match["confidence"])
        commodity_match["evidence_count"] = len(evidence)
        commodity_match["evidence"] = evidence[:8] if include_evidence else []

        if commodity_match["confidence"] >= min_confidence:
            results.append(commodity_match)

    results.sort(key=lambda item: (item["confidence"], item["evidence_count"]), reverse=True)
    top_k = max(1, min(top_k, 50))

    return {
        "matches": results[:top_k],
        "metadata": {
            "commodity_count": commodity_count,
            "term_count": len(entries),
            "normalized_text_length": len(normalized_text),
            "fuzzy_enabled": enable_fuzzy and fuzz is not None,
        },
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def identify_commodities(
        text: str,
        top_k: int = 10,
        min_confidence: float = 0.25,
        include_evidence: bool = True,
        enable_fuzzy: bool = True,
    ) -> dict[str, Any]:
        """
        Identify possible CRD13 commodities in a free-text passage.

        Returns ranked commodity matches with confidence scores and evidence terms
        from the CRD13 commodities resource file.
        """
        return identify_commodities_from_text(
            text=text,
            top_k=top_k,
            min_confidence=min_confidence,
            include_evidence=include_evidence,
            enable_fuzzy=enable_fuzzy,
        )
