from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .models import AuditResult

load_dotenv()

DB_PATH = Path(os.getenv("CLIENTHUNTER_DB", "clienthunter.sqlite3"))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT,
                website TEXT NOT NULL,
                industry TEXT,
                source TEXT,
                contact_email TEXT,
                phone TEXT,
                location TEXT,
                final_url TEXT,
                status_code INTEGER,
                response_time_ms INTEGER,
                page_size_kb REAL,
                title TEXT,
                meta_description TEXT,
                has_viewport INTEGER,
                has_canonical INTEGER,
                has_open_graph INTEGER,
                has_schema INTEGER,
                has_sitemap INTEGER,
                has_robots INTEGER,
                footer_year INTEGER,
                stale_footer INTEGER,
                detected_platform TEXT,
                https_enabled INTEGER,
                opportunity_score INTEGER,
                issues_json TEXT,
                recommendations_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_lead(
    audit: AuditResult,
    business_name: str | None = None,
    industry: str | None = None,
    source: str | None = None,
    contact_email: str | None = None,
    phone: str | None = None,
    location: str | None = None,
) -> int:
    init_db()

    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO leads (
                business_name,
                website,
                industry,
                source,
                contact_email,
                phone,
                location,
                final_url,
                status_code,
                response_time_ms,
                page_size_kb,
                title,
                meta_description,
                has_viewport,
                has_canonical,
                has_open_graph,
                has_schema,
                has_sitemap,
                has_robots,
                footer_year,
                stale_footer,
                detected_platform,
                https_enabled,
                opportunity_score,
                issues_json,
                recommendations_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                business_name,
                audit.url,
                industry,
                source,
                contact_email,
                phone,
                location,
                audit.final_url,
                audit.status_code,
                audit.response_time_ms,
                audit.page_size_kb,
                audit.title,
                audit.meta_description,
                int(audit.has_viewport),
                int(audit.has_canonical),
                int(audit.has_open_graph),
                int(audit.has_schema),
                int(audit.has_sitemap),
                int(audit.has_robots),
                audit.footer_year,
                int(audit.stale_footer),
                audit.detected_platform,
                int(audit.https_enabled),
                audit.opportunity_score,
                json.dumps(audit.issues),
                json.dumps(audit.recommendations),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_lead(lead_id: int) -> sqlite3.Row | None:
    init_db()

    with connect() as conn:
        return conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()


def list_leads(limit: int = 20) -> list[sqlite3.Row]:
    init_db()

    with connect() as conn:
        return conn.execute(
            """
            SELECT id, business_name, website, industry, opportunity_score, footer_year, stale_footer, created_at
            FROM leads
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def all_leads() -> list[sqlite3.Row]:
    init_db()

    with connect() as conn:
        return conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
