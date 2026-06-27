# Design note — per-employee payroll calculation, review & posting (task-centric)

Status: proposal (no code written). **Revision 2** — supersedes the earlier `payroll.runs[]` +
bespoke-review-surface draft. That version invented a parallel workflow; the system already has
one (tasks/tracks). This version models the payroll work as **tasks**, which is simpler in both
interface (one surface: the Plan + the track modal) and logic (one lifecycle: compute → review →
pay, reusing close-gates / `blocked_by` / waves / assist).

## 1. The realization

The earlier note conflated two things. **Work** (compute the May payroll, review it, pay by the
15th) is a *work item with a lifecycle* — that is a **task**, and the system already models it as
one. The **per-employee numbers** are *data the work item carries*. So we don't build a second
workflow; we attach the calculation to the existing payroll task and review it through the
existing task machinery.

Verified the machinery already exists:
- task types `payroll_pph21_bpjs`, `review_checkpoint`, `tax_pay`, `period_close` — all present.
- a real payroll task already carries `type_specific` (today just `period`).
- `type_specific` is **free-form** (the track modal renders it as a localized "Details" rail via
  `_TS_RU_LOC`, which already has keys like `breakdown`, `count`); no schema gate in `state_ops`.
- `blocked_by` is a real, lint-checked dependency (state_lint §K).

**Consequence: adding the calculation needs no new top-level schema and — because `type_specific`
is free-form — no migration.** It is additive payload the runtime writes, plus a render
extension and a reconciliation lint.

## 2. The model — one payroll task per masa, carrying the lines

```
task  payroll_pph21_bpjs   "Зарплата — май 2026"      (one per masa per client; already exists)
  type_specific:
    period: "2026-05"
    payroll_lines: [ {per-employee calc line}, ... ]   # NEW free-form payload
    totals: { pph, bpjs, net }                          # == financials.periods[2026-05].taxes
    review: { done: N, total: 14 }                      # roll-up for the modal header
  status: active → (reviewed) → done                    # operator close = the review gate
        │
        ├─ review_checkpoint  "Сверить расчёт — май"     (optional; the in-Plan review handle)
        │
        └─ blocks →  tax_pay  "PPh 21 + BPJS к уплате до 15.06"
                       blocked_by: [the payroll task]    # pay only AFTER review
                       → tax_calendar entry + payment_ref (migration 0018) on payment
```

A per-employee line (the calc the runtime writes; same fields as rev 1, now as task payload):

```
line = {
  employee_id,        # -> payroll.employees[].id (the roster row)
  gross, method,      # "ter" | "annualisasi" | "pph26"
  ptkp_category,      # "TK/0" … ; null for pph26
  ter_rate, pph,      # withheld income tax for the month
  bpjs: { kesehatan: {employee, employer}, ketenagakerjaan: {employee, employer} },
  net, source,        # "ведомость май 2026"
  parity_status,      # "pending" | "pass" | "fail" — same vocab as 0017
  parity_ref          # bukti potong id / incumbent line checked against
}
```

The **roster** (`payroll.json → employees[]`) stays the *standing-attributes* view; the **monthly
calculation** rides the *monthly task*. The annual **1721-A1 per employee** derives by summing
that employee's lines across the year's twelve payroll tasks — no separate store.

## 3. Lifecycle (all on existing task mechanics)

1. Runtime executes `payroll-pph21-bpjs.md`, computes each employee's figures, and **writes them
   into the payroll task's `type_specific.payroll_lines`** (via `state_ops`), with `totals` that
   must equal `financials.periods[masa].taxes`.
2. Review happens **in the track modal** (which already renders `type_specific`): each line shows
   gross → method → PPh → BPJS emp/empr → net with its parity chip. The operator confirms lines
   (sets `parity_status: pass`); an optional `review_checkpoint` task is the handle that surfaces
   this on the Plan.
3. **Closing the payroll task is the review gate** — the operator-close is already gated
   (`safety.approval_required: [track_close]`), so "the period can't settle until reviewed" needs
   no new gate: the dependent `tax_pay` is `blocked_by` the payroll task and simply can't proceed
   until it closes.
4. Pay → write the receipt into `tax_calendar` `payment_ref` (0018) → `tax_pay` done.

## 4. What this reuses (i.e. what we DON'T build)

