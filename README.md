# OpenTaberna Wiki

The published wiki for the [OpenTaberna](https://github.com/OpenTaberna) project. Pages are
Markdown with Wiki.js front matter and are rendered at
[wiki.opentaberna.de](https://wiki.opentaberna.de).

## Pages

| Page | Covers |
|---|---|
| `home.md` | What the project is, the architecture, the four repositories |
| `Getting-Started.md` | Running the whole stack locally |
| `Authorization.md` | Keycloak roles, clients, and what the API enforces |
| `API/Architecture.md` | Endpoint reference, response envelope, error model |
| `Database/Architecture.md` | The schema as it is actually built |
| `Orders-and-Fulfillment.md` | Order lifecycle, payments, the outbox, returns |
| `Configuration.md` | Every setting and where it can come from |
| `Deployment.md` | Production deployment |

## Running the wiki locally

```bash
docker compose up -d
```

Then open **http://localhost:3000**. That is a self-hosted [Wiki.js](https://js.wiki)
serving this repository's pages — the same software the published wiki runs on, so a page
looks here exactly as it will look once published.

**No login.** The setup wizard is completed for you and guests can read every page
anonymously. There is nothing to click through and no account to create.

Port 3000 taken?

```bash
WIKI_PORT=3030 docker compose up -d
```

### What comes up

| Service | Role |
|---|---|
| `wiki` | Wiki.js 2.5 |
| `db` | PostgreSQL 16, its backing store |
| `bootstrap` | Runs once and exits — completes setup, imports the pages, confirms guest read |

Your checkout is mounted **read-only**, so Wiki.js can import from it but never writes back
and never dirties your working tree.

An admin account exists because Wiki.js requires one
(`admin@opentaberna.local` / `opentaberna-local-admin`), but nothing asks you to use it.
It is a local development stack on a throwaway database — do not expose it to a network.

### Refreshing after an edit

Pages are imported into Wiki.js, so editing a `.md` file does not change what is served
until you re-import:

```bash
docker compose run --rm --no-deps bootstrap
```

That is idempotent — it re-imports the content and repairs the configuration if anything
has drifted.

### Starting over

```bash
docker compose down -v      # -v drops the database, so setup runs again
```

## Quick preview without Docker

```bash
python3 tools/serve.py      # http://localhost:8090
```

A lighter alternative when you only want to eyeball a change: it renders the Markdown with
Mermaid diagrams and working internal links. Standard library only, no install step. Marked
and Mermaid load from a CDN, so the first page view needs a network connection.

It is a preview shim, not Wiki.js — use `docker compose up -d` when it matters how the page
will really look.

## Keeping it honest

This wiki drifted nine months out of date once ([#1](https://github.com/OpenTaberna/wiki/issues/1)),
documenting database tables that were never created and endpoints that never existed.

`tools/check_wiki.py` is what stops that happening quietly again:

```bash
python3 tools/check_wiki.py
```

It fails when

1. the API serves an endpoint no page mentions,
2. a page documents a path the API does not serve, or
3. an internal link points at a page that does not exist.

`tools/check_wikijs.py` covers the other half — that the stack above still serves every page
without a login:

```bash
docker compose up -d
python3 tools/check_wikijs.py
```

It fails when a page is missing, returns a non-200, or bounces an anonymous visitor to the
login screen.

CI runs both on every push and pull request.

### When the API changes

The check reads `openapi.snapshot.json`, a committed copy of the API's OpenAPI paths, so
CI needs nothing running. After the API changes, refresh it against a live instance:

```bash
# with the API running — see the fastapi repository
python3 tools/check_wiki.py --refresh http://localhost:8000
```

That is the point at which the check bites: pulling in a snapshot with a new endpoint makes
the check fail until somebody documents it. Refreshing the snapshot and updating the pages
belong in the same change.

## Conventions

- Front matter stays. Wiki.js uses `title`, `description`, `published`, `date`, `tags`,
  `editor` and `dateCreated`; bump `date` when you edit a page.
- Internal links are wiki-absolute — `/Getting-Started`, `/API/Architecture` — not relative
  file paths. The checker verifies they resolve.
- Prefer describing what is built. Where something is proposed rather than shipped, say so
  on the page; a proposal read as a description is how the last drift happened.
