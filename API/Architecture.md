---
title: API Architecture
description: Endpoint reference, response envelope and error model
published: true
date: 2026-08-26T12:00:00.000Z
tags: api, architecture, endpoints, reference
editor: markdown
dateCreated: 2025-11-19T20:13:35.465Z
---

# API Architecture

> **The authoritative reference is the running instance.** Every deployment serves
> interactive documentation at `/docs` and the raw schema at `/openapi.json`, both
> generated from the code. This page describes the shape of the API and lists what it
> serves so you can read it without booting anything — but where the two disagree, `/docs`
> is right and this page is stale. Please fix it.

All application endpoints are served under the **`/v1`** prefix. Health endpoints are not
versioned. There is no `/api` prefix — if you see one in browser dev tools it is the
storefront's own Nginx proxying `/api/v1` to `/v1`.

## Service layout

The API is a set of self-contained "mini-API" modules, each owning its models, routes and
persistence:

| Service | Prefix | Purpose |
|---|---|---|
| Item store | `/v1/items` | Product catalogue and product images |
| Customers | `/v1/customers` | Profiles and addresses, always self-scoped |
| Orders | `/v1/orders` | Draft orders, checkout, cancellation, return requests |
| Inventory | `/v1/admin/inventory` | Stock levels and reservations |
| Admin | `/v1/admin/orders` | Back-office fulfillment |
| Analytics | `/v1/admin/analytics` | Commercial reporting over the order history |
| Storefront analytics | `/v1/analytics` | Anonymous shopper telemetry ingest (public) |
| Frontend errors | `/v1/telemetry` | Uncaught browser error reports (public ingest) |
| Admin mail | `/v1/admin/mail` | Mailbox configuration and folders |
| Returns | `/v1/admin/returns` | Admin decisions on return requests |
| Webhooks | `/v1/webhooks` | Inbound payment provider callbacks |
| Health | `/health` | Liveness and readiness |

Payments and shipments have no public router of their own. They are driven by the order,
webhook and admin endpoints, and are documented under
[Orders and Fulfillment](/Orders-and-Fulfillment).

---

## Endpoints

**Auth** below means a bearer token is required. Which token is not always the same
question — admin endpoints additionally check which client issued it. See
[Authorization](/Authorization).

### Catalogue — `/v1/items`

Reads are public so that shoppers can browse before signing in. Writes are admin-only:
what is listed is what customers see, so anyone able to create, alter or delete a product
controls the shop.

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/v1/items/` | List items | — |
| `GET` | `/v1/items/{item_uuid}` | Get item by UUID | — |
| `GET` | `/v1/items/by-sku/{sku}` | Get item by SKU | — |
| `GET` | `/v1/items/{item_uuid}/image` | Get the product image | — |
| `POST` | `/v1/items/` | Create a new item | admin |
| `PATCH` | `/v1/items/{item_uuid}` | Update item | admin |
| `DELETE` | `/v1/items/{item_uuid}` | Delete item | admin |
| `PUT` | `/v1/items/{item_uuid}/image` | Upload the product image | admin |

Product images are held in MinIO, not in the database. Uploads are capped by
`STORAGE_MAX_IMAGE_BYTES` (5 MB by default) so a single oversized file cannot fill the
object store.

### Customers — `/v1/customers`

Every route here is scoped to the caller. The customer is identified from the verified
`sub` claim on the token, so passing somebody else's id alongside your own valid token
does not get you their data.

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/v1/customers/me` | Get my profile | yes |
| `PATCH` | `/v1/customers/me` | Update my profile | yes |
| `GET` | `/v1/customers/me/addresses` | List my addresses | yes |
| `POST` | `/v1/customers/me/addresses` | Create an address | yes |
| `PATCH` | `/v1/customers/me/addresses/{address_id}` | Update an address | yes |
| `DELETE` | `/v1/customers/me/addresses/{address_id}` | Delete an address | yes |

