---
name: retool-classic-apps-skill
description: >
  Build, edit, and improve classic Retool apps using ToolScript (RSX format).
  Use this skill whenever the user mentions retool, toolscript, RSX,
  internal tool, admin panel, data management app, CRUD app, or wants
  to create any Retool application — whether from scratch, modifying
  an existing one, or improving it with production patterns. Also use it
  when a Retool import silently does nothing ("no error but nothing
  changed", "import shows no error"), when packing or unpacking a Retool
  app zip, or when working in a Retool app workspace repo (app/ dir,
  retool.sh, pack/unpack round-trip, migrations and wiki conventions).
  Also triggers for: retool import, retool zip, retool table, retool
  modal, retool form, retool filter, retool dashboard, retool chat,
  build internal app, admin dashboard, data editor, silent import failure.
  NOT for Retool Workflows (scheduled/webhook automation JSON) — those
  belong to the retool-workflows-skill.
---

# Retool App Builder

Build importable Retool apps using ToolScript/RSX — Retool's markup language for source-controlled apps.

## A. Orientation

This skill creates importable Retool apps. Each app is a directory containing RSX markup files, position layout JSON, and metadata — zipped for Retool import.

**Reference files** (paths relative to this skill):
- `references/TOOLSCRIPT-CHEATSHEET.md` — **READ FIRST.** Condensed rules for component nesting, positioning, IDs, queries, events.
- `references/TOOLSCRIPT-SPEC.md` — Full 2500-line spec. Use for deep lookups when the cheatsheet isn't enough.
- `assets/examples/` — 8 importable template apps (Minimal, CRUD Table, Master-Detail, Search Filter, AI Chat, Advanced CRUD, Charts Dashboard, API Dashboard).

**Scripts** in `scripts/` handle validation, scaffolding, and position math — use them instead of manual RSX editing whenever possible.

**Output contract:** ALWAYS produce a named directory in the **multi-page layout** (the default, see A1) — `main.rsx`, one `src/<page>.rsx` `<Screen>` per page, `metadata.json` with `appTemplate.rootScreen`, and `.positions/.<page>.positions.json` — AND a **flat** zip via `zip_app.sh` (`main.rsx` at the archive root — a wrapper folder can make the import silently no-op). Keep an existing single-page app single-page (`functions.rsx` + `.positions.json`) unless the user asks to convert it.

## A1. App Layout: Multi-Page (default) vs Single-Page (legacy)

Retool's current app shape, taken from real exports:

```
app-name/
├── main.rsx                         # <App> + one <Include> per page (+ global frames)
├── metadata.json                    # appTemplate.rootScreen = the page that opens first
├── src/
│   ├── page1.rsx                    # <Screen id="page1"> — that page's queries, State,
│   │                                #   its $main Frame, its ModalFrame/DrawerFrame
│   └── editModal.rsx                # included from page1.rsx: <Include src="./editModal.rsx" />
├── lib/                             # SQL/JS, included from src/ as ../lib/x.sql
└── .positions/
    ├── .page1.positions.json        # layout of page1's components only
    └── .global_positions.json       # components outside every Screen (a $header frame)
```

- **Page scope.** A page's components and queries are invisible to other pages, and global code (outside every `<Screen>`) cannot read page objects. Share through a global State, URL params, or the global `$header`/sidebar frame. `validate_app.py` WARNs on cross-page references.
- **One positions file per page.** A component's entry goes in its own page's file; an entry in another page's file is never read (validator FAILs). An empty page has no file.
- **Frame ids are app-unique:** `$main` on the first page, `$main2`, `$main3`... on later ones.
- **Frames** (`ModalFrame`, `DrawerFrame`, `SplitPaneFrame`, `SidebarFrame`) are direct children of their page's `<Screen>`.
- **Add a page** with `add_page.py <dir> --id settings --title "Settings"` (unique `_order`, `uuid`, `urlSlug`, frame id). Navigation between pages: a `Navigation` in a global `$header` frame (Quick Templates, I).
- **Single-page (legacy):** `functions.rsx` (`<GlobalFunctions>`) holds the queries, `.positions.json` the layout, frames are children of `<App>`. Every script still handles it; `scaffold_app.py --single-page` creates one.

## A2. The Silent Import Model

Three facts govern every Retool import; not knowing them costs days:

1. **A failed import is SILENT** — a zip the importer can't parse produces
   nothing: no error, no toast, no change. "I imported and nothing changed"
   means a parse failure in the archive, not a Retool glitch to retry.
2. **An import REPLACES the app it's imported into** (same identity, same
   custom URL). It does not fork; create-new is a separate deliberate path.
