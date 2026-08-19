"""Scraper for boligzonen.dk.

Listing cards on the city search page (<a class="property-component-card" data-id="...">)
carry id/url/price/size/rooms/address directly. Move-in date ("Ledig fra") is only on the
detail page, so it's fetched lazily via fetch_detail() — only called for NEW listings.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Listing
from .base import BaseSite, polite_sleep

logger = logging.getLogger(__name__)

BASE_URL = "https://boligzonen.dk"

DANISH_MONTHS = {
    "januar": 1, "jan": 1,
    "februar": 2, "feb": 2,
    "marts": 3, "mar": 3,
    "april": 4, "apr": 4,
    "maj": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9,
    "oktober": 10, "okt": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
AVAILABLE_NOW_MARKERS = ("snarest", "med det samme", "straks", "nu")


def _parse_price(text: str) -> Optional[int]:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _parse_rooms_size(text: str) -> Tuple[Optional[float], Optional[float]]:
    rooms = None
    size = None
    m_rooms = re.search(r"(\d+)\s*v[æa]relse", text, re.I)
    if m_rooms:
        rooms = float(m_rooms.group(1))
    m_size = re.search(r"(\d+(?:[.,]\d+)?)\s*m", text, re.I)
    if m_size:
        size = float(m_size.group(1).replace(",", "."))
    return rooms, size


def parse_danish_move_in_date(text: str) -> Optional[date]:
    t = text.strip().casefold()
    if not t or any(marker in t for marker in AVAILABLE_NOW_MARKERS):
        return None
    m = re.search(r"(\d{1,2})\.?\s+([a-zæøå]+)\s+(\d{4})", t)
    if m:
        day, month_name, year = m.groups()
        month = DANISH_MONTHS.get(month_name)
        if month:
            return date(int(year), month, int(day))
    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m2:
        return date(*(int(x) for x in m2.groups()))
    logger.warning("boligzonen: kunne ikke parse overtagelsesdato %r", text)
    return None


def _extract_card(a_tag) -> Optional[Listing]:
    listing_id = a_tag.get("data-id")
    href = a_tag.get("href")
    if not listing_id or not href:
        return None

    content = a_tag.find("div", class_="content")
    if content is None:
        return None

    location_title = content.find("div", class_="location-title")
    rooms, size = (None, None)
    if location_title is not None:
        rooms, size = _parse_rooms_size(location_title.get_text(" ", strip=True))

    location_div = content.find("div", class_="location")
    street = ""
    area = ""
    if location_div is not None:
        street_span = location_div.find("span")
        if street_span is not None:
            street = street_span.get_text(strip=True).rstrip(",")
        area_div = location_div.find("div", class_="zip-code-name")
        if area_div is not None:
            area = area_div.get_text(strip=True)
    address = ", ".join(p for p in (street, area) if p)

    price_el = content.select_one(".price .price-amount")
    price = _parse_price(price_el.get_text(strip=True)) if price_el else None

    type_div = content.select_one(".title > div")
    property_type = type_div.get_text(strip=True) if type_div else "Lejebolig"
    title = f"{property_type} - {address}" if address else property_type

    return Listing(
        site="boligzonen",
        listing_id=str(listing_id),
        title=title,
        address=address,
        url=urljoin(BASE_URL, href),
        price_kr=price,
        size_m2=size,
        rooms=rooms,
    )


class BoligzonenSite(BaseSite):
    name = "boligzonen"

    def search(self, city_slug: str, max_pages: int = 3) -> List[Listing]:
        listings: List[Listing] = []
        for page in range(1, max_pages + 1):
            url = f"{BASE_URL}/lejebolig/{city_slug}"
            if page > 1:
                url += f"?page={page}"
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 404:
                logger.warning("boligzonen: 404 for by-slug %r (%s)", city_slug, url)
                break
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.find_all("a", class_="property-component-card")
            if not cards:
                break
            for card in cards:
                listing = _extract_card(card)
                if listing is not None:
                    listings.append(listing)
            if page < max_pages:
                polite_sleep()
        return listings

    def fetch_detail(self, listing: Listing) -> Listing:
        resp = self.session.get(listing.url, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for bar in soup.find_all("div", class_="section-bar"):
            label = bar.find("div", class_="section-bar-label")
            value = bar.find("div", class_="section-bar-value")
            if label is None or value is None:
                continue
            if label.get_text(strip=True) == "Ledig fra":
                raw = value.get_text(strip=True)
                listing.move_in_raw = raw
                listing.move_in_date = parse_danish_move_in_date(raw)
                break
        return listing
