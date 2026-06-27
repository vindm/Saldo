# Multiple standardized cycles — BUILT (2026-06-26)

> Status: **implemented**. Canonical docs: `docs/ARCHITECTURE.md` (the cycles
> model) and `jurisdictions/README.md` (authoring `cycles/*.yaml`). RU ships four
> cycles (`jurisdictions/ru/cycles/`): monthly_close (primary), payroll,
> tax_quarterly, ausn_monthly. The engine API is `_pipeline.cycles()` /
> `locate_stage()`; Periods renders one band per cycle and counts tasks. This file
> is kept as the design record / rationale.

---


Follow-on to `MONTHLY-PIPELINE-PROPOSAL.md`. That one made the **monthly close** a
canonical 6-stage pipeline. This one generalizes "one pipeline" into **several named
cycles**, so recurring work that isn't the monthly close (payroll, quarterly tax,
AUSN) stops landing in the undifferentiated "off-pipeline" pile and gets its own
period-anchored lane in the Periods view.

## Why

The Periods lens today renders exactly one cycle (monthly close, 6 stages). On the
real snapshot (`saldo-migrated_data`, 62 open tasks) only **17** are pipeline-stage
tasks; the other **45** are "off-pipeline." But ~13 of those 45 are *recurring,
period-bearing* work that simply belongs to a different cadence than the monthly
close — they're off-pipeline only because no other cycle exists to hold them:

| Currently off-pipeline | Belongs to | Cadence |
|---|---|---|
| `tax_calc` (Расчёт налога УСН за полугодие) | Quarterly tax / ЕНС | quarterly + annual |
| `ens_reconciliation` (Сверка с ЕНС) | Quarterly tax / ЕНС | quarterly |
| `ndfl_register` (Реестр выплат НДФЛ) | Payroll | monthly (own deadlines) |
| `ausn_markup_review`, `ausn_bank_marking` | AUSN | monthly (variant flow) |
| `bank_check` → `primary_collection` (statement collection); `kkt_check`, `balance_reconciliation` → `month_audit` | promoted feeders | — |

The other ~31 (`awaiting_external` ×14, `client_followup` ×6, `note`, `monitoring`,
`access_request`, …) are **genuinely ad-hoc** — exception handling and client comms.
They must stay off-pipeline and visible in Plan/Calendar. So the honest ceiling is
~17 → ~30 stage tasks, not 62/62. Standardizing cycles is about giving recurring
work a deterministic lane, **not** about forcing every task into a pipeline.

## Blast radius (good news)

Cycles surface in only **two renderers** plus the pack data and the API module:

- `engine/_pipeline.py` — the stage/cycle API (today: `stages()`, `stage_index_of()`).
- `engine/_periods.py` — the Periods lens.
- `engine/_plan_waves.py` — Plan wave grouping (`_op_canonical` / `_stage_of_token`).
- `jurisdictions/<code>/pipeline.yaml` — the declared cycles (pure data).

`client_pipeline()` / `on_pipeline` / `off_pipeline` exist in `_pipeline.py` but are
**not consumed by any renderer** (the client cockpit renders by track, not by a stage
strip). So there is no per-client progress-strip to refactor. The change is contained.

## Data model — cycles are pure pack data

No new state. A cycle is a **VIEW over existing `task_type`s**, exactly like the
current pipeline. Generalize `pipeline.yaml` from a single `stages:` list to a
`cycles:` list. Each cycle declares a cadence and its own ordered stages:

```yaml
cycles:
  - code: monthly_close            # the existing one — unchanged
    cadence: monthly               # monthly | quarterly | annual
    title: { ru: "Месячный цикл", en: "Monthly close" }
    primary: true                  # renders first, with NO cycle header (byte-identical)
    stages: [ ... as today ... ]
    feeders: [ acquiring_reconciliation, ausn_reconciliation ]

  - code: payroll
    cadence: monthly
    title: { ru: "Зарплата", en: "Payroll" }
    stages:
      - { code: payroll_calc,    title: {ru: "Расчёт зарплаты"},        task_types: [payroll_calc, payroll_pph21_bpjs] }
      - { code: ndfl,            title: {ru: "НДФЛ — реестр/уплата"},   task_types: [ndfl_register] }
      - { code: contributions,   title: {ru: "Страховые взносы"},        task_types: [contributions] }
      - { code: payroll_reports, title: {ru: "6-НДФЛ / РСВ / ЕФС-1"},   task_types: [payroll_reports] }

  - code: tax_quarterly
    cadence: quarterly
    title: { ru: "Налоги: квартал / год", en: "Quarterly tax" }
    stages:
      - { code: tax_calc,    title: {ru: "Расчёт налога/аванса"}, task_types: [tax_calc] }
      - { code: ens_sverka,  title: {ru: "Сверка с ЕНС"},         task_types: [ens_reconciliation] }
      - { code: declaration, title: {ru: "Декларация"},           task_types: [declaration] }

  - code: ausn_monthly
    cadence: monthly
    title: { ru: "АУСН", en: "AUSN" }
    stages:
      - { code: ausn_markup, title: {ru: "Разметка операций"},  task_types: [ausn_markup_review, ausn_bank_marking] }
      - { code: ausn_calc,   title: {ru: "Расчёт + уплата"},     task_types: [ausn_monthly] }
```

