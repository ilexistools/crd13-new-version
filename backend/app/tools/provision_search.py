from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from mcp.server.fastmcp import FastMCP

from app.scripts.sentence_rag_index import (
    DEFAULT_DB_FILE,
    DEFAULT_MODEL,
    DEFAULT_MODELS_DIR,
    blob_to_vector,
    candidate_sql,
    load_model,
    normalize_filter_value,
)


MAX_RESULTS = 100


@lru_cache(maxsize=1)
def _cached_model(model_name: str, models_dir: str, device: str | None):
    return load_model(model_name, Path(models_dir), device)


def _read_meta(conn: sqlite3.Connection) -> dict[str, str]:
    return dict(conn.execute("SELECT key, value FROM meta").fetchall())


def _build_candidate_args(
    commodities: list[str],
    *,
    include_terms: bool,
    match_all: bool,
) -> Any:
    class CandidateArgs:
        pass

    args = CandidateArgs()
    args.commodity = commodities
    args.include_terms = include_terms
    args.match_all = match_all
    return args


def _candidate_rows(
    conn: sqlite3.Connection,
    commodities: list[str],
    *,
    include_terms: bool,
    match_all: bool,
) -> list[tuple[int, str, str, bytes]]:
    normalized_commodities = [
        normalize_filter_value(commodity)
        for commodity in commodities
        if normalize_filter_value(commodity)
    ]

    args = _build_candidate_args(
        normalized_commodities,
        include_terms=include_terms,
        match_all=match_all,
    )
    sql, params = candidate_sql(args)
    return conn.execute(sql, params).fetchall()


def _format_result(
    *,
    rank: int,
    score: float,
    doc_id: int,
    text: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rank": rank,
        "score": round(score, 6),
        "score_percent": round(score * 100, 2),
        "id": doc_id,
        "text": text,
        "sentence": metadata.get("sentence", ""),
        "document_id": metadata.get("document_id", ""),
        "section_title": metadata.get("section_title", ""),
        "page_start": metadata.get("page_start", ""),
        "page_end": metadata.get("page_end", ""),
        "modality": metadata.get("modality", ""),
        "function": metadata.get("function", ""),
        "commodities": metadata.get("commodities") or [],
        "commodity_terms": metadata.get("commodity_terms") or [],
        "metadata": metadata,
    }


def search_provisions_by_commodity_and_sentence(
    commodities: list[str],
    sentence: str,
    top_k: int = MAX_RESULTS,
    include_terms: bool = True,
    match_all_commodities: bool = False,
    db_path: str | None = None,
    model_name: str | None = None,
    models_dir: str | None = None,
    device: str | None = None,
) -> dict[str, Any]:
    """Search indexed CRD13 provisions after filtering candidates by commodity."""
    query = (sentence or "").strip()
    if not query:
        raise ValueError("sentence must not be empty.")

    db_file = Path(db_path) if db_path else DEFAULT_DB_FILE
    model_cache_dir = Path(models_dir) if models_dir else DEFAULT_MODELS_DIR
    limit = max(1, min(int(top_k), MAX_RESULTS))

    conn = sqlite3.connect(db_file)
    try:
        meta = _read_meta(conn)
        selected_model_name = model_name or meta.get("model_name") or DEFAULT_MODEL
        embedding_dim = int(meta.get("embedding_dim") or 0)
        if embedding_dim <= 0:
            raise ValueError("Index metadata does not contain a valid embedding_dim. Rebuild the index.")

        rows = _candidate_rows(
            conn,
            commodities,
            include_terms=include_terms,
            match_all=match_all_commodities,
        )
        candidate_count = len(rows)
        if candidate_count == 0:
            return {
                "results": [],
                "metadata": {
                    "candidate_count": 0,
                    "returned_count": 0,
                    "requested_top_k": limit,
                    "commodities": commodities,
                    "normalized_commodities": [
                        normalize_filter_value(commodity)
                        for commodity in commodities
                        if normalize_filter_value(commodity)
                    ],
                    "include_terms": include_terms,
                    "match_all_commodities": match_all_commodities,
                    "model_name": selected_model_name,
                    "db_path": str(db_file),
                },
            }

        model = _cached_model(selected_model_name, str(model_cache_dir.resolve()), device)
        query_vector = model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype(np.float32, copy=False)[0]

        ids: list[int] = []
        texts: list[str] = []
        metadatas: list[dict[str, Any]] = []
        vectors = np.empty((candidate_count, embedding_dim), dtype=np.float32)

        for row_index, (doc_id, text, metadata_json, embedding_blob) in enumerate(rows):
            ids.append(int(doc_id))
            texts.append(str(text))
            metadatas.append(json.loads(metadata_json))
            vectors[row_index] = blob_to_vector(embedding_blob, embedding_dim)

        scores = vectors @ query_vector
        result_count = min(limit, candidate_count)
        top_positions = np.argpartition(-scores, result_count - 1)[:result_count]
        top_positions = top_positions[np.argsort(-scores[top_positions])]

        results = [
            _format_result(
                rank=rank,
                score=float(scores[position]),
                doc_id=ids[position],
                text=texts[position],
                metadata=metadatas[position],
            )
            for rank, position in enumerate(top_positions, start=1)
        ]

        return {
            "results": results,
            "metadata": {
                "candidate_count": candidate_count,
                "returned_count": len(results),
                "requested_top_k": limit,
                "commodities": commodities,
                "normalized_commodities": [
                    normalize_filter_value(commodity)
                    for commodity in commodities
                    if normalize_filter_value(commodity)
                ],
                "include_terms": include_terms,
                "match_all_commodities": match_all_commodities,
                "model_name": selected_model_name,
                "db_path": str(db_file),
            },
        }
    finally:
        conn.close()


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def search_provisions(
        commodities: list[str],
        sentence: str,
        top_k: int = MAX_RESULTS,
        include_terms: bool = True,
        match_all_commodities: bool = False,
    ) -> dict[str, Any]:
        """
        Search CRD13 normative provisions by filtering on commodities first, then
        ranking the filtered candidates by semantic similarity to the sentence.

        Returns at most 100 ranked examples with score, sentence, document,
        section, page, modality, function, and commodity metadata.
        """
        return search_provisions_by_commodity_and_sentence(
            commodities=commodities,
            sentence=sentence,
            top_k=top_k,
            include_terms=include_terms,
            match_all_commodities=match_all_commodities,
        )
