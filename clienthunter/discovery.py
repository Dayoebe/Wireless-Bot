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

INDUSTRY_OSM_TAGS: dict[str, list[tuple[str, str]]] = {
    "school": [("amenity", "school")],
    "schools": [("amenity", "school")],
    "clinic": [("amenity", "clinic"), ("amenity", "doctors"), ("healthcare", "clinic")],
    "hospital": [("amenity", "hospital"), ("healthcare", "hospital")],
    "hotel": [("tourism", "hotel"), ("tourism", "guest_house")],
    "restaurant": [("amenity", "restaurant"), ("amenity", "fast_food")],
    "real estate": [("office", "estate_agent")],
    "bank": [("amenity", "bank")],
    "pharmacy": [("amenity", "pharmacy"), ("healthcare", "pharmacy")],
    "church": [("amenity", "place_of_worship")],
}


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
        seen_domains: set[str] = set()
        seen_names: set[str] = set()

        for candidate in self._discover_from_openstreetmap(industry, location, keywords):
            key = normalized_domain(candidate.website) or candidate.business_name.lower()
            if key in seen_domains or candidate.business_name.lower() in seen_names:
                continue

            seen_domains.add(key)
            seen_names.add(candidate.business_name.lower())
            candidates.append(candidate)

            if len(candidates) >= max_results:
                return candidates

        fallback_candidates: list[LeadCandidate] = []

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

    def _discover_from_openstreetmap(
        self,
        industry: str,
        location: str,
        keywords: str,
    ) -> list[LeadCandidate]:
        if not location:
            self.last_debug.append("OpenStreetMap skipped: location is required")
            return []

        try:
            area_id = self._resolve_osm_area_id(location)
        except Exception as exc:
            self.last_debug.append(f"OpenStreetMap area lookup failed: {exc}")
            return []

        if area_id is None:
            self.last_debug.append(f"OpenStreetMap area lookup returned no area for {location!r}")
            return []

        tags = osm_tags_for_industry(industry)
        if not tags:
            self.last_debug.append(f"OpenStreetMap skipped: no OSM tag mapping for {industry!r}")
            return []

        query = build_overpass_query(area_id, tags)

        try:
            response = self.session.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                timeout=self.timeout + 20,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            self.last_debug.append(f"OpenStreetMap Overpass lookup failed: {exc}")
            return []

        elements = payload.get("elements", [])
        self.last_debug.append(f"OpenStreetMap: {len(elements)} mapped {industry} result(s) around {location}")

        candidates: list[LeadCandidate] = []
        for element in elements:
            tags_data = element.get("tags", {})
            name = clean_text(tags_data.get("name"))
            if not name:
                continue

            website = first_non_empty(
                tags_data.get("website"),
                tags_data.get("contact:website"),
                tags_data.get("url"),
            )
            website = normalize_result_url(website) if website else ""
            phone = first_non_empty(tags_data.get("phone"), tags_data.get("contact:phone"))
            email = first_non_empty(tags_data.get("email"), tags_data.get("contact:email"))
            address = format_osm_address(tags_data)
            manual_query = build_business_research_query(name, industry, location, keywords)

            snippet_parts = [part for part in [address, phone, email] if part]
            if not website:
                snippet_parts.append("No website listed in OpenStreetMap; use research links before outreach.")

            candidates.append(
                LeadCandidate(
                    business_name=name,
                    website=website,
                    industry=industry,
                    location=location,
                    source="OpenStreetMap",
                    search_query=manual_query,
                    title=name,
                    snippet=truncate(" | ".join(snippet_parts), 240),
                )
            )

        return candidates

    def _resolve_osm_area_id(self, location: str) -> int | None:
        query = f"{location}, Nigeria"
        response = self.session.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 1},
            timeout=self.timeout,
        )
        response.raise_for_status()
        results = response.json()

        if not results:
            return None

        osm_type = results[0].get("osm_type")
        osm_id = int(results[0].get("osm_id"))

        if osm_type == "relation":
            return 3600000000 + osm_id
        if osm_type == "way":
            return 2400000000 + osm_id
        if osm_type == "node":
            return 3600000000 + osm_id

        return None

    def _search_all(self, query: str) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []

        for searcher in (self._search_duckduckgo_html, self._search_duckduckgo_lite, self._search_bing):
            try:
                searcher_results = searcher(query)
                self.last_debug.append(f"{searcher.__name__}: {len(searcher_results)} result(s)")
                results.extend(searcher_results)
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
                f"{industry} {location} site:.com",
                f"{industry} {location} site:.com.ng",
            ]
        )

    return dedupe_texts(queries)


