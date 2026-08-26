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

## Reading it locally

```bash
python3 tools/serve.py      # http://localhost:8090
```

Renders the Markdown with Mermaid diagrams and working internal links, so a change can be
checked before it is published. Standard library only — no install step. Marked and
Mermaid load from a CDN, so the first page view needs a network connection.

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

CI runs it on every push and pull request.

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
