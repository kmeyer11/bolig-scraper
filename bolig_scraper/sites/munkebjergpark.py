"""Scraper for munkebjergpark.dk — a single rental property in Odense M, not a
searchable-by-city portal like boligzonen/boligportal.

The property's "boligoversigt" (housing overview) WordPress plugin renders each of its
~10 buildings as a separate SVG floor-plan/map, fetched via a plain GET to
includes/public.php?post_id=X&list_id=Y&post_type=imagemap (no auth, no JS execution
needed — confirmed with curl). Every apartment on that map is a <path class="bolig">
carrying its address/rooms/size/price/status/move-in-date as data-* attributes.

The (post_id, list_id) pair per building are internal WordPress post IDs with no
derivable pattern (found by inspecting the "Områder" building-picker's
data-target-id/data-target-list in a browser), so they're hardcoded below. If the site
adds/renames a building, re-discover the pair the same way and update BUILDINGS.

The site has no notion of "city" — data-adresse never includes an area name, so the
fixed AREA below is appended to every address so it matches a krav.txt `sted` of
"Odense M".
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

from ..models import Listing
from .base import BaseSite, polite_sleep
from .boligzonen import parse_danish_move_in_date

logger = logging.getLogger(__name__)

BASE_URL = "https://munkebjergpark.dk"
LIST_URL = f"{BASE_URL}/wp-content/plugins/boligoversigt-plugin/includes/public.php"
AREA = "Odense M"

BUILDINGS: List[Tuple[str, str, str]] = [
    ("M-Tower 1", "890", "2178"),
    ("M-Tower 2", "7689", "7684"),
    ("Skovmærke 1", "7691", "7685"),
    ("Skovmærke 2", "7690", "7686"),
    ("Ved Søen", "11105", "7929"),
    ("Skovkanten", "10303", "10304"),
    ("Skovranken 1", "11272", "11719"),
    ("Skovranken 2", "11273", "11718"),
    ("Skovly 1", "12040", "12041"),
    ("Skovly 2", "11957", "12039"),
]


def _parse_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _extract_unit(el) -> Optional[Listing]:
    post_id = el.get("data-post_id")
    adresse = el.get("data-adresse")
    permalink = el.get("data-permalink")
    if not post_id or not adresse or not permalink:
        return None

    move_in_raw = el.get("data-indflytningsdato") or ""

    return Listing(
        site="munkebjergpark",
        listing_id=post_id,
        title=adresse,
        address=f"{adresse}, {AREA}",
        url=permalink,
        price_kr=_parse_int(el.get("data-pris")),
        size_m2=_parse_float(el.get("data-bbr_areal")),
        rooms=_parse_float(el.get("data-antal_vaerelser")),
        move_in_raw=move_in_raw,
        move_in_date=parse_danish_move_in_date(move_in_raw) if move_in_raw else None,
    )


class MunkebjergparkSite(BaseSite):
    name = "munkebjergpark"

    def search(self, city_slug: str, max_pages: int = 3) -> List[Listing]:
        """Ignores city_slug/max_pages — this is one fixed property, not a per-city search."""
        listings: List[Listing] = []
        seen_ids = set()
        for index, (name, post_id, list_id) in enumerate(BUILDINGS):
            params = {"post_id": post_id, "list_id": list_id, "post_type": "imagemap"}
            resp = self.session.get(LIST_URL, params=params, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for el in soup.select('path.bolig[data-statusvalue="ledig"]'):
                unit = _extract_unit(el)
                if unit is None or unit.listing_id in seen_ids:
                    continue
                seen_ids.add(unit.listing_id)
                listings.append(unit)
            if index < len(BUILDINGS) - 1:
                polite_sleep()
        return listings
