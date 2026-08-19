"""Sends one combined email (via the Mail.app the user already has Hotmail set up in)
for all new matches found in a run, using AppleScript / osascript.

No SMTP credentials are stored anywhere — this just remote-controls the already
logged-in Mail.app to compose+send from its default account.
"""
from __future__ import annotations

import logging
import subprocess
from typing import List, Sequence

from .models import Listing

logger = logging.getLogger(__name__)

DEFAULT_RECIPIENT = "brandvarm91@hotmail.com"


def _as_applescript_string(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _body_expression(lines: Sequence[str]) -> str:
    """AppleScript string literals can't contain raw newlines, so build the body
    as `"line1" & return & "line2" & ...` instead of one multi-line literal."""
    if not lines:
        return '""'
    return " & return & ".join(_as_applescript_string(line) for line in lines)


def _format_listing_lines(listing: Listing) -> List[str]:
    details = []
    if listing.price_kr is not None:
        details.append(f"{listing.price_kr:,} kr/md".replace(",", "."))
    if listing.size_m2 is not None:
        details.append(f"{listing.size_m2:g} m²")
    if listing.rooms is not None:
        details.append(f"{listing.rooms:g} vær.")
    details.append(f"ledig: {listing.move_in_raw or 'ukendt'}")

    return [
        f"— {listing.title} ({listing.site})",
        f"  {listing.address}",
        "  " + ", ".join(details),
        f"  {listing.url}",
        "",
    ]


def _run_osascript(script: str) -> bool:
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        logger.warning("osascript ikke fundet — email-notifikation kræver macOS/Mail.app.")
        return False
    if result.returncode != 0:
        logger.warning("osascript fejlede (%s): %s", result.returncode, result.stderr.strip())
        return False
    return True


def send_new_matches_email(listings: List[Listing], recipient: str = DEFAULT_RECIPIENT) -> bool:
    if not listings:
        return True

    subject = f"Bolig-scraper: {len(listings)} ny(e) lejlighed(er)"
    lines: List[str] = []
    for listing in listings:
        lines.extend(_format_listing_lines(listing))

    script = f"""
tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:{_as_applescript_string(subject)}, content:{_body_expression(lines)}, visible:false}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:{_as_applescript_string(recipient)}}}
    end tell
    send newMessage
end tell
""".strip()

    ok = _run_osascript(script)
    if ok:
        logger.info("Email sendt til %s med %d nye match.", recipient, len(listings))
    return ok


def send_test_email(recipient: str = DEFAULT_RECIPIENT) -> bool:
    script = f"""
tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:{_as_applescript_string("Bolig-scraper: test")}, content:{_as_applescript_string("Dette er en testmail fra bolig-scraper — hvis du ser denne, virker notifikationen.")}, visible:false}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:{_as_applescript_string(recipient)}}}
    end tell
    send newMessage
end tell
""".strip()
    return _run_osascript(script)
