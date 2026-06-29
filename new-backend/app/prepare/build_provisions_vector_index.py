from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_INPUT_PATH = PROJECT_ROOT / "app" / "assets" / "resources" / "provisions_index_documents.json"
DEFAULT_DB_PATH = PROJECT_ROOT / "app" / "assets" / "indexes" / "provisions_units.sqlite3"
DEFAULT_CHUNK_SIZE = 512
DEFAULT_EMBEDDING_BATCH_SIZE = 64


def load_index_documents(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")

    valid_items: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Item {index} must be an object")
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError(f"Item {index} must contain a non-empty text field")
        if not isinstance(item.get("metadata"), dict):
            raise ValueError(f"Item {index} must contain a metadata object")
        valid_items.append({"text": item["text"], "metadata": item["metadata"]})

    return valid_items


def chunks(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def remove_existing_index(db_path: Path) -> None:
    for path in (db_path, db_path.with_suffix(db_path.suffix + "-wal"), db_path.with_suffix(db_path.suffix + "-shm")):
        if path.exists():
            path.unlink()


def build_index(
    *,
    input_path: Path,
    db_path: Path,
    model_name: str | None,
    models_dir: Path | None,
    device: str | None,
    chunk_size: int,
    embedding_batch_size: int,
    rebuild: bool,
) -> None:
    try:
        from app.embeddings.sqlite_vec_search import SQLiteVecSearch
    except ModuleNotFoundError as exc:
        if exc.name == "sentence_transformers":
            raise ModuleNotFoundError(
                "Missing dependency 'sentence-transformers'. "
                "Install/sync the project dependencies before indexing."
            ) from exc
        raise

    if rebuild:
        remove_existing_index(db_path)

    documents = load_index_documents(input_path)
    if not documents:
        raise ValueError(f"No index documents found in {input_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    index = SQLiteVecSearch(
        db_path=db_path,
        model_name=model_name or "sentence-transformers/all-mpnet-base-v2",
        models_dir=str(models_dir) if models_dir else None,
        device=device,
        embedding_batch_size=embedding_batch_size,
    )

    try:
        existing_count = index.count()
        if existing_count and not rebuild:
            raise ValueError(
                f"Index already contains {existing_count} documents. "
                "Use --rebuild to recreate it."
            )

        total = len(documents)
        for batch_number, batch in enumerate(chunks(documents, chunk_size), start=1):
            first = ((batch_number - 1) * chunk_size) + 1
            last = min(first + len(batch) - 1, total)
            print(f"Indexing documents {first}-{last}/{total}")
            index.add(batch)

        index.vacuum()
        print(f"Done. Indexed documents: {index.count()}")
        print(f"SQLite index: {db_path}")
    finally:
        index.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a SQLite vector index for provision units."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"Prepared index documents JSON. Default: {DEFAULT_INPUT_PATH}",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Output SQLite index path. Default: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="SentenceTransformers model name. Default: sentence-transformers/all-mpnet-base-v2",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=None,
        help="Local model/cache directory.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help='Embedding device, e.g. "cpu", "mps", "cuda", or "cuda:0".',
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Number of index documents inserted per add() call. Default: {DEFAULT_CHUNK_SIZE}",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=DEFAULT_EMBEDDING_BATCH_SIZE,
        help=f"SentenceTransformer encode batch size. Default: {DEFAULT_EMBEDDING_BATCH_SIZE}",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete the existing SQLite index before indexing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_index(
        input_path=args.input,
        db_path=args.db,
        model_name=args.model,
        models_dir=args.models_dir,
        device=args.device,
        chunk_size=max(1, args.chunk_size),
        embedding_batch_size=max(1, args.embedding_batch_size),
        rebuild=args.rebuild,
    )


if __name__ == "__main__":
    main()
