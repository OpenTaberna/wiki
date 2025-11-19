---
title: API Architecture
description: Architecture Design for MVP Endpoints
published: true
date: 2025-11-19T20:36:00.097Z
tags: api, architecture
editor: markdown
dateCreated: 2025-11-19T20:13:35.465Z
---

# API Architecture


Item description:

```json
{
  "uuid": "0b9e2c50-5e3b-4cc1-9a6a-2b3e9a0b1234",
  "sku": "CHAIR-RED-001", // Stock Keeping Unit (like uuid just human readable)
  "status": "active",                // draft | active | archived

  "name": "Red Wooden Chair",
  "slug": "red-wooden-chair",  // shown in the url instead of uuid

  "short_description": "Comfortable red wooden chair for dining rooms.",
  "description": "Long HTML/Markdown description here...",

  "categories": [
    "2f61e8db-bb70-4b22-9aa0-4d7fa3b7aa11"   // category UUIDs
  ],
  "brand": "Acme Furniture",

  "price": {
    "amount": 9999,                  // store as integer cents
    "currency": "EUR",
    "includes_tax": true,
    "original_amount": 12999,        // optional (for discounts)
    "tax_class": "standard"          // e.g. standard | reduced | none
  },

  "media": {
    "main_image": "https://cdn.example.com/items/chair-main.jpg",
    "gallery": [
      "https://cdn.example.com/items/chair-side.jpg",
      "https://cdn.example.com/items/chair-back.jpg"
    ]
  },

  "inventory": {
    "stock_quantity": 25,
    "stock_status": "in_stock",      // in_stock | out_of_stock | preorder | backorder
    "allow_backorder": false
  },

  "shipping": {
    "is_physical": true,
    "weight": {
      "value": 7.5,
      "unit": "kg"
    },
    "dimensions": {
      "width": 45.0,
      "height": 90.0,
      "length": 50.0,
      "unit": "cm"
    },
    "shipping_class": "standard"     // e.g. standard, bulky, letter
  },

  "attributes": {
    "color": "red",
    "material": "wood"
  },

  "identifiers": {
    "barcode": "4006381333931",
    "manufacturer_part_number": "AC-CHAIR-RED-01",
    "country_of_origin": "DE"
  },

  "custom": {
    "any_plugin_can_put": "whatever_here"
  },

  "system": {
    "log_table": "uuid_to_conversation_in_different_table",
  }
}
```


















 