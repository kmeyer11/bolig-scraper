"""Entrypoint: `python -m bolig_scraper.cli [--krav krav.txt] [...]`

Flow: load krav.txt -> for each configured site x sted: fetch listings -> skip
already-seen ones -> filter new ones against the full criteria (fetching the
detail page first if a site didn't already supply everything, e.g. move-in date)
-> record every new listing as seen (matched or not, so it's never re-evaluated)
-> print + CSV-log + one combined email for whatever newly matched.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import requests

from . import notify, xlsx_export
from .config import Criteria, load_krav
from .models import Listing
from .sites import SITE_REGISTRY
from .sites.base import polite_sleep
from .storage import SeenStore

logger = logging.getLogger("bolig_scraper")

CSV_FIELDS = [
    "scraped_at", "site", "price_kr", "size_m2", "rooms",
    "move_in", "address", "title", "url",
]


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan boligzonen/boligportal for nye lejligheder.")
    parser.add_argument("--krav", default="krav.txt", help="Sti til krav-fil (default: krav.txt)")
    parser.add_argument("--db", default="bolig_scraper.db", help="Sti til sqlite seen-db")
    parser.add_argument("--csv", default="matches.csv", help="Sti til matches-csv (rå historik)")
    parser.add_argument("--xlsx", default="matches.xlsx", help="Sti til pænt formateret matches-xlsx (overblik)")
    parser.add_argument("--max-pages", type=int, default=3, help="Max sider pr. site x sted (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Ingen DB/CSV-writes, ingen email, kun print")
    parser.add_argument("--no-notify", action="store_true", help="Spring email over, men skriv stadig DB/CSV")
    parser.add_argument("--test-notify", action="store_true", help="Send én testmail og afslut")
    parser.add_argument("-v", "--verbose", action="store_true", help="Vis debug-logging")
    return parser.parse_args(argv)


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def append_csv(csv_path: Path, listings: List[Listing]) -> None:
    if not listings:
        return
    is_new_file = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if is_new_file:
            writer.writeheader()
        for listing in listings:
            writer.writerow(
                {
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "site": listing.site,
                    "price_kr": listing.price_kr,
                    "size_m2": listing.size_m2,
                    "rooms": listing.rooms,
                    "move_in": listing.move_in_raw,
                    "address": listing.address,
                    "title": listing.title,
                    "url": listing.url,
                }
            )


def print_listing(listing: Listing) -> None:
    bits = []
    if listing.price_kr is not None:
        bits.append(f"{listing.price_kr:,} kr/md".replace(",", "."))
    if listing.size_m2 is not None:
        bits.append(f"{listing.size_m2:g} m²")
    if listing.rooms is not None:
        bits.append(f"{listing.rooms:g} vær.")
    if listing.move_in_raw:
        bits.append(f"ledig: {listing.move_in_raw}")
    print(f"[{listing.site}] {listing.title} — {listing.address}")
    if bits:
        print("  " + ", ".join(bits))
    print(f"  {listing.url}")


def run(args: argparse.Namespace) -> int:
    criteria: Criteria = load_krav(args.krav)
    if not criteria.sted:
        logger.error("krav.txt mangler 'sted' — intet at søge på.")
        return 1

    unknown_sites = [s for s in criteria.sites if s not in SITE_REGISTRY]
    if unknown_sites:
        logger.warning("Ukendte sites i krav.txt, ignoreres: %s", unknown_sites)
    active_sites = [s for s in criteria.sites if s in SITE_REGISTRY]

    db_path = ":memory:" if args.dry_run else args.db
    new_matches: List[Listing] = []

    with SeenStore(db_path) as store:
        for site_name in active_sites:
            site = SITE_REGISTRY[site_name]()
            for city_slug in criteria.city_slugs:
                logger.info("Søger %s / %s ...", site_name, city_slug)
                try:
                    candidates = site.search(city_slug, max_pages=args.max_pages)
                except requests.RequestException as exc:
                    logger.warning("%s: fejl ved søgning i %s: %s", site_name, city_slug, exc)
                    continue
                logger.debug("%s/%s: %d opslag fundet på oversigtssiden", site_name, city_slug, len(candidates))

                for listing in candidates:
                    if not store.is_new(listing.dedup_key):
                        continue
                    if not criteria.matches(listing):
                        store.mark_seen(listing, matched=False)
                        continue
                    if listing.move_in_raw == "":
                        try:
                            listing = site.fetch_detail(listing)
                        except requests.RequestException as exc:
                            logger.warning("%s: fejl ved detail-fetch %s: %s", site_name, listing.url, exc)
                            continue
                        polite_sleep()
                        if not criteria.matches(listing):
                            store.mark_seen(listing, matched=False)
                            continue
                    store.mark_seen(listing, matched=True)
                    new_matches.append(listing)
                polite_sleep()

        if new_matches:
            print(f"\n{len(new_matches)} ny(e) lejlighed(er) fundet:\n")
            for listing in new_matches:
                print_listing(listing)
                print()
        else:
            print("Ingen nye lejligheder denne gang.")

        if not args.dry_run:
            append_csv(Path(args.csv), new_matches)
            if new_matches:
                xlsx_export.write_xlsx(args.csv, args.xlsx)

        if new_matches and not args.dry_run and not args.no_notify:
            recipients = [notify.DEFAULT_RECIPIENT, *criteria.ekstra_email]
            notify.send_new_matches_email(new_matches, recipients=recipients)

    return 0


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)

    if args.test_notify:
        ekstra_email: List[str] = []
        try:
            ekstra_email = load_krav(args.krav).ekstra_email
        except (OSError, ValueError) as exc:
            logger.warning("Kunne ikke læse ekstra_email fra %s (%s) — sender kun til standardmodtager.", args.krav, exc)
        recipients = [notify.DEFAULT_RECIPIENT, *ekstra_email]
        ok = notify.send_test_email(recipients=recipients)
        print("Testmail sendt." if ok else "Testmail fejlede — se log ovenfor.")
        return 0 if ok else 1

    return run(args)


if __name__ == "__main__":
    sys.exit(main())
