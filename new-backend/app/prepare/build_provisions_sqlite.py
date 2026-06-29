"""Convert provisions.json into a SQLite database searchable by commodity.

The database intentionally contains no embeddings or vector-search extension.  A
normalized commodity association table is indexed for exact, case-insensitive
commodity lookups.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_PATH = PROJECT_ROOT / "app" / "assets" / "resources" / "provisions.json"
DEFAULT_DB_PATH = PROJECT_ROOT / "app" / "assets" / "indexes" / "provisions.sqlite3"

_SPACE = re.compile(r"\s+")


def normalize_commodity(value: str) -> str:
    """Return the canonical form used in commodity lookups."""
    return _SPACE.sub(" ", value.strip()).casefold()


def load_provisions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        data = data.get("provisions") or data.get("sentences") or data.get("results")
    if not isinstance(data, list):
        raise ValueError(f"Expected a list of provisions in {path}")

    return [item for item in data if isinstance(item, dict)]


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP TABLE IF EXISTS provisions_fts;
        DROP TABLE IF EXISTS provision_commodities;
        DROP TABLE IF EXISTS provisions;

        CREATE TABLE provisions (
            id INTEGER PRIMARY KEY,
            sentence_id INTEGER,
            document_id TEXT,
            type TEXT,
            section_title TEXT,
            page_start INTEGER,
            page_end INTEGER,
            sentence TEXT,
            category TEXT,
            modality TEXT,
            function TEXT,
            units_json TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE provision_commodities (
            provision_id INTEGER NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
            commodity TEXT NOT NULL,
            normalized_commodity TEXT NOT NULL,
            PRIMARY KEY (provision_id, normalized_commodity)
        );

        CREATE INDEX idx_provision_commodities_normalized
            ON provision_commodities(normalized_commodity);
        CREATE INDEX idx_provisions_document_id ON provisions(document_id);
        CREATE INDEX idx_provisions_sentence_id ON provisions(sentence_id);
        """
    )


def build_database(provisions: list[dict[str, Any]], db_path: Path) -> tuple[int, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        create_schema(connection)

        commodity_rows: list[tuple[int, str, str]] = []
        for provision in provisions:
            cursor = connection.execute(
                """
                INSERT INTO provisions (
                    sentence_id, document_id, type, section_title, page_start, page_end,
                    sentence, category, modality, function, units_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provision.get("sentence_id"),
                    provision.get("document_id"),
                    provision.get("type"),
                    provision.get("section_title"),
                    provision.get("page_start"),
                    provision.get("page_end"),
                    provision.get("sentence"),
                    provision.get("category"),
                    provision.get("modality"),
                    provision.get("function"),
                    json.dumps(provision.get("units") or [], ensure_ascii=False),
                    json.dumps(provision, ensure_ascii=False),
                ),
            )
            provision_id = cursor.lastrowid
            for commodity in provision.get("commodities") or []:
                if not isinstance(commodity, str) or not commodity.strip():
                    continue
                commodity_rows.append(
                    (provision_id, _SPACE.sub(" ", commodity.strip()), normalize_commodity(commodity))
                )

        connection.executemany(
            """
            INSERT OR IGNORE INTO provision_commodities
                (provision_id, commodity, normalized_commodity)
            VALUES (?, ?, ?)
            """,
            commodity_rows,
        )
        connection.execute("ANALYZE")
        commodity_count = connection.execute(
            "SELECT COUNT(*) FROM provision_commodities"
        ).fetchone()[0]

    return len(provisions), commodity_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a SQLite provisions database indexed by commodity (without embeddings)."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    provisions = load_provisions(args.input)
    provision_count, commodity_count = build_database(provisions, args.db)
    print(f"Read provisions: {provision_count}")
    print(f"Wrote commodity associations: {commodity_count}")
    print(f"SQLite database: {args.db}")


if __name__ == "__main__":
    main()
