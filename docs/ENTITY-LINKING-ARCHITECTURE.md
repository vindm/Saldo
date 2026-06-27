# Entity & linking architecture

Status: **decided 2026-06-26.** Governing note — applies to every domain entity (employee, risk,
deadline, counterparty, account, real-estate object, period …), not just payroll. The payroll
calculation layer (`PAYROLL-CALCULATION-REVIEW-PROPOSAL.md`) is the first consumer.

## The pattern

Saldo already has one recurring shape: **tasks are the hub; domain entities are spokes that link
to tasks.** A risk carries `linked_tasks`; a `tax_calendar` entry carries `linked_task`; a task's
`type_specific` carries `counterparty_id`. An employee is simply the next spoke.

The decision is to make this **one mechanism, not N bespoke ones.**

## Principle — link owned by the task; everything reverse is derived

> The link's single source of truth lives on the **task**. "Entity X's tasks", its timeline, its
> reports, and its card are **derived by filtering** — never stored as a second copy.

This is the engine's existing law ("the dashboard is a pure derivation of state") extended from
*values* to *relationships*. Storing reverse links (an entity's own `linked_tasks`) creates two
sources of truth that drift — which is exactly why a `risk_link` lint already exists to catch it.
A derivation cannot drift, needs no sync, and needs no extra lint.

## The uniform reference (DECIDED)

A task declares what it concerns via **one** field in `type_specific`:

```
type_specific.refs: [ { type: "employee",     id: "emp_expat" },
                      { type: "period",       id: "2026-05"   } ]
```

- `type` ∈ a small open vocabulary: `employee | counterparty | risk | deadline | account |
  real_estate | period | …`. `id` is the entity's id **within its client's domain file**
  (everything is client-scoped, so the client is implicit — the file owner).
- A list, because one task can concern several entities (a withholding task → a counterparty +
  a period; a payroll review → the period; a "register BPJS" task → an employee).
- This is the **forward standard**. Existing bespoke keys (`counterparty_id`, `period`,
  `linked_task[s]`) are **not** ripped out — they keep working; `refs` is what new links use, and
  the two can be converged later by a lint/migration **only if it pays off**. No big-bang refactor.

History events may carry the same `refs` (additive to `history.jsonl`); a per-entity timeline is
the subset of events whose `refs` include that entity. Old event lines without `refs` simply don't
appear in a sub-timeline — graceful.

## Derivations (the only way to read the reverse direction)

- `tasks_for(entity)` = tasks whose `refs` include `{type, id}`. One generic function, every entity
  type for free.
- `history_for(entity)` = `history.jsonl` events whose `refs` include the entity.
- `reports_for(employee)` = the per-employee payroll lines across the year's monthly payroll tasks
  (keyed by `employee_id`); annual 1721-A1 = their sum. (Per the payroll note, lines ride the
  monthly task — no per-employee report store.)

## Cards are lazy derived views

A richer per-entity surface — the **employee card** (statuses + linked tasks + history + monthly
reports), like the client card — is a render over the entity's attribute record + the three
derivations above. Because the link is uniform, **a card can be added at any time with zero data
migration.** So: a row in the roster panel suffices today; build the card only when accumulation
justifies it ("если инфы много копится"). You never pay for it until you need it.

## The discipline (the one trap to avoid)

**No entity gets its own stores** — no per-employee task list, no per-employee `history.jsonl`, no
per-employee reports store. The moment relationships are denormalized per entity, you get
O(entities) machinery and drift. Hub (tasks) + derivation keeps it O(entities) *records* and O(1)
*mechanisms*.

## Lint

Generalize the existing `risk_link` check into one rule: **every `refs[].id` must resolve to an
existing entity of its `type`** in the client's state. That single check covers employees, periods,
counterparties, and any future type — no per-type lint.

## Why this is simple / scalable / maintainable

- **Simple** — two primitives: a lightweight entity record + a uniform task ref. No new workflow,
  no per-entity stores.
- **Scalable** — a new entity type ("contract", "asset", …) is a record + the same `refs`. Its
  card, task list, and timeline come free as derivations. N types cost O(N) *records*, not O(N)
  *machinery*.
- **Maintainable** — one link mechanism (single source of truth on the task), one history stream,
  one card pattern, one lint. Fewer moving parts, nothing to keep in sync. And it suits the
  AI runtime: **one predictable reference shape** to read and write, instead of a special case per
  entity type.

## Application to payroll / employees (the first consumer)

- `payroll.employees[]` stays the lightweight roster (attributes/statuses).
- The monthly payroll task carries the per-employee calc lines (each with `employee_id`) and
  `refs:[{type:"period", id:<masa>}]`; a task that concerns a specific employee (register BPJS,
  renew KITAS, review a line) adds `{type:"employee", id:…}` to `refs`.
- "This employee's open tasks / history / monthly reports" are derivations. The employee **card**
  is built later, when it earns its place — no migration required to add it.

## Open decisions resolved / remaining

- **#1 uniform `refs` vs per-type keys** → **RESOLVED: uniform `refs`.**
- **#2 derive reverse links vs store `linked_tasks`** → **default: derive** (no drift). Existing
  risk/calendar stored links stay as-is; new entities derive. (Flip only if a perf need appears —
  none expected at this scale.)

## Next steps (when moving design → build)

1. Adopt `refs` in the task writer paths + a generic `tasks_for(id)` derivation.
2. Generalize `risk_link` → a `ref_resolves` lint.
3. Apply to the payroll task (period + employee refs); keep the calc lines on the monthly task.
4. Scenario coverage: extend S27 to assert employee↔task links are by `refs` and the reverse views
   are derived (no stored back-refs).
