from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clienthunter import database
from clienthunter.models import AuditResult
from clienthunter.outreach import build_outreach


class DatabaseFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "wireless_bot_test.sqlite3"
        self.previous_db_path = database.DB_PATH
        database.DB_PATH = str(self.db_path)

    def tearDown(self) -> None:
        database.DB_PATH = self.previous_db_path
        self.temp_dir.cleanup()

    def test_can_initialize_save_list_read_pitch_and_export_leads(self) -> None:
        database.init_db()

        audit = AuditResult(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            response_time_ms=420,
            page_size_kb=98.5,
            title="Example Business",
            meta_description="A sample business website.",
            has_viewport=True,
            has_canonical=True,
            has_open_graph=False,
            has_schema=False,
            has_sitemap=True,
            has_robots=True,
            footer_year=2021,
            stale_footer=True,
            detected_platform="WordPress",
            https_enabled=True,
            opportunity_score=72,
            issues=["Footer copyright year appears outdated: 2021"],
            recommendations=["Update footer, content, design, and maintenance workflow."],
        )

        lead_id = database.save_lead(
            audit,
            business_name="Example Business",
            industry="Hotel",
            source="Manual Research",
            contact_name="Manager",
            contact_email="hello@example.com",
            phone="+234000000000",
            location="Akure",
        )

        self.assertIsInstance(lead_id, int)
        self.assertGreater(lead_id, 0)

        saved_lead = database.get_lead(lead_id)
        self.assertIsNotNone(saved_lead)
        self.assertEqual(saved_lead["business_name"], "Example Business")
        self.assertEqual(saved_lead["contact_name"], "Manager")
        self.assertEqual(saved_lead["opportunity_score"], 72)

        recent_leads = database.list_leads(limit=5)
        self.assertEqual(len(recent_leads), 1)

        all_saved_leads = database.all_leads()
        self.assertEqual(len(all_saved_leads), 1)

        outreach = build_outreach(saved_lead)
        self.assertIn("Example Business", outreach["email"])
        self.assertIn("Manager", outreach["email"])
        self.assertIn("Bookings & Customer Enquiry Website Package", outreach["proposal"])


if __name__ == "__main__":
    unittest.main()