### Orders — `/v1/orders`

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/v1/orders/` | Create a draft order | yes |
| `GET` | `/v1/orders/{order_id}` | Get order by ID | yes |
| `DELETE` | `/v1/orders/{order_id}` | Cancel a draft order | yes |
| `POST` | `/v1/orders/{order_id}/checkout` | Start checkout | yes |
| `POST` | `/v1/orders/{order_id}/returns` | Request a return | yes |

`POST /checkout` is the interesting one: it reserves stock and creates the payment intent.
See [Orders and Fulfillment](/Orders-and-Fulfillment).

### Back office — `/v1/admin`

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/v1/admin/orders/` | List all orders | admin |
| `GET` | `/v1/admin/orders/pick-list` | Batch pick list | admin |
| `GET` | `/v1/admin/orders/{order_id}` | Get order detail | admin |
| `PATCH` | `/v1/admin/orders/{order_id}/status` | Override order status | admin |
| `POST` | `/v1/admin/orders/{order_id}/shipments` | Create shipment | admin |
| `POST` | `/v1/admin/orders/{order_id}/label` | Trigger DHL label job | admin |
| `GET` | `/v1/admin/orders/{order_id}/label` | Download carrier label | admin |
| `GET` | `/v1/admin/orders/{order_id}/packing-slip` | Packing slip | admin |
| `POST` | `/v1/admin/orders/{order_id}/ship` | Mark order as shipped | admin |
| `PATCH` | `/v1/admin/returns/{return_id}` | Approve, reject or complete a return | admin |

### Analytics — `/v1/admin/analytics`

Commercial reporting, computed in SQL over **all** orders rather than a recent sample.

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/v1/admin/analytics/summary` | Revenue, refunds, AOV, units, vs the previous period | admin |
| `GET` | `/v1/admin/analytics/timeseries` | The same figures bucketed by day, week or month | admin |
| `GET` | `/v1/admin/analytics/products` | Per-SKU units, revenue, return rate, unsold stock | admin |
| `GET` | `/v1/admin/analytics/funnel` | Where orders stop | admin |

All four take optional `from` and `to` calendar dates, inclusive, defaulting to the last 30
days. A window longer than five years is refused: the figures are computed live rather than
from a rollup table, so an unbounded range is a slow query waiting to happen.

#### What counts as revenue

These are choices, not facts, so they are written down rather than left implicit in a query:

| Term | Definition |
|---|---|
| Gross revenue | Orders in `paid`, `ready_to_ship` or `shipped` |
| Refunded | Orders in `refunded` — **whole-order only** |
| Net revenue | Gross less refunded |
| Average order value | Gross divided by revenue-producing orders |
| Units | Line quantities on revenue-producing orders |

Never counted: `draft`, `pending_payment`, `cancelled`, and anything soft-deleted.

#### Money is grouped by currency

Every money-bearing response is a **list keyed by currency**, not a single figure.
`orders.currency` permits more than one, and a total summed across currencies is not
slightly wrong — it is meaningless. For the usual single-currency shop the list has one
entry and reads like a plain number.

A client must not add these together. The response shape exists to make that mistake
visible rather than silent.

#### Days are cut in the shop's timezone

Buckets use `SHOP_TIMEZONE` (default `Europe/Berlin`), not UTC. An order placed at 23:30
UTC belongs to the next day in Berlin, and bucketing on UTC would file a day's takings
against the wrong day — an error that looks like a data problem for weeks. See
[Configuration](/Configuration).

#### The shopper funnel

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/v1/admin/analytics/storefront` | Sessions → product views → carts → checkouts → paid | admin |

What happens *before* an order exists — which the order funnel above cannot see, because
nothing has happened in the order tables yet. Fed by the public ingest endpoint below.

Sessions are counted distinctly: ten product views from one shopper is one person
considering a purchase, not ten.

