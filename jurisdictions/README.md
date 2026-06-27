# Jurisdiction packs

Saldo is multi-jurisdiction: one operator (one instance) can serve clients in
different tax systems. Everything tax-system-specific — regimes, the recurring
cycles (monthly close, payroll, quarterly tax, AUSN…), the tax authority and
portal, terminology, currency, the procedures — lives in a **jurisdiction pack**,
`jurisdictions/<code>/`. A client binds to a
pack through `state/regime.json → jurisdiction` (default `"ru"`).

These packs are **declared data, in English** (the instruction layer is
locale-independent). Locale governs what the *operator* sees (dashboard + chat);
the *jurisdiction* governs tax content. The two are independent: a Russian
operator can run an Indonesian-jurisdiction client — the UI stays Russian, the
filings are Indonesian.

> The runtime entry point is `policies/INSTRUCTIONS.md §0`: resolve the client's
> jurisdiction, load its pack, and take every authority/term/checklist from it —
> never assume RF. If a client's jurisdiction has no pack, the runtime stops and
> surfaces it; it never falls back to RF procedures.

## A pack's files

```
jurisdictions/<code>/
  manifest.yaml      index: pointers + workflow domains + task_type -> checklist map
  authorities.yaml   tax authority, filing systems, currency(+symbol), term map
  regimes.yaml       tax-regime display rules (label / object / rate / patent)
  cycles/            one file per recurring cycle (monthly_close, payroll,
                     tax_quarterly, ausn…): ordered stages + cadence + icon/glyph
  pipeline.yaml      LEGACY single-pipeline form — still supported: auto-wrapped as
                     one 'monthly_close' cycle when cycles/ is absent (id/ uses this)
  lint.yaml          regime invariants + account format, applied by state_lint
  obligations.yaml   recurring (non-monthly) filing/payment obligations + cadence
                     — runtime + deadline_monitor read this
  checklists/        one procedure per task type (browser-driving, etc.)
  glossary.md        native-term glosses for the operator UI (optional; INSTRUCTIONS §0.1)
  ter.yaml           id-only: PPh 21 data (TER + PTKP + annual scale) — runtime-read,
                     no engine calculator
```

**manifest.yaml** — `code`, `name`, file pointers (`authorities`, `regimes`,
`pipeline`), `workflow_domains: [...]`, and `checklists: {<task_type>: <path>}`.
A task type absent from `checklists` does not apply in this jurisdiction.

**authorities.yaml** — `currency`, `currency_symbol`, `period_income_label`,
`tax_authority`, `filing_systems`, `accounting_system`, registry/portal names,
and `term_map` (abstract concept -> the term used in the instruction layer:
`tax_account`, `classifier_code`, `tax_return`, …).

**regimes.yaml** — `regimes: {<TYPE>: {label, show_rate, objects: {<object>: <label>}}}`
plus `patent: {active_status, suffix}`. Drives the dashboard regime string. The
`label` / `object` / `patent.suffix` tokens are authored in **English** (pack =
source language); `render_regime_label` localises them via `t()` at render time,
so the operator surface (snippet card + client-page header, which share the same
`c['regime']` string) is fully translated. Each token is therefore also an
`engine/_strings.py` catalog key — see the localisation note under "How to add".

