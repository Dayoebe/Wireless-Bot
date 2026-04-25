from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse


def current_year() -> int:
    return datetime.now().year


def normalize_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        raise ValueError("URL cannot be empty")

    if not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned

    parsed = urlparse(cleaned)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")

    return cleaned.rstrip("/")


def extract_years(text: str) -> list[int]:
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text or "")
    return [int(year) for year in years]


def truncate(value: str | None, length: int = 180) -> str:
    if not value:
        return ""
    value = " ".join(value.split())
    return value if len(value) <= length else value[: length - 3] + "..."


def safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
