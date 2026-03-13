#!/usr/bin/env python3
"""Convert scenario CSV/MD files into a single SQLite database.

Usage:
    python scripts/csv_to_sqlite.py <scenario_id>
    python scripts/csv_to_sqlite.py checkout_conversion_drop

Reads all .csv and .md files from scenarios/<id>/tables/ and creates
scenarios/<id>/tables/scenario.db with one table per CSV and a
'documents' table for markdown files.

Idempotent — drops and recreates tables on each run.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def migrate(scenario_id: str) -> None:
    tables_dir = SCENARIOS_DIR / scenario_id / "tables"
    if not tables_dir.exists():
        print(f"Error: {tables_dir} does not exist.")
        sys.exit(1)

    db_path = tables_dir / "scenario.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # --- CSV files → one table each ---
    csv_files = sorted(tables_dir.glob("*.csv"))
    for csv_file in csv_files:
        table_name = csv_file.stem  # e.g. "orders" from "orders.csv"
        df = pd.read_csv(csv_file)
        cursor.execute(f"DROP TABLE IF EXISTS [{table_name}]")
        df.to_sql(table_name, conn, index=False)
        print(f"  {table_name}: {len(df)} rows, {len(df.columns)} columns")

    # --- Markdown files → documents table ---
    md_files = sorted(tables_dir.glob("*.md"))
    cursor.execute("DROP TABLE IF EXISTS documents")
    cursor.execute("CREATE TABLE documents (name TEXT PRIMARY KEY, content TEXT)")
    for md_file in md_files:
        content = md_file.read_text()
        cursor.execute("INSERT INTO documents (name, content) VALUES (?, ?)", (md_file.name, content))
        print(f"  documents/{md_file.name}: {len(content)} chars")

    conn.commit()
    conn.close()
    print(f"\nDone → {db_path}  ({db_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/csv_to_sqlite.py <scenario_id>")
        sys.exit(1)
    scenario_id = sys.argv[1]
    print(f"Migrating scenario '{scenario_id}' ...")
    migrate(scenario_id)
