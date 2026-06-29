from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from dotenv import find_dotenv, load_dotenv
from sentence_transformers import SentenceTransformer


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_FILE = APP_DIR / "assets" / "resources" / "new_organization_sentence_rag.json"
DEFAULT_DB_FILE = APP_DIR / "assets" / "resources" / "new_organization_sentence_rag.sqlite3"
DEFAULT_MODELS_DIR = APP_DIR / "embeddings" / "models"
DEFAULT_MODEL = "sentence-transformers/paraphrase-MiniLM-L3-v2"

load_dotenv(find_dotenv())


def normalize_filter_value(value: str) -> str:
    return " ".join((value or "").strip().casefold().split())


def setup_model_cache(models_dir: Path) -> None:
    models_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(models_dir))
    os.environ.setdefault("HF_HOME", str(models_dir))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(models_dir))


def load_model(model_name: str, models_dir: Path, device: str | None) -> SentenceTransformer:
    setup_model_cache(models_dir)
    return SentenceTransformer(model_name, cache_folder=str(models_dir), device=device)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    return conn


def reset_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS commodity_terms;
        DROP TABLE IF EXISTS commodities;
        DROP TABLE IF EXISTS documents;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            document_id TEXT NOT NULL,
            section_title TEXT NOT NULL,
            page_start TEXT NOT NULL,
            page_end TEXT NOT NULL,
            sentence TEXT NOT NULL,
            modality TEXT NOT NULL,
            function TEXT NOT NULL,
            embedding BLOB NOT NULL
        );

        CREATE TABLE commodities (
            doc_id INTEGER NOT NULL,
            commodity TEXT NOT NULL,
            commodity_norm TEXT NOT NULL,
            FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE TABLE commodity_terms (
            doc_id INTEGER NOT NULL,
            term TEXT NOT NULL,
            term_norm TEXT NOT NULL,
            FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE INDEX idx_documents_document_id ON documents(document_id);
        CREATE INDEX idx_commodities_norm_doc ON commodities(commodity_norm, doc_id);
        CREATE INDEX idx_commodity_terms_norm_doc ON commodity_terms(term_norm, doc_id);
        """
    )


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def document_count(conn: sqlite3.Connection) -> int:
    if not table_exists(conn, "documents"):
        return 0
    return int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])


def batched(items: list[dict[str, Any]], batch_size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def vector_to_blob(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def blob_to_vector(blob: bytes, expected_dim: int) -> np.ndarray:
    vector = np.frombuffer(blob, dtype=np.float32)
    if vector.size != expected_dim:
        raise ValueError(f"Embedding dimension mismatch: expected {expected_dim}, got {vector.size}.")
    return vector


def insert_batch(
    conn: sqlite3.Connection,
    batch: list[dict[str, Any]],
    embeddings: np.ndarray,
) -> None:
    doc_rows: list[tuple[Any, ...]] = []
    commodity_rows: list[tuple[int, str, str]] = []
    term_rows: list[tuple[int, str, str]] = []

    for item, embedding in zip(batch, embeddings):
        metadata = item["metadata"]
        doc_rows.append(
            (
                item["text"],
                json.dumps(metadata, ensure_ascii=False),
                str(metadata.get("document_id") or ""),
                str(metadata.get("section_title") or ""),
                str(metadata.get("page_start") or ""),
                str(metadata.get("page_end") or ""),
                str(metadata.get("sentence") or ""),
                str(metadata.get("modality") or ""),
                str(metadata.get("function") or ""),
                vector_to_blob(embedding),
            )
        )

    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO documents(
            text, metadata_json, document_id, section_title, page_start, page_end,
            sentence, modality, function, embedding
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        doc_rows,
    )

    last_id = int(cursor.execute("SELECT last_insert_rowid()").fetchone()[0])
    first_id = last_id - len(batch) + 1
    for offset, item in enumerate(batch):
        doc_id = first_id + offset
        metadata = item["metadata"]

        for commodity in metadata.get("commodities") or []:
            commodity_text = str(commodity or "").strip()
            if commodity_text:
                commodity_rows.append((doc_id, commodity_text, normalize_filter_value(commodity_text)))

        for term in metadata.get("commodity_terms") or []:
            term_text = str(term or "").strip()
            if term_text:
                term_rows.append((doc_id, term_text, normalize_filter_value(term_text)))

    cursor.executemany(
        "INSERT INTO commodities(doc_id, commodity, commodity_norm) VALUES (?, ?, ?)",
        commodity_rows,
    )
    cursor.executemany(
        "INSERT INTO commodity_terms(doc_id, term, term_norm) VALUES (?, ?, ?)",
        term_rows,
    )
    cursor.close()


def index_items(args: argparse.Namespace) -> None:
    input_path = args.input.resolve()
    db_path = args.db.resolve()

    with input_path.open("r", encoding="utf-8") as file:
        items = json.load(file)

    if not isinstance(items, list):
        raise ValueError("Input JSON must be a list of {'text', 'metadata'} items.")

    model = load_model(args.model, args.models_dir.resolve(), args.device)
    embedding_dim = int(model.get_sentence_embedding_dimension())

    conn = connect(db_path)
    if args.rebuild or not table_exists(conn, "documents"):
        reset_schema(conn)
        existing_count = 0
        conn.execute("INSERT INTO meta(key, value) VALUES (?, ?)", ("model_name", args.model))
        conn.execute("INSERT INTO meta(key, value) VALUES (?, ?)", ("embedding_dim", str(embedding_dim)))
        conn.execute("INSERT INTO meta(key, value) VALUES (?, ?)", ("source_json", str(input_path)))
        conn.commit()
    else:
        meta = read_meta(conn)
        if meta.get("model_name") and meta["model_name"] != args.model:
            raise ValueError(
                f"Existing index uses model {meta['model_name']!r}; use --rebuild to recreate with {args.model!r}."
            )
        if meta.get("embedding_dim") and int(meta["embedding_dim"]) != embedding_dim:
            raise ValueError("Existing index embedding dimension differs; use --rebuild.")
        existing_count = document_count(conn)

    start = time.time()
    indexed = existing_count
    total = len(items)

    if indexed >= total:
        print(f"Index already complete: {indexed}/{total} items in {db_path}.")
        conn.close()
        return

    print(f"Starting at {indexed}/{total} items.")

    for batch_number, batch in enumerate(batched(items[indexed:], args.batch_size), start=1):
        texts = [str(item["text"]) for item in batch]
        embeddings = model.encode(
            texts,
            batch_size=args.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype(np.float32, copy=False)
        insert_batch(conn, batch, embeddings)
        conn.commit()
        indexed += len(batch)
        if batch_number == 1 or batch_number % args.log_every == 0 or indexed == total:
            print(f"Indexed {indexed}/{total}")

    elapsed = time.time() - start
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("indexed_items", str(indexed)))
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("indexed_at_unix", str(int(time.time()))))
    conn.commit()
    conn.close()

    print(f"Done. Indexed {indexed} items into {db_path} in {elapsed:.1f}s for this run.")


def read_meta(conn: sqlite3.Connection) -> dict[str, str]:
    return dict(conn.execute("SELECT key, value FROM meta").fetchall())


def candidate_sql(args: argparse.Namespace) -> tuple[str, list[Any]]:
    filters = [normalize_filter_value(value) for value in args.commodity if normalize_filter_value(value)]
    params: list[Any] = []

    if not filters:
        return "SELECT id, text, metadata_json, embedding FROM documents", params

    placeholders = ", ".join("?" for _ in filters)
    params.extend(filters)

    if args.include_terms:
        source = f"""
            SELECT doc_id, commodity_norm AS value_norm FROM commodities
            UNION ALL
            SELECT doc_id, term_norm AS value_norm FROM commodity_terms
        """
    else:
        source = "SELECT doc_id, commodity_norm AS value_norm FROM commodities"

    if args.match_all:
        return (
            f"""
            SELECT id, text, metadata_json, embedding
            FROM documents
            WHERE id IN (
                SELECT doc_id
                FROM ({source})
                WHERE value_norm IN ({placeholders})
                GROUP BY doc_id
                HAVING COUNT(DISTINCT value_norm) = ?
            )
            """,
            [*params, len(set(filters))],
        )

    return (
        f"""
        SELECT id, text, metadata_json, embedding
        FROM documents
        WHERE id IN (
            SELECT DISTINCT doc_id
            FROM ({source})
            WHERE value_norm IN ({placeholders})
        )
        """,
        params,
    )


def search(args: argparse.Namespace) -> None:
    conn = connect(args.db.resolve())
    meta = read_meta(conn)
    model_name = args.model or meta.get("model_name") or DEFAULT_MODEL
    embedding_dim = int(meta.get("embedding_dim") or 0)
    if embedding_dim <= 0:
        raise ValueError("Index metadata does not contain a valid embedding_dim. Rebuild the index.")

    sql, params = candidate_sql(args)
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("No candidates found for the provided commodity filter.")
        return

    model = load_model(model_name, args.models_dir.resolve(), args.device)
    query_vector = model.encode(
        [args.query],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).astype(np.float32, copy=False)[0]

    ids: list[int] = []
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    vectors = np.empty((len(rows), embedding_dim), dtype=np.float32)

    for row_index, (doc_id, text, metadata_json, embedding_blob) in enumerate(rows):
        ids.append(int(doc_id))
        texts.append(str(text))
        metadatas.append(json.loads(metadata_json))
        vectors[row_index] = blob_to_vector(embedding_blob, embedding_dim)

    scores = vectors @ query_vector
    top_k = min(args.top_k, len(rows))
    top_positions = np.argpartition(-scores, top_k - 1)[:top_k]
    top_positions = top_positions[np.argsort(-scores[top_positions])]

    results = [
        {
            "rank": rank,
            "score": float(scores[position]),
            "id": ids[position],
            "text": texts[position],
            "metadata": metadatas[position],
        }
        for rank, position in enumerate(top_positions, start=1)
    ]

    conn.close()

    if args.json:
        print(json.dumps({"candidate_count": len(rows), "results": results}, ensure_ascii=False, indent=2))
        return

    print(f"Candidates searched: {len(rows)}")
    for result in results:
        metadata = result["metadata"]
        print("")
        print(f"#{result['rank']} score={result['score']:.4f}")
        print(f"Document: {metadata.get('document_id', '')}")
        print(f"Section: {metadata.get('section_title', '')}")
        print(f"Pages: {metadata.get('page_start', '')}-{metadata.get('page_end', '')}")
        print(f"Modality: {metadata.get('modality', '')}")
        print(f"Function: {metadata.get('function', '')}")
        print(f"Commodities: {', '.join(metadata.get('commodities') or [])}")
        print(f"Sentence: {metadata.get('sentence', '')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index and search sentence-level CRD13 RAG data.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Build the SQLite sentence embedding index.")
    index_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_FILE)
    index_parser.add_argument("--db", type=Path, default=DEFAULT_DB_FILE)
    index_parser.add_argument("--model", default=os.getenv("SENTENCE_RAG_MODEL", DEFAULT_MODEL))
    index_parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    index_parser.add_argument("--batch-size", type=int, default=128)
    index_parser.add_argument("--device", default=os.getenv("SENTENCE_RAG_DEVICE") or None)
    index_parser.add_argument("--rebuild", action="store_true", help="Drop and recreate the index.")
    index_parser.add_argument("--log-every", type=int, default=10, help="Print progress every N batches.")
    index_parser.set_defaults(func=index_items)

    search_parser = subparsers.add_parser("search", help="Search the sentence embedding index.")
    search_parser.add_argument("query")
    search_parser.add_argument("--db", type=Path, default=DEFAULT_DB_FILE)
    search_parser.add_argument("--model", default=None, help="Defaults to the model stored in the index.")
    search_parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    search_parser.add_argument("--device", default=os.getenv("SENTENCE_RAG_DEVICE") or None)
    search_parser.add_argument("--top-k", type=int, default=5)
    search_parser.add_argument("--commodity", action="append", default=[])
    search_parser.add_argument("--include-terms", action="store_true")
    search_parser.add_argument("--match-all", action="store_true")
    search_parser.add_argument("--json", action="store_true")
    search_parser.set_defaults(func=search)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
