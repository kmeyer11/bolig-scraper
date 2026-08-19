"""Data model for a single rental listing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Listing:
    site: str
    listing_id: str  # unique within `site`; combine as f"{site}:{listing_id}" for global dedup
    title: str
    address: str
    url: str
    price_kr: Optional[int] = None
    size_m2: Optional[float] = None
    rooms: Optional[float] = None
    move_in_raw: str = ""
    move_in_date: Optional[date] = None  # None = available now / unknown
    photo_url: Optional[str] = None

    @property
    def dedup_key(self) -> str:
        return f"{self.site}:{self.listing_id}"
