# Silent Import Failures

Everything needed to make a Retool app zip that actually imports — and to debug
one that doesn't. Every "proven" below means proven against a real Retool
instance by a real import, not taken from documentation. The two killers on
this page each cost a production team days of confusion; the rules stick better
when you know what they cost, so the incidents are summarised at the bottom.

## The import model

Three facts, and every debugging mistake around Retool imports comes from not
knowing one of them:

1. **A failed import is SILENT.** A zip the importer cannot parse produces
   nothing: no toast, no console output, no error page. The import simply does
   not happen. Treat "I imported and nothing changed" as a **parse failure in
   the archive**, never as a Retool glitch to retry.
2. **An import REPLACES the app it is imported into.** Same identity, same
   custom URL — it does not fork a copy. A new app appears only through a
   deliberate create-new path (where the name comes from the import dialog,
   not from the archive).
3. **1 + 2 compose badly:** a successful import of a small change and a zip
   that failed to parse look *identical* — same app, nothing visibly
   different. You cannot tell them apart by looking.

**So verify with a probe, not with your eyes.** Before an import you need
certainty about, add an unmissable marker to the build — a
`style={{ background: "#ff0000" }}` on the root container, or a suffix on the
`DocumentTitle`. Reload the target app: marker present means the archive parsed
and landed; unchanged means it did not. Strip the probe before the production
build. When the change itself introduces something findable (a new query id, a
new component), checking for that in the imported app is an equally good probe.

## The two proven killers

### 1. A raw `"` inside a `="{{ … }}"` attribute expression

```jsx
label="{{ user.name + "'s budget" }}"     ← kills the entire import
label="{{ user.name + '’s budget' }}"     ← fine
```

The RSX attribute parser is textual: the first unescaped `"` terminates the
attribute, whatever braces it sits inside. The tag becomes garbage and the
importer discards the whole archive without a word. Inside expressions, use
single-quoted JS strings; when the string itself needs an apostrophe, use the
typographic `’` (nothing to escape, and non-ASCII in attributes is proven
fine). Same parser family as the other textual rules: no `<!-- -->` comments,
no angle-bracketed tag names inside attribute text.

### 2. `_comment` on a `<View>`

`_comment` is safe on every other element — proven round-tripping on `Event`,
`SqlQueryUnified`, `Alert`, `State`, `RESTQuery`, `Button`, `Select`,
`TextInput`, `Container`, `Function`, `Text`, `NumberInput`,
`SegmentedControl`, `Multiselect`, `Switch`, `ModalFrame`, `Form`,
`Statistic`, `SplitPaneFrame`, `Tabs`, `WorkflowRun`, `JavascriptQuery`. On a
`<View>` it silently kills the import. That fits what a View is: a transparent
grouping element with no position entry and no component of its own.

⚠️ **It survives an EXPORT.** Add the comment in-editor, export, and Retool
hands you a zip that will not re-import. *Surviving an export is not the same
as being accepted on import* — never infer importability from an export
round-trip. Put a View's rationale in the repo's docs (a wiki page or ADR)
instead; a View that needs explaining is explaining a decision.

Both killers are checks in `scripts/validate_app.py` ("silent import killer"
FAILs). `zip_app.sh` runs the validator before zipping — **never bypass a red
validator with a hand-rolled zip.**

## The zip

- **Flat archive**: `main.rsx` and `metadata.json` at the zip root, no wrapper
  folder — the shape Retool's own *Export to ZIP* produces and round-trips. A
  wrapped zip can import as nothing. `zip_app.sh` emits the flat shape:
  `(cd "$APP_DIR" && zip -r "$OUTPUT" . -x '*.DS_Store')`.
- **Compression does not matter.** Deflate imports fine; Retool's own exports
  happen to use stored entries. Not a variable worth controlling.
- **The archive carries no identity.** Display name comes from the import
  dialog; custom URL and workspace-list name are Retool-side settings that
  never travel in an export. Only the browser title travels (`DocumentTitle`
  in `main.rsx`). `metadata.json`'s `pageUuid` is informational — a matching
  uuid neither collides with nor updates an existing app.

## Constructs proven innocent

All suspected during real incidents and individually cleared by real imports —
do not burn time re-suspecting them:

- `<Tabs>` with `navigateContainer={true}` / `targetContainerId` (in-app page
  switching over Container `<View>`s)
- `<ModalFrame>` as a child of `<App>`, with `<Form>` inside
- A second `<SplitPaneFrame>` in one app
- `<Select>`, `<Switch>`, `<Date>`, `<SegmentedControl>`, `<Multiselect>`,
  `<ToolbarButton>`, `<Action>`, `<WorkflowRun>`
- `params={{}}` on widget events; `method="show"` / `method="hide"` on frames
- Raw `&` and other non-ASCII (`’`, `·`, `—`) in attribute values
- `<` / `>` comparison signs inside `_comment` text

## Debugging a new unknown killer: the bisection method

When an import no-ops and the validator is green, a new killer exists. The
method that found both known ones, written down so nobody reinvents it. It
needs one thing: **any export known to import** (export the live app — that
artefact is gold; keep a known-good export in the repo).

1. **Split archive from content.** Build two zips: the known-good content
   through your packing pipeline, and your content re-zipped to match the
   known-good archive's style. Whichever fails names the guilty half.
2. **Bisect the content in halves** against the working base: its UI files
   with your queries, then your UI files with its queries. One half carries
   the failure.
3. **Graft one feature at a time** onto the working base until the failing
   file is cornered. Strip dangling `pluginId` references in each graft so a
   missing target can't confound the result.
4. **Isolate within the file with a probe matrix.** If two candidate changes
   coexist, build one zip per cell of the 2×2 (each change alone, both,
   neither), each with a distinct `DocumentTitle` marker so you can read the
   result off the browser tab. The change that predicts failure across all
   cells is the killer — this is exactly how `_comment`-on-`<View>` was
   isolated while an innocent new element type was suspected.
5. **Diff the cornered file** for anything that could terminate an attribute
   early. It will be a quoting problem before it is an exotic component.

Each round costs one manual import per zip, so make every zip answer exactly
one question. When you find a new killer: add a check to `validate_app.py`,
and add it to this page.

## The incidents, for the record

**The quote (found by bisection, one evening).** During a feature build, every
import of the app silently produced nothing — across wrapper-folder and flat
zips, fresh uuids, and a probe build. A/B on archive-vs-content, C/D/E on
halves, F/G/H on features cleared every suspected construct and cornered one
file, where the new work had added `+ "'s budget"` inside a label expression.
Two characters terminated the attribute; the importer discarded the whole
archive without a word. Fixed with `'’s budget'`.

**The View comment (nine days, found by the 2×2 probe matrix).** Two
`_comment` attributes added in-editor to `<View>` elements survived the
export, sat in the repo, and killed every subsequent import. The next feature
(a new `<WorkflowRun>` query) took the blame at first — probes isolating the
two variables proved the comments predicted failure 4-for-4 and the new
element was innocent. The comments' rationale moved to an ADR; the validator
check was added the same day.