**The pre-order steps are a floor, not a count.** Blocked scripts, a tab closed before the
batch flushed and disabled JavaScript all lose events. The `paid` step is read from the
orders table and is exact. A funnel that undercounts its first step but not its last
overstates the drop, so the two are labelled differently rather than presented as one
continuous measurement. Real conversion is never worse than reported.

Returns `enabled: false` with zeroes when the deployment is not collecting — "nobody
visited" and "we are not counting" would otherwise look identical.

#### What these numbers cannot tell you

Stated plainly, because a reader will otherwise infer something stronger:

- **The funnel is an order funnel, not a visitor funnel.** It begins at order creation and
  cannot see shoppers who browsed without ordering. Visitor conversion needs session data
  the API does not collect.
- **Partial refunds are not modelled.** `orders.status = refunded` is all-or-nothing, so
  refund figures will not reconcile against a partially refunded Stripe charge.
- **Per-SKU return rate is an upper bound.** Returns are recorded per order, not per line,
  so a return on a two-line order counts against both SKUs.
- **Product revenue need not equal order revenue.** Product figures sum line values; an
  order total may carry shipping or adjustments belonging to no line.

Checkout is counted from the `payments` table rather than from `orders.status`. Status
records only where an order is *now*, so a cancelled order is indistinguishable from one
that never reached checkout, and an order that shipped then was refunded no longer says it
shipped. A payment row is written when checkout starts and survives whatever follows.

### Inventory — `/v1/admin/inventory`

Stock is deliberately separate from the catalogue. The `inventory` block on an item is
catalogue metadata for display; authoritative stock lives here and is what checkout
reserves against.

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/v1/admin/inventory/` | Create inventory record | admin |
| `GET` | `/v1/admin/inventory/` | List inventory items | admin |
| `GET` | `/v1/admin/inventory/by-sku/{sku}` | Get inventory item by SKU | admin |
| `GET` | `/v1/admin/inventory/{inventory_id}` | Get inventory item by UUID | admin |
| `PATCH` | `/v1/admin/inventory/{inventory_id}` | Update stock | admin |
| `DELETE` | `/v1/admin/inventory/{inventory_id}` | Delete inventory record | admin |

### Storefront ingest — `/v1/analytics`

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/v1/analytics/events` | Record anonymous shopper events | — |

**Public by design**, because a shopper who has not signed in is exactly who this measures.
Off unless `STOREFRONT_ANALYTICS_ENABLED` is set, returning `404` while off so a deployment
that has not opted in does not advertise the capability. Returns `202`: the browser must
neither wait on the result nor retry.

Nothing stored identifies a person. There is no column for an IP address, a user agent, an
email or a customer id, and query strings are stripped before storage — that is where
personal data arrives by accident, in a share link or a redirect. The request schema
forbids unknown fields, so a client sending `email` gets a `422` rather than having it
quietly dropped.

Because nothing identifies anyone and the browser stores only a per-tab session id, this
requires no consent banner in the EU. That is the reason for the shape rather than a happy
accident: a banner costs 40–60% of sessions to opt-outs, which would make the funnel it
feeds mostly fiction.

Being public, it is guarded accordingly — rate limited, batch capped at 50 events, a closed
event vocabulary, and every field length-bounded. The worst an abusive client achieves is
noise in a report.

Browser timestamps outside ±24 hours of server time are discarded and counted in
`rejected`. Clocks are wrong often enough that rejecting all skew would lose real data, and
trusting all of it would let anyone write into a period already reported on.