def build_manual_search_links(industry: str, location: str = "", keywords: str = "") -> list[dict[str, str]]:
    """Build one-click search links when automatic scraping returns no candidates."""
    queries = build_search_queries(industry, location, keywords)[:5]
    links: list[dict[str, str]] = []

    for query in queries:
        encoded = quote_plus(query)
        links.extend(
            [
                {"source": "Google", "query": query, "url": f"https://www.google.com/search?q={encoded}"},
                {"source": "Bing", "query": query, "url": f"https://www.bing.com/search?q={encoded}"},
                {"source": "DuckDuckGo", "query": query, "url": f"https://duckduckgo.com/?q={encoded}"},
            ]
        )

    return links


def build_business_research_links(candidate: LeadCandidate) -> list[dict[str, str]]:
    query = build_business_research_query(
        candidate.business_name,
        candidate.industry,
        candidate.location,
        "website contact",
    )
    encoded = quote_plus(query)
    return [
        {"source": "Google", "query": query, "url": f"https://www.google.com/search?q={encoded}"},
        {"source": "Bing", "query": query, "url": f"https://www.bing.com/search?q={encoded}"},
        {"source": "DuckDuckGo", "query": query, "url": f"https://duckduckgo.com/?q={encoded}"},
    ]


def build_business_research_query(name: str, industry: str, location: str, keywords: str = "") -> str:
    return clean_text(f"{name} {industry} {location} {keywords} official website contact")


def osm_tags_for_industry(industry: str) -> list[tuple[str, str]]:
    key = clean_text(industry).lower()
    if key in INDUSTRY_OSM_TAGS:
        return INDUSTRY_OSM_TAGS[key]

    for known_key, tags in INDUSTRY_OSM_TAGS.items():
        if known_key in key or key in known_key:
            return tags

    return []


def build_overpass_query(area_id: int, tags: list[tuple[str, str]]) -> str:
    clauses = []
    for key, value in tags:
        clauses.extend(
            [
                f'node["{key}"="{value}"](area.searchArea);',
                f'way["{key}"="{value}"](area.searchArea);',
                f'relation["{key}"="{value}"](area.searchArea);',
            ]
        )

    return f"""
    [out:json][timeout:25];
    area({area_id})->.searchArea;
    (
      {''.join(clauses)}
    );
    out center tags 50;
    """


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
    noise_words = ("official website", "home page", "homepage", "welcome to", "best", "contact us")
    cleaned = value.strip()

    for noise in noise_words:
        cleaned = re.sub(rf"\b{re.escape(noise)}\b", "", cleaned, flags=re.IGNORECASE)

    return clean_text(cleaned)


def format_osm_address(tags_data: dict[str, str]) -> str:
    parts = [
        tags_data.get("addr:housenumber"),
        tags_data.get("addr:street"),
        tags_data.get("addr:suburb"),
        tags_data.get("addr:city"),
        tags_data.get("addr:state"),
    ]
    return clean_text(", ".join(part for part in parts if part)
    )


def first_non_empty(*values: str | None) -> str:
    for value in values:
        cleaned = clean_text(value)
        if cleaned:
            return cleaned
    return ""


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
