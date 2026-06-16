from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import app as wk_app  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace the local SQLite database with a WK Hub backup JSON dump."
    )
    parser.add_argument("backup", type=Path, help="Path to wk-hub-backup JSON file")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=wk_app.DB_PATH,
        help=f"SQLite database path to write, default: {wk_app.DB_PATH}",
    )
    return parser.parse_args()


def insert_rows(conn: sqlite3.Connection, table_name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    values = [tuple(row.get(column) for column in columns) for row in rows]
    conn.executemany(
        f"INSERT INTO {table_name} ({column_sql}) VALUES ({placeholders})",
        values,
    )


def main() -> int:
    args = parse_args()
    if wk_app.USING_POSTGRES:
        print(
            "Refusing to import into Postgres. Unset DATABASE_URL/POSTGRES_URL first.",
            file=sys.stderr,
        )
        return 2

    payload = json.loads(args.backup.read_text(encoding="utf-8"))
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        print("Backup JSON has no tables object.", file=sys.stderr)
        return 2

    wk_app.DB_PATH = args.db_path
    wk_app.DB_INIT_DONE = False
    wk_app.DB_INIT_ERROR = None
    wk_app.init_db()

    with wk_app.get_db() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            for table_name, _order_by in reversed(wk_app.DB_BACKUP_TABLES):
                wk_app.execute(conn, f"DELETE FROM {table_name}")
            for table_name, _order_by in wk_app.DB_BACKUP_TABLES:
                table = tables.get(table_name) or {}
                rows = table.get("rows") or []
                if not isinstance(rows, list):
                    raise ValueError(f"Backup table {table_name} rows must be a list.")
                insert_rows(conn, table_name, rows)
            conn.commit()
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

    row_counts = {
        table_name: len((tables.get(table_name) or {}).get("rows") or [])
        for table_name, _order_by in wk_app.DB_BACKUP_TABLES
    }
    print(
        json.dumps(
            {
                "ok": True,
                "db_path": str(args.db_path),
                "source_database": payload.get("database"),
                "generated_at": payload.get("generated_at"),
                "row_counts": row_counts,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
