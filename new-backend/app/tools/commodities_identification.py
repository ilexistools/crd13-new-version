from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.orchestration import gpt
from app.orchestration.config import default_model
from app.orchestration.util import instruction_loader
from pydantic import BaseModel

class CommodityIdentificationResponse(BaseModel):
    commodities: list[str]
    

DEFAULT_COMMODITIES_PATH = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "resources"
    / "commodities_with_related_terms.json"
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SPACE = re.compile(r"\s+")


def normalize_term(value: str) -> str:
    value = value.lower()
    value = value.replace("’", "'").replace("‘", "'").replace("`", "'")
    value = value.replace("‐", "-").replace("‑", "-").replace("–", "-").replace("—", "-")
    value = value.replace("'", "")
    value = _NON_ALNUM.sub(" ", value)
    return _SPACE.sub(" ", value).strip()


def term_regex(normalized_term: str) -> re.Pattern[str]:
    escaped = re.escape(normalized_term)
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")


def term_weight(term: str, *, is_commodity_name: bool, ambiguity: int) -> float:
    token_count = len(term.split())
    if is_commodity_name:
        base = 6.0 if token_count > 1 else 4.0
    elif token_count > 1:
        base = min(5.0, 2.0 + (0.6 * token_count))
    else:
        base = 1.0

    if ambiguity <= 1:
        return base

    return base / math.log2(ambiguity + 1)


@dataclass
class TermEntry:
    term: str
    original_terms: set[str] = field(default_factory=set)
    commodities: set[str] = field(default_factory=set)
    commodity_name_for: set[str] = field(default_factory=set)


@dataclass
class CommodityScore:
    commodity: str
    score: float = 0.0
    matched_terms: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_exact_commodity_name(self) -> bool:
        return any(match["is_commodity_name"] for match in self.matched_terms)

    @property
    def has_multiword_evidence(self) -> bool:
        return any(match["token_count"] > 1 for match in self.matched_terms)

    @property
    def ambiguous_terms(self) -> list[str]:
        return sorted(
            {
                match["term"]
                for match in self.matched_terms
                if match["ambiguity"] > 1
            }
        )


class CommoditiesIdentifierTool:
    """
    Identifies commodities using a controlled vocabulary.

    The tool is intentionally lexical-first:
    - exact and multiword term matches are favored;
    - generic ambiguous terms are penalized;
    - results include evidence for auditability.
    """

    def __init__(self, commodities_path: str | Path = DEFAULT_COMMODITIES_PATH):
        self.commodities_path = Path(commodities_path)
        self._term_entries = self._load_term_entries(self.commodities_path)
        self._ordered_terms = sorted(
            self._term_entries.values(),
            key=lambda entry: (len(entry.term.split()), len(entry.term)),
            reverse=True,
        )
        self.__create_gpts()
    
    def __create_gpts(self):
        self.__commodities_identifier = gpt.GPT(agent_id='commodities_identifier')
        self.__commodities_identifier.output_type = CommodityIdentificationResponse

    @staticmethod
    def _load_rows(path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as handle:
            rows = json.load(handle)
        if not isinstance(rows, list):
            raise ValueError(f"Expected a list in {path}")
        return rows

    def _load_term_entries(self, path: Path) -> dict[str, TermEntry]:
        entries: dict[str, TermEntry] = {}
        for row in self._load_rows(path):
            commodity = str(row.get("commodity", "")).strip()
            if not commodity:
                continue

            terms = [commodity, *(row.get("related_terms") or [])]
            for original in terms:
                if not isinstance(original, str):
                    continue
                normalized = normalize_term(original)
                if not normalized:
                    continue

                entry = entries.setdefault(normalized, TermEntry(term=normalized))
                entry.original_terms.add(original)
                entry.commodities.add(commodity)
                if normalized == normalize_term(commodity):
                    entry.commodity_name_for.add(commodity)

        return entries

    def identify(
        self,
        text: str,
        *,
        top_k: int = 10,
        min_score: float = 0.75,
    ) -> dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            return {
                "commodities": [],
                "candidates": [],
                "needs_review": True,
                "reason": "empty_text",
            }

        normalized_text = normalize_term(text)
        scores: dict[str, CommodityScore] = {}
        consumed_spans: list[tuple[int, int]] = []

        for entry in self._ordered_terms:
            match = term_regex(entry.term).search(normalized_text)
            if not match:
                continue

            span = match.span()
            token_count = len(entry.term.split())
            # Prefer the longest phrase evidence. Short terms inside an already
            # matched long term are kept only when they name the commodity itself.
            overlaps = any(not (span[1] <= start or span[0] >= end) for start, end in consumed_spans)
            if overlaps and token_count == 1:
                continue
            if token_count > 1:
                consumed_spans.append(span)

            ambiguity = len(entry.commodities)
            for commodity in entry.commodities:
                is_commodity_name = commodity in entry.commodity_name_for
                weight = term_weight(
                    entry.term,
                    is_commodity_name=is_commodity_name,
                    ambiguity=ambiguity,
                )
                score = scores.setdefault(commodity, CommodityScore(commodity=commodity))
                score.score += weight
                score.matched_terms.append(
                    {
                        "term": entry.term,
                        "original_terms": sorted(entry.original_terms),
                        "token_count": token_count,
                        "ambiguity": ambiguity,
                        "is_commodity_name": is_commodity_name,
                        "weight": round(weight, 4),
                    }
                )

        candidates = [
            self._candidate_payload(score)
            for score in scores.values()
            if score.score >= min_score
        ]
        candidates.sort(
            key=lambda item: (
                item["score"],
                item["has_exact_commodity_name"],
                item["has_multiword_evidence"],
                -len(item["ambiguous_terms"]),
            ),
            reverse=True,
        )
        candidates = candidates[: max(1, top_k)]

        high_confidence = [item["commodity"] for item in candidates if item["confidence"] == "high"]
        medium_confidence = [item["commodity"] for item in candidates if item["confidence"] == "medium"]
        selected = high_confidence or medium_confidence

        return {
            "commodities": selected,
            "candidates": candidates,
            "needs_review": not bool(high_confidence),
            "reason": "ok" if candidates else "no_terms_matched",
        }

    def _candidate_payload(self, score: CommodityScore) -> dict[str, Any]:
        rounded_score = round(score.score, 4)
        confidence = self._confidence(score)
        return {
            "commodity": score.commodity,
            "confidence": confidence,
            "score": rounded_score,
            "matched_terms": score.matched_terms,
            "ambiguous_terms": score.ambiguous_terms,
            "has_exact_commodity_name": score.has_exact_commodity_name,
            "has_multiword_evidence": score.has_multiword_evidence,
        }

    @staticmethod
    def _confidence(score: CommodityScore) -> str:
        if score.has_exact_commodity_name and score.has_multiword_evidence:
            return "high"
        if score.score >= 8.0 and score.has_multiword_evidence:
            return "high"
        if score.score >= 4.0:
            return "medium"
        return "low"

    def run(self, text: str) -> dict[str, Any]:
        candidates = self.identify(text)
        result = self.__commodities_identifier.run_sync(
            f"Identify commodities in the following text: {text}\n\nCandidates: {candidates}"
        )
        return {"input": {"text": text}, "results": result.commodities}

    async def run_async(self, text: str) -> dict[str, Any]:
        candidates = self.identify(text)
        result = await self.__commodities_identifier.run(
            f"Identify commodities in the following text: {text}\n\nCandidates: {candidates}"
        )
        return {"input": {"text": text}, "results": result.commodities}


