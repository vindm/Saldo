# Jurisdiction packs

Saldo is multi-jurisdiction: one operator (one instance) can serve clients in
different tax systems. Everything tax-system-specific — regimes, the monthly
pipeline, the tax authority and portal, terminology, currency, the procedures —
lives in a **jurisdiction pack**, `jurisdictions/<code>/`. A client binds to a
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
  pipeline.yaml      ordered monthly-cycle stages (+ icon/glyph per stage)
  lint.yaml          regime invariants + account format, applied by state_lint
  checklists/        one procedure per task type (browser-driving, etc.)
```

**manifest.yaml** — `code`, `name`, file pointers (`authorities`, `regimes`,
`pipeline`), `workflow_domains: [...]`, and `checklists: {<task_type>: <path>}`.
A task type absent from `checklists` does not apply in this jurisdiction.

**authorities.yaml** — `currency`, `currency_symbol`, `period_income_label`,
`tax_authority`, `filing_systems`, `accounting_system`, registry/portal names,
and `term_map` (abstract concept -> the term used in the instruction layer:
`tax_account`, `classifier_code`, `tax_return`, …).

**regimes.yaml** — `regimes: {<TYPE>: {label, show_rate, objects: {<object>: <label>}}}`
plus `patent: {active_status, suffix}`. Drives the dashboard regime string.

**pipeline.yaml** — `stages: [{code, title:{<lang>}, task_types:[...], checklist, icon, glyph}]`
plus `feeders: [...]`. Each stage declares its own `icon` (a lucide name) and
`glyph` (emoji) so a new jurisdiction needs no engine edit.

**lint.yaml** — `regime_rules: {<TYPE>: {...}}` (e.g. expected rates, one-bank,
partner-flag) and `account_format: {length}`. `state_lint` runs only the rules
the client's pack defines, so a non-RU client never gets RU warnings.

## How the engine reads a pack

`engine/_jurisdiction.py`:
- `load_jurisdiction(code)` -> `Pack` (cached). Empty/None -> `"ru"`; an unknown
  code with no pack directory raises `JurisdictionError` (loud, never a silent RU
  fallback).
- `Pack`: `.regimes`, `.patent`, `.manifest`, `.authorities`, `.lint`,
  `.checklist_for(task_type)`.
- `render_regime_label(pack, primary, patents)` -> the dashboard regime string.

`engine/_pipeline.py`: `stages(jurisdiction)`, `stage_index_of(task_type, jurisdiction)`,
`stage_attr(code, jurisdiction, key)` (icon/glyph). `engine/_plan_waves.py`
resolves a task's jurisdiction from its `client_id` and threads it through wave /
periods rendering. `engine/state_lint.py` reads `lint.yaml` per client.

## How to add a jurisdiction (pure data — no engine code change)

1. Create `jurisdictions/<code>/` with `manifest.yaml`, `authorities.yaml`,
   `regimes.yaml`, `pipeline.yaml`, `lint.yaml`, and `checklists/`.
2. Author the content for that tax system (regimes, authority/portal/currency,
   the monthly stages, the procedures). Pipeline stage `icon` must be a lucide
   name already used elsewhere (the sprite is built from used icons; `icon()`
   accepts such names directly).
3. Tag clients: set `state/regime.json → jurisdiction: "<code>"`.
4. Verify by **runtime scenario** (`tests/runtime_scenarios/`) — confirm the
   runtime reasons in the new tax system and emits no RF artefacts — and by a
   render (`generate.py`): RU clients stay byte-identical; the new client renders
   under its own pipeline/regime/currency.

No Python change is required to add a jurisdiction. Touch the engine only if the
rendered *view* itself needs a new capability.

## Packs present

- `ru/` — Russian Federation (USN/AUSN/OSNO/PSN; FTS; 1C; ENP/KBK; the practice's
  RU pipeline and checklists). The default jurisdiction.
- `id/` — Indonesia, scoped to a UMKM micro client (final PPh 0.5%; DJP; Coretax;
  SPT). Synthetic demo pack — see `instances/example` client `melati`.