3. Together: a successful no-op-looking import and a failed one are
   **indistinguishable by eye**. Verify imports you must be certain about with
   a probe marker (loud background / `DocumentTitle` suffix), or by checking
   for a component/query the change introduces.

Two constructs are proven to silently kill an entire import: a raw `"` inside
a `="{{ … }}"` attribute expression, and `_comment` on a `<View>` (which even
survives an export — surviving export ≠ accepted on import). `validate_app.py`
fails on both; never bypass a red validator with a hand-rolled zip. Full
model, probe method, proven-innocent list, and the bisection procedure for
debugging a new unknown killer: `references/SILENT-FAILURES.md`.

## A3. Workspace Mode

If the target repo has a `retool.sh` and an `app/` directory, you are in an
**app workspace** — a repo that round-trips one app with Retool — and its
conventions override the plain single-directory workflow:

| Path | Rule |
|---|---|
| `app/` | **Retool owns it.** Replaced wholesale by each export unpack. App code only — never docs, notes, or scratch files. |
| `app/lib/*.sql` | **All SQL lives here**, even one-liners — never inline `query="…"` in RSX. Same for nontrivial JS bodies. |
| `app.bak/` | One-version undo, written by unpack. Often the only undo — these workspaces may not be under version control. |
| `build/` | Generated zips (and other build artifacts). Never hand-edited. |
| `docs/` | `wiki/` = current truth, rewritten in place; `adr/` = append-only decision records (never edit an accepted ADR — supersede it); `stream/` = dated notes. |
| `migrations/` | Idempotent DDL, run by hand against the database. The app never migrates anything. |
| `exports/` | Known-good Retool exports, kept as bisection bait for import debugging. |

Work through the round-trip script, not around it: `./retool.sh pack`
(validate + flat zip into `build/`) and `./retool.sh unpack <export.zip>`
(replace `app/`, previous version → `app.bak/`). For a NEW workspace, start
from `assets/templates/retool.sh`.

**The doc gate:** changing structure or behaviour means rewriting the affected
`docs/wiki/` page in the same turn, and writing an ADR for any decision a
reasonable engineer could have made differently. After an unpack, check
whether the export dropped RSX `_comment` rationale and make sure the wiki
still carries it.

## B. Scripts Reference

| Script | Purpose | When to use |
|--------|---------|-------------|
| `validate_app.py <dir>` | Validate against all import rules | **ALWAYS** before zipping. Catches import-breaking errors. |
| `scaffold_app.py "Name" --template <type> [--single-page]` | Create app from template. Types: `minimal`, `crud`, `master-detail`, `search-filter`, `chat`, `advanced-crud`. Multi-page (one page, `page1`) unless `--single-page`. | Start here for **NEW** apps. |
| `add_page.py <dir> --id P [--title T] [--url-slug S]` | Add a page: `src/P.rsx` `<Screen>` + its positions file + the `main.rsx` Include | Multi-page apps, any time a new page is needed. |
| `list_components.py <dir>` | Show component tree (pages show as `Screen` nodes) | Start here for **EDIT/IMPROVE**. Understand the app without reading RSX. |
| `add_component.py <dir> --type T --id I [--screen P] ...` | Add component + update the right positions file | Add components with correct layout math. The page comes from where `--after`/`--before`/`--parent-frame` lives; `--screen P` alone targets page P's main frame. |
| `add_query.py <dir> --type T --id I [--screen P] ...` | Add query with event chains | Into page P's `<Screen>` (or the only page); `functions.rsx` in a single-page app. |
| `extract_component.py <dir> --component ID` | Move subtree to src/ file | When a page file (or main.rsx) gets too large. |
| `fix_positions.py <dir> [--apply] [--screen P] [--scope S] [--shift-from N --by M]` | Recalculate vertical layout, each page file on its own. **Dry-run by default** (add `--apply` to persist). Use `--shift-from` for the "I just inserted content, shift rows below" case. | Fix layout after adding/removing components. |
| `zip_app.sh <dir>` | Zip for Retool import (runs validate) | Final step — produces the importable zip. |
| `bundle-apps.sh <app-dir> [output]` | Bundle app into single `.toolscript-bundle` file (dev tool) | Skill development: feed full app context to LLM. `--all` for batch. |
| `compact_bundles.py` | Strip positions/metadata and truncate large inline data from bundles (dev tool) | Skill development: reduce bundle size for bulk analysis. |

