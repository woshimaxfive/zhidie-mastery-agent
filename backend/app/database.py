from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DEFAULT_DATABASE = Path(__file__).resolve().parents[1] / "data" / "mastery.db"


def database_path() -> Path:
    configured = os.getenv("MASTERY_DB_PATH")
    return Path(configured).resolve() if configured else DEFAULT_DATABASE


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                learner_id TEXT NOT NULL,
                knowledge_point_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                revision INTEGER NOT NULL,
                current_hint_level INTEGER NOT NULL DEFAULT 0,
                highest_hint_level INTEGER NOT NULL DEFAULT 0,
                mastery_state TEXT NOT NULL,
                evidence_level TEXT NOT NULL,
                mastery_reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mastery_profiles (
                learner_id TEXT NOT NULL,
                knowledge_point_id TEXT NOT NULL,
                mastery_state TEXT NOT NULL,
                evidence_level TEXT NOT NULL,
                mastery_reason TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (learner_id, knowledge_point_id)
            );

            CREATE TABLE IF NOT EXISTS attempts (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                task_id TEXT NOT NULL,
                raw_answer TEXT NOT NULL,
                normalized_answer TEXT,
                correct INTEGER NOT NULL,
                hint_level INTEGER NOT NULL,
                diagnosis_code TEXT,
                diagnosis TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                task_id TEXT NOT NULL,
                level TEXT NOT NULL,
                correct INTEGER NOT NULL,
                hint_level INTEGER NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS traces (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                tool TEXT NOT NULL,
                label TEXT NOT NULL,
                status TEXT NOT NULL,
                input_summary TEXT NOT NULL,
                output_summary TEXT NOT NULL,
                error TEXT,
                started_at TEXT NOT NULL,
                duration_ms INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_learner_knowledge_updated
                ON sessions (learner_id, knowledge_point_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_evidence_session_created
                ON evidence (session_id, created_at DESC);

            INSERT OR IGNORE INTO mastery_profiles
                (learner_id, knowledge_point_id, mastery_state, evidence_level, mastery_reason, updated_at)
            SELECT learner_id, knowledge_point_id, mastery_state, evidence_level, mastery_reason, updated_at
            FROM sessions AS candidate
            WHERE candidate.rowid = (
                SELECT latest.rowid
                FROM sessions AS latest
                WHERE latest.learner_id = candidate.learner_id
                  AND latest.knowledge_point_id = candidate.knowledge_point_id
                ORDER BY latest.updated_at DESC, latest.rowid DESC
                LIMIT 1
            );
            """
        )
