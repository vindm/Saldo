# Design system — operator dashboards

Scope: the static HTML dashboards rendered by `engine/` — the **operator-facing
view**. This is the developer/view layer (per Invariant 0, touch Python only when
the rendered view must change). It is distinct from `policies/brand-and-tone.md`,
which governs **client-facing** output (the Russian reports/messages a client sees).

One client-facing artifact is *also* an engine-rendered view: the monthly
one-pager (`engine/_owner_report.py`). It is the dev/view layer like the
dashboards, but wears the **client brand** (navy/gold) rather than the indigo
chrome — its rules are in **Client one-pager (owner report)** below; brand
identity and tone come from `policies/brand-and-tone.md`.

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
  `--accent-red` = overdue / bad health, `--accent-yellow` = due-soon / waiting /
  **blocked**, `--accent-green` = ready / good health. Their `*-bg` tints back the
  matching badges and rows. When the accent changes for fashion, these stay put.
  *`blocked` is yellow, not red* (single source `_status.py → CANON_PILL`): a
  blocked task waits on something else — nothing to do on it now — so it must not
  pull attention like an overdue item. Red is reserved for "act now".
- **Client identity colour:** each client's avatar tint is a deterministic
  hash→HSL hue (`_helpers._avatar_color`, used by `client_avatar`), not a fixed
  palette — so any number of clients each get a distinct, memorable colour
  (the colour *is* the meaning: same client = same colour everywhere).
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
- **Motion:** see **Motion** below. **Type:** system sans; sizes via `--fs-*`.

### Vertical rhythm — list spacing (proximity)

A list reads as one list only when its items sit **closer to each other than
to whatever surrounds the list**. So the gap **between** list items must be
**≤** the gap **before/after** the whole list, and the tightest gap of all is
**within** an item (a card header to its own body). The hierarchy is always:

> `within-item  <  between-items  ≤  before/after-list  <  between-sections`

Never let the inter-item gap exceed the gap around the list — that makes an
item look attached to the section heading above it instead of to its own list
(this bit the Periods page: 26px between periods vs 12px from the cycle head).

Worked example — Periods (`_periods.py`), period cards within a cycle:
header→card **8px** < between periods **16px** ≤ cycle-head→first-period
**20px** < between cycles **32px** < between jurisdictions **36px**.

## Motion

- **Token:** `--transition` = `150ms ease` — the value **already includes the
  easing keyword**. Write `transition:<prop> var(--transition)`; **never**
  `var(--transition) ease` (it expands to `150ms ease ease`, which is invalid and
  silently drops the whole declaration — this bit us on the wave animation). When
  you need a different curve or a delay, write the value in full (the wave reveal
  uses `240ms cubic-bezier(.16,1,.3,1)`).
- **Reduced motion:** a global guard in `DESIGN_TOKENS_CSS`
  (`@media (prefers-reduced-motion: reduce)`) collapses every transition/animation
  duration to ~0. New animations inherit it automatically — don't special-case.
- **Open/collapse (the wave "drawer"):** height animates via the CSS grid-rows
  technique — `grid-template-rows:0fr↔1fr` on a `.wave-reveal` wrapper whose single
  child is `overflow:hidden;min-height:0` (no JS height measuring). Content fades
  via `opacity`; the header eases grey→`--accent-soft`; the chevron rotates.
  Collapsed content is pulled out of tab order/clicks (`visibility:hidden`, delayed
  to the end of the collapse). `display:none` can't be transitioned — use this
  pattern for any future expand/collapse.

## Component patterns (established conventions — reuse, don't reinvent)

