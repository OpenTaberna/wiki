---
title: Database Architecture
description: Holds Ideas for a possible Database Architecture
published: true
date: 2025-11-19T20:59:12.870Z
tags: architecture, database
editor: markdown
dateCreated: 2025-11-19T20:45:46.121Z
---

# Database Architecture

To improve indexation and performance I suggest the following layout. (See the Item description in [API Architecture](/API/Architecture) to have a better understanding of the data set we are thinking about).

**Diagram**
Sadly the wiki can not display it. Therefore please copy paste the mermaid section into any markdown convertor and have a look (I like Obsidian for that). Here is a picture of the diagram.


![database_diagram_layout.jpg](/database/database_diagram_layout.jpg)

```mermaid
erDiagram

    SHOPS {
        uuid id PK
        text name
        timestamptz created_at
    }

    CATEGORIES {
        uuid id PK
        uuid shop_id FK
        text name
        text slug
        uuid parent_id FK
        int position
        timestamptz created_at
        timestamptz updated_at
    }

    ITEMS {
        uuid id PK
        uuid shop_id FK
        uuid uuid UNIQUE
        text sku UNIQUE
        text status
        text name
        text slug
        text short_description
        text description
        text brand

        bigint price_amount
        char(3) price_currency
        boolean price_includes_tax
        bigint price_original_amount
        text tax_class

        int stock_quantity
        text stock_status
        boolean allow_backorder

        text main_image_url

        boolean is_physical
        numeric weight_value
        text weight_unit
        numeric dim_width
        numeric dim_height
        numeric dim_length
        text dim_unit
        text shipping_class

        text barcode
        text manufacturer_part_number
        char(2) country_of_origin

        jsonb custom_data

        timestamptz created_at
        timestamptz updated_at
        text created_by
        text updated_by
    }

    ITEM_CATEGORIES {
        uuid item_id FK
        uuid category_id FK
    }

    ITEM_MEDIA {
        uuid id PK
        uuid item_id FK
        text url
        int position
        text alt_text
    }

    ATTRIBUTES {
        uuid id PK
        uuid shop_id FK
        text code
        text name
        text data_type
        timestamptz created_at
    }

    ITEM_ATTRIBUTES {
        uuid item_id FK
        uuid attribute_id FK
        text value_text
        numeric value_number
        boolean value_bool
    }

    ITEM_EVENTS {
        uuid id PK
        uuid item_id FK
        text event_type
        jsonb payload
        timestamptz created_at
        text user_id
    }

    %% Relationships

    SHOPS ||--o{ CATEGORIES : "has many"
    SHOPS ||--o{ ITEMS : "has many"
    SHOPS ||--o{ ATTRIBUTES : "has many"

    CATEGORIES ||--o{ CATEGORIES : "parent_of (self-rel)"
    ITEMS ||--o{ ITEM_CATEGORIES : "categorized_by"
    CATEGORIES ||--o{ ITEM_CATEGORIES : "contains_items"

    ITEMS ||--o{ ITEM_MEDIA : "has media"
    ITEMS ||--o{ ITEM_ATTRIBUTES : "has attributes"
    ATTRIBUTES ||--o{ ITEM_ATTRIBUTES : "used by"

    ITEMS ||--o{ ITEM_EVENTS : "has events"

```






Table for Categories:
```sql
CREATE TABLE categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id     UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,

    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    parent_id   UUID REFERENCES categories(id),

    position    INT NOT NULL DEFAULT 0,    -- for sorting
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX ux_categories_shop_slug
    ON categories (shop_id, slug);
```

Table to store essential item data

```sql
CREATE TABLE items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id     UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,

    uuid        UUID NOT NULL UNIQUE,             -- external UUID if you want it separate
    sku         TEXT UNIQUE,                      -- can be NULL, but unique if present
    status      TEXT NOT NULL CHECK (status IN ('draft', 'active', 'archived')),

    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    short_description TEXT,
    description TEXT,
    brand       TEXT,

    -- Price
    price_amount        BIGINT NOT NULL,         -- cents
    price_currency      CHAR(3) NOT NULL,        -- 'EUR', 'USD', ...
    price_includes_tax  BOOLEAN NOT NULL DEFAULT TRUE,
    price_original_amount BIGINT,                -- NULL if no discount
    tax_class           TEXT NOT NULL DEFAULT 'standard',

    -- Inventory
    stock_quantity      INT NOT NULL DEFAULT 0,
    stock_status        TEXT NOT NULL CHECK (stock_status IN ('in_stock', 'out_of_stock', 'preorder', 'backorder')),
    allow_backorder     BOOLEAN NOT NULL DEFAULT FALSE,

    -- Media
    main_image_url      TEXT,

    -- Shipping
    is_physical         BOOLEAN NOT NULL DEFAULT TRUE,
    weight_value        NUMERIC(12,4),
    weight_unit         TEXT,
    dim_width           NUMERIC(12,4),
    dim_height          NUMERIC(12,4),
    dim_length          NUMERIC(12,4),
    dim_unit            TEXT,
    shipping_class      TEXT,

    -- Identifiers
    barcode                 TEXT,
    manufacturer_part_number TEXT,
    country_of_origin       CHAR(2),             -- ISO country code, e.g. 'DE'

    -- Custom
    custom_data         JSONB,                   -- for plugins/free-form data

    -- System
    log_table_ref       UUID,                    -- references some other log table if you want
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by          TEXT,                    -- keycloak user ID
    updated_by          TEXT
);

-- URL friendly & shop-scoped: one slug per shop
CREATE UNIQUE INDEX ux_items_shop_slug
    ON items (shop_id, slug);

-- Useful query indexes
CREATE INDEX ix_items_shop_status
    ON items (shop_id, status);

CREATE INDEX ix_items_shop_brand
    ON items (shop_id, brand);

CREATE INDEX ix_items_price
    ON items (shop_id, price_amount);

CREATE INDEX ix_items_stock_status
    ON items (shop_id, stock_status);

```


Model join relationship between the item and category table:


```sql
CREATE TABLE item_categories (
    item_id     UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, category_id)
);

CREATE INDEX ix_item_categories_category
    ON item_categories (category_id);

```

Table for the Media Gallery:

```sql
CREATE TABLE item_media (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id     UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    position    INT NOT NULL DEFAULT 0,   -- 0,10,20,... for reordering
    alt_text    TEXT
);

CREATE INDEX ix_item_media_item
    ON item_media (item_id);
```

Attribute definition table
```sql
CREATE TABLE attributes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id     UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,

    code        TEXT NOT NULL,               -- e.g. 'color', 'material'
    name        TEXT NOT NULL,               -- display name
    data_type   TEXT NOT NULL CHECK (data_type IN ('text', 'number', 'boolean')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX ux_attributes_shop_code
    ON attributes (shop_id, code);

```


Item_Attribute table:

```sql

CREATE TABLE item_attributes (
    item_id     UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    attribute_id UUID NOT NULL REFERENCES attributes(id) ON DELETE CASCADE,

    value_text  TEXT,
    value_number NUMERIC(20,4),
    value_bool  BOOLEAN,

    PRIMARY KEY (item_id, attribute_id)
);

CREATE INDEX ix_item_attributes_attr
    ON item_attributes (attribute_id);
```




For later the System log and event table:

```sql
CREATE TABLE item_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id     UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,          -- 'created', 'updated', 'price_changed', ...
    payload     JSONB,                  -- old/new values, diff, etc.
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id     TEXT                    -- Keycloak ID if available
);

CREATE INDEX ix_item_events_item
    ON item_events (item_id);

CREATE INDEX ix_item_events_type
    ON item_events (event_type);

```



























