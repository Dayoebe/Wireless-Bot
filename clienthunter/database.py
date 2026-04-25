from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from .models import AuditResult

load_dotenv()

DB_PATH = os.getenv("CLIENTHUNTER_DB", "clienthunter.sqlite3")


LEADS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name TEXT,
    website TEXT NOT NULL,
    final_url TEXT,
    industry TEXT,
    source TEXT,
    contact_name TEXT,
    contact_email TEXT,
    phone TEXT,
    location TEXT,
    status_code INTEGER,
    response_time_ms INTEGER,
    page_size_kb REAL,
    title TEXT,
    meta_description TEXT,
    detected_platform TEXT,
    footer_year INTEGER,
    stale_footer INTEGER,
    https_enabled INTEGER,
    has_viewport INTEGER,
    has_canonical INTEGER,
    has_open_graph INTEGER,
    has_schema INTEGER,
    has_sitemap INTEGER,
    has_robots INTEGER,
    opportunity_score INTEGER,
    issues_json TEXT,
    recommendations_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


OPTIONAL_COLUMNS: dict[str, str] = {
    "business_name": "TEXT",
    "final_url": "TEXT",
    "industry": "TEXT",
    "source": "TEXT",
    "contact_name": "TEXT",
    "contact_email": "TEXT",
    "phone": "TEXT",
    "location": "TEXT",
    "status_code": "INTEGER",
    "response_time_ms": "INTEGER",
    "page_size_kb": "REAL",
    "title": "TEXT",
    "meta_description": "TEXT",
    "detected_platform": "TEXT",
    "footer_year": "INTEGER",
    "stale_footer": "INTEGER",
    "https_enabled": "INTEGER",
    "has_viewport": "INTEGER",
    "has_canonical": "INTEGER",
    "has_open_graph": "INTEGER",
    "has_schema": "INTEGER",
    "has_sitemap": "INTEGER",
    "has_robots": "INTEGER",
    "opportunity_score": "INTEGER",
    "issues_json": "TEXT",
    "recommendations_json": "TEXT",
    "updated_at": "TEXT",
}


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection using the configured database path."""
    db_file = Path(DB_PATH)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the leads table and indexes if they do not already exist."""
    with get_connection() as conn:
        conn.execute(LEADS_TABLE_SQL)
        ensure_columns(conn)
        create_indexes(conn)


def ensure_columns(conn: sqlite3.Connection) -> None:
    """Add newly introduced columns when an older local database already exists."""
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(leads)").fetchall()
    }

    for column_name, column_type in OPTIONAL_COLUMNS.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {column_name} {column_type}")


def create_indexes(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create helpful indexes for common lead lookup and sorting operations."""
    should_close = False

    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_website ON leads(website)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_opportunity_score ON leads(opportunity_score)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads(industry)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at)")
    finally:
        if should_close:
            conn.close()


def save_lead(
    audit: AuditResult,
    business_name: Optional[str] = None,
    industry: Optional[str] = None,
    source: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_email: Optional[str] = None,
    phone: Optional[str] = None,
    location: Optional[str] = None,
) -> int:
    """Persist one audited website as a prospecting lead."""
    init_db()
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO leads (
                business_name,
                website,
                final_url,
                industry,
                source,
                contact_name,
                contact_email,
                phone,
                location,
                status_code,
                response_time_ms,
                page_size_kb,
                title,
                meta_description,
                detected_platform,
                footer_year,
                stale_footer,
                https_enabled,
                has_viewport,
                has_canonical,
                has_open_graph,
                has_schema,
                has_sitemap,
                has_robots,
                opportunity_score,
                issues_json,
                recommendations_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                business_name,
                audit.url,
                audit.final_url,
                industry,
                source,
                contact_name,
                contact_email,
                phone,
                location,
                audit.status_code,
                audit.response_time_ms,
                audit.page_size_kb,
                audit.title,
                audit.meta_description,
                audit.detected_platform,
                audit.footer_year,
                int(audit.stale_footer),
                int(audit.https_enabled),
                int(audit.has_viewport),
                int(audit.has_canonical),
                int(audit.has_open_graph),
                int(audit.has_schema),
                int(audit.has_sitemap),
                int(audit.has_robots),
                audit.opportunity_score,
                json.dumps(audit.issues, ensure_ascii=False),
                json.dumps(audit.recommendations, ensure_ascii=False),
                now,
                now,
            ),
        )

        return int(cursor.lastrowid)


def get_lead(lead_id: int) -> sqlite3.Row | None:
    """Fetch one lead by ID."""
    init_db()

    with get_connection() as conn:
        return conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()


def list_leads(limit: int = 20) -> list[sqlite3.Row]:
    """Return recently saved leads."""
    init_db()

    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM leads
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def all_leads() -> list[sqlite3.Row]:
    """Return every saved lead for export."""
    init_db()

    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM leads
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
