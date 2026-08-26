#!/usr/bin/env python3
"""
Check that the wiki still describes the system that is actually built.

The wiki drifted nine months out of date once (OpenTaberna/wiki#1) — documenting
tables that were never created and endpoints that never existed. This is the check
that fails when that starts happening again.

Three things are verified:

1. Every endpoint the API serves is documented somewhere in the wiki.
2. Every endpoint path the wiki mentions actually exists in the API.
3. Every internal wiki link resolves to a page that exists.

The API surface is read from openapi.snapshot.json rather than a live server, so
CI needs nothing running. Refresh the snapshot with:

    python3 tools/check_wiki.py --refresh http://localhost:8000

Refreshing is what makes the check bite: pull in a snapshot with a new endpoint and
the check fails until somebody documents it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "openapi.snapshot.json"

# Paths the wiki is allowed to mention without them being API endpoints.
IGNORED_PATHS = {"/health/live"}

# A path the API serves, as written in markdown. Placeholders are normalised so
# /v1/orders/{id} and /v1/orders/{order_id} compare equal.
PATH_RE = re.compile(r"(?<![\w/])(/v1/[A-Za-z0-9_{}/-]*|/health(?:/[A-Za-z0-9_-]+)?)")
PLACEHOLDER_RE = re.compile(r"\{[^}]*\}")
LINK_RE = re.compile(r"\]\((/[^)\s#]*)(#[^)\s]*)?\)")


def is_known(path: str, api_paths: set[str]) -> bool:
    """
    True if the path is an endpoint, or a router prefix the wiki names in prose.

    The wiki legitimately refers to `/v1/admin/**` and `/v1/customers` when
    describing a service as a whole, so a proper prefix of a real endpoint is
    accepted. A path that prefixes nothing real — a typo, or an endpoint that was
    removed — still fails.
    """
    if path in api_paths:
        return True
    return any(real.startswith(path + "/") for real in api_paths)


def normalise(path: str) -> str:
    path = PLACEHOLDER_RE.sub("{}", path)
    return path.rstrip("/") or "/"


def wiki_pages() -> list[Path]:
    return sorted(
        p
        for p in ROOT.rglob("*.md")
        if ".git" not in p.parts and p.name != "README.md"
    )


def load_api_paths() -> set[str]:
    if not SNAPSHOT.exists():
        sys.exit(
            f"{SNAPSHOT.name} is missing. Generate it with:\n"
            f"  python3 tools/check_wiki.py --refresh http://localhost:8000"
        )
    spec = json.loads(SNAPSHOT.read_text())
    return {normalise(p) for p in spec["paths"]}


def refresh(base_url: str) -> None:
    url = base_url.rstrip("/") + "/openapi.json"
    with urllib.request.urlopen(url, timeout=10) as response:
        spec = json.load(response)
    trimmed = {
        "info": spec["info"],
        "paths": {
            path: {
                method: {"summary": op.get("summary", "")}
                for method, op in ops.items()
                if method in ("get", "post", "put", "patch", "delete")
            }
            for path, ops in sorted(spec["paths"].items())
        },
    }
    SNAPSHOT.write_text(json.dumps(trimmed, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {SNAPSHOT.name}: {len(trimmed['paths'])} paths from {url}")


def check() -> int:
    api_paths = load_api_paths()
    pages = wiki_pages()
    if not pages:
        sys.exit("No wiki pages found.")

    page_names = {
        p.relative_to(ROOT).with_suffix("").as_posix().lower() for p in pages
    }
    documented: dict[str, set[str]] = {}
    failures: list[str] = []

    for page in pages:
        text = page.read_text(encoding="utf-8")
        rel = page.relative_to(ROOT).as_posix()

        for raw in PATH_RE.findall(text):
            path = normalise(raw)
            if path in IGNORED_PATHS:
                continue
            documented.setdefault(path, set()).add(rel)
            if not is_known(path, api_paths):
                failures.append(
                    f"{rel}: documents `{raw}`, which the API does not serve"
                )

        for target, _anchor in LINK_RE.findall(text):
            name = target.strip("/").lower()
            if not name or name in page_names:
                continue
            failures.append(f"{rel}: link to /{target.strip('/')} — no such page")

    for path in sorted(api_paths):
        if path not in documented and path not in IGNORED_PATHS:
            failures.append(f"API serves `{path}`, but no wiki page mentions it")

    print(f"Checked {len(pages)} pages against {len(api_paths)} API paths.")

    if failures:
        unique = sorted(set(failures))
        print(f"\n{len(unique)} problem(s):\n")
        for failure in unique:
            print(f"  FAIL  {failure}")
        print("\nThe wiki no longer matches the system. Fix the pages, or refresh")
        print("the snapshot if the API legitimately changed.")
        return 1

    print("OK — every endpoint is documented, and every documented path exists.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        metavar="BASE_URL",
        help="Fetch a fresh snapshot from a running API instead of checking",
    )
    args = parser.parse_args()

    if args.refresh:
        refresh(args.refresh)
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