### Frontend errors — `/v1/telemetry` and `/v1/admin/telemetry`

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/v1/telemetry/errors` | Report uncaught browser errors | — |
| `GET` | `/v1/admin/telemetry/errors` | Read them, grouped by frequency | admin |

Traces and metrics see nothing that happens in a browser. A component that throws leaves the
server returning `200` with healthy metrics while the shop is broken for a real customer —
and for a shop, by the time someone reports it the sale is gone.

Reporting is **public**, because storefront visitors are not signed in and an error before
login is exactly the one worth catching. Off unless `FRONTEND_ERRORS_ENABLED` is set,
returning `404` while off.

**The user agent is reduced, never stored.** A raw agent string is a fingerprint, but "which
browser?" is genuinely diagnostic, so it is reduced at the boundary to a family and major
version — `Safari 18` reproduces a bug and does not recognise anyone. The reduction doubles
as a filter: whatever a client sends, the output is a known family name and an integer.

Errors are grouped by application, error class and message, **not by stack**: the same fault
reached from two routes produces two stacks and is one bug. `affected_paths` carries the
spread instead.

> **This shows only what browsers managed to send.** An error that breaks a page badly
> enough to stop the reporter is precisely the one that will not appear. Read a quiet list as
> *no news*, never as *no errors*.

Being public, it is rate limited harder than the analytics ingest — a component throwing in
a render loop reports as fast as the browser can loop — with a batch cap, a closed `app`
vocabulary, bounded fields and truncated stacks.

### Admin mail — `/v1/admin/mail`

Provider-neutral mailbox access for the back office, over IMAP and SMTP.

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/v1/admin/mail/status` | Mailbox configuration status | admin |
| `GET` | `/v1/admin/mail/folders` | List mail folders | admin |
| `POST` | `/v1/admin/mail/folders` | Create a folder | admin |
| `PATCH` | `/v1/admin/mail/folders/{folder}` | Rename a folder | admin |
| `DELETE` | `/v1/admin/mail/folders/{folder}` | Delete a folder | admin |
| `GET` | `/v1/admin/mail/folders/{folder}/messages` | List messages | admin |
| `GET` | `/v1/admin/mail/folders/{folder}/messages/{uid}` | Read a message | admin |
| `DELETE` | `/v1/admin/mail/folders/{folder}/messages/{uid}` | Permanently delete a message | admin |
| `PATCH` | `/v1/admin/mail/folders/{folder}/messages/{uid}/flags` | Update message flags | admin |
| `POST` | `/v1/admin/mail/folders/{folder}/messages/{uid}/move` | Move a message | admin |
| `GET` | `/v1/admin/mail/folders/{folder}/messages/{uid}/attachments/{part_id}` | Download an attachment | admin |
| `POST` | `/v1/admin/mail/messages` | Send a message | admin |

Messages are addressed by IMAP `uid` within a folder, so a `uid` is only meaningful
alongside the folder it came from. `GET /status` reports whether a mailbox is configured at
all, which is the endpoint to check first when the others return nothing.

This is separate from the transactional mail the API sends itself — order tracking
notifications go out over the `SMTP_*` settings in [Configuration](/Configuration) and do
not pass through here.