The Plan/waves grouping, the track modal + its `type_specific` Details rail, `review_checkpoint`,
`tax_pay`, `blocked_by`, the operator-close gate, `assist` (the runtime's per-task hypothesis),
the parity vocabulary (`parity_status`/`parity_ref`), `payment_ref` (0018), and
`financials.periods.taxes` as the aggregate. **No `payroll.runs[]`, no new page, no new gate, no
migration.**

## 5. What is actually new (minimal)

- **Checklist extension** (`payroll-pph21-bpjs.md`) — the runtime writes per-employee
  `payroll_lines` onto the payroll task instead of only a total, and sets each line's parity
  before close. Pure markdown; no engine code.
- **Track-modal render** — the Details rail renders a `payroll_lines` array as a small table
  (employee · method · gross · PPh · BPJS · net · parity chip), reusing the roster pill styles.
  One key in the modal's renderer special-cased from key-value to table.
- **Reconciliation lint** — `state_lint`:
  - `sum(payroll_lines[].pph) == financials.periods[masa].taxes.pph21` (and BPJS roll-up);
  - completeness: every active roster employee has a line; every line → an existing `employee_id`;
  - coverage tie-in: a line whose employee `bpjs.kesehatan=="missing"` must carry no posted
    kesehatan contribution;
  - method tie-in (mirrors H3): `non_id` → `pph26`; resident salaried → `annualisasi`, not `ter`.
  Correctness of each figure is the **parity review's** job (operator vs the ведомость / bukti
  potong), not lint's — lint checks consistency only.

## 6. The boundary to hold

A task is a **work item with a lifecycle, not a ledger**:
- **One** payroll task per masa, **not 14** (one per employee). 14 calc-tasks would bloat the Plan
  and abuse status-as-data. The per-employee numbers are *payload*, reviewed *through* the one
  task.
- The numbers must still reconcile (Σ = period aggregate) and feed the 1721-A1 / report — that is
  structured data the task carries, which is why it lives in `type_specific.payroll_lines`, not in
  titles/statuses.

## 7. Render — the review surface is the track modal

Opening the May payroll task shows: the header (title, status, `blocked_by`/`blocks`, review
roll-up «отревьюено N/14»), then the Details rail with the **lines table** (per-employee row +
parity chip) and a footer total carrying a reconciliation badge («= период 2026-05 ✓» / ⚠
mismatch). The roster panel stays the standing-attributes view, with a "посмотреть расчёт за
<масу>" link to the task. No standalone page.

## 8. Verification plan

- `generate` byte-identical until the modal render lands (`payroll_lines` is inert payload);
  `state_lint` 0 errors; integrity ALL CLEAN.
- Reconciliation lint proven on a **seeded synthetic payroll task** (e.g. `kirana`): lines summing
  to the period aggregate → clean; perturb one → `payroll_reconcile` fires.
- Runtime scenario **S27**: "compute and review the May payroll for `id_demo`" — the runtime
  writes `payroll_lines` onto the payroll task, sets parity, the totals reconcile, the dependent
  `tax_pay` stays `blocked_by` until the payroll task closes, zero RF reflex, operator-locale +
  glossed.

## Linking — governed by the architecture note

Employee↔task and period↔task links use the **uniform `refs:[{type,id}]`** convention, and the
reverse views ("this employee's tasks / history / reports") are **derived, not stored** — per
`ENTITY-LINKING-ARCHITECTURE.md` (decided 2026-06-26). The employee **card** is a lazy derived
view to add later with zero migration; today the roster panel row + the payroll task carry it.

## 9. Open decisions

1. **Where the lines live** — `task.type_specific.payroll_lines[]` (fully task-native, no
   migration; recommended) vs a thin `payroll.json[masa]` record the task references (keeps the
   task lean; needs the slot). Both keep the *workflow* on tasks.
2. **Review grain** — per-line `parity_status` rolled up to the task close (recommended) vs a
   single `review_checkpoint` for the whole run.
3. **BPJS granularity** — `{employee, employer}` per kas (recommended) vs full JHT/JKK/JKM/JP split.
4. **Aggregate** — `financials.periods.taxes` *reconciled-to* the lines by lint (recommended,
   smaller) vs *derived-from* them on close (single source, larger change).
