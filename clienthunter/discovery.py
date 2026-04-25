from __future__ import annotations

import base64
import re
from dataclasses import asdict, dataclass
from html import unescape
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .utils import normalize_url, truncate

DEFAULT_DISCOVERY_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36 WirelessBot/0.4"
)

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
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
    "school": [("amenity", "school"), ("amenity", "college"), ("amenity", "university")],
    "schools": [("amenity", "school"), ("amenity", "college"), ("amenity", "university")],
    "college": [("amenity", "college"), ("amenity", "school")],
    "clinic": [("amenity", "clinic"), ("amenity", "doctors"), ("healthcare", "clinic")],
    "hospital": [("amenity", "hospital"), ("healthcare", "hospital")],
    "hotel": [("tourism", "hotel"), ("tourism", "guest_house"), ("tourism", "motel")],
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
    phone: str = ""
    email: str = ""
    address: str = ""
    confidence: str = "research"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class LeadDiscovery:
    """Discover business prospects from map data and search results."""

    def __init__(
        self,
        timeout: int = 8,
        user_agent: str = DEFAULT_DISCOVERY_USER_AGENT,
        enable_deep_search: bool = False,
    ):
        self.timeout = timeout
        self.enable_deep_search = enable_deep_search
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
        directory_fallbacks: list[LeadCandidate] = []
        seen_keys: set[str] = set()

        for source_candidates in (
            self._discover_from_openstreetmap(industry, location, keywords),
            self._discover_from_nominatim(industry, location, keywords),
        ):
            for candidate in source_candidates:
                key = candidate_key(candidate)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                candidates.append(candidate)
                if len(candidates) >= max_results:
                    return candidates

        search_queries = build_search_queries(industry, location, keywords)
        if not self.enable_deep_search:
            search_queries = search_queries[:3]

        for query in search_queries:
            search_results = self._search_all(query)
            self.last_debug.append(f"{query}: {len(search_results)} raw result(s)")

            for result in search_results:
                website = result.get("url", "")
                if not website:
                    continue

                domain = normalized_domain(website)
                if not domain:
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
                    confidence="website",
                )

                key = candidate_key(candidate)
                if key in seen_keys:
                    continue

                if is_probably_business_website(website):
                    seen_keys.add(key)
                    candidates.append(candidate)
                    if len(candidates) >= max_results:
                        return candidates
                elif is_soft_directory_url(website):
                    directory_fallbacks.append(candidate)

        for candidate in directory_fallbacks:
            key = candidate_key(candidate)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            candidates.append(candidate)
            if len(candidates) >= max_results:
                break

        return candidates[:max_results]

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

        payload = self._fetch_overpass(build_overpass_query(area_id, tags))
        if payload is None:
            return []

        elements = payload.get("elements", [])
        self.last_debug.append(f"OpenStreetMap: {len(elements)} mapped {industry} result(s) around {location}")
        return [
            candidate
            for element in elements
            if (candidate := self._candidate_from_osm_element(element, industry, location, keywords))
        ]

    def _discover_from_nominatim(
        self,
        industry: str,
        location: str,
        keywords: str,
    ) -> list[LeadCandidate]:
        if not location:
            return []

        query = clean_text(f"{industry} {location} Nigeria")
        try:
            response = self.session.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 50,
                    "addressdetails": 1,
                    "extratags": 1,
                    "namedetails": 1,
                },
                timeout=self.timeout + 5,
            )
            response.raise_for_status()
            results = response.json()
        except Exception as exc:
            self.last_debug.append(f"Nominatim business search failed: {exc}")
            return []

        self.last_debug.append(f"Nominatim: {len(results)} mapped prospect result(s) for {query!r}")
        candidates: list[LeadCandidate] = []
        for item in results:
            name = clean_text(
                item.get("name")
                or item.get("namedetails", {}).get("name")
                or first_display_name_part(item.get("display_name", ""))
            )
            if not name:
                continue

            extra = item.get("extratags", {}) or {}
            website = normalize_result_url(first_non_empty(extra.get("website"), extra.get("contact:website"), extra.get("url")))
            phone = first_non_empty(extra.get("phone"), extra.get("contact:phone"))
            email = first_non_empty(extra.get("email"), extra.get("contact:email"))
            address = clean_text(item.get("display_name"))
            manual_query = build_business_research_query(name, industry, location, keywords)
            confidence = "website" if website else "mapped-business"

            snippet_parts = [part for part in [address, phone, email] if part]
            if not website:
                snippet_parts.append("Mapped business prospect. Website not confirmed yet.")

            candidates.append(
                LeadCandidate(
                    business_name=name,
                    website=website,
                    industry=industry,
                    location=location,
                    source="OpenStreetMap/Nominatim",
                    search_query=manual_query,
                    title=name,
                    snippet=truncate(" | ".join(snippet_parts), 240),
                    phone=phone,
                    email=email,
                    address=address,
                    confidence=confidence,
                )
            )
        return candidates

    def _candidate_from_osm_element(
        self,
        element: dict,
        industry: str,
        location: str,
        keywords: str,
    ) -> LeadCandidate | None:
        tags_data = element.get("tags", {})
        name = clean_text(tags_data.get("name"))
        if not name:
            return None

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
        confidence = "website" if website else "mapped-business"

        snippet_parts = [part for part in [address, phone, email] if part]
        if not website:
            snippet_parts.append("Mapped business prospect. Website not confirmed yet.")

        return LeadCandidate(
            business_name=name,
            website=website,
            industry=industry,
            location=location,
            source="OpenStreetMap",
            search_query=manual_query,
            title=name,
            snippet=truncate(" | ".join(snippet_parts), 240),
            phone=phone,
            email=email,
            address=address,
            confidence=confidence,
        )

    def _fetch_overpass(self, query: str) -> dict | None:
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                response = self.session.post(
                    endpoint,
                    data=query.encode("utf-8"),
                    headers={"Content-Type": "text/plain; charset=utf-8"},
                    timeout=self.timeout + 12,
                )
                response.raise_for_status()
                self.last_debug.append(f"OpenStreetMap Overpass source worked: {endpoint}")
                return response.json()
            except Exception as exc:
                self.last_debug.append(f"OpenStreetMap Overpass source failed ({endpoint}): {exc}")
        return None

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
        searchers = [self._search_bing]

        if self.enable_deep_search:
            searchers.extend([self._search_duckduckgo_html, self._search_duckduckgo_lite])
        else:
            self.last_debug.append("Deep search disabled: skipping slower DuckDuckGo checks")

        for searcher in searchers:
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


