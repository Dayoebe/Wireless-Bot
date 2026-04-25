from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .database import all_leads


def export_leads(output_dir: str = "exports") -> Path:
    rows = all_leads()
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    filename = f"wireless_bot_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output_path = Path(output_dir) / filename

    if not rows:
        output_path.write_text("", encoding="utf-8")
        return output_path

    fieldnames = rows[0].keys()

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(dict(row))

    return output_path
