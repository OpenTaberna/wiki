#!/usr/bin/env python3
"""
Check the Wiki.js stack serves this repository's pages with no login.

Assumes the stack is already up:

    docker compose up -d
    python3 tools/check_wikijs.py

Fails when

1. a page in the repository is missing from Wiki.js,
2. a page does not return 200 to an anonymous request,
3. a page's own title is absent from what is served, or
4. anonymous access is bounced to a login screen.

Point 4 is the one that guards "no auth". Wiki.js answers a page a guest may not
read with the login screen under a 200, so status alone proves nothing — the
title has to actually be in the body.

Override the base URL with WIKI_URL when not on the default port:

    WIKI_PORT=3030 docker compose up -d
    WIKI_URL=http://localhost:3030 python3 tools/check_wikijs.py
"""

from __future__ import annotations

import html
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI_URL = os.environ.get("WIKI_URL", "http://localhost:3000").rstrip("/")

# Present in the repository, deliberately not published as a wiki page.
NOT_WIKI_PAGES = {"README"}

LOGIN_MARKERS = ("login-container", "loginBgUrl", "Sign In")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """
    Refuse to follow redirects.

    Wiki.js bounces a guest who may not read a page to /login with a 302. Left
    to follow it, urllib lands on the login page, which returns 200 and carries
    the site title — so a redirect would read as a pass. A redirect is the
    failure, so it has to be seen rather than followed.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def pages() -> list[tuple[str, str]]:
    """(wiki path, title) for every page the repository publishes."""
    found = []
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts:
            continue
        name = path.relative_to(ROOT).with_suffix("").as_posix()
        if name in NOT_WIKI_PAGES:
            continue
        title = ""
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if match:
            for line in match.group(1).splitlines():
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip()
                    break
        found.append((name, title))
    return found


def fetch(path: str) -> tuple[int, str]:
    try:
        with OPENER.open(f"{WIKI_URL}/{path}", timeout=30) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, OSError) as exc:
        sys.exit(
            f"Cannot reach {WIKI_URL} ({exc}).\n"
            f"Is the stack up?  docker compose up -d"
        )


def main() -> int:
    expected = pages()
    if not expected:
        sys.exit("No wiki pages found in the repository.")

    failures: list[str] = []

    for path, title in expected:
        status, body = fetch(path)

        if status in (301, 302, 303, 307, 308):
            failures.append(
                f"/{path}: HTTP {status} — redirected away, guests cannot read it"
            )
            continue

        if status != 200:
            failures.append(f"/{path}: HTTP {status}")
            continue

        if any(marker in body for marker in LOGIN_MARKERS):
            failures.append(f"/{path}: served a login screen — guests cannot read it")
            continue

        if title and title not in body and html.escape(title) not in body:
            failures.append(f"/{path}: served 200 but the title {title!r} is missing")

    print(f"Checked {len(expected)} pages against {WIKI_URL}.")

    if failures:
        print(f"\n{len(failures)} problem(s):\n")
        for failure in failures:
            print(f"  FAIL  {failure}")
        print("\nThe Wiki.js stack is not serving this repository anonymously.")
        return 1

    print("OK — every page is served, and no page asks for a login.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
