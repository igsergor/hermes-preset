---
name: storefront-catalog-audit
description: "Use when auditing a shop's catalog, prices, or labels."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ecommerce, shopify, catalog, pricing, labels, research]
    related_skills: [product-price-monitor]
---

# Storefront Catalog Audit (Shopify & friends)

Enumerating a shop's products, real prices, variant counts and label facts to
produce an exact buy-list. The shop is a **structured catalog**, not prose —
reach for its own endpoints before scraping rendered pages.

## When to Use

Load this when the task is to enumerate what a vendor sells and what it costs:
«посмотри в его магазине, что купить», exact quantities for a course, price
and variant comparison across pack sizes, or "does this store even sell X".
Not for watching one known item over time — that is `product-price-monitor`.

## The ladder

1. **The storefront's JSON endpoint** — the authoritative source of price,
   variants, availability and SKU:
   ```bash
   curl -s "https://<shop>/products/<handle>.json" | python3 -m json.tool
   ```
   Gives every variant's `title`, `price`, `available`, `sku`, plus
   `available`/`published_at` on the product. No scraping, no JS.
2. **`/search/suggest.json`** for autocomplete ids when handles are unknown.
3. **`/sitemap_products_*.xml`** — the ONLY reliable way to get the complete
   catalog. Handles are not guessable and search does not filter (see below).
4. **A reader proxy** (`r.jina.ai/<product-url>`) when JSON is rate-limited but
   you need the human-facing bullets: benefit lines, "per serving" amounts,
   price block. Prefer it over re-trying a rate-limited JSON call.
5. **Product images + vision** for the Supplement Facts panel — storefront
   text frequently omits the actual label doses.

## Pitfalls

- **The on-site search does NOT filter.** `search?q=zinc` returns ~16 results
  for a store with 3 zinc products, and the same count for a nonsense query
  (`zzzzqqqxx`). Proving it: run a fake query and compare the result count. If
  a term has no hits in page text but the count is normal, the product does
  not exist — but confirm via the sitemap, never by trusting search absence.
- **`.json` endpoints rate-limit aggressively** and then return a bare
  `local_rate_limited` body that is NOT JSON — a parse error that reads like
  a wrong URL. Space the calls, or switch to the reader proxy; do not loop.
- **`backordered` / `available: false` is a real product state.** A product
  page rendering "Unavailable" can still be the only formulation of that
  ingredient. Report it as out of stock rather than silently substituting.
- **Price from the JSON variant list is per-variant.** A "$14.99–$34.99"
  range on a collection page means two potencies of the SAME product — pick by
  dose, and state the potency you chose and why.
- **Never trust a blog/supplement page for dose or price.** The label dose,
  the speaker's recommended dose, and the storefront price are three different
  numbers; cite each to its own source.
- **Deduplicate products by handle, not by title** — bundles (`<a>-and-<b>-bundle`)
  and single SKUs share most of their catalog content, and buying both
  double-doses what the bundle already contains.

## Building the buy-list

- Compute quantities from the protocol (dose × people × days) and reconcile
  against pack sizes in one table. Show the arithmetic, and flag where the
  result leaves a surplus (buying 4 bottles for a 360-capsule need) with the
  cheaper alternative costed alongside — do not silently pad the order.
- Name the exact variant per line ("150 Capsules ×2, 90 Capsules ×1") and link
  the product page, so the order is reproducible without re-deriving it.
- Separate what is already covered inside another purchased product from what
  genuinely must be bought.
- State totals per currency and per store; note when a store cannot ship to
  the user's country.