- **The sidebar's only left-edge bar is the active-item accent rail** (`_sidebar.py`
  `.sb-item.active` → `box-shadow:inset 3px 0 0 var(--accent)`). Selection has a
  *single* signal: accent-soft fill + the rail. Do **not** give a category of nav
  rows (e.g. client groups) a permanent decorative `border-left` — a standing bar
  on un-selected items competes with the rail and makes the real selected state
  easy to miss (failure-mode #1). The old purple client-group border was removed
  for exactly this reason (2026-06-26). The one sanctioned exception is the gold
  `.sb-update` "update available" CTA, where the bar *encodes* a transient state.
  Spacing is deliberately generous, not dense (the 248px column, 28/20 padding and
  a stacked left-aligned brand block were tuned to the `design-mockup-s-tier.html`
  reference, 2026-06-26): nav type is 14.5px on an 8px row rhythm, inactive rows
  are the calmer `--text-secondary` with `--text-muted` icons, both going `--accent`
  (navy) when selected; the "Clients" caption is a quiet 10.5px wide-tracked
  micro-label (`--text-muted`), not a peer of the nav items; counts are plain
  tabular numbers, with a red tint reserved for the overdue Plan count.
- **Filter-active banner** (`_mode_switch.py`): whenever a filter hides rows, show
  a high-visibility banner stating shown-vs-hidden counts plus a one-click reset;
  the selected segment is filled `--accent`. Rule: *a filter must never silently
  swallow items.*
- **Expanded container / "drawer"** (`_plan_waves.py`, `.wave:not(.collapsed)`):
  an open group lifts into its own card — full border, an `--accent` left-rail, a
  soft-lavender (`--accent-soft`) header, a light shadow — so its start and end are
  unambiguous. (We deliberately chose this calm variant over a full-indigo bar.) It
  **animates open** (grid-rows reveal + content fade + grey→lavender header) — see
  **Motion**.
- **Client identity = one avatar everywhere** (`_helpers.client_avatar`): the
  coloured initials circle is the single identity marker for a client. Fill colour
  is a deterministic hash of the client's name, so the *same* client is the *same*
  colour on every surface — task/event rows, the client cards
  (`_clients_group.py` `.dc-av`), and the client-page header
  (`_client_dashboard_v2.py` `.client-av`, where a health-coloured **ring** around
  the avatar carries health, replacing the old standalone dot). Always render
  identity through this helper; never invent a per-surface avatar. Colour itself
  comes from `_helpers._avatar_color` (stable name→HSL hash, near-unique per
  client); `client_avatar` is the single producer of the initials + inline style,
  used by task rows, event rows, cards, and the page header alike.
- **Transient focus highlight** (e.g. Periods → Plan deep-link): use a *removable
  class* (`.wave-focus` → `outline`), never an inline style. Wire user actions
  (collapse, collapse-all) to clear it and strip the deep-link hash via
  `history.replaceState`, so it doesn't reappear on reload.
- **Periods view = a per-cycle progress stepper, counted by task** (`_periods.py`).
  Each jurisdiction renders one band per recurring cycle (`_pipeline.cycles()`): the
  primary cycle (monthly close) is first and **headerless**, other cycles get a slim
  gold-bar header (`.pp-cycle-head`), jurisdictions a navy-bar header
  (`.pp-juris-head`). Within a band, each reporting period is a card whose stages are
  a horizontal **stepper** (`.pp-step`) — one node per stage: done = green ✓, active =
  navy circle with the open count, overdue = red, not-yet-started = a faint outline
  circle with a muted label (**never a "—" cell** — empty stages must recede, not
  compete). The connector fills green through completed stages; a status line
  («Сейчас: <stage>» / «Завершено ✓», red when overdue) summarises the period.
  **Counts are by TASK, not by distinct client** — matching the Plan's wave counts;
  the cohort pill uses `_plural_tasks` (RU-declined: 1 задача / 2 задачи / 5 задач).
  The page must read as "where does each cycle stand", at a glance.
- **Counts shown side by side must share one definition.** If two numbers sit near
  each other they must use the same window — e.g. the Plan sidebar badge and the
  "{N} in the next 7 days" summary both use `horizon_counts(...)['near']`.
- **Interaction affordances:** row hover = visible `--bg-page` tint; keyboard
  focus = 2px `--accent` `:focus-visible` outline.
- **The shared task-row snippet clamps every text line to one line** (`_brief.py`
  `render_task_snippet`: `.an-rec-title` and `.an-why` are
  `white-space:nowrap;overflow:hidden;text-overflow:ellipsis`). Rows stay a uniform
  height across every surface (overview «Сводка», client «Сводка», Plan, active
  tracks) and the avatar never looks size-mismatched against a tall wrapped row; the
  full text is in the track modal on click. Don't reintroduce multi-line wrapping in
  a row — put detail in the modal.
- **A summary count sits on the right of its section header**, not inline after the
  title (`section-title`/`an-head` are `flex; justify-content:space-between`; the
  count is a *sibling* of the title span, never nested inside it).
- **Every page header renders its count-summary through the ONE shared KPI band**
  (`_analytics_widgets.render_kpi_band`, CSS `KPI_BAND_CSS` / `.aw-stats` ≡
  `.kpi-band`): transparent — **no card/island**, no border — label-over-value, navy
  `--accent` value, vertical `--border` dividers between tiles; semantic value
  colours (red / amber / green) kept as signal. This is the look on the overview,
  the **Plan** (`в работе / ближайшие 7 дней / дальше`), the **clients-group** pages
  (`срочные / скоро / в норме`) and the **client cockpit** alike — one metric look
  across the whole product. Never fork a parallel summary renderer: the old inline
  `.plan-summary` and `.cd-summary` dot-strings were retired into the band on
  2026-06-26 (three visual languages for the same job → one). Tiles differ per page
  only in *which* metrics they carry; the component, type scale and colours do not.
  **Numbers shared across pages share their definition AND their label** — e.g. the
  leading «В работе» tile = `aggregate_tasks(TODAY)['all']` on both the overview and
  the Plan (same count, same word), per the side-by-side-counts rule above.
- **A list row has one action — open its card — with one deliberate exception: the
  dependency chip.** The whole `.track-card-clickable` row opens the track modal; do
  **not** add per-row controls that merely duplicate that (a hover "→" to the client
  page was removed 2026-06-25). The **one** sanctioned second target is the
  «🔒 → blocker» dependency chip (`.an-dep`, and the modal’s `.tm-dep-link`): it is
  its own `track-card-clickable` and jumps to the *blocker’s* card, not this row’s. It
  carries a trailing `→` so it reads as a link at rest, and fills its background only
  on its *own* hover — both signal it is a separate target. The modal also shows the
  inverse «🔓 →» «Блокирует» section (reverse deps, `_track_attrs` blocks-json).
- **One task-row snippet everywhere** (`_brief.render_task_snippet`, `.an-*`): the
  overview «Сводка», the client «Сводка», the Plan and the client card’s
  «Активные треки» all render the SAME row component. The only per-surface
  difference is the «признаки клиента» (avatar + client line), shown on
  cross-client lists and omitted on a single client’s card — driven purely by whether
  the item carries `avatar` / `client`. Right-aligned chips read left→right: status
  («заблокировано» / «ждём», yellow `_status.py` palette), «разблокирует N»
  (reverse-dependency count), the shared due badge, then the go-arrow. Change a row
  once, here — never fork a parallel renderer (the old `.task-*` plan grid was retired
  into this on 2026-06-25).
- **Fixed trailing columns so chips don’t jump.** Status/due on task rows and the
  readiness-bar + due-badge on wave headers (`.wave-meta`: a 64px bar slot + a 92px
  badge cell) sit in fixed-width, right-aligned columns so they align vertically down
  the list instead of shifting with text width.
- **Event/history timeline** (`_track_modal.py` `.tm-history-*`,
  `_client_dashboard_v2.py` `.kdh-*`): chronological lists render as a vertical
  rail with one dot per entry. The dot legend is fixed and meaning-bearing:
  **filled `--accent` dot = an operator/system action or decision; hollow ring
  (`--border-strong`) = an automatic event.** Reuse this legend wherever events
  are shown; never invent per-list dot meanings.
- **Operator history shows decisions, not engine bookkeeping.** The key-decisions
  timeline filters audit rows out of `history.jsonl` (schema migrations,
  `lint_hardening`, `assist_seeded`, `source_backfill`, `bell_consumed`,
  `cd_migration`) via `_loaders._history_is_noise`; those are developer audit —
  they belong on the Changelog page, never the client view. This was also the
  sole source of English text leaking into the Russian surface (see i18n below).
  When a new engine process writes to `history.jsonl`, add its source/kind/event
  to `_history_is_noise` so it can't resurface in the operator view.
- **One prompt modal for every "act on this" affordance** (`_css.py`
  `PROMPT_MODAL_*`). Every button that hands work to the runtime — track-modal
  "Разобрать", client header, wave "Разобрать", analysis recommendations, the
  open-questions options — opens the **same shared editable modal**, never a
  bespoke editor. Wiring: put the editable default in `data-prompt` and (optional)
  the immutable facts in `data-prompt-ctx`; a single document-level handler reads
  both. If a button must `stopPropagation` (it sits on a clickable row), it has to
  call `window.openPromptModal(this.dataset.prompt, {ctx})` itself — a stopped
  event never reaches the global handler (this silently broke the header button
  once). Dictation is **inside** the modal (Win+H), so there is **one button, not
  a button + a mic** — the old `_dictate.py` module has been removed.
- **Prompt = context + ask, never the program.** `data-prompt-ctx` is the
  **immutable** context block (client/task facts, question + hypothesis) shown
  read-only and always prepended on copy; `data-prompt` is a **short editable**
  ask (e.g. «Разбери задачу и предложи конкретное следующее действие»). Do **not**
  restate the standing operating procedure (resolve jurisdiction, pick the
  checklist, apply via `mm_update` with approval, send nothing outward) inside a
  prompt — that is the runtime's program and lives in `policies/INSTRUCTIONS.md`;
  the pasted prompt is a *pointer*, not a copy of the rules. This keeps prompts
  thin and means the operator can clear the ask and write/dictate their own
  without losing the context.
- **Action buttons use the `tm-btn` family; "Разобрать" is primary-outline.**
  The shared verb-button is `.tm-btn.tm-btn-outline` (accent border + accent text,
  light fill on hover) — present but not heavy, so several on a page don't fight
  for attention. Use the compound selector (`.tm-btn.tm-btn-outline`) so a later
  plain `.tm-btn{border:…}` can't reset the accent border.

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
  `i18n_task_type` (a `task_type` with no `_TASK_TYPE_LABEL` entry),
  `i18n_ts_key` (a `type_specific` key with no `_TS_RU_LOC` label and not in
  `INTERNAL_TS_KEYS`), and `i18n_cp_label` (a counterparty `relation_type` or
  `category` with no entry in `_CP_RELATION_LABEL` / `_CP_CATEGORY_LABEL` in
  `_client_dashboard_v2.py`; these render in `.cp-meta`, which is
  `text-transform:uppercase`, so an unmapped value leaked as a SCREAMING raw enum
  — `BOOKKEEPING_SERVICE_PROVIDER_TEAM_LEAD`). These run on every `generate`. When you add a new enum
  value or detail field, run `state_lint`; if it lists the token, add its label
  (or mark it internal) before shipping. Bespoke keys that bake a date/id into
  the key itself (e.g. `q1_2026_paid`) are a data-shape smell — fix the data, not
  the label table.

## Glyphs & the emoji sanitizer (gotcha)

`generate.py` runs a final pass that strips decorative emoji from the rendered HTML
(`_EMOJI` regex, `\U0001F000-\U0001FAFF` + symbol blocks) so the UI shows the
monochrome line icons only — **arrows (→) survive, but any literal emoji in a render
string is silently removed.** To keep a specific glyph (e.g. the lock 🔒 on a
dependency chip), emit it as an **HTML entity** (`&#128274;`; `&#128275;` = open lock):
entities are ASCII, so they pass the sanitizer untouched and the browser decodes them.
A literal `\U0001F512` in Python vanishes from the output (this bit the plan dep chip +
track-modal on 2026-06-25). SVG icons (`_icons.py`) are the preferred path; the entity
trick is only for the few semantic glyphs we keep (lock / open-lock).

## Client one-pager (owner report)

The monthly statement the operator opens from a client card, prints to PDF and
sends. **Single source: `engine/_owner_report.py` (`_CSS` + `_PAGE`)** — never
hand-edit a generated `report_*.html` (Invariant 3). Client-facing, so it carries
the navy/gold brand, NOT the indigo dashboard accent; brand + tone per
`policies/brand-and-tone.md`.

Aesthetic — a **financial statement**, not a dashboard: calm, airy, rhythmic.
The bar to clear is "a serious professional practice", and the explicit failure
mode is "boxy / cramped".

- **Statement rows, not card grids, for the tax breakdown.** Each line is a
  hairline-separated row (label + plain-language note on the left, amount
  right-aligned). This holds an even cadence for one line or six, and avoids the
  lonely half-width card a 2-col grid leaves on an odd count.
- **Generous, consistent vertical rhythm** — wide sheet margins, a clear
  client-name block with a divider, fixed gaps between sections. Whitespace does
  the work; don't fill it.
- **Serif tabular figures for money** (`.num`) so columns align; one display
  serif (Georgia) for headings/figures over a clean system sans body.
- **Flat fills, one sparing accent.** Solid navy for the total band / current
  trend bar / print button (no gradients — they read cheap and print poorly).
  Gold is a single thin accent (the top rule, the currency glyph), never a
  field of colour.
- **The trend chart lives in the hero**, beside the figure — compact, ≥2 months
  or it's omitted. Not a separate full-width section.

**Empty / sparse states must be graceful — this is load-bearing, not polish.**
A just-onboarded client legitimately has no turnover and no tax lines yet.

- No turnover on file → a quiet italic caption (`t('No turnover recorded yet')`),
  **never a lone "—"** (which reads as a broken render).
- No tax lines → the honest note "no payment was due", **never "paid ✓ / 0"**.
- Turnover source order (first non-null wins): `turnover_idr` → `income_usn` →
  `income_ausn` → `ausn_monthly[latest].income_base`. Add a jurisdiction's income
  field here when its packs land, so its clients show a figure rather than the
  empty state.

**Verify on real shape, both data dirs.** Regenerate the example *and*
`saldo-migrated_data` (the proving ground) and eyeball the hardest cases: a
no-data АУСН client (empty state), a multi-line ID client with a trend
(face-protocol). Under `ru`, confirm no English leaks (every label via `t()`).

## How to evolve it

1. Adjust tokens in `DESIGN_TOKENS_CSS` first.
2. Keep the semantic colours intact; only the accent and neutrals are "fashion".
3. Build new components from the existing tokens and the patterns above.
4. Regenerate (`generate.py` → `OK` per page + `LINT OK`) and eyeball the Plan
   page and one client dashboard; for interactive bits, actually click them.
5. **Update this doc in the same change** (working norm: docs track code).
