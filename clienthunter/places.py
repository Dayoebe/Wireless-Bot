from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

import requests
from dotenv import load_dotenv

from .utils import truncate

load_dotenv()

GOOGLE_PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
GOOGLE_PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

PLACE_DETAIL_FIELDS = ",".join(
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
    """Discover real local businesses through Google Places API."""

    def __init__(self, api_key: str | None = None, timeout: int = 15):
        self.api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
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
            self.last_debug.append("Google Places skipped: GOOGLE_PLACES_API_KEY is not configured.")
            return []

        if not industry or not location:
            self.last_debug.append("Google Places skipped: industry and location are required.")
            return []

        query = clean_text(f"{industry} {keywords} in {location}, Nigeria")
        places = self._text_search(query, max_results=max_results)
        prospects: list[PlaceProspect] = []
        seen_place_ids: set[str] = set()

        for place in places:
            place_id = place.get("place_id")
            if not place_id or place_id in seen_place_ids:
                continue
            seen_place_ids.add(place_id)

            details = self._place_details(place_id)
            if not details:
                details = place

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
            rating = str(details.get("rating") or place.get("rating") or "")
            total_ratings = str(
                details.get("user_ratings_total")
                or place.get("user_ratings_total")
                or ""
            )
            business_status = clean_text(details.get("business_status") or place.get("business_status"))
            confidence = "verified-business"
            if website:
                confidence = "verified-business-with-website"
            elif phone:
                confidence = "verified-business-with-phone"

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

            prospects.append(
                PlaceProspect(
                    business_name=name,
                    website=website,
                    industry=industry,
                    location=location,
                    source="Google Places",
                    search_query=query,
                    title=name,
                    snippet=truncate(" | ".join(snippet_parts), 260),
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

        self.last_debug.append(f"Google Places: returned {len(prospects)} real prospect(s) for {query!r}.")
        return prospects

    def _text_search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        params = {
            "query": query,
            "key": self.api_key,
        }

        while len(results) < max_results:
            response = requests.get(
                GOOGLE_PLACES_TEXT_SEARCH_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            status = payload.get("status", "UNKNOWN")

            if status not in {"OK", "ZERO_RESULTS"}:
                message = payload.get("error_message") or status
                self.last_debug.append(f"Google Places text search failed: {message}")
                return results

            results.extend(payload.get("results", []))
            next_page_token = payload.get("next_page_token")

            if not next_page_token or len(results) >= max_results:
                break

            # Google requires a short delay before next_page_token becomes valid.
            import time

            time.sleep(2)
            params = {
                "pagetoken": next_page_token,
                "key": self.api_key,
            }

        return results[:max_results]

    def _place_details(self, place_id: str) -> dict[str, Any]:
        response = requests.get(
            GOOGLE_PLACES_DETAILS_URL,
            params={
                "place_id": place_id,
                "fields": PLACE_DETAIL_FIELDS,
                "key": self.api_key,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        status = payload.get("status", "UNKNOWN")

        if status != "OK":
            message = payload.get("error_message") or status
            self.last_debug.append(f"Google Places detail lookup failed for {place_id}: {message}")
            return {}

        return payload.get("result", {})


def clean_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())