**Principle:** Prefer scripts over manual RSX editing. Scripts handle position math, ID generation, and file consistency automatically. Only edit RSX directly for complex customizations scripts can't handle (custom attribute values, conditional logic, complex nesting).

## C. Task Identification

Determine the mode based on what the user asks:

- **NEW** — "build me a retool app for..." → `scaffold_app.py` with closest template → customize → validate → zip
- **EDIT** — "add X to my retool app" / "change Y in this app" → `list_components.py` first → targeted changes → validate → zip
- **IMPROVE** — "make this app production-ready" / "review my app" → `list_components.py` → audit → apply changes → validate → zip

## D. Template Selection Matrix

For NEW apps, pick the closest template:

| User needs... | Template | Patterns included |
|---|---|---|
| Simple display, read-only data | `minimal` | Text, basic layout |
| Table + create/edit/delete modals | `crud` | Modal, ModalFrame, Form, SQL CRUD, State, event chains |
| Table + side panel editing | `master-detail` | SplitPaneFrame, Container+Tabs+View, dynamic width |
| Filtered data, search bar | `search-filter` | setFilterStack, DateRange, JavascriptQuery |
| AI/chat interface | `chat` | Chat component, RESTQuery, JavascriptQuery |
| Complex: bulk ops, filters, detail pane | `advanced-crud` | Everything above combined |
| Dashboard with stats / charts | Charts Dashboard example | Statistic, PlotlyChart with dataseries, lib/ data+layout JSON |
| REST API table + drawer detail | API Dashboard example | RESTQuery, DrawerFrame, EditableText, setFilterStack |
| Firebase / Firestore app | `crud` | Replace SqlQueryUnified with FirebaseQuery (queryFirestore/setFirestore/updateFirestore/deleteFirestore) |
| GraphQL API dashboard | `minimal` | Add GraphQLQuery with .gql files in lib/ |
| S3 file browser | `minimal` | Add S3Query (list/read/download), S3Uploader, IFrame for preview |

Read the template example files from `assets/examples/<name>/` before customizing — understand what you're starting from.

## E. NEW App Workflow

1. **Read** `references/TOOLSCRIPT-CHEATSHEET.md` for rules
2. **Scaffold:**
   ```bash
   python scripts/scaffold_app.py "App Name" --template <type> --output-dir <path>
   ```
3. **Note:** Scaffolded apps include mock data fallbacks and a Setup Guide modal so the app is functional on import without a database. See "Mock Data" below. The output is multi-page (A1): the template's content is page `page1` in `src/page1.rsx`. The examples in `assets/examples/` are stored single-page; the scaffolder converts them.
4. **Read ALL generated files** to understand the starting point
5. **Read the closest example** from `assets/examples/` for pattern reference
6. **Customize:** modify query SQL, component labels/attributes, column definitions, form fields
7. **Add pages** if the app needs more than one (each page gets its own queries, frame and positions file):
   ```bash
   python scripts/add_page.py <dir> --id settings --title "Settings"
   ```
