---
kind: system
---

# Data model

Last verified: 2026-05-10. Everything lives in `public` on the products RDS.
DDL is in `migrations/`, run by hand; the app never migrates anything.

## `public.products`

The catalogue the app manages. Columns the app reads or writes:

| Column | Meaning |
|---|---|
| `id` | PK. |
| `name` | Display name, shown in the table and edit modal. |
| `category` | Free text; the category filter matches it exactly. |
| `price` | numeric(10,2), USD. |
| `stock` | Units on hand. Never negative (CHECK). |
| `created_at`, `updated_at` | `updated_at` touched by every app write. |

## Migrations

| File | What it does |
|---|---|
| `migrations/2026-05-10-01-create-products.sql` | Creates `public.products` and its CHECK constraints. Idempotent. |

All are safe to re-run. None is applied automatically — run them in filename
order by hand. Filenames are `YYYY-MM-DD-nn-slug.sql`.
