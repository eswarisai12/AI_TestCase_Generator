from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

DATABASE_PATH = Path(__file__).resolve().parent / "data" / "test_cases.db"


def _connect(db_path: str | Path = DATABASE_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: str | Path = DATABASE_PATH) -> None:
    with closing(_connect(db_path)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requirement TEXT NOT NULL,
                    test_cases_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )


def save_generation(
    requirement: str,
    test_cases: list[dict[str, str]],
    db_path: str | Path = DATABASE_PATH,
) -> int:
    with closing(_connect(db_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO generations (requirement, test_cases_json, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    requirement,
                    json.dumps(test_cases, ensure_ascii=True),
                    datetime.now().astimezone().isoformat(timespec="seconds"),
                ),
            )
        return int(cursor.lastrowid)


def list_generations(
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT id, requirement, created_at, test_cases_json
            FROM generations
            ORDER BY id DESC
            """
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "requirement": row["requirement"],
            "created_at": row["created_at"],
            "test_case_count": len(json.loads(row["test_cases_json"])),
        }
        for row in rows
    ]


def get_generation(
    generation_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    with closing(_connect(db_path)) as connection:
        row = connection.execute(
            """
            SELECT id, requirement, test_cases_json, created_at
            FROM generations
            WHERE id = ?
            """,
            (generation_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "requirement": row["requirement"],
        "test_cases": json.loads(row["test_cases_json"]),
        "created_at": row["created_at"],
    }