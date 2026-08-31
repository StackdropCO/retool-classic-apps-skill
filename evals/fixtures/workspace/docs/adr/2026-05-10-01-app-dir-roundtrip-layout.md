# app/ is Retool's; everything else is ours

Date: 2026-05-10
Status: Accepted

## Decision

`app/` holds exactly what Retool exports and is replaced wholesale by
`./retool.sh unpack`. Documentation lives in `docs/`, DDL in `migrations/`,
built zips in `build/`. Nothing outside `app/` is ever inside the zip, and
nothing inside `app/` is hand-authored documentation.

## Consequences

- An export can never clobber docs or migrations.
- All SQL lives in `app/lib/*.sql` so it survives the round-trip legibly —
  never inline in RSX attributes.
- `app.bak/` (written by unpack) is the only undo; this workspace is not
  under version control.
- Changing structure or behaviour means updating the affected `docs/wiki/`
  page in the same change.
