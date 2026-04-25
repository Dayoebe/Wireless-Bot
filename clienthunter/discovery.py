from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from html import unescape
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

from .utils import normalize_url, truncate

DEFAULT_DISCOVERY_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36 WirelessBot/0.1"
)

EXCLUDED_DOMAINS = (
    "duckduckgo.com",
    "google.com",
    "google.com.ng",
    "maps.google.com",
    "bing.com",
    "yahoo.com",
    "facebook.com",
    "fb.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "pinterest.com",
    "tripadvisor.com",
    "wikipedia.org",
    "foursquare.com",
    "nairaland.com",
)

SOFT_DIRECTORY_DOMAINS = (
    "businesslist.com.ng",
    "finelib.com",
    "vconnect.com",
    "yellowpages.com",
    "ng-check.com",
    "cybo.com",
)

IGNORED_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
)


@dataclass(frozen=True)
class LeadCandidate:
    business_name: str
    website: str
    industry: str
    location: str
    source: str
    search_query: str
    title: str
    snippet: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class LeadDiscovery:
    """Discover likely business websites from industry/location search terms."""

    def __init__(self, timeout: int = 15, user_agent: str = DEFAULT_DISCOVERY_USER_AGENT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self.last_debug: list[str] = []

    def discover(
        self,
        industry: str,
        location: str = "",
        keywords: str = "",
        max_results: int = 10,
    ) -> list[LeadCandidate]:
        industry = clean_text(industry)
        location = clean_text(location)
        keywords = clean_text(keywords)
        self.last_debug = []

        if not industry:
            raise ValueError("Industry is required for lead discovery.")

        candidates: list[LeadCandidate] = []
        fallback_candidates: list[LeadCandidate] = []
        seen_domains: set[str] = set()

        for query in build_search_queries(industry, location, keywords):
            search_results = self._search_all(query)
            self.last_debug.append(f"{query}: {len(search_results)} raw result(s)")

            for result in search_results:
                website = result.get("url", "")
                if not website:
                    continue

                domain = normalized_domain(website)
                if not domain or domain in seen_domains:
                    continue

                title = clean_text(result.get("title", ""))
                snippet = clean_text(result.get("snippet", ""))
                business_name = infer_business_name(title, domain)
                candidate = LeadCandidate(
                    business_name=business_name,
                    website=website,
                    industry=industry,
                    location=location,
                    source=result.get("source") or "Web Discovery",
                    search_query=query,
                    title=title,
                    snippet=truncate(snippet, 240),
                )

                if is_probably_business_website(website):
                    seen_domains.add(domain)
                    candidates.append(candidate)
                    if len(candidates) >= max_results:
                        return candidates
                elif is_soft_directory_url(website):
                    fallback_candidates.append(candidate)

        if candidates:
            return candidates[:max_results]

        # If direct websites are scarce, return directory-like candidates instead of showing a blank page.
        # These should be reviewed manually before outreach.
        deduped_fallbacks: list[LeadCandidate] = []
        fallback_seen: set[str] = set()
        for candidate in fallback_candidates:
            domain = normalized_domain(candidate.website)
            if domain and domain not in fallback_seen:
                fallback_seen.add(domain)
                deduped_fallbacks.append(candidate)
            if len(deduped_fallbacks) >= max_results:
                break

        return deduped_fallbacks

    def _search_all(self, query: str) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []

        for searcher in (self._search_duckduckgo_html, self._search_duckduckgo_lite, self._search_bing):
            try:
                results.extend(searcher(query))
            except requests.RequestException as exc:
                self.last_debug.append(f"{searcher.__name__} failed: {exc}")
            except Exception as exc:
                self.last_debug.append(f"{searcher.__name__} parse failed: {exc}")

        return dedupe_results(results)

    def _search_duckduckgo_html(self, query: str) -> list[dict[str, str]]:
        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return add_source(parse_duckduckgo_results(response.text), "DuckDuckGo")

    def _search_duckduckgo_lite(self, query: str) -> list[dict[str, str]]:
        url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return add_source(parse_generic_results(response.text), "DuckDuckGo Lite")

    def _search_bing(self, query: str) -> list[dict[str, str]]:
        url = f"https://www.bing.com/search?q={quote_plus(query)}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return add_source(parse_bing_results(response.text), "Bing")


def build_search_queries(industry: str, location: str = "", keywords: str = "") -> list[str]:
    base_parts = [industry]

    if location:
        base_parts.append(location)

    if keywords:
        base_parts.append(keywords)

    base = " ".join(base_parts).strip()

    queries = [
        f"{base} official website",
        f"{base} contact website",
        f"{base} company website",
        f"{base} business website",
    ]

    if location:
        queries.extend(
            [
                f"{industry} in {location} official website",
                f"{industry} companies in {location} website",
                f"{industry} {location} contact",
            ]
        )

    return dedupe_texts(queries)


def parse_duckduckgo_results(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []

    for link in soup.select("a.result__a"):
        raw_url = link.get("href", "")
        resolved_url = resolve_duckduckgo_url(raw_url)
        title = clean_text(link.get_text(" ", strip=True))
        snippet = ""

        result_container = link.find_parent("div", class_=re.compile("result"))
        if result_container:
            snippet_tag = result_container.select_one(".result__snippet")
            if snippet_tag:
                snippet = clean_text(snippet_tag.get_text(" ", strip=True))

        if title and resolved_url:
            results.append({"title": title, "url": resolved_url, "snippet": snippet})

    if results:
        return results

    return parse_generic_results(html)


def parse_bing_results(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []

    for item in soup.select("li.b_algo"):
        link = item.find("a", href=True)
        if not link:
            continue

        title = clean_text(link.get_text(" ", strip=True))
        url = normalize_result_url(link.get("href", ""))
        snippet_tag = item.find("p")
        snippet = clean_text(snippet_tag.get_text(" ", strip=True)) if snippet_tag else ""

        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})

    if results:
        return results

    return parse_generic_results(html)


def parse_generic_results(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []

    for link in soup.find_all("a", href=True):
        title = clean_text(link.get_text(" ", strip=True))
        resolved_url = resolve_duckduckgo_url(link["href"]) or normalize_result_url(link["href"])

        if title and resolved_url:
            results.append({"title": title, "url": resolved_url, "snippet": ""})

    return dedupe_results(results)


def resolve_duckduckgo_url(raw_url: str) -> str:
    if not raw_url:
        return ""

    raw_url = unescape(raw_url)

    if raw_url.startswith("//"):
        raw_url = "https:" + raw_url

    parsed = urlparse(raw_url)
    query = parse_qs(parsed.query)

    if "uddg" in query and query["uddg"]:
        raw_url = query["uddg"][0]

    return normalize_result_url(raw_url)


def normalize_result_url(raw_url: str) -> str:
    if not raw_url:
        return ""

    raw_url = unescape(raw_url).strip()

    if raw_url.startswith("//"):
        raw_url = "https:" + raw_url

    if not raw_url.startswith(("http://", "https://")):
        return ""

    try:
        return normalize_url(raw_url)
    except ValueError:
        return ""


def is_probably_business_website(url: str) -> bool:
    parsed = urlparse(url)
    domain = normalized_domain(url)

    if not domain:
        return False

    if any(domain == excluded or domain.endswith(f".{excluded}") for excluded in EXCLUDED_DOMAINS):
        return False

    if any(domain == directory or domain.endswith(f".{directory}") for directory in SOFT_DIRECTORY_DOMAINS):
        return False

    if parsed.path.lower().endswith(IGNORED_EXTENSIONS):
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    return True


def is_soft_directory_url(url: str) -> bool:
    domain = normalized_domain(url)
    return any(domain == directory or domain.endswith(f".{directory}") for directory in SOFT_DIRECTORY_DOMAINS)


def normalized_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower().strip()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def infer_business_name(title: str, domain: str) -> str:
    title = clean_text(title)

    if title:
        parts = re.split(r"\s+[|–—-]\s+|:\s+", title)
        candidate = clean_text(parts[0]) if parts else title
        candidate = remove_common_title_noise(candidate)

        if len(candidate) >= 2:
            return candidate

    domain_without_tld = domain.split(".")[0]
    return domain_without_tld.replace("-", " ").replace("_", " ").title()


def remove_common_title_noise(value: str) -> str:
    noise_words = (
        "official website",
        "home page",
        "homepage",
        "welcome to",
        "best",
        "contact us",
    )

    cleaned = value.strip()

    for noise in noise_words:
        cleaned = re.sub(rf"\b{re.escape(noise)}\b", "", cleaned, flags=re.IGNORECASE)

    return clean_text(cleaned)


def clean_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def dedupe_texts(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []

    for value in values:
        cleaned = clean_text(value)
        key = cleaned.lower()

        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)

    return output


def dedupe_results(results: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    output: list[dict[str, str]] = []

    for result in results:
        url = result.get("url", "")
        domain = normalized_domain(url)
        key = domain or url

        if not key or key in seen:
            continue

        seen.add(key)
        output.append(result)

    return output


def add_source(results: list[dict[str, str]], source: str) -> list[dict[str, str]]:
    for result in results:
        result["source"] = source
    return results
