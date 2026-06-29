"""Commodity-filtered provision search ranked with SQLite FTS5/BM25."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.orchestration import gpt
from app.orchestration.config import default_model
from app.orchestration.util import instruction_loader



DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "assets" / "indexes" / "provisions.sqlite3"
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
        "is", "it", "must", "of", "on", "or", "shall", "that", "the", "their",
        "to", "with",
    }
)


class ProvisionFilterResponse(BaseModel):
    """Structured output used internally to select existing provision records."""

    selected_candidate_ids: list[int] = Field(
        description="IDs of the relevant supplied candidates, ordered by relevance."
    )


class ProvisionsSearchTool:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self._provision_filter: gpt.GPT | None = None

    def _get_provision_filter(self) -> gpt.GPT:
        if self._provision_filter is None:
            self._provision_filter = gpt.GPT(agent_id="provision_filter")
            self._provision_filter.output_type = ProvisionFilterResponse
        return self._provision_filter

    def _open_db(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def normalize_commodity(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip()).casefold()

    @classmethod
    def commodity_query_terms(cls, value: str) -> set[str]:
        normalized = cls.normalize_commodity(value)
        if not normalized:
            return set()

        terms = {normalized}
        for suffix in (" products", " product"):
            if normalized.endswith(suffix):
                terms.add(normalized[: -len(suffix)].strip())
        return {term for term in terms if term}

    @staticmethod
    def _fts_query(text: str) -> str:
        """Make a safe FTS5 OR query from the meaningful words in *text*."""
        terms = []
        seen: set[str] = set()
        for term in _TOKEN.findall(text.casefold()):
            if len(term) < 2 or term in _STOP_WORDS or term in seen:
                continue
            seen.add(term)
            terms.append(term)
        return " OR ".join(terms)

    @staticmethod
    def _ensure_fts_index(connection: sqlite3.Connection) -> None:
        """Create or refresh the FTS index when its content is absent or stale."""
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS provisions_fts
            USING fts5(
                provision_id UNINDEXED,
                search_text,
                tokenize='porter unicode61'
            )
            """
        )
        provision_count = connection.execute("SELECT COUNT(*) FROM provisions").fetchone()[0]
        indexed_count = connection.execute("SELECT COUNT(*) FROM provisions_fts").fetchone()[0]
        if indexed_count == provision_count:
            return

        connection.execute("DELETE FROM provisions_fts")
        connection.execute(
            """
            INSERT INTO provisions_fts(rowid, provision_id, search_text)
            SELECT id, id, trim(coalesce(sentence, '') || ' ' || coalesce(units_json, ''))
            FROM provisions
            """
        )

    @staticmethod
    def _add_relevance(results: list[dict[str, Any]]) -> None:
        """Add a 0-100 relevance relative to the current BM25 result set."""
        bm25_results = [
            result for result in results if result.get("bm25_score") is not None
        ]
        if not bm25_results:
            for result in results:
                result["relevance"] = None
            return

        scores = [-float(result["bm25_score"]) for result in bm25_results]
        lowest, highest = min(scores), max(scores)
        for result in results:
            bm25_score = result.get("bm25_score")
            if bm25_score is None:
                result["relevance"] = None
                continue
            result["relevance"] = (
                100
                if highest == lowest
                else round(100 * ((-float(bm25_score)) - lowest) / (highest - lowest))
            )

    def filter_results(
        self,
        commodities: list[str],
        text: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return commodity-matched provisions ordered by FTS5 BM25 relevance.

        When the sentence has no searchable terms or produces no lexical hit, the
        method returns commodity matches as a deterministic fallback. This keeps
        downstream LLM evaluation supplied with candidates.
        """
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if limit < 1:
            raise ValueError("limit must be at least 1")

        normalized_commodities = sorted(
            {
                term
                for commodity in commodities
                if isinstance(commodity, str) and commodity.strip()
                for term in self.commodity_query_terms(commodity)
            }
        )
        if not normalized_commodities:
            return []

        placeholders = ", ".join("?" for _ in normalized_commodities)
        fts_query = self._fts_query(text)
        with self._open_db() as connection:
            self._ensure_fts_index(connection)
            if fts_query:
                rows = connection.execute(
                    f"""
                    WITH commodity_candidates AS (
                        SELECT DISTINCT provision_id
                        FROM provision_commodities
                        WHERE normalized_commodity IN ({placeholders})
                    )
                    SELECT p.*, bm25(provisions_fts) AS bm25_score
                    FROM provisions_fts
                    JOIN commodity_candidates AS candidates
                        ON candidates.provision_id = provisions_fts.provision_id
                    JOIN provisions AS p ON p.id = candidates.provision_id
                    WHERE provisions_fts MATCH ?
                    ORDER BY bm25_score ASC, p.id ASC
                    LIMIT ?
                    """,
                    (*normalized_commodities, fts_query, limit),
                ).fetchall()
            else:
                rows = []

            if not rows:
                rows = connection.execute(
                    f"""
                    SELECT DISTINCT p.*, NULL AS bm25_score
                    FROM provisions AS p
                    JOIN provision_commodities AS pc ON pc.provision_id = p.id
                    WHERE pc.normalized_commodity IN ({placeholders})
                    ORDER BY p.id ASC
                    LIMIT ?
                    """,
                    (*normalized_commodities, limit),
                ).fetchall()

        results = [dict(row) for row in rows]
        for result in results:
            for field in ("units_json", "raw_json"):
                raw = result.get(field)
                if isinstance(raw, str):
                    try:
                        result[field] = json.loads(raw)
                    except json.JSONDecodeError:
                        pass
        self._add_relevance(results)
        for rank, result in enumerate(results, start=1):
            result["rank"] = rank
        return results
    
    
    def filter_provisions(
        self,
        source_sentence: str,
        provisions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Use the LLM to retain relevant candidates without changing their schema."""
        if not isinstance(source_sentence, str):
            raise TypeError("source_sentence must be a string")
        if not provisions:
            return []

        candidates = []
        for provision in provisions:
            provision_id = provision.get("id")
            if not isinstance(provision_id, int):
                continue
            units_json = provision.get("units_json") or "[]"
            if isinstance(units_json, list):
                units = units_json
            else:
                try:
                    units = json.loads(units_json)
                except json.JSONDecodeError:
                    units = []
            candidates.append(
                {
                    "id": provision_id,
                    "sentence": provision.get("sentence"),
                    "units": units,
                    "category": provision.get("category"),
                    "modality": provision.get("modality"),
                    "function": provision.get("function"),
                    "rank": provision.get("rank"),
                    "relevance": provision.get("relevance"),
                    "bm25_score": provision.get("bm25_score"),
                }
            )

        if not candidates:
            return []

        response = self._get_provision_filter().run_sync(
            json.dumps(
                {
                    "source_sentence": source_sentence,
                    "candidates": candidates,
                },
                ensure_ascii=False,
            )
        )
        selected_ids = set(response.selected_candidate_ids)
        # Keep the original search order and dictionaries, preserving the exact
        # schema exposed by filter_results.
        return [
            provision
            for provision in provisions
            if provision.get("id") in selected_ids
        ]

    async def filter_provisions_async(
        self,
        source_sentence: str,
        provisions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Use the LLM to retain relevant candidates without changing their schema."""
        if not isinstance(source_sentence, str):
            raise TypeError("source_sentence must be a string")
        if not provisions:
            return []

        candidates = []
        for provision in provisions:
            provision_id = provision.get("id")
            if not isinstance(provision_id, int):
                continue
            units_json = provision.get("units_json") or "[]"
            if isinstance(units_json, list):
                units = units_json
            else:
                try:
                    units = json.loads(units_json)
                except json.JSONDecodeError:
                    units = []
            candidates.append(
                {
                    "id": provision_id,
                    "sentence": provision.get("sentence"),
                    "units": units,
                    "category": provision.get("category"),
                    "modality": provision.get("modality"),
                    "function": provision.get("function"),
                    "rank": provision.get("rank"),
                    "relevance": provision.get("relevance"),
                    "bm25_score": provision.get("bm25_score"),
                }
            )

        if not candidates:
            return []

        response = await self._get_provision_filter().run(
            json.dumps(
                {
                    "source_sentence": source_sentence,
                    "candidates": candidates,
                },
                ensure_ascii=False,
            )
        )
        selected_ids = set(response.selected_candidate_ids)
        return [
            provision
            for provision in provisions
            if provision.get("id") in selected_ids
        ]

    def run(self, commodities: list[str], text: str, limit: int = 25) -> list[dict[str, Any]]:
        candidates = self.filter_results(commodities, text, limit=limit)
        return {"output": {"input": {"commodities": commodities, "text": text}, "results": self.filter_provisions(text, candidates)}}

    async def run_async(self, commodities: list[str], text: str, limit: int = 25) -> dict[str, Any]:
        candidates = self.filter_results(commodities, text, limit=limit)
        return {"output": {"input": {"commodities": commodities, "text": text}, "results": await self.filter_provisions_async(text, candidates)}}
