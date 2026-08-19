"""Scraper for boligportal.dk.

The search page embeds a full JSON dump of the results in
<script id="store" type="application/json"> (props.page_props.results) — no HTML
card-scraping needed, and it already includes price/size/rooms/address/move-in-date,
so fetch_detail() is a no-op for this site.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Listing
from .base import BaseSite, polite_sleep

logger = logging.getLogger(__name__)

BASE_URL = "https://www.boligportal.dk"


def _parse_available_from(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        logger.warning("boligportal: kunne ikke parse available_from %r", value)
        return None


def _extract_listing(item: dict) -> Optional[Listing]:
    listing_id = item.get("id")
    url = item.get("url")
    if listing_id is None or not url:
        return None

    street = (item.get("street_name") or "").strip()
    number = (item.get("street_number") or "").strip()
    area = (item.get("city_area") or item.get("city") or "").strip()
    street_full = f"{street} {number}".strip()
    address = ", ".join(p for p in (street_full, area) if p)

    photo_url = None
    images = item.get("images") or []
    if images:
        photo_url = images[0].get("url")

    rent = item.get("monthly_rent")

    return Listing(
        site="boligportal",
        listing_id=str(listing_id),
        title=item.get("title") or address or "Lejebolig",
        address=address,
        url=urljoin(BASE_URL, url),
        price_kr=int(rent) if rent is not None else None,
        size_m2=item.get("size_m2"),
        rooms=item.get("rooms"),
        move_in_raw=item.get("available_from") or "Ledig nu",
        move_in_date=_parse_available_from(item.get("available_from")),
        photo_url=photo_url,
    )


class BoligportalSite(BaseSite):
    name = "boligportal"

    def search(self, city_slug: str, max_pages: int = 3) -> List[Listing]:
        listings: List[Listing] = []
        path = f"/lejeboliger/{city_slug}/"
        for page in range(1, max_pages + 1):
            url = urljoin(BASE_URL, path)
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 404:
                logger.warning("boligportal: 404 for by-slug %r (%s)", city_slug, url)
                break
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            store_tag = soup.find("script", id="store")
            if store_tag is None or not store_tag.string:
                logger.warning("boligportal: fandt ikke #store JSON på %s", url)
                break
            data = json.loads(store_tag.string)
            page_props = data.get("props", {}).get("page_props", {})
            for item in page_props.get("results") or []:
                listing = _extract_listing(item)
                if listing is not None:
                    listings.append(listing)
            next_page_url = page_props.get("next_page_url")
            if not next_page_url or page >= max_pages:
                break
            path = next_page_url
            polite_sleep()
        return listings
