"""Shared HTTP/session helpers and the scraper contract every site module implements."""
from __future__ import annotations

import random
import time
from typing import List, Optional

import requests

from ..models import Listing

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
        }
    )
    return session


def polite_sleep(min_s: float = 1.5, max_s: float = 3.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


class BaseSite:
    name: str

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or make_session()

    def search(self, city_slug: str, max_pages: int = 3) -> List[Listing]:
        """Return listing summaries for a city. Implementations should page politely."""
        raise NotImplementedError

    def fetch_detail(self, listing: Listing) -> Listing:
        """Enrich a listing with fields only available on its detail page (e.g. move-in date).

        Default is a no-op — override only if `search()` can't already provide
        everything `Criteria.matches()` needs.
        """
        return listing
