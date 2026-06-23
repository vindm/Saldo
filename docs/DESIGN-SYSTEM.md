# Design system — operator dashboards

Scope: the static HTML dashboards rendered by `engine/` — the **operator-facing
view**. This is the developer/view layer (per Invariant 0, touch Python only when
the rendered view must change). It is distinct from `policies/brand-and-tone.md`,
which governs **client-facing** output (the Russian reports/messages a client sees).

## North-star & principles

The reference points are Linear and similar modern product dashboards: calm,
information-dense, restrained. Every accent must carry meaning — decoration that
doesn't encode something is noise. Spacing is generous but tight.

Two failure modes we explicitly design against, because both let the operator
miss work:

1. **A control whose active/selected state is easy to miss** — e.g. a filter that
   silently hides rows. If state isn't obvious, the operator acts on a partial view.
2. **A container whose boundaries are unclear** — e.g. where an expanded group ends
   and the next begins.

## Where the system lives (single source of truth)

- **Tokens:** `engine/_css.py` → `DESIGN_TOKENS_CSS` (the `:root` variables).
  Change colours / spacing / radii / shadows here; everything inherits. Prefer a
  token change over a per-rule hex value.
- **Shared component CSS:** `engine/_css.py` (cards, the `tm-btn-*` buttons,
  badges, modals), `engine/_sidebar.py` (left nav), `engine/_mode_switch.py`
  (All/Team/Direct switch + filter banner), `engine/_plan_waves.py` (operation
  "waves"), `engine/_icons.py` (Lucide sprite — **generated, do not hand-edit**;
  reuse an existing symbol or inline a one-off SVG).
- **Never edit generated `*.html`** (Invariant 3). Change the Python, run
  `python3 engine/generate.py`, then verify.

## Colour roles

- **`--accent` (indigo `#5E6AD2`)** plus `--accent-hover / -active / -soft /
  -soft-border / -text`: the primary **interactive** colour — active states,
  links, primary buttons, focus rings, the selected nav item, the expanded-wave
  accent. `--accent-blue` is an alias of `--accent`, so legacy interactive rules
  follow the accent without per-rule edits.
- **Semantic colours are stable and meaning-bearing — do not repurpose:**
  `--accent-red` = overdue / blocked / bad health, `--accent-yellow` = due-soon /
  waiting, `--accent-green` = ready / good health. Their `*-bg` tints back the
  matching badges and rows. When the accent changes for fashion, these stay put.
- **Neutrals are cool greys:** `--bg-canvas` (the desk), `--bg-card` (white
  surface), `--bg-page` / `--bg-subtle` (insets, hovers), `--border` /
  `--border-strong`.
- **Client-facing brand (navy `#1F4E79` + gold `#B79257`) is NOT the dashboard
  accent.** It stays per `policies/brand-and-tone.md`. The sidebar logo keeps the
  practice brand identity; the dashboard *chrome* (nav, controls) uses indigo.

## Scale

- **Radii:** `--radius-card` 10px, `--radius-btn` 6px, `--radius-badge` 4px.
- **Spacing:** `--space-xs … -xl` = 4 / 8 / 16 / 24 / 32px.
- **Shadows:** `--shadow-card` (resting surface), `--shadow-pop` (lifted / indigo).
- **Motion:** `--transition` 150ms. **Type:** system sans; sizes via `--fs-*`.

## Component patterns (established conventions — reuse, don't reinvent)

- **Filter-active banner** (`_mode_switch.py`): whenever a filter hides rows, show
  a high-visibility banner stating shown-vs-hidden counts plus a one-click reset;
  the selected segment is filled `--accent`. Rule: *a filter must never silently
  swallow items.*
- **Expanded container / "drawer"** (`_plan_waves.py`, `.wave:not(.collapsed)`):
  an open group lifts into its own card — full border, an `--accent` left-rail, a
  soft-lavender (`--accent-soft`) header, a light shadow — so its start and end are
  unambiguous. (We deliberately chose this calm variant over a full-indigo bar.)
