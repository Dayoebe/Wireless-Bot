from __future__ import annotations

import unittest

from clienthunter.discovery import (
    build_search_queries,
    infer_business_name,
    is_probably_business_website,
    parse_duckduckgo_results,
)


class DiscoveryTest(unittest.TestCase):
    def test_build_search_queries_uses_industry_location_and_keywords(self) -> None:
        queries = build_search_queries("Hotel", "Akure", "booking")

        self.assertIn("Hotel Akure booking official website", queries)
        self.assertIn("Hotel in Akure official website", queries)

    def test_parse_duckduckgo_results_extracts_uddg_url(self) -> None:
        html = """
        <html>
            <body>
                <div class="result">
                    <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexamplehotel.com%2F&amp;rut=abc">
                        Example Hotel - Official Website
                    </a>
                    <a class="result__snippet">Book rooms and contact Example Hotel.</a>
                </div>
            </body>
        </html>
        """

        results = parse_duckduckgo_results(html)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://examplehotel.com")
        self.assertEqual(results[0]["title"], "Example Hotel - Official Website")
        self.assertIn("Book rooms", results[0]["snippet"])

    def test_filters_non_business_websites(self) -> None:
        self.assertFalse(is_probably_business_website("https://facebook.com/example"))
        self.assertFalse(is_probably_business_website("https://example.com/brochure.pdf"))
        self.assertTrue(is_probably_business_website("https://examplehotel.com"))

    def test_infer_business_name_from_title_or_domain(self) -> None:
        self.assertEqual(
            infer_business_name("Example Hotel - Official Website", "examplehotel.com"),
            "Example Hotel",
        )
        self.assertEqual(
            infer_business_name("", "my-sample-clinic.com"),
            "My Sample Clinic",
        )


if __name__ == "__main__":
    unittest.main()