**cycles/*.yaml** — one file per recurring cycle. Each declares `code`, `cadence`
(`monthly` | `quarterly` | `annual`), `title: {<lang>}`, optional `primary: true`
(the monthly close — renders first and headerless in Periods), `order`, and
`stages: [{code, title:{<lang>}, task_types:[...], checklist, icon, glyph}]` plus
`feeders: [...]`. Stage `code`s are **globally unique across cycles**, so a
`task_type` maps to exactly one cycle+stage. Each stage declares its own `icon` (a
lucide name) and `glyph` (emoji) so a new cycle needs no engine edit. A pack may
instead use a single legacy **pipeline.yaml** (same `stages`/`feeders` shape) — the
engine wraps it as one `monthly_close` cycle. RU uses `cycles/`; `id/` still uses
`pipeline.yaml`. The **Periods** view renders one band per cycle (primary first,
headerless); the **Plan** batches each stage into a wave. Counts are by **task**,
not by client.

**lint.yaml** — `regime_rules: {<TYPE>: {...}}` (e.g. expected rates, one-bank,
partner-flag) and `account_format: {length}`. `state_lint` runs only the rules
the client's pack defines, so a non-RU client never gets RU warnings.

**obligations.yaml** — `obligations: {<key>: {cadence, ...}}`: the pack's recurring non-monthly filings/payments (single periodic obligations). Exposed as `Pack.obligations`; read by `engine/_cadence.py`, `engine/state_lint.py`, and the `deadline_monitor` connector. Absent → `{}` (no obligations declared).

**glossary.md** (optional) — native-term glosses (`term | gloss` rows) the operator UI wraps in tooltips; the canonical gloss source named by `INSTRUCTIONS.md §0.1`.

**ter.yaml** (id only) — PPh 21 computation data: TER tables + PTKP + the annual scale. **Runtime-read pack DATA, not engine-read** — the AI applies it per `checklists/payroll-pph21-bpjs.md`; there is no Python PPh calculator. The engine's `_PTKP_TER_TABLE` is only a display-only mirror of its `ter_category` sub-map.

## How the engine reads a pack

`engine/_jurisdiction.py`:
- `load_jurisdiction(code)` -> `Pack` (cached). Empty/None -> `"ru"`; an unknown
  code with no pack directory raises `JurisdictionError` (loud, never a silent RU
  fallback).
- `Pack`: `.regimes`, `.patent`, `.manifest`, `.authorities`, `.lint`,
  `.obligations`, `.checklist_for(task_type)`.
- `render_regime_label(pack, primary, patents)` -> the dashboard regime string.

`engine/_pipeline.py`: `cycles(jurisdiction)` (ordered cycle dicts),
`stages(jurisdiction, cycle=None)` (a cycle's stages; default = the primary cycle),
`locate_stage(task_type, jurisdiction)` -> `(cycle_code, stage_code)` across all
cycles, `cycle_of_stage(stage_code, jurisdiction)`, `stage_index_of` (primary
cycle), `stage_attr(code, jurisdiction, key)` (icon/glyph, searched across cycles).
`engine/_plan_waves.py`
resolves a task's jurisdiction from its `client_id` and threads it through wave /
periods rendering. `engine/state_lint.py` reads `lint.yaml` per client.

## How to add a jurisdiction (pure data — no engine code change)

1. Create `jurisdictions/<code>/` with `manifest.yaml`, `authorities.yaml`,
   `regimes.yaml`, `cycles/` (one file per recurring cycle; or a single legacy
   `pipeline.yaml`), `lint.yaml`, `obligations.yaml` (recurring non-monthly
   filings; cadence/deadline derivation reads it), and `checklists/`.
2. Author the content for that tax system (regimes, authority/portal/currency,
   the cycle stages, the procedures). A stage `icon` must be a lucide
   name already used elsewhere (the sprite is built from used icons; `icon()`
   accepts such names directly).
3. Tag clients: set `state/regime.json → jurisdiction: "<code>"`.
4. Verify by **runtime scenario** (`tests/runtime_scenarios/`) — confirm the
   runtime reasons in the new tax system and emits no RF artefacts — and by a
   render (`generate.py`): RU clients stay byte-identical; the new client renders
   under its own pipeline/regime/currency.

No Python change is required to add a jurisdiction. Touch the engine only if the
rendered *view* itself needs a new capability.

**Localisation caveat (the one non-data step):** pack tokens are English. For
any **non-`en` operator locale**, add a matching entry to the locale catalog in
`engine/_strings.py` for each regime `label` / `object` token and the
`patent.suffix` you introduce — otherwise `t()` falls back to the English token
and that English string shows on the operator's snippet card and client-page
header. The `generate.py` i18n guard ("all operator-facing strings translated
for locale 'ru'") catches a missed token. Example (ru): `'USN Income' →
'УСН Доходы'`, `'+ PSN' → '+ ПСН'`, `'UMKM final (turnover)' → 'UMKM (оборот)'`.

## Packs present

- `ru/` — Russian Federation (USN/AUSN/OSNO/PSN; FTS; 1C; ENP/KBK; the practice's
  RU pipeline and checklists). The default jurisdiction.
- `id/` — Indonesia, scoped to a UMKM micro client (final PPh 0.5%; DJP; Coretax;
  SPT). Synthetic demo pack — see `instances/example` client `melati`.
