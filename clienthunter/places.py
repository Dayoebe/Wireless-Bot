from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass
from typing import Any

import requests
from dotenv import load_dotenv

from .utils import truncate

load_dotenv()

GOOGLE_PLACES_NEW_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_PLACES_LEGACY_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
GOOGLE_PLACES_LEGACY_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

NEW_TEXT_SEARCH_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.googleMapsUri",
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
        "places.types",
    ]
)

LEGACY_PLACE_DETAIL_FIELDS = ",".join(
    [
        "place_id",
        "name",
        "formatted_address",
        "formatted_phone_number",
        "international_phone_number",
        "website",
        "url",
        "rating",
        "user_ratings_total",
        "business_status",
        "types",
    ]
)


@dataclass(frozen=True)
class PlaceProspect:
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
    confidence: str = "google-places"
    maps_url: str = ""
    rating: str = ""
    user_ratings_total: str = ""
    business_status: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class GooglePlacesDiscovery:
    """Discover real local businesses through Google Places API.

    The class tries Places API (New) first, then falls back to Places API
    (Legacy). This helps when a Google Cloud project has enabled only one of
    the two API versions.
    """

    def __init__(self, api_key: str | None = None, timeout: int = 15):
        self.api_key = clean_text(
            api_key
            or os.getenv("GOOGLE_PLACES_API_KEY")
            or os.getenv("GOOGLE_MAPS_API_KEY")
        )
        self.timeout = timeout
        self.last_debug: list[str] = []

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def discover(
        self,
        industry: str,
        location: str,
        keywords: str = "",
        max_results: int = 20,
    ) -> list[PlaceProspect]:
        industry = clean_text(industry)
        location = clean_text(location)
        keywords = clean_text(keywords)
        self.last_debug = []

        if not self.api_key:
            self.last_debug.append("Google Places skipped: API key is not configured.")
            return []

        if not industry or not location:
            self.last_debug.append("Google Places skipped: industry and location are required.")
            return []

        query = clean_text(f"{industry} {keywords} in {location}, Nigeria")

        prospects = self._discover_with_new_api(query, industry, location, max_results)
        if prospects:
            self.last_debug.append(
                f"Google Places New: returned {len(prospects)} real prospect(s) for {query!r}."
            )
            return prospects[:max_results]

        self.last_debug.append("Google Places New returned no usable prospects; trying legacy endpoint.")
        prospects = self._discover_with_legacy_api(query, industry, location, max_results)
        if prospects:
            self.last_debug.append(
                f"Google Places Legacy: returned {len(prospects)} real prospect(s) for {query!r}."
            )
            return prospects[:max_results]

        self.last_debug.append(f"Google Places: returned 0 prospects for {query!r}.")
        return []

    def _discover_with_new_api(
        self,
        query: str,
        industry: str,
        location: str,
        max_results: int,
    ) -> list[PlaceProspect]:
        try:
            places = self._text_search_new(query, max_results=max_results)
        except Exception as exc:
            self.last_debug.append(f"Google Places New failed: {exc}")
            return []

        prospects: list[PlaceProspect] = []
        for place in places:
            name = clean_text((place.get("displayName") or {}).get("text"))
            if not name:
                continue

            address = clean_text(place.get("formattedAddress"))
            website = clean_text(place.get("websiteUri"))
            maps_url = clean_text(place.get("googleMapsUri"))
            phone = clean_text(
                place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
            )
            rating = stringify(place.get("rating"))
            total_ratings = stringify(place.get("userRatingCount"))
            business_status = clean_text(place.get("businessStatus"))
            confidence = build_confidence(website, phone)
            snippet = build_snippet(address, phone, rating, total_ratings, business_status, website)

            prospects.append(
                PlaceProspect(
                    business_name=name,
                    website=website,
                    industry=industry,
                    location=location,
                    source="Google Places New",
                    search_query=query,
                    title=name,
                    snippet=truncate(snippet, 260),
                    phone=phone,
                    address=address,
                    confidence=confidence,
                    maps_url=maps_url,
                    rating=rating,
                    user_ratings_total=total_ratings,
                    business_status=business_status,
                )
            )

            if len(prospects) >= max_results:
                break

        return prospects

    def _discover_with_legacy_api(
        self,
        query: str,
        industry: str,
        location: str,
        max_results: int,
    ) -> list[PlaceProspect]:
        try:
            places = self._text_search_legacy(query, max_results=max_results)
        except Exception as exc:
            self.last_debug.append(f"Google Places Legacy failed: {exc}")
            return []

        prospects: list[PlaceProspect] = []
        seen_place_ids: set[str] = set()

        for place in places:
            place_id = place.get("place_id")
            if not place_id or place_id in seen_place_ids:
                continue
            seen_place_ids.add(place_id)

            details = self._place_details_legacy(place_id) or place
            name = clean_text(details.get("name") or place.get("name"))
            if not name:
                continue

            address = clean_text(details.get("formatted_address") or place.get("formatted_address"))
            website = clean_text(details.get("website"))
            maps_url = clean_text(details.get("url"))
            phone = clean_text(
                details.get("international_phone_number")
                or details.get("formatted_phone_number")
            )
            rating = stringify(details.get("rating") or place.get("rating"))
            total_ratings = stringify(
                details.get("user_ratings_total") or place.get("user_ratings_total")
            )
            business_status = clean_text(details.get("business_status") or place.get("business_status"))
            confidence = build_confidence(website, phone)
            snippet = build_snippet(address, phone, rating, total_ratings, business_status, website)

            prospects.append(
                PlaceProspect(
                    business_name=name,
                    website=website,
                    industry=industry,
                    location=location,
                    source="Google Places Legacy",
                    search_query=query,
                    title=name,
                    snippet=truncate(snippet, 260),
                    phone=phone,
                    address=address,
                    confidence=confidence,
                    maps_url=maps_url,
                    rating=rating,
                    user_ratings_total=total_ratings,
                    business_status=business_status,
                )
            )

            if len(prospects) >= max_results:
                break

        return prospects

    def _text_search_new(self, query: str, max_results: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        body: dict[str, Any] = {
            "textQuery": query,
            "languageCode": "en",
            "regionCode": "NG",
            "pageSize": min(max_results, 20),
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": NEW_TEXT_SEARCH_FIELD_MASK,
        }

        while len(results) < max_results:
            response = requests.post(
                GOOGLE_PLACES_NEW_TEXT_SEARCH_URL,
                json=body,
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code >= 400:
                self.last_debug.append(
                    f"Google Places New HTTP {response.status_code}: {extract_google_error(response)}"
                )
                return results

            payload = response.json()
            results.extend(payload.get("places", []))
            next_page_token = payload.get("nextPageToken")

            if not next_page_token or len(results) >= max_results:
                break

            time.sleep(2)
            body = {"textQuery": query, "pageToken": next_page_token}

        return results[:max_results]

    def _text_search_legacy(self, query: str, max_results: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        params = {
            "query": query,
            "key": self.api_key,
        }

        while len(results) < max_results:
            response = requests.get(
                GOOGLE_PLACES_LEGACY_TEXT_SEARCH_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            status = payload.get("status", "UNKNOWN")

            if status not in {"OK", "ZERO_RESULTS"}:
                message = payload.get("error_message") or status
                self.last_debug.append(f"Google Places Legacy text search failed: {message}")
                return results

            results.extend(payload.get("results", []))
            next_page_token = payload.get("next_page_token")

            if not next_page_token or len(results) >= max_results:
                break

            time.sleep(2)
            params = {
                "pagetoken": next_page_token,
                "key": self.api_key,
            }

        return results[:max_results]

    def _place_details_legacy(self, place_id: str) -> dict[str, Any]:
        try:
            response = requests.get(
                GOOGLE_PLACES_LEGACY_DETAILS_URL,
                params={
                    "place_id": place_id,
                    "fields": LEGACY_PLACE_DETAIL_FIELDS,
                    "key": self.api_key,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            status = payload.get("status", "UNKNOWN")

            if status != "OK":
                message = payload.get("error_message") or status
                self.last_debug.append(f"Google Places Legacy detail lookup failed for {place_id}: {message}")
                return {}

            return payload.get("result", {})
        except Exception as exc:
            self.last_debug.append(f"Google Places Legacy detail lookup failed for {place_id}: {exc}")
            return {}


def extract_google_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500]

    if "error" in payload:
        error = payload["error"]
        message = error.get("message") or str(error)
        status = error.get("status")
        return f"{status}: {message}" if status else message

    return str(payload)[:500]


def build_confidence(website: str, phone: str) -> str:
    if website:
        return "verified-business-with-website"
    if phone:
        return "verified-business-with-phone"
    return "verified-business"


def build_snippet(
    address: str,
    phone: str,
    rating: str,
    total_ratings: str,
    business_status: str,
    website: str,
) -> str:
    snippet_parts = [
        part
        for part in [
            address,
            phone,
            f"Rating: {rating}" if rating else "",
            f"Reviews: {total_ratings}" if total_ratings else "",
            business_status,
        ]
        if part
    ]
    if not website:
        snippet_parts.append("No website returned by Google Places; strong website prospect.")
    return " | ".join(snippet_parts)


def stringify(value: Any) -> str:
    return "" if value is None else str(value)


def clean_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())
