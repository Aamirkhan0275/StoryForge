"""Small SQLite persistence layer for the local-first MVP."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


DATA_DIRECTORY = Path("data")
DATABASE_PATH = DATA_DIRECTORY / "storyforge.db"


@contextmanager
def get_connection():
    """Yield a SQLite connection and make sure it is always closed."""
    DATA_DIRECTORY.mkdir(exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database() -> None:
    """Create the database structure required by the current MVP."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                notes TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
            """
        )
        existing_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(sources)").fetchall()
        }
        if "extracted_text" not in existing_columns:
            connection.execute("ALTER TABLE sources ADD COLUMN extracted_text TEXT")
        if "extracted_at" not in existing_columns:
            connection.execute("ALTER TABLE sources ADD COLUMN extracted_at TEXT")

        project_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(projects)").fetchall()
        }
        if "research_brief" not in project_columns:
            connection.execute("ALTER TABLE projects ADD COLUMN research_brief TEXT")
        if "research_generated_at" not in project_columns:
            connection.execute("ALTER TABLE projects ADD COLUMN research_generated_at TEXT")
        if "research_model" not in project_columns:
            connection.execute("ALTER TABLE projects ADD COLUMN research_model TEXT")
        if "research_language" not in project_columns:
            connection.execute("ALTER TABLE projects ADD COLUMN research_language TEXT")
