#!/usr/bin/env python3
"""
Bring a fresh Wiki.js up preconfigured against this repository.

Wiki.js normally needs a browser-driven setup wizard, an admin account and a
storage target configured by hand before it shows a single page. That is three
manual steps between cloning this repository and reading it, so this script does
them over Wiki.js's own APIs instead:

1. Completes the setup wizard (POST /finalize) if it has not run yet.
2. Sets the site title and turns off comments and ratings — this is a docs
   mirror, not a forum.
3. Points the Local File System storage target at the mounted repository and
   imports every Markdown page.
4. Removes README, which documents the repository rather than the project.
5. Rebuilds the sidebar so every page is reachable without knowing its URL.
6. Verifies guests can read without logging in, and grants it if not.

Every step is idempotent, so re-running only refreshes the content.

Standard library only, matching tools/check_wiki.py — the image this runs in is
plain python:alpine with nothing installed.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

WIKI_URL = os.environ.get("WIKI_URL", "http://wiki:3000").rstrip("/")
CONTENT_PATH = os.environ.get("WIKI_CONTENT_PATH", "/wiki-content")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@opentaberna.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "opentaberna-local-admin")

# Pages that exist in the repository but are not wiki content.
NOT_WIKI_PAGES = {"README"}

GUEST_GROUP_ID = 2
READ_PERMISSIONS = ["read:pages", "read:assets", "read:comments"]

# Reading order for the sidebar: what somebody new should meet first, not
# alphabetical. Pages not listed here are appended alphabetically, so adding a
# page still shows up without touching this list.
NAV_ORDER = [
    "home",
    "Getting-Started",
    "Authorization",
    "API/Architecture",
    "Database/Architecture",
    "Orders-and-Fulfillment",
    "Configuration",
    "Deployment",
]

NAV_ICONS = {
    "home": "mdi-home",
    "Getting-Started": "mdi-rocket-launch-outline",
    "Authorization": "mdi-shield-key-outline",
    "API/Architecture": "mdi-api",
    "Database/Architecture": "mdi-database-outline",
    "Orders-and-Fulfillment": "mdi-truck-outline",
    "Configuration": "mdi-cog-outline",
    "Deployment": "mdi-server",
}
DEFAULT_NAV_ICON = "mdi-file-document-outline"


def log(message: str) -> None:
    print(f"[bootstrap] {message}", flush=True)


def post(path: str, payload: dict, token: str | None = None) -> dict:
    request = urllib.request.Request(
        f"{WIKI_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def graphql(query: str, token: str, variables: dict | None = None) -> dict:
    body = post("/graphql", {"query": query, "variables": variables or {}}, token)
    if "errors" in body:
        raise RuntimeError(f"GraphQL error: {body['errors']}")
    return body["data"]


def wait_for_http(timeout: int = 300) -> None:
    log(f"waiting for {WIKI_URL}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(WIKI_URL, timeout=5) as response:
                if response.status == 200:
                    log("Wiki.js is responding")
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(2)
    sys.exit(f"Wiki.js did not respond within {timeout}s")


def login() -> str | None:
    query = """
    mutation($u: String!, $p: String!) {
      authentication {
        login(username: $u, password: $p, strategy: "local") {
          responseResult { succeeded message }
          jwt
        }
      }
    }
    """
    try:
        body = post(
            "/graphql",
            {"query": query, "variables": {"u": ADMIN_EMAIL, "p": ADMIN_PASSWORD}},
        )
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    if "errors" in body:
        return None
    result = body.get("data", {}).get("authentication", {}).get("login")
    if result and result["responseResult"]["succeeded"]:
        return result["jwt"]
    return None


def run_setup_wizard() -> None:
    log("running the setup wizard")
    body = post(
        "/finalize",
        {
            "adminEmail": ADMIN_EMAIL,
            "adminPassword": ADMIN_PASSWORD,
            "adminPasswordConfirm": ADMIN_PASSWORD,
            "siteUrl": WIKI_URL,
            "telemetry": False,
        },
    )
    if not body.get("ok"):
        sys.exit(f"setup failed: {body}")
    log("setup complete, waiting for Wiki.js to restart")


def authenticate() -> str:
    token = login()
    if token:
        log("already set up")
        return token

    run_setup_wizard()

    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(3)
        token = login()
        if token:
            log("signed in")
            return token
    sys.exit("could not sign in after setup")


def configure_site(token: str) -> None:
    query = """
    mutation($host: String!, $title: String!, $descr: String!) {
      site {
        updateConfig(
          host: $host, title: $title, description: $descr,
          robots: [], analyticsService: "", analyticsId: "", company: "",
          contentLicense: "", footerOverride: "", logoUrl: "",
          pageExtensions: "md, html, txt",
          authAutoLogin: false, authEnforce2FA: false, authHideLocal: false,
          authLoginBgUrl: "", authJwtAudience: "urn:wiki.js",
          authJwtExpiration: "30m", authJwtRenewablePeriod: "14d",
          editFab: true, editMenuBar: false, editMenuBtn: true,
          editMenuExternalBtn: false, editMenuExternalName: "",
          editMenuExternalIcon: "", editMenuExternalUrl: "",
          featurePageRatings: false, featurePageComments: false,
          featurePersonalWikis: false,
          securityOpenRedirect: true, securityIframe: true,
          securityReferrerPolicy: true, securityTrustProxy: true,
          securitySRI: true, securityHSTS: false, securityHSTSDuration: 300,
          securityCSP: false, securityCSPDirectives: ""
        ) { responseResult { succeeded message } }
      }
    }
    """
    result = graphql(
        query,
        token,
        {
            "host": WIKI_URL,
            "title": "OpenTaberna Wiki",
            "descr": "Documentation for the OpenTaberna project",
        },
    )["site"]["updateConfig"]["responseResult"]
    if not result["succeeded"]:
        sys.exit(f"could not configure the site: {result['message']}")
    log("site configured")


def set_disk_target(token: str, enabled: bool) -> None:
    query = """
    mutation($targets: [StorageTargetInput]!) {
      storage {
        updateTargets(targets: $targets) {
          responseResult { succeeded message }
        }
      }
    }
    """
    targets = [
        {
            "isEnabled": enabled,
            "key": "disk",
            "mode": "push",
            "syncInterval": "P0D",
            "config": [
                {"key": "path", "value": json.dumps({"v": CONTENT_PATH})},
                {"key": "createDailyBackups", "value": json.dumps({"v": False})},
            ],
        }
    ]
    result = graphql(query, token, {"targets": targets})["storage"]["updateTargets"][
        "responseResult"
    ]
    if not result["succeeded"]:
        sys.exit(f"could not update the storage target: {result['message']}")


def import_content(token: str) -> None:
    log(f"importing pages from {CONTENT_PATH}")
    set_disk_target(token, enabled=True)

    query = """
    mutation {
      storage {
        executeAction(targetKey: "disk", handler: "importAll") {
          responseResult { succeeded message }
        }
      }
    }
    """
    result = graphql(query, token)["storage"]["executeAction"]["responseResult"]
    if not result["succeeded"]:
        sys.exit(f"import failed: {result['message']}")

    # Disable it again. The target is a "push" target, so leaving it on would
    # have Wiki.js write edits back out to a read-only mount and log errors.
    # Importing is all we want from it.
    set_disk_target(token, enabled=False)
    log("import complete")


def list_pages(token: str) -> list[dict]:
    return graphql("{ pages { list { id path title } } }", token)["pages"]["list"]


def remove_non_wiki_pages(token: str) -> None:
    for page in list_pages(token):
        if page["path"] in NOT_WIKI_PAGES:
            graphql(
                "mutation($id: Int!) { pages { delete(id: $id) "
                "{ responseResult { succeeded message } } } }",
                token,
                {"id": page["id"]},
            )
            log(f"removed non-wiki page: {page['path']}")


def rebuild_navigation(token: str) -> None:
    """
    Replace the sidebar with one entry per published page.

    Wiki.js seeds a static navigation list holding only Home. Left alone, every
    other page is reachable by URL but linked from nowhere, so a reader who does
    not already know the page names cannot find them.

    Rebuilt from the pages that actually exist rather than from a hand-kept
    list, so adding or removing a page is reflected on the next run.
    """
    pages = {page["path"]: page["title"] for page in list_pages(token)}
    ordered = [p for p in NAV_ORDER if p in pages]
    ordered += sorted(p for p in pages if p not in NAV_ORDER)

    items = [
        {
            "id": f"page-{index}",
            "kind": "link",
            "label": pages[path],
            "icon": NAV_ICONS.get(path, DEFAULT_NAV_ICON),
            # The home page is reached at / rather than /home.
            "targetType": "home" if path == "home" else "page",
            "target": "/" if path == "home" else f"/{path}",
            "visibilityMode": "all",
            "visibilityGroups": [],
        }
        for index, path in enumerate(ordered)
    ]

    result = graphql(
        """
        mutation($tree: [NavigationTreeInput]!) {
          navigation {
            updateTree(tree: $tree) { responseResult { succeeded message } }
          }
        }
        """,
        token,
        {"tree": [{"locale": "en", "items": items}]},
    )["navigation"]["updateTree"]["responseResult"]
    if not result["succeeded"]:
        sys.exit(f"could not rebuild the navigation: {result['message']}")

    # MIXED keeps the list above and still offers the page browser alongside it.
    graphql(
        "mutation { navigation { updateConfig(mode: MIXED) "
        "{ responseResult { succeeded message } } } }",
        token,
    )
    log(f"sidebar rebuilt with {len(items)} entries")


def ensure_guest_read(token: str) -> None:
    group = graphql(
        """
        query($id: Int!) {
          groups { single(id: $id) {
            id name redirectOnLogin permissions
            pageRules { id deny match roles path locales }
          } }
        }
        """,
        token,
        {"id": GUEST_GROUP_ID},
    )["groups"]["single"]

    if all(p in group["permissions"] for p in READ_PERMISSIONS):
        log("guests can read without signing in")
        return

    log("granting guests read access")
    graphql(
        """
        mutation($id: Int!, $name: String!, $redirect: String!,
                 $perms: [String]!, $rules: [PageRuleInput]!) {
          groups {
            update(id: $id, name: $name, redirectOnLogin: $redirect,
                   permissions: $perms, pageRules: $rules) {
              responseResult { succeeded message }
            }
          }
        }
        """,
        token,
        {
            "id": group["id"],
            "name": group["name"],
            "redirect": group.get("redirectOnLogin") or "/",
            "perms": READ_PERMISSIONS,
            "rules": [
                {
                    "id": "guest",
                    "deny": False,
                    "match": "START",
                    "roles": READ_PERMISSIONS,
                    "path": "",
                    "locales": [],
                }
            ],
        },
    )


def main() -> int:
    wait_for_http()
    token = authenticate()
    configure_site(token)
    import_content(token)
    remove_non_wiki_pages(token)
    rebuild_navigation(token)
    ensure_guest_read(token)

    pages = list_pages(token)
    log(f"{len(pages)} pages available:")
    for page in sorted(pages, key=lambda p: p["path"]):
        log(f"    /{page['path']}  —  {page['title']}")
    log("ready — open the wiki, no login required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
