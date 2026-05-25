"""Google Places API (New) — locales sin web."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
SEARCH_FIELD_MASK = "places.id"
DETAILS_FIELD_MASK = (
    "id,displayName,formattedAddress,nationalPhoneNumber,websiteUri,"
    "reviews,rating,userRatingCount,regularOpeningHours,"
    "primaryTypeDisplayName,addressComponents"
)
MAX_REVIEWS = 8
REQUEST_TIMEOUT = 30


@dataclass
class ReviewCard:
    name: str
    initials: str
    stars: int
    text: str
    time: str


@dataclass
class PlaceLead:
    place_id: str
    name: str
    address: str
    phone: str
    city: str = ""
    category: str = "Restaurante"
    rating: float = 4.5
    review_count: int = 0
    opening_hours: list[str] = field(default_factory=list)
    reviews: list[str] = field(default_factory=list)
    review_cards: list[ReviewCard] = field(default_factory=list)


class GooglePlacesScraper:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY")
        if not self.api_key:
            raise ValueError("Falta GOOGLE_PLACES_API_KEY")

    def _headers(self, mask: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": mask,
        }

    def search_without_website(self, query: str, max_results: int = 20) -> list[PlaceLead]:
        ids = self._search_ids(query, max_results * 4)
        leads: list[PlaceLead] = []
        for pid in ids:
            if len(leads) >= max_results:
                break
            try:
                lead = self._details(pid)
            except requests.RequestException as e:
                logger.warning("%s: %s", pid, e)
                continue
            if lead:
                leads.append(lead)
        logger.info("'%s': %d sin web", query, len(leads))
        return leads

    def _search_ids(self, query: str, cap: int) -> list[str]:
        body: dict[str, Any] = {"textQuery": query, "languageCode": "es", "maxResultCount": 20}
        ids: list[str] = []
        token: str | None = None
        while len(ids) < cap:
            if token:
                body["pageToken"] = token
            r = requests.post(SEARCH_TEXT_URL, headers=self._headers(SEARCH_FIELD_MASK), json=body, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            for p in data.get("places", []):
                pid = _norm_id(p.get("id", ""))
                if pid and pid not in ids:
                    ids.append(pid)
            token = data.get("nextPageToken")
            if not token:
                break
        return ids[:cap]

    def _details(self, place_id: str) -> PlaceLead | None:
        pid = _norm_id(place_id)
        url = PLACE_DETAILS_URL.format(place_id=requests.utils.quote(pid, safe=""))
        r = requests.get(url, headers=self._headers(DETAILS_FIELD_MASK), params={"languageCode": "es"}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        res = r.json()
        if (res.get("websiteUri") or "").strip():
            return None
        cards, texts = _reviews(res.get("reviews") or [])
        dn = res.get("displayName") or {}
        return PlaceLead(
            place_id=pid,
            name=(dn.get("text") or "Sin nombre").strip(),
            address=(res.get("formattedAddress") or "").strip(),
            phone=(res.get("nationalPhoneNumber") or "").strip(),
            city=_city(res.get("addressComponents") or [], res.get("formattedAddress", "")),
            category=((res.get("primaryTypeDisplayName") or {}).get("text") or "Restaurante"),
            rating=float(res.get("rating") or 4.5),
            review_count=int(res.get("userRatingCount") or 0),
            opening_hours=_hours(res.get("regularOpeningHours") or {}),
            reviews=texts,
            review_cards=cards,
        )


def _norm_id(pid: str) -> str:
    pid = (pid or "").strip()
    return pid.split("/", 1)[1] if pid.startswith("places/") else pid


def _city(components: list, address: str) -> str:
    for c in components:
        if "locality" in (c.get("types") or []) or "postal_town" in (c.get("types") or []):
            return (c.get("longText") or c.get("shortText") or "").strip()
    parts = [p.strip() for p in address.split(",")]
    return parts[-2] if len(parts) >= 2 else "Barcelona"


def _hours(reg: dict) -> list[str]:
    return [str(x).strip() for x in (reg.get("weekdayDescriptions") or []) if str(x).strip()]


def _reviews(raw: list) -> tuple[list[ReviewCard], list[str]]:
    cards, texts = [], []
    for rv in raw[:MAX_REVIEWS]:
        to = rv.get("text") or rv.get("originalText") or {}
        text = (to.get("text") if isinstance(to, dict) else str(to)).strip()
        if not text:
            continue
        texts.append(text)
        au = rv.get("authorAttribution") or {}
        name = (au.get("displayName") or "Cliente").strip()
        cards.append(ReviewCard(
            name=name,
            initials=_ini(name),
            stars=max(1, min(5, int(rv.get("rating") or 5))),
            text=text,
            time=(rv.get("relativePublishTimeDescription") or "Google").strip(),
        ))
    return cards, texts


def _ini(name: str) -> str:
    p = re.sub(r"[^\w\s]", "", name).split()
    if not p:
        return "CL"
    return (p[0][0] + p[-1][0]).upper() if len(p) > 1 else p[0][:2].upper()


def search_leads(query: str, max_results: int = 20) -> list[PlaceLead]:
    return GooglePlacesScraper().search_without_website(query, max_results=max_results)
