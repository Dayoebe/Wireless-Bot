from __future__ import annotations

import os
import re
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from .models import AuditResult
from .utils import current_year, extract_years, normalize_url, truncate

load_dotenv()

DEFAULT_USER_AGENT = os.getenv(
    "CLIENTHUNTER_USER_AGENT",
    "WirelessBot/0.1 (+https://github.com/Dayoebe/Wireless-Bot)",
)


class WebsiteAuditor:
    def __init__(self, timeout: int = 15, user_agent: str = DEFAULT_USER_AGENT):
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.max_redirects = 10

    def audit(self, url: str) -> AuditResult:
        normalized_url = normalize_url(url)
        parsed = urlparse(normalized_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        has_robots = self._check_exists(urljoin(base_url, "/robots.txt"))
        has_sitemap = self._check_exists(urljoin(base_url, "/sitemap.xml"))

        if has_robots and not self._allowed_by_robots(base_url, normalized_url):
            return AuditResult(
                url=normalized_url,
                final_url=normalized_url,
                status_code=0,
                response_time_ms=0,
                page_size_kb=0,
                title=None,
                meta_description=None,
                has_viewport=False,
                has_canonical=False,
                has_open_graph=False,
                has_schema=False,
                has_sitemap=has_sitemap,
                has_robots=has_robots,
                footer_year=None,
                stale_footer=False,
                detected_platform=None,
                https_enabled=normalized_url.startswith("https://"),
                opportunity_score=40,
                issues=["Website blocks crawling through robots.txt"],
                recommendations=["Review this website manually before outreach."],
            )

        start = time.perf_counter()

        try:
            response = self.session.get(
                normalized_url,
                timeout=self.timeout,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            return AuditResult(
                url=normalized_url,
                final_url=normalized_url,
                status_code=0,
                response_time_ms=0,
                page_size_kb=0,
                title=None,
                meta_description=None,
                has_viewport=False,
                has_canonical=False,
                has_open_graph=False,
                has_schema=False,
                has_sitemap=has_sitemap,
                has_robots=has_robots,
                footer_year=None,
                stale_footer=False,
                detected_platform=None,
                https_enabled=normalized_url.startswith("https://"),
                opportunity_score=75,
                issues=[f"Could not load website: {exc}"],
                recommendations=["This business may need technical support if the website is down or misconfigured."],
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        html = response.text or ""
        soup = BeautifulSoup(html, "html.parser")

        title = self._get_title(soup)
        meta_description = self._get_meta_content(soup, "description")
        has_viewport = self._has_meta_name(soup, "viewport")
        has_canonical = bool(soup.find("link", rel=lambda value: value and "canonical" in value))
        has_open_graph = bool(soup.find("meta", property=lambda value: value and value.startswith("og:")))
        has_schema = bool(soup.find("script", attrs={"type": "application/ld+json"}))

        footer_year = self._get_footer_year(soup)
        stale_footer = bool(footer_year and footer_year < current_year())
        detected_platform = self._detect_platform(html, soup, response.headers)
        https_enabled = response.url.startswith("https://")
        page_size_kb = round(len(response.content) / 1024, 2)

        issues, recommendations = self._build_findings(
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            title=title,
            meta_description=meta_description,
            has_viewport=has_viewport,
            has_canonical=has_canonical,
            has_open_graph=has_open_graph,
            has_schema=has_schema,
            has_sitemap=has_sitemap,
            has_robots=has_robots,
            footer_year=footer_year,
            stale_footer=stale_footer,
            https_enabled=https_enabled,
            page_size_kb=page_size_kb,
        )

        score = self._score_opportunity(issues)

        return AuditResult(
            url=normalized_url,
            final_url=response.url,
            status_code=response.status_code,
            response_time_ms=elapsed_ms,
            page_size_kb=page_size_kb,
            title=truncate(title, 140),
            meta_description=truncate(meta_description, 220),
            has_viewport=has_viewport,
            has_canonical=has_canonical,
            has_open_graph=has_open_graph,
            has_schema=has_schema,
            has_sitemap=has_sitemap,
            has_robots=has_robots,
            footer_year=footer_year,
            stale_footer=stale_footer,
            detected_platform=detected_platform,
            https_enabled=https_enabled,
            opportunity_score=score,
            issues=issues,
            recommendations=recommendations,
        )

    def _allowed_by_robots(self, base_url: str, target_url: str) -> bool:
        parser = urllib.robotparser.RobotFileParser()
        robots_url = urljoin(base_url, "/robots.txt")
        try:
            r = self.session.get(robots_url, timeout=min(8, self.timeout), allow_redirects=True)
            if r.status_code >= 400 or not r.text.strip():
                return True
            parser.parse(r.text.splitlines())
            return parser.can_fetch(self.headers["User-Agent"], target_url)
        except Exception:
            return True

    def _check_exists(self, url: str) -> bool:
        try:
            r = self.session.get(url, timeout=8, allow_redirects=True)
            return r.status_code < 400 and bool(r.text.strip())
        except requests.RequestException:
            return False

    def _get_title(self, soup: BeautifulSoup) -> str | None:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        return None

    def _get_meta_content(self, soup: BeautifulSoup, name: str) -> str | None:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
        return None

    def _has_meta_name(self, soup: BeautifulSoup, name: str) -> bool:
        return bool(soup.find("meta", attrs={"name": name}))

    def _get_footer_year(self, soup: BeautifulSoup) -> int | None:
        footer_texts = []
        for footer in soup.find_all("footer"):
            footer_texts.append(footer.get_text(" ", strip=True))
        copyright_candidates = soup.find_all(
            string=lambda text: text and ("©" in text or "copyright" in text.lower())
        )
        footer_texts.extend(str(text) for text in copyright_candidates)
        text = " ".join(footer_texts)
        years = extract_years(text)
        if not years:
            body_text = soup.get_text(" ", strip=True)
            years = extract_years(body_text[-2000:])
        return max(years) if years else None

    def _detect_platform(self, html: str, soup: BeautifulSoup, headers: dict) -> str | None:
        lower_html = html.lower()
        generator = soup.find("meta", attrs={"name": "generator"})
        if generator and generator.get("content"):
            return generator["content"].strip()
        platform_signals = {
            "WordPress": ["wp-content", "wp-includes"],
            "Shopify": ["cdn.shopify.com", "myshopify"],
            "Wix": ["wixstatic", "wix.com"],
            "Squarespace": ["squarespace.com", "static1.squarespace.com"],
            "Drupal": ["drupal-settings-json", "sites/default/files"],
            "Joomla": ['content="joomla', "/media/system/js/"],
            "Laravel": ["laravel_session"],
            "Webflow": ["webflow.js", "webflow.com"],
        }
        header_text = " ".join(f"{key}: {value}" for key, value in headers.items()).lower()
        for platform, signals in platform_signals.items():
            if any(signal in lower_html or signal in header_text for signal in signals):
                return platform
        return None

    def _build_findings(
        self,
        status_code: int,
        elapsed_ms: int,
        title: str | None,
        meta_description: str | None,
        has_viewport: bool,
        has_canonical: bool,
        has_open_graph: bool,
        has_schema: bool,
        has_sitemap: bool,
        has_robots: bool,
        footer_year: int | None,
        stale_footer: bool,
        https_enabled: bool,
        page_size_kb: float,
    ) -> tuple[list[str], list[str]]:
        issues = []
        recommendations = []
        if status_code >= 400:
            issues.append(f"Homepage returns HTTP {status_code}")
            recommendations.append("Fix homepage availability and server response issues.")
        if elapsed_ms > 3000:
            issues.append(f"Homepage is slow to respond: {elapsed_ms}ms")
            recommendations.append("Improve hosting, caching, image optimization, and frontend asset loading.")
        if page_size_kb > 2500:
            issues.append(f"Homepage is heavy: {page_size_kb}KB")
            recommendations.append("Compress images and reduce unused scripts/styles.")
        if not https_enabled:
            issues.append("Website is not using HTTPS")
            recommendations.append("Install SSL and redirect all traffic to HTTPS.")
        if not title:
            issues.append("Missing page title")
            recommendations.append("Add a strong SEO title that explains the business clearly.")
        if not meta_description:
            issues.append("Missing meta description")
            recommendations.append("Add a persuasive meta description for search and social previews.")
        if not has_viewport:
            issues.append("Missing mobile viewport tag")
            recommendations.append("Improve mobile responsiveness and add proper viewport configuration.")
        if not has_canonical:
            issues.append("Missing canonical link")
            recommendations.append("Add canonical URLs to reduce SEO duplication issues.")
        if not has_open_graph:
            issues.append("Missing Open Graph social sharing tags")
            recommendations.append("Add Open Graph metadata for better previews on Facebook, LinkedIn, and WhatsApp.")
        if not has_schema:
            issues.append("Missing structured data/schema markup")
            recommendations.append("Add business/schema markup to improve search understanding.")
        if not has_sitemap:
            issues.append("Missing sitemap.xml")
            recommendations.append("Create and submit sitemap.xml to improve indexing.")
        if not has_robots:
            issues.append("Missing robots.txt")
            recommendations.append("Add a robots.txt file with sitemap reference.")
        if stale_footer:
            issues.append(f"Footer copyright year appears outdated: {footer_year}")
            recommendations.append("Update footer, content, design, and maintenance workflow.")
        if not issues:
            recommendations.append(
                "Website has strong basic signals. Look for deeper UX, conversion, and business automation opportunities."
            )
        return issues, recommendations

    def _score_opportunity(self, issues: list[str]) -> int:
        score = 25
        issue_weights = {
            "outdated": 18,
            "slow": 12,
            "heavy": 8,
            "https": 10,
            "title": 8,
            "description": 8,
            "mobile": 12,
            "canonical": 4,
            "open graph": 5,
            "structured": 5,
            "sitemap": 6,
            "robots": 3,
            "http": 10,
            "could not load": 20,
        }
        text = " ".join(issues).lower()
        for keyword, weight in issue_weights.items():
            if re.search(r"\b" + re.escape(keyword) + r"\b", text):
                score += weight
        return max(0, min(100, score))