8. **Add new components** (the page follows the anchor; `--screen settings` alone targets that page's main frame):
   ```bash
   python scripts/add_component.py <dir> --type TextInput --id searchInput --after pageTitle --attrs 'label="" placeholder="Search..."' --width 6
   ```
9. **Add new queries** (`--screen` picks the page once there is more than one):
   ```bash
   python scripts/add_query.py <dir> --type SELECT --id selectItems --table items --sql-file
   ```
10. **Extract if a page file is large:**
    ```bash
    python scripts/extract_component.py <dir> --component editModal
    ```
11. **Fix positions if needed** (dry-run first to preview the diff, then apply):
    ```bash
    # Preview what would change (no writes)
    python scripts/fix_positions.py <dir>
    # Persist the changes
    python scripts/fix_positions.py <dir> --apply
    ```
12. **Validate:**
    ```bash
    python scripts/validate_app.py <dir>
    ```
    Fix ALL failures before proceeding.
13. **Zip:**
    ```bash
    bash scripts/zip_app.sh <dir>
    ```

## F. EDIT Workflow

1. **Understand the app:**
   ```bash
   python scripts/list_components.py <dir>
   ```
2. **Read specific files** that need changes
3. **Make targeted modifications** using scripts where possible:
   - Adding components → `add_component.py`
   - Adding queries → `add_query.py`
   - Extracting to src/ → `extract_component.py`
4. **For complex changes** (modifying existing attributes, rewiring events), edit RSX directly
5. **Fix positions** (dry-run first, then apply). For mature apps where you're inserting content into an existing scope, use `--shift-from` to bump rows below a cutoff without touching the rest of the layout:
   ```bash
   # Preview (dry-run is the default)
   python scripts/fix_positions.py <dir>

   # Apply across the whole app (only scopes with overlaps / zero-heights are touched)
   python scripts/fix_positions.py <dir> --apply

   # Targeted additive shift: "I inserted N units at row X in scope Y"
   python scripts/fix_positions.py <dir> --scope EditInteractionForm \
       --shift-from 10.2 --by 3.2 --apply
   ```
   The script is safe-by-default: without `--apply` it only prints the planned diff. Scopes with no overlaps and no zero-height entries are left untouched, so intentional authored spacing is preserved.
6. **Validate:**
   ```bash
   python scripts/validate_app.py <dir>
   ```
7. **Zip:**
   ```bash
   bash scripts/zip_app.sh <dir>
   ```

## G. IMPROVE Workflow + Audit Checklist

1. **Understand the app:**
   ```bash
   python scripts/list_components.py <dir>
   ```
2. **Read the queries** fully to understand query patterns: inside each page's `<Screen>` (`src/<page>.rsx`), or `functions.rsx` in a single-page app
3. **Audit against checklist:**
   - [ ] Destructive queries (DELETE) have `requireConfirmation={true}`?
   - [ ] Mutation queries have success events that refresh data?
   - [ ] After update: does it re-select the updated row (`selectRow`)?
   - [ ] After delete: does it clear selection (`clearSelection`)?
   - [ ] Forms have `loading="{{ query.isFetching }}"` and `disableSubmit="{{ query.isFetching }}"`?
   - [ ] Could dropdown options use SqlTransformQuery instead of separate queries?
   - [ ] Could filtering use client-side `setFilterStack()` instead of SQL WHERE?
   - [ ] Are State variables used for UI mode flags (bulk update, editing state)?
   - [ ] Does the app have proper event chains (mutate → refresh → UI update)?
   - [ ] Are ModalFrame/SplitPaneFrame/DrawerFrame/SidebarFrame children of their page's `<Screen>` (single-page: `<App>`), not of a Frame?
   - [ ] Multi-page: no page reads another page's components or queries (validator WARNs "Cross-page references")?
   - [ ] PlotlyChart data/layout stored in lib/ JSON files (not inline)?
   - [ ] HTML/IFrame components sanitize user-provided content?
   - [ ] Panes/single-row mutations on a *filtered* table read a State snapshot set on row-select, not `table.selectedRow` (which empties when the row leaves the filter)?
   - [ ] Write-guards live in the SQL WHERE (`AND status = 'pending'`), not only in button disabled-state?
   - [ ] No arrays passed as single SQL params (`= ANY({{ arr }})`) — use `jsonb_array_elements_text({{ JSON.stringify(arr) }}::jsonb)`?
   - [ ] Remove mock data fallbacks if real DB is connected (`Array.isArray(q.data) ? q.data : [...]` in Table/Select data attributes)?
   - [ ] Remove Setup Guide modal if no longer needed?
4. **Present findings** and proposed changes to user
5. **Apply approved improvements**
6. **Validate + zip**

## H. Manual Editing Reference

For when scripts aren't sufficient — the critical rules to follow:

### Nesting
- ModalFrame/SplitPaneFrame/DrawerFrame must be children of their page's `<Screen>` (single-page: `<App>`), not `<Frame>`
- Form requires `<Header>` + `<Body>` + `<Footer>` (all three; use `showHeader={false}` to hide)
- Container requires at least one `<View>` direct child (not inside Body)
- Table requires at least one `<Column>` child
- **Never use `enableFullBleed={true}` on Containers inside SplitPaneFrame/DrawerFrame** — causes overflow

### Positioning
- Every visible component needs a position entry, in its page's `.positions/.<page>.positions.json` (outside every page: `.global_positions.json`; single-page: `.positions.json`)
- Omit `row` and `col` when they are 0 (zero is the default)
- View is transparent — no position entry ever
- `col + width <= 12`
- Children inside a View use `container: parentContainerId` + `subcontainer: viewId`
- Header/footer items use `rowGroup: "header"` or `rowGroup: "footer"`
- ModalFrame children use `subcontainer: modalId`

### Toolbar Layout
When placing buttons alongside filter inputs (Select, DateRange, TextInput), buttons need special sizing to look right:
- Add `heightType="auto"` to the Button RSX
- In positions: use `height: 0.8` (not 1.0) and offset `row` by +0.2 from the filter row
- **Ordering: filters → search → action buttons** (left to right)
- Extract ModalFrame components (especially Setup Guide) to `src/` files via Include

### IDs
- All IDs globally unique across all .rsx files
- Columns/Views/Options/Actions: 5-char hex `[0-9a-f]{5}`
- Events: 8-char hex `[0-9a-f]{8}`

### Syntax
- No `<!-- comments -->` — use `_comment="text"` attribute
- Boolean: `{true}` not `"true"`
- Expressions: `{{ widget.value }}`
- Include: `{include("./lib/file.sql", "string")}`
- **All SQL goes in lib/ files** — even one-liners. Never use inline `query="SELECT ..."`.

### Attributes to Omit
Don't include these — Retool strips them and they clutter the output:
- `resourceDisplayName` on any query (cosmetic label, not used for import)
- `transformer="return data"` on SELECT queries (it's the default)
- `resourceDisplayName="JavascriptQuery"` and `runWhenModelUpdates={false}` on JavascriptQuery
- `query=""` on RESTQuery (empty string is the default)
- `hidden={false}`, `showFooter={false}` on any component (false is always the default)

### Mock Data

Scaffolded apps (crud, master-detail, search-filter, advanced-crud) include inline mock data fallbacks on Table and Select `data` attributes. This makes the app fully functional with sample data before a real database is connected.

**How it works:** `data="{{ Array.isArray(query.data) ? query.data : [{ id: 1, name: 'Example' }] }}"` — when the query has no resource, `query.data` returns an error object (not an array), so the fallback is used. When a real DB returns data (an array), the ternary uses it directly.

**To connect your real database:**
1. Update `resourceName` in each query (inside the page's `<Screen>`; `functions.rsx` in a single-page app) to your database resource UUID
2. Remove the mock data fallbacks from Table/Select `data` attributes (change `{{ Array.isArray(query.data) ? query.data : [...] }}` to `{{ query.data }}`)
3. Delete the Setup Guide modal (`setupGuideModal` ModalFrame) and the `setupGuideBtn` button

For deeper reference: read `references/TOOLSCRIPT-CHEATSHEET.md` or the full spec.

## I. Quick Templates

### Multi-page skeleton (default)
`main.rsx`:
```jsx
<App>
  <Include src="./src/page1.rsx" />
</App>
```
`src/page1.rsx` (queries and State go inside the Screen, `include()` paths are `../lib/…`):
```jsx
<Screen id="page1" _customShortcuts={[]} _hashParams={[]} _order={0} _searchParams={[]}
  browserTitle="App Title" title="App Title" urlSlug="" uuid="<uuid4>">
  <SqlQueryUnified id="selectItems" query={include("../lib/selectItems.sql", "string")}
    resourceName="REPLACE_WITH_RESOURCE_UUID" resourceTypeOverride="" warningCodes={[]} />
  <Frame id="$main" type="main" padding="8px 12px" paddingType="normal" sticky={false}
    isHiddenOnDesktop={false} isHiddenOnMobile={false}>
    <Text id="pageTitle" value="### App Title" verticalAlign="center" marginType="normal" />
  </Frame>
</Screen>
```
`.positions/.page1.positions.json`:
```json
{
  "pageTitle": { "height": 0.6, "width": 12 }
}
```
`metadata.json`: the template below plus `"rootScreen": "page1"` inside `appTemplate`.

### Page navigation (global header, from a real export)
A `$header` frame included from `main.rsx` outside every Screen is global: it shows on every page. Its components go in `.positions/.global_positions.json`, and a component directly in the header frame carries `"subcontainer": "header"` there.
```jsx
<Frame id="$header" type="header" isHiddenOnDesktop={false} isHiddenOnMobile={true}
  padding="8px 12px" paddingType="normal" sticky={true}>
  <Navigation id="pageNav" data="{{ retoolContext.pages }}"
    highlightByIndex="{{ retoolContext.currentPage === item.id }}"
    labels="{{ item.title || item.id }}" retoolFileObject={{}}>
    <Event id="a1b2c3d4" event="click" method="openPage"
      params={{ map: { pageName: "{{ item.id }}" } }} pluginId="" type="util"
      waitMs="0" waitType="debounce" />
  </Navigation>
</Frame>
```
```json
{ "pageNav": { "subcontainer": "header", "height": 0.8, "width": 12 } }
```

### Single-page skeleton (legacy)
```jsx
<App>
  <Include src="./functions.rsx" />
  <Frame id="$main" type="main" padding="8px 12px" paddingType="normal" sticky={false}
    isHiddenOnDesktop={false} isHiddenOnMobile={false}>
    <Text id="pageTitle" value="### App Title" verticalAlign="center" marginType="normal" />
  </Frame>
</App>
```

`functions.rsx`:
```jsx
<GlobalFunctions>
</GlobalFunctions>
```

### metadata.json template
```json
{
  "toolscriptVersion": "1.0.0",
  "version": "43.0.9",
  "pageUuid": "00000000-0000-0000-0000-000000000001",
  "appTemplate": {
    "appMaxWidth": "100%",
    "appThemeId": -1,
    "experimentalFeatures": { "object": { "sourceControlTemplateDehydration": false } },
    "notificationsSettings": { "object": { "globalQueryShowFailureToast": true, "globalQueryShowSuccessToast": true, "globalQueryToastDuration": 4.5 } },
    "version": "3.338.0"
  }
}
```

### .positions.json minimal (single-page)
```json
{
  "pageTitle": { "row": 0, "height": 0.6, "width": 12 }
}
```

### Event template
```jsx
<Event id="hex8char" event="success" method="trigger"
  params={{ ordered: [] }} pluginId="queryId" type="datasource"
  waitMs="0" waitType="debounce" />
```

### SELECT query one-liner
```jsx
<SqlQueryUnified id="selectItems" query={include("./lib/selectItems.sql", "string")}
  resourceName="REPLACE_WITH_RESOURCE_UUID"
  resourceTypeOverride="" warningCodes={[]} />
```

### INSERT one-liner
```jsx
<SqlQueryUnified id="insertItem" actionType="INSERT" changesetIsObject={true}
  changesetObject="{{ { ...CreateForm.data } }}" editorMode="gui"
  resourceName="REPLACE_WITH_RESOURCE_UUID"
  resourceTypeOverride="" runWhenModelUpdates={false} tableName="public.items">
  <Event id="hex8" event="success" method="trigger" pluginId="selectItems" type="datasource" waitMs="0" waitType="debounce" />
</SqlQueryUnified>
```

### UPDATE_BY one-liner
```jsx
<SqlQueryUnified id="updateItem" actionType="UPDATE_BY" changesetIsObject={true}
  changesetObject="{{ { ...EditForm.data } }}" editorMode="gui"
  filterBy={
    '[{"key":"id","value":"{{ table.selectedRow.id }}","operation":"="}]'
  }
  resourceName="REPLACE_WITH_RESOURCE_UUID"
  resourceTypeOverride="" runWhenModelUpdates={false} tableName="public.items" />
```

### DELETE_BY one-liner
```jsx
<SqlQueryUnified id="deleteItem" actionType="DELETE_BY" editorMode="gui"
  filterBy={
    '[{"key":"id","value":"{{ table.selectedRow.id }}","operation":"="}]'
  }
  requireConfirmation={true} confirmationMessage="Delete **{{ table.selectedRow.name }}**?"
  resourceName="REPLACE_WITH_RESOURCE_UUID"
  resourceTypeOverride="" runWhenModelUpdates={false} tableName="public.items" />
```
