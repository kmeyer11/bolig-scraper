"""Parses krav.txt (the user's search criteria) into a Criteria object."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional

from .models import Listing

DANISH_TRANSLIT = str.maketrans({"æ": "ae", "ø": "oe", "å": "aa"})
DIRECTION_SUFFIXES = {"c", "ø", "v", "n", "s", "nv", "sv", "nø", "sø"}
DEFAULT_SITES = ["boligzonen", "boligportal"]


def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, drop accents-as-typed differences we care about."""
    return re.sub(r"\s+", " ", text.strip().casefold())


def city_slug(sted: str) -> str:
    """Best-effort mapping from a 'sted' like 'Aarhus C' to a site URL slug like 'aarhus'.

    Strips a trailing Danish cardinal-direction suffix (C/Ø/V/N/S/NV/SV/NØ/SØ),
    transliterates æøå, and hyphenates. This is a heuristic — verify the resulting
    slug actually loads a valid page for sites/cities not already tested.
    """
    words = sted.strip().split()
    if len(words) > 1 and words[-1].casefold() in DIRECTION_SUFFIXES:
        words = words[:-1]
    slug = "-".join(words).casefold().translate(DANISH_TRANSLIT)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug


def _parse_int(value: str) -> Optional[int]:
    value = value.strip()
    return int(value) if value else None


def _parse_float(value: str) -> Optional[float]:
    value = value.strip()
    return float(value) if value else None


def _parse_date(value: str) -> Optional[date]:
    value = value.strip()
    return date.fromisoformat(value) if value else None


def _parse_list(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass
class Criteria:
    sted: List[str] = field(default_factory=list)
    min_pris: Optional[int] = None
    max_pris: Optional[int] = None
    min_kvm: Optional[float] = None
    max_kvm: Optional[float] = None
    min_vaerelser: Optional[float] = None
    max_vaerelser: Optional[float] = None
    overtagelse_tidligst: Optional[date] = None
    overtagelse_senest: Optional[date] = None
    sites: List[str] = field(default_factory=lambda: list(DEFAULT_SITES))

    @property
    def city_slugs(self) -> List[str]:
        seen = []
        for sted in self.sted:
            slug = city_slug(sted)
            if slug not in seen:
                seen.append(slug)
        return seen

    def matches_sted(self, address: str) -> bool:
        if not self.sted:
            return True
        norm_address = normalize(address)
        for sted in self.sted:
            norm_sted = normalize(sted)
            if norm_sted in norm_address or norm_address in norm_sted:
                return True
        return False

    def matches(self, listing: Listing) -> bool:
        if not self.matches_sted(listing.address):
            return False
        if listing.price_kr is not None:
            if self.min_pris is not None and listing.price_kr < self.min_pris:
                return False
            if self.max_pris is not None and listing.price_kr > self.max_pris:
                return False
        if listing.size_m2 is not None:
            if self.min_kvm is not None and listing.size_m2 < self.min_kvm:
                return False
            if self.max_kvm is not None and listing.size_m2 > self.max_kvm:
                return False
        if listing.rooms is not None:
            if self.min_vaerelser is not None and listing.rooms < self.min_vaerelser:
                return False
            if self.max_vaerelser is not None and listing.rooms > self.max_vaerelser:
                return False
        # move_in_date of None means "available now", which always satisfies
        # overtagelse_tidligst; it can never satisfy an overtagelse_senest bound
        # that's in the past, but a None value here means "now" so it always
        # passes a "no later than X" bound too as long as X >= today isn't required.
        if listing.move_in_date is not None:
            if self.overtagelse_tidligst is not None and listing.move_in_date < self.overtagelse_tidligst:
                return False
            if self.overtagelse_senest is not None and listing.move_in_date > self.overtagelse_senest:
                return False
        return True


FIELD_PARSERS = {
    "sted": _parse_list,
    "min_pris": _parse_int,
    "max_pris": _parse_int,
    "min_kvm": _parse_float,
    "max_kvm": _parse_float,
    "min_vaerelser": _parse_float,
    "max_vaerelser": _parse_float,
    "overtagelse_tidligst": _parse_date,
    "overtagelse_senest": _parse_date,
    "sites": _parse_list,
}


def load_krav(path: str | Path) -> Criteria:
    path = Path(path)
    values = {}
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{path}:{lineno}: forventede 'key: value', fik {raw_line!r}")
        key, _, value = line.partition(":")
        key = key.strip().casefold()
        parser = FIELD_PARSERS.get(key)
        if parser is None:
            raise ValueError(f"{path}:{lineno}: ukendt felt {key!r}")
        values[key] = parser(value)

    criteria = Criteria()
    for key, value in values.items():
        if value is not None:
            setattr(criteria, key, value)
    return criteria