- **Transient focus highlight** (e.g. Periods → Plan deep-link): use a *removable
  class* (`.wave-focus` → `outline`), never an inline style. Wire user actions
  (collapse, collapse-all) to clear it and strip the deep-link hash via
  `history.replaceState`, so it doesn't reappear on reload.
- **Counts shown side by side must share one definition.** If two numbers sit near
  each other they must use the same window — e.g. the Plan sidebar badge and the
  "{N} in the next 7 days" summary both use `horizon_counts(...)['near']`.
- **Interaction affordances:** row hover = visible `--bg-page` tint; keyboard
  focus = 2px `--accent` `:focus-visible` outline.

## Localization (i18n) — every visible label goes through `t()`

The dashboard is bilingual: `instance.locale` (`en`/`ru`) drives the chrome via
`engine/_strings.py → t()`. The rule is absolute: **no operator-facing string is
ever printed raw.** A literal that reaches the screen without `t()` renders English
under `ru` — exactly the bug class that left `PROPERTIES` / `Break down` and the
`task_type` / `status` chips in English on a Russian instance.

Concretely:

- **Static chrome** (headings, buttons, section labels): wrap in `t('…')`. In JS
  templates use `__TOKEN__` placeholders substituted through `t()` at render time
  (see `_track_modal.py`), never hard-coded English in the script.
- **Enum-like values are chrome, not data — localize them.** `task_type` and
  `status` come from state but are a controlled vocabulary, so they must display
  localized: map the token to a clean English label that is also a `t()` catalog
  key (`_track_attrs.py._TASK_TYPE_LABEL`), then route through `t()`; unknown
  tokens fall back to a humanized form (`foo_bar` → `foo bar`) still via `t()`.
- **Normalize before you localize when the vocabulary is open-ended.** Free-form
  statuses (`blocked_by_anastasia`, `scheduled_calc_by_fact`) don't scale and can't
  be translated one-by-one. `engine/_status.py` collapses any raw status to a small
  canonical set by keyword/prefix (so new variants bucket automatically); the chip
  shows the localized canonical label and the CSS class follows the canonical token.
  The specifics belong in context / history, not in the status enum.
- **True data stays untouched** — client names, task titles, amounts, free text
  pass through verbatim (`tp()` for prompts). Only the engine's own vocabulary is
  translated.
- **Verify under `ru`, not just the English demo** (engine Invariant 4): render with
  `ABA_LOCALE=ru` against both the example and real Russian data and confirm no
  English leaks. A quick check: `grep -o 'data-track-task-type="[^"]*"' … | grep -P '="[\x00-\x7F]+"'` should return nothing.
- **The build catches gaps for you — don't rely on eyeballing.** `state_lint`
  enforces label coverage so a new enum value or detail key can't silently ship
  untranslated: `status_noncanon` (status outside the canonical set),
  `i18n_task_type` (a `task_type` with no `_TASK_TYPE_LABEL` entry), and
  `i18n_ts_key` (a `type_specific` key with no `_TS_RU_LOC` label and not in
  `INTERNAL_TS_KEYS`). These run on every `generate`. When you add a new enum
  value or detail field, run `state_lint`; if it lists the token, add its label
  (or mark it internal) before shipping. Bespoke keys that bake a date/id into
  the key itself (e.g. `q1_2026_paid`) are a data-shape smell — fix the data, not
  the label table.

## How to evolve it

1. Adjust tokens in `DESIGN_TOKENS_CSS` first.
2. Keep the semantic colours intact; only the accent and neutrals are "fashion".
3. Build new components from the existing tokens and the patterns above.
4. Regenerate (`generate.py` → `OK` per page + `LINT OK`) and eyeball the Plan
   page and one client dashboard; for interactive bits, actually click them.
5. **Update this doc in the same change** (working norm: docs track code).
