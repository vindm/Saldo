# Design note — payroll review cockpit (review by exception)

Status: proposal (no code). Scope: turn the payroll-run modal from a *read-only table* into a
*review tool*, so the operator reviews **by exception** (look at 2–3 flagged lines) instead of
scanning all 14. Builds on the run-as-task + parity model and the entity-linking architecture.

## 1. The problem (from the synthetic kirana payroll months)

The operator opens a payroll run and sees 14 rows plus an aggregate diff vs the incumbent (e.g.
`−88 500`). She cannot see **where** the gap is or **what changed** — so review is O(employees)
and quality depends on her catching things by eye. The recurring real signals she needs surfaced:

- The diff vs the incumbent is **THR-driven** (April, no bonus → exact; Feb/Mar/May, bonus → under) —
  but nothing tells her *which lines carry THR* this month.
- A salary can shift for a **timing** reason (Made Wijaya 20M vs 30M — Jan paid in Feb) — a
  month-over-month jump she must notice.
- People **join/leave** between months; the run set silently changes.
- BPJS coverage gaps exist but aren't summarized at the top of the run.

## 2. The cockpit — a header band + per-line signals

**Header band** (replaces the bare `на проверке: N/M` roll-up) — the whole month at a glance:

> `14 строк · Σ PPh 2 400 000 · Предшественник 2 500 000 (−100 000 · THR) · к проверке: 3 · изменения: 2 · BPJS: дыра по соцстраху`

**Per-line signals** (badges next to the row, only where they fire):

- **THR / bonus** chip — the line carries a bonus this month → it's where our flat-TER differs
  from the incumbent's separate-THR method. Explains the gap; directs the eye.
- **Δ vs prev month** — `↑ +10 000 000` / `↓` / `новый` / (in prev, absent now → a "left" note in
  the header). Catches timing anomalies and data errors. Big Δ → the line is flagged "to review".
- **Method/coverage** flags already exist (non-resident→pph26, BPJS missing) — keep, fold into the
  same "to review" count.

A line with **no** signal and `parity_status: pass` collapses to the calm `покрыт`-style one-liner
(as covered rows already do); the operator's attention goes only to flagged rows.

**Review action** — the `Разобрать` button pre-fills a contextual prompt:
> «Проверь майский прогон kirana: подтверди строки без флагов, разберись с подсвеченными
> (THR / изменения / покрытие), затем предложи закрыть.»
One click → a focused review conversation, not a blank chat. (Closing the task stays the gate.)

## 3. Data vs derived (keep the engine honest)

Per "the dashboard is a pure derivation" and "derive don't store":

- **Derived at render** (no new state) — computed at the existing enrichment point
  `_track_attrs.py` `_ts_render` (it already has `client_id` and deep-copies `type_specific`):
  - **Δ vs prev**: find the prior masa's `payroll_pph21_bpjs` task, diff its `payroll_lines` by
    `employee_id`. New = absent in prev; left = in prev, absent now.
  - **Parity localization**: `sum(lines.pph)` vs `financials.periods[masa].taxes.pph21`; mark the
    THR-carrying lines as the likely contributors (we cannot per-employee-parity — incumbent files
    aggregate only — so we *localize by signal*, not by their numbers).
  - **Roster diff / coverage roll-up**: lines vs roster vs prev.
  - The **header band** is a roll-up of the above.
- **Data on the line** (the runtime writes when building the run, from the ведомость): **`thr`** —
  the bonus component of gross (`gross = gross_regular + thr`). Free-form addition to the line →
  **no migration**. It's the one real new input; everything else is a view.

This keeps the run's stored state minimal (lines + totals + refs); the cockpit is a lens over it
plus the prior run — exactly the entity-linking model (derive reverse views, don't duplicate).

## 4. Render hooks

- **Enrichment** (`engine/_track_attrs.py`, the `_ts_render` block): read prior-masa run +
  period aggregate + roster, attach to each line a small `_review` object
  (`{delta, is_new, thr, contributes}`) and a run-level `_summary` — all in the rendered copy only.
- **Modal** (`engine/_track_modal.py`): render the header band from `_summary`; render per-line
  badges from `_review`; reuse the `tm-pay-*` pill styles + semantic colors. The `Разобрать`
  prompt gains the contextual review text.
- Labels via `t()` (locale-correct, as the table already is).

## 5. What it buys (flow / UX / efficiency / quality)

- **Efficiency**: review drops from 14 rows to the 2–3 flagged ones; the header answers the month
  in one glance.
- **Quality**: timing anomalies and roster changes are caught structurally, not by eye; the THR
  gap is explained rather than mysterious.
- **UX**: one contextual `Разобрать` instead of free-typing; covered rows recede.
- **Trust**: the operator sees *why* a number is flagged (Δ, THR), and that the rest reconciled.

## 6. Verification + scenario

- `generate` byte-identical for runs without a prior month (no Δ to show) / no thr; LINT OK.
- Derive Δ proven on kirana: opening **May** shows Δ vs April per employee, the THR chips on
  bonus lines, the header `(−222 083 · THR)`, and `к проверке` = only the changed/THR lines.
- Scenario **S28**: role-play the operator opening the May run — the cockpit surfaces the
  exceptions, the `Разобрать` prompt is contextual, no RF reflex, operator-locale.

## 7. Open decisions

1. **Δ source** — prior **run** (payroll task masa−1) vs prior **ведомость**. Recommend the prior
   run (already in state, consistent unit).
2. **"to review" threshold** — what Δ counts as flag-worthy (e.g. |Δgross| ≥ 20% or ≥ 2M, any THR,
   any new). Start simple, tune.
3. **`thr` now or with #3** — split `thr` on the line now (enables the chip + the later THR-method
   fix) vs defer. Recommend now (additive, no migration).
4. **Header band placement** — top of the modal body vs in the Properties rail. Recommend top of
   body (it's the operator's first read).
