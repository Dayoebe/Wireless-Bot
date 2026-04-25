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
VALID_LEAD_STATUSES = ("new", "contacted", "replied", "won", "lost")


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
    address TEXT,
    prospect_type TEXT NOT NULL DEFAULT 'website',
    status TEXT NOT NULL DEFAULT 'new',
    status_updated_at TEXT,
    notes TEXT,
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
    "address": "TEXT",
    "prospect_type": "TEXT NOT NULL DEFAULT 'website'",
    "status": "TEXT NOT NULL DEFAULT 'new'",
    "status_updated_at": "TEXT",
    "notes": "TEXT",
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
        normalize_existing_statuses(conn)
        normalize_existing_prospect_types(conn)
        create_indexes(conn)


def ensure_columns(conn: sqlite3.Connection) -> None:
    """Add newly introduced columns when an older local database already exists."""
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(leads)").fetchall()
    }

    for column_name, column_type in OPTIONAL_COLUMNS.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {column_name} {column_type}")


def normalize_existing_statuses(conn: sqlite3.Connection) -> None:
    """Keep old rows usable after status tracking is introduced."""
    now = datetime.now().isoformat(timespec="seconds")
    placeholders = ", ".join("?" for _ in VALID_LEAD_STATUSES)

    conn.execute(
        "UPDATE leads SET status = 'new' WHERE status IS NULL OR TRIM(status) = ''"
    )
    conn.execute(
        f"UPDATE leads SET status = 'new' WHERE LOWER(status) NOT IN ({placeholders})",
        VALID_LEAD_STATUSES,
    )
    conn.execute(
        """
        UPDATE leads
        SET status_updated_at = COALESCE(status_updated_at, created_at, ?)
        WHERE status_updated_at IS NULL OR TRIM(status_updated_at) = ''
        """,
        (now,),
    )


def normalize_existing_prospect_types(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE leads
        SET prospect_type = CASE
            WHEN website IS NULL OR TRIM(website) = '' THEN 'business'
            ELSE COALESCE(NULLIF(TRIM(prospect_type), ''), 'website')
        END
        """
    )


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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_prospect_type ON leads(prospect_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at)")
    finally:
        if should_close:
            conn.close()


def normalize_status(status: Optional[str]) -> str:
    """Validate and normalize lead status values."""
    normalized = (status or "new").strip().lower()

    if normalized not in VALID_LEAD_STATUSES:
        allowed = ", ".join(VALID_LEAD_STATUSES)
        raise ValueError(f"Invalid lead status: {status!r}. Allowed statuses: {allowed}.")

    return normalized


def save_lead(
    audit: AuditResult,
    business_name: Optional[str] = None,
    industry: Optional[str] = None,
    source: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_email: Optional[str] = None,
    phone: Optional[str] = None,
    location: Optional[str] = None,
    address: Optional[str] = None,
    status: Optional[str] = "new",
    notes: Optional[str] = None,
) -> int:
    """Persist one audited website as a prospecting lead."""
    init_db()
    now = datetime.now().isoformat(timespec="seconds")
    normalized_status = normalize_status(status)

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
                address,
                prospect_type,
                status,
                status_updated_at,
                notes,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                address,
                "website",
                normalized_status,
                now,
                notes,
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


def save_prospect(
    business_name: str,
    industry: Optional[str] = None,
    source: Optional[str] = None,
    website: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_email: Optional[str] = None,
    phone: Optional[str] = None,
    location: Optional[str] = None,
    address: Optional[str] = None,
    status: Optional[str] = "new",
    notes: Optional[str] = None,
) -> int:
    """Save a business prospect even when there is no website to audit yet."""
    init_db()
    now = datetime.now().isoformat(timespec="seconds")
    normalized_status = normalize_status(status)
    clean_website = (website or "").strip()
    prospect_type = "website" if clean_website else "business"
    opportunity_score = 65 if clean_website else 80

    default_notes = []
    if notes:
        default_notes.append(notes)
    if not clean_website:
        default_notes.append("No website found yet. This may be a stronger website-design prospect.")
    if phone:
        default_notes.append(f"Phone available: {phone}")
    if contact_email:
        default_notes.append(f"Email available: {contact_email}")

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
                address,
                prospect_type,
                status,
                status_updated_at,
                notes,
                status_code,
                opportunity_score,
                issues_json,
                recommendations_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                business_name,
                clean_website,
                clean_website,
                industry,
                source,
                contact_name,
                contact_email,
                phone,
                location,
                address,
                prospect_type,
                normalized_status,
                now,
                "\n".join(default_notes),
                None,
                opportunity_score,
                json.dumps(
                    ["No website found yet"] if not clean_website else ["Website discovered but not audited yet"],
                    ensure_ascii=False,
                ),
                json.dumps(
                    [
                        "Research the business contact details and pitch a new website or digital upgrade."
                    ]
                    if not clean_website
                    else ["Audit the website before sending a final proposal."],
                    ensure_ascii=False,
                ),
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


def update_lead_status(
    lead_id: int,
    status: str,
    notes: Optional[str] = None,
) -> sqlite3.Row | None:
    """Update a lead's pipeline status and optional notes."""
    init_db()
    normalized_status = normalize_status(status)
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection() as conn:
        existing = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()

        if existing is None:
            return None

        if notes is None:
            conn.execute(
                """
                UPDATE leads
                SET status = ?, status_updated_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (normalized_status, now, now, lead_id),
            )
        else:
            conn.execute(
                """
                UPDATE leads
                SET status = ?, status_updated_at = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (normalized_status, now, notes, now, lead_id),
            )

        return conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()


def delete_lead(lead_id: int) -> bool:
    """Delete one saved lead permanently."""
    init_db()

    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        return cursor.rowcount > 0