Invariants kept from the original proposal: stages ordered; a client's position =
earliest stage with open tasks for the period; done = all tasks terminal; **the
engine invents nothing** — it reads the declared cycle and the `task_type`s already
in state.

Rule: a `task_type` maps to **exactly one** (cycle, stage). The snapshot inventory
confirms every type is distinct, so no ambiguity. Stage `code`s stay **globally
unique** across cycles (`payroll_calc`, not a second `tax_pp`) → the Plan token
format `stage:<code>|<period>` is unchanged; only the lookup widens to span cycles.

### Backward-compat & the byte-identical invariant

- If a pack still has top-level `stages:` (no `cycles:`), the loader wraps it as a
  single `monthly_close` cycle. The `id/` pack and any legacy reader keep working.
- The `monthly_close` cycle is `primary: true` → rendered first with **no cycle
  header**, exactly as RU renders today with no jurisdiction header. Its output is
  **byte-identical**. New cycles render below as additional bands (same mechanism as
  the existing ИНДОНЕЗИЯ jurisdiction band). The change is purely additive to the
  existing Periods output.

## Engine / view changes

1. **`_pipeline.py`** — add `cycles(juris)` → ordered cycle dicts; make
   `stage_index_of` return `(cycle_code, stage_idx)`; keep `stages()` as
   `stages(juris, cycle="monthly_close")` for callers that still want one cycle.
   Cadence-aware period formatting/sort (`monthly`→`YYYY-MM`, `quarterly`→`YYYY-Qn`,
   `annual`→`YYYY`).
2. **`_periods.py`** — group `jurisdiction → cycle → period → stage`. Render each
   cycle as a band (primary cycle headerless first). A cycle band only appears if it
   has tasks → AUSN clients show the AUSN band, not an empty monthly close; a client
   with no payroll shows no payroll band.
3. **`_plan_waves.py`** — `_stage_of_token` resolves a token to its (cycle, stage)
   across all cycles. The keyword-no-period guard we just added stays. `ausn_monthly`
   moves out of the monthly-close `tax_pp` stage into the AUSN cycle (note: this is a
   deliberate *change* to current Plan output for AUSN clients).

## Migration?

**None.** This reshapes the *declared view* (pack YAML) and the *render*, not state.
No field is added, renamed, or moved in `clients/<id>/state/*.json`; every `task_type`
referenced already exists. Per the migration rule, migrations are for data/state
reshapes — this is a behaviour change, so the obligation is (a) update what the
runtime reads (the pack + any policy note) and (b) verify by scenario. There is no
`NNNN_*.py` to ship.

Two `task_type`s referenced above don't yet appear in the snapshot (`contributions`,
`payroll_reports`, `declaration`) — they're declared so the cycle is complete for
when such tasks arrive; absent tasks simply render as empty stages.

## What visibly changes (to approve)

- New Periods bands: **Зарплата**, **Налоги: квартал/год**, **АУСН** — appearing only
  for clients with matching tasks.
- `tax_calc` (cobalt, 2026-H1) now shows under the quarterly-tax cycle instead of being
  invisible; `ndfl_register` (meridian) under payroll; AUSN tasks under AUSN.
- `bank_check` / `kkt_check` / `balance_reconciliation` promoted from invisible feeders
  to members of `month_audit` (smallest sub-change; can be done independently).
- Monthly-close band: **unchanged, byte-identical.**

## Verification plan

1. `generate.py` → OK per page + LINT OK; `state_lint.py`; `system_integrity_check.py`.
2. **Byte-diff** the monthly-close band against pre-change `periods.html` — must match.
3. **Scenario role-play** (the Invariant-0 gate, `tests/runtime_scenarios/`): a payroll
   client surfaces the payroll cycle; an AUSN client surfaces the AUSN cycle and **no**
   standard-close tax_pp artefact; a micro/no-payroll client shows no payroll band.
4. Confirm the ~31 genuinely-ad-hoc tasks are still off-pipeline (no false promotions).

## Open questions for you

1. **Cycle list/cadence** above correct? Especially: is AUSN a separate *cycle*, or a
   *regime variant* of monthly close? (I lean separate — AUSN's flow truly differs.)
2. **Quarterly rollup:** should monthly tasks roll up into the quarter, or does each
   task keep its own period? (I lean: keep its own period; cadence only drives
   formatting/sort.)
3. **Scope of v1:** all three cycles at once, or land the framework + the smallest
   cycle (promote-feeders + quarterly tax) first, then payroll + AUSN?
4. **Pack-data location:** keep cycles in `pipeline.yaml` (`cycles:`), or split into
   `jurisdictions/<code>/cycles/*.yaml` (one file per cycle)?

## Build plan (incremental, each step verified vs original)

1. `_pipeline.py`: add `cycles()` + cycle-aware `stage_index_of`; legacy `stages:`
   wrapped as `monthly_close`. (Pure function, no writes; byte-diff parity.)
2. Author the cycles in `jurisdictions/ru/pipeline.yaml` (data only).
3. `_periods.py`: render cycle bands; byte-diff the primary band.
4. `_plan_waves.py`: widen token resolution to cycles; move `ausn_monthly`.
5. Promote feeders: `bank_check` → `primary_collection` (it's statement collection, a
   collection input); `kkt_check` + `balance_reconciliation` → `month_audit`.
6. Scenario + gates; update the `id/` pack note if its single-pipeline form needs the
   wrapper path exercised.
