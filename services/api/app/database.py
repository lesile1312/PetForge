from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class PetRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS pets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    original_image TEXT,
                    processed_image TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def list(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM pets ORDER BY updated_at DESC").fetchall()
        return [self._decode(row) for row in rows]

    def get(self, pet_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
        return self._decode(row) if row else None

    def save(self, pet: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO pets (id, name, config_json, original_image, processed_image, created_at, updated_at)
                   VALUES (:id, :name, :config_json, :original_image, :processed_image, :created_at, :updated_at)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name, config_json=excluded.config_json,
                   original_image=excluded.original_image, processed_image=excluded.processed_image,
                   updated_at=excluded.updated_at""",
                {
                    "id": pet["id"],
                    "name": pet["name"],
                    "config_json": json.dumps(pet["config"], ensure_ascii=False),
                    "original_image": pet.get("original_image"),
                    "processed_image": pet.get("processed_image"),
                    "created_at": pet["created_at"],
                    "updated_at": pet["updated_at"],
                },
            )

    def delete(self, pet_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM pets WHERE id = ?", (pet_id,))

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "config": json.loads(row["config_json"]),
            "original_image": row["original_image"],
            "processed_image": row["processed_image"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
