"""Sends one combined email (via the Mail.app the user already has Hotmail set up in)
for all new matches found in a run, using AppleScript / osascript.

No SMTP credentials are stored anywhere — this just remote-controls the already
logged-in Mail.app to compose+send from its default account.

Two non-obvious things had to be true for `send` to actually deliver, confirmed by
checking the account's Sent mailbox via AppleScript after each attempt:
1. `sender` must be set explicitly — this Mail.app has two accounts registered under
   the same address, and without it `send` silently picked one that never delivered.
2. The outgoing message must be created with `visible:true`. With `visible:false`,
   `send` returns success but the message is never actually transmitted — it's left
   sitting as an open, unsent compose window. Mail.app closes the window itself once
   a `visible:true` send actually succeeds, so this doesn't leave clutter behind.

`visible:true` also activates Mail.app (brings it to the front) while composing —
macOS/iOS generally suppress a "new mail" banner for the app that's currently frontmost,
so the synced-back copy of a self-addressed send was arriving without a notification.
Explicitly reactivating Finder right after `send` defocuses Mail again, so it's no
longer frontmost by the time the message syncs back into the inbox.
"""
from __future__ import annotations

import logging
import subprocess
from typing import List, Sequence

from .models import Listing

logger = logging.getLogger(__name__)

DEFAULT_RECIPIENT = "brandvarm91@hotmail.com"
# Mail.app has both an Exchange (Hotmail) and a Google account registered under this
# same address; without an explicit sender, `send` silently picked an account whose
# message never actually reached the inbox. Setting `sender` explicitly fixed it —
# confirmed by checking the Exchange account's Sent mailbox via AppleScript.
DEFAULT_SENDER = "brandvarm91@hotmail.com"


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


def send_new_matches_email(
    listings: List[Listing], recipient: str = DEFAULT_RECIPIENT, sender: str = DEFAULT_SENDER
) -> bool:
    if not listings:
        return True

    subject = f"Bolig-scraper: {len(listings)} ny(e) lejlighed(er)"
    lines: List[str] = []
    for listing in listings:
        lines.extend(_format_listing_lines(listing))

    script = f"""
tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:{_as_applescript_string(subject)}, content:{_body_expression(lines)}, visible:true}}
    tell newMessage
        set sender to {_as_applescript_string(sender)}
        make new to recipient at end of to recipients with properties {{address:{_as_applescript_string(recipient)}}}
    end tell
    send newMessage
    delay 2
end tell
tell application "Finder" to activate
""".strip()

    ok = _run_osascript(script)
    if ok:
        logger.info("Email sendt til %s med %d nye match.", recipient, len(listings))
    return ok


def send_test_email(recipient: str = DEFAULT_RECIPIENT, sender: str = DEFAULT_SENDER) -> bool:
    script = f"""
tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:{_as_applescript_string("Bolig-scraper: test")}, content:{_as_applescript_string("Dette er en testmail fra bolig-scraper — hvis du ser denne, virker notifikationen.")}, visible:true}}
    tell newMessage
        set sender to {_as_applescript_string(sender)}
        make new to recipient at end of to recipients with properties {{address:{_as_applescript_string(recipient)}}}
    end tell
    send newMessage
    delay 2
end tell
tell application "Finder" to activate
""".strip()
    return _run_osascript(script)