def build_business_research_query(name: str, industry: str, location: str, keywords: str = "") -> str:
    return clean_text(f"{name} {industry} {location} {keywords} official website contact")


def candidate_key(candidate: LeadCandidate) -> str:
    if candidate.website:
        return normalized_domain(candidate.website)
    key_parts = [candidate.business_name, candidate.address, candidate.phone, candidate.email]
    return "|".join(part.lower() for part in key_parts if part)


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
[out:json][timeout:20];
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
        url = resolve_bing_url(link.get("href", ""))
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
        resolved_url = (
            resolve_bing_url(link["href"])
            or resolve_duckduckgo_url(link["href"])
            or normalize_result_url(link["href"])
        )

        if title and resolved_url:
            results.append({"title": title, "url": resolved_url, "snippet": ""})

    return dedupe_results(results)


def resolve_bing_url(raw_url: str) -> str:
    if not raw_url:
        return ""

    raw_url = unescape(raw_url).strip()
    if raw_url.startswith("/"):
        raw_url = urljoin("https://www.bing.com", raw_url)

    parsed = urlparse(raw_url)
    query = parse_qs(parsed.query)

    if "u" in query and query["u"]:
        decoded = decode_bing_u_parameter(query["u"][0])
        if decoded:
            return normalize_result_url(decoded)

    return normalize_result_url(raw_url)


def decode_bing_u_parameter(value: str) -> str:
    value = unquote(value)

    if value.startswith("a1"):
        value = value[2:]

    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(value + padding).decode("utf-8", errors="ignore")
        if decoded.startswith(("http://", "https://")):
            return decoded
    except Exception:
        pass

    return value if value.startswith(("http://", "https://")) else ""


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
    return clean_text(", ".join(part for part in parts if part))


def first_display_name_part(display_name: str) -> str:
    return clean_text(display_name.split(",")[0])


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