### Webhooks and health

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/v1/webhooks/stripe` | Stripe payment webhook | signature |
| `GET` | `/health` | Liveness check | — |
| `GET` | `/health/ready` | Readiness check | — |

The webhook is unauthenticated in the bearer-token sense but is not open: it verifies the
Stripe signature and rejects anything that fails, and it is idempotent — a replayed event
is a no-op returning `200`.

`/health` answers as soon as the process is up. `/health/ready` additionally probes
PostgreSQL and Redis and reports the latency and error for each, which is the one you want
behind a load balancer.

---

## The response envelope

Every JSON response shares a common envelope rather than returning a bare object:

```json
{
  "success": true,
  "message": "Items retrieved successfully",
  "timestamp": "2026-08-26T11:54:20.530614Z",
  "request_id": null,
  "metadata": null,
  "items": [ ... ]
}
```

The payload key is named for what it carries (`items`, `order`, `customer`, …), so a
client can tell a list response from a single-object one without inspecting types.

`request_id` carries the correlation ID. Every request passes through a middleware that
assigns one and threads it through the logs, so a customer's report of "it broke at
14:32" can be traced to the exact request across the API and the worker.

## Errors

Errors use the same envelope with `success: false` plus error fields:

```json
{
  "success": false,
  "message": "Item not found",
  "timestamp": "2026-08-26T11:54:20.530614Z",
  "request_id": "3f9c…",
  "status_code": 404,
  "error_code": "NOT_FOUND",
  "error_category": "not_found",
  "details": null
}
```

The HTTP status is derived from the error category, so a category is never reported under
an inconsistent status:

| `error_category` | HTTP status |
|---|---|
| `not_found` | 404 |
| `validation` | 422 |
| `authentication` | 401 |
| `authorization` | 403 |
| `business_rule` | 400 |
| `database` | 500 |
| `external_service` | 502 |
| `internal` | 500 |

Request validation failures (wrong types, missing fields) return `422` with an extra
`validation_errors` array, each entry carrying `loc`, `msg` and `type`. This is
FastAPI's own validation output remapped into the envelope, so the response actually
matches the `422` schema documented in `/docs` — which the raw Pydantic format does not.

Unhandled exceptions are caught by a catch-all handler, logged with the correlation ID and
returned as a generic `500`. Internal detail is never leaked to the client.

## Rate limiting

Rate limiting is applied per client IP via SlowAPI and is **opt-in per route** rather than
global. Two settings control it: `RATE_LIMIT_ENABLED` turns it off entirely (useful in
tests and local development) and `RATE_LIMIT_PER_MINUTE` sets the budget, 60 by default.
Exceeding it returns `429`.

Behind a load balancer the limiter needs to read `X-Forwarded-For` instead of the socket
address, or every request will look like it came from the proxy. See
[Deployment](/Deployment).

---

## The item shape

An item as the API returns it. Prices are integer minor units — cents, never floats:

```json
{
  "uuid": "0b9e2c50-5e3b-4cc1-9a6a-2b3e9a0b1234",
  "sku": "CHAIR-RED-001",
  "status": "active",
  "name": "Red Wooden Chair",
  "slug": "red-wooden-chair",
  "short_description": "Comfortable red wooden chair for dining rooms.",
  "description": "Long HTML/Markdown description here...",
  "categories": ["furniture", "chairs"],
  "brand": "Acme Furniture",

  "price": {
    "amount": 9999,
    "currency": "EUR",
    "includes_tax": true,
    "original_amount": 12999,
    "tax_class": "standard"
  },

  "media": {
    "main_image": "https://cdn.example.com/items/chair-main.jpg",
    "gallery": []
  },

  "inventory": {
    "stock_quantity": 25,
    "stock_status": "in_stock",
    "allow_backorder": false
  },

  "shipping": {
    "is_physical": true,
    "weight": { "value": 7.5, "unit": "kg" },
    "dimensions": { "width": 45.0, "height": 90.0, "length": 50.0, "unit": "cm" },
    "shipping_class": "standard"
  },

  "attributes": { "color": "red", "material": "wood" },

  "identifiers": {
    "barcode": "4006381333931",
    "manufacturer_part_number": "AC-CHAIR-RED-01",
    "country_of_origin": "DE"
  },

  "custom": { "any_plugin_can_put": "whatever_here" },
  "system": {}
}
```

`status` is one of `draft`, `active` or `archived`. `stock_status` is one of `in_stock`,
`out_of_stock`, `preorder` or `backorder`.

Two fields are traps worth naming:

- **`inventory` is display metadata, not truth.** Authoritative stock lives in the
  inventory service and is what checkout reserves against. An item claiming
  `stock_quantity: 25` will still fail checkout if the inventory record says otherwise.
- **`custom` is free-form** and belongs to whatever plugin writes it. Nothing in the API
  validates its contents.

The nested blocks are stored as `JSONB` columns rather than normalised into separate
tables — see [Database Architecture](/Database/Architecture) for why, and for what that
costs.
