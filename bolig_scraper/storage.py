"""SQLite-backed 'seen listings' store so runs only report new matches."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from .models import Listing


class SeenStore:
    def __init__(self, db_path: Union[str, Path] = "bolig_scraper.db"):
        self.db_path = Path(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_items (
                listing_id TEXT PRIMARY KEY,
                site TEXT NOT NULL,
                title TEXT,
                price TEXT,
                address TEXT,
                url TEXT NOT NULL,
                matched INTEGER NOT NULL,
                first_seen TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def is_new(self, dedup_key: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM seen_items WHERE listing_id = ?", (dedup_key,)
        )
        return cur.fetchone() is None

    def mark_seen(self, listing: Listing, matched: bool) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO seen_items
                (listing_id, site, title, price, address, url, matched, first_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                listing.dedup_key,
                listing.site,
                listing.title,
                str(listing.price_kr) if listing.price_kr is not None else None,
                listing.address,
                listing.url,
                1 if matched else 0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SeenStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
