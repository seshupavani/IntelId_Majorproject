import os
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "life_ops.db"


def _resolve_db_path():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url.startswith("sqlite:///"):
        return database_url.replace("sqlite:///", "", 1)
    if database_url:
        raise ValueError(
            "Only sqlite DATABASE_URL values are currently supported, "
            "for example sqlite:///./life_ops.db"
        )
    return os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH))


DB_PATH = _resolve_db_path()


def get_connection():
    path = Path(DB_PATH)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                budget_level TEXT NOT NULL DEFAULT 'balanced',
                comfort_priority TEXT NOT NULL DEFAULT 'balanced',
                health_sensitivity TEXT NOT NULL DEFAULT 'medium',
                preferred_modes TEXT NOT NULL DEFAULT 'cab,bike,walk,train',
                home_location TEXT,
                work_location TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS trip_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                source TEXT,
                destination TEXT,
                decision_type TEXT,
                context_json TEXT NOT NULL,
                risk_json TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_trip_decisions_user_created
            ON trip_decisions(user_id, created_at DESC);
            """
        )
        conn.commit()
    finally:
        conn.close()
