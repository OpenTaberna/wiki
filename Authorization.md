---
title: Authorization
description: Roles, clients, and what the API actually enforces
published: true
date: 2026-08-26T12:00:00.000Z
tags: authorization, keycloak, security, roles, authentication
editor: markdown
dateCreated: 2026-08-26T12:00:00.000Z
---

# Authorization

User management runs on **Keycloak 26**. The realm is managed *in the `fastapi`
repository* (`keycloak/opentaberna-realm.json`) and imported on container start, so the
whole setup is reproducible from a clean checkout rather than being a thing somebody once
clicked together in an admin console.

## Two kinds of user

| Role | How it is granted | What it allows |
|---|---|---|
| `customer` | Automatically, to every account | Nothing special. It is the default role. |
| `admin` | Only by another admin | The back-office endpoints under `/v1/admin/**` |

`customer` is attached to `default-roles-opentaberna`, so anyone who registers receives it
without an administrator doing anything.

`admin` is a composite role that additionally carries the `realm-management` client roles
`manage-users`, `view-users`, `query-users` and `view-realm`. That is what makes "admins
are created by admins" true rather than aspirational: an existing admin holds exactly the
permissions needed to read the `admin` role and grant it to someone else, and a customer
holds none of them. A customer attempting either is refused by **Keycloak itself** — the
API is never consulted.

> `view-realm` is easy to miss when editing the realm by hand. Without it an admin can call
> the user endpoints but cannot read the role definition they are trying to grant, so
> promotion fails with a confusing `403` that looks like it comes from the API.

## Clients

| Client | Type | Purpose |
|---|---|---|
| `opentaberna-api` | confidential | The resource server. Validates tokens, mints none. Its client id is the audience the API expects. |
| `opentaberna-admin-ui` | public, PKCE | Back-office frontend. **The only client whose tokens are accepted on admin endpoints.** |
| `opentaberna-store-ui` | public, PKCE | Storefront. Never accepted on admin endpoints. |

Both frontends carry an audience mapper adding `opentaberna-api` to the token. Without it
a public client receives a token scoped only to `account`, leaving the API nothing
meaningful to validate.

## What the API enforces

### Admin endpoints — `/v1/admin/**`

All three must hold:

1. A token whose **signature, issuer, audience and expiry** check out.
2. The **`admin` realm role**.
3. An **`azp` in `KEYCLOAK_ADMIN_CLIENT_IDS`** — that is, the token was issued to the admin
   UI.

The third is the one worth understanding. Roles alone are not enough: an administrator
browsing the shop still carries the `admin` role in their *storefront* token. Accepting it
would mean any script running on the shop page — an injected ad, a compromised dependency,
an XSS — could drive the back office using the token sitting in that tab.

So the API asks not just *who are you* but *which application are you speaking through*.

### Catalogue writes

`POST`, `PATCH` and `DELETE` on `/v1/items` require an administrator too, and for the same
reason the admin endpoints do: what is listed is what customers see, so anyone able to
create, alter or delete a product controls the shop.

Reads stay public — shoppers browse before signing in.

### Customer-scoped endpoints

Endpoints under `/v1/customers/me` and a customer's own orders identify the caller from
the **verified `sub` claim**. A verified `sub` always beats any user id supplied in a
header or body, so a caller cannot read another customer's profile by passing an id
alongside their own valid token.

### Open by design

The catalogue reads, both health endpoints, and the Stripe webhook take no bearer token.
The webhook is not unprotected — it verifies the Stripe signature — but it is not
protected *by Keycloak*, because Stripe has no account here.

## Issuer URLs: the one that bites

Two settings look redundant and are not:

| Setting | Used for |
|---|---|
| `KEYCLOAK_URL` | Where the API fetches signing keys, server to server |
| `KEYCLOAK_PUBLIC_URL` | The base URL that appears in the token's `iss` claim |

Inside Compose the API reaches Keycloak at `http://opentaberna-keycloak:8080`, while the
browser that obtained the token used `http://localhost:8080`. The `iss` claim carries the
URL the *browser* used. If issuer validation compares against the internal URL, every
otherwise-valid token is rejected.

`KEYCLOAK_PUBLIC_URL` empty falls back to `KEYCLOAK_URL`, which is correct only when both
are the same host — typically outside Docker, or in production behind one public name.

## Signing keys are cached, not fetched once

`KEYCLOAK_JWKS_CACHE_SECONDS` (default 300) bounds how long the API caches Keycloak's
signing keys. Keycloak rotates keys, so fetching them once at startup means the API keeps
validating against a key that is eventually retired and then rejects everything. Caching
with an expiry is the whole fix.

## Development users

Three users ship in the realm import. These passwords are development-only and are
committed to a public repository — they are for your laptop, nowhere else.

| Username | Password | Role |
|---|---|---|
| `adminuser` | `adminpassword` | `admin` |
| `testuser` | `testpassword` | `customer` |
| `testuser2` | `testpassword2` | `customer` |

`testuser2` exists so cross-customer authorization can actually be tested: one customer
attempting to read another's data is a case you want a test for, and that needs two
customers.

## Getting a token by hand

Both frontend clients have direct grant enabled in development, so you can skip the browser:

```bash
TOKEN=$(curl -s -X POST \
  http://localhost:8080/realms/opentaberna/protocol/openid-connect/token \
  -d "client_id=opentaberna-admin-ui" \
  -d "grant_type=password" \
  -d "username=adminuser" \
  -d "password=adminpassword" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/admin/orders/
```

Without the header the same call returns `403`. Requesting the token through
`client_id=opentaberna-store-ui` instead also returns `403`, even for `adminuser` — which
is the `azp` check doing its job, and the quickest way to confirm it is working.

Direct grant is a **development** convenience. Production frontends use the authorization
code flow with PKCE, and `directAccessGrantsEnabled` should be off.

## In production

- Turn off direct access grants on both public clients.
- Replace the three seeded users, and change the Keycloak admin password from `admin`.
- Set `KEYCLOAK_CLIENT_SECRET` from a secret store, never from `.env`.
- Set `KEYCLOAK_PUBLIC_URL` to the public identity URL.
- Keep `KEYCLOAK_ADMIN_CLIENT_IDS` to the admin UI alone. Adding the storefront to it
  removes the protection described above entirely.

See [Configuration](/Configuration) and [Deployment](/Deployment).
