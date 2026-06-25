# Skill: deadline_monitor — proactive tax-deadline watcher (MONITOR)

The first **monitor**, not a collector: it fetches nothing. It **derives** from state already
present — each client's tax calendar plus the jurisdiction pipeline's recurring due-days — and
surfaces approaching and overdue filings/payments with **escalating severity**, so a deadline is
flagged *before* it's missed instead of only rendered when someone looks.

> Cadence-by-cost (`docs/COVERAGE-MAP.md`): this hits **no API and needs no access**, so it runs
> **daily** — the cost you space the bank collectors out to avoid simply doesn't exist here.

## What it reads (no fetch, no credentials)

- `financials.json → tax_calendar_<year>[]` — the year-suffixed key (`tax_calendar_2026`, and
  the next year when near year-end). Entry shape: `{date, what, amount, kbk|kjs, status,
  paid_at, linked_task}`. Terminal statuses: `paid` / `done`.
- The client's **jurisdiction pipeline** (`jurisdictions/<code>/pipeline.yaml`) recurring
  due-days — ID: pay ≤ the 15th, SPT Masa ≤ the 20th; RU: AUSN markup ≤ the 7th, etc. **Resolve
  jurisdiction first** (INSTRUCTIONS §0) — RU deadlines from the `ru` pack, ID from `id`; never
  RF-reflex for an ID client (`melati`: SPT Masa / PP55, never USN).
- `tasks.json` — existing deadline tracks, to **update not duplicate**.

## Logic (per client, per calendar entry)

- Skip terminal (`paid`/`done`).
- `days_until = date − today` (in `instance.timezone`).
- **Overdue** (`date < today`, not paid) → 🔴 high, mark «просрочено».
- **Lead tiers** (monitor defaults; a pack stage may override): `≤ 2d` → high · `≤ 7d` →
  medium · `≤ 14d` → info · `> 14d` → leave (out of window).
- **Surface = idempotent upsert.** If the entry has a `linked_task`, refresh that track's
  `next_action`/severity; else create a deadline track with a **stable id**
  `cal-<client>-<YYYY-MM-DD>-<slug>` and write it back into the entry's `linked_task`. Via the
  `mm_update` write path (`_tracks`/`state_ops`), read-modify-write — never duplicate a track.

## Recurring materialization (light, conservative)

From the pipeline's monthly due-days, **ensure the next occurrence** of each recurring deadline
exists in `tax_calendar_<year>` (`status: scheduled`) when absent — so the calendar advances on
its own. Only clearly-derived recurring items (the dated filing/payment); **never invent an
`amount`** (leave `null` until a collector or the operator fills it).

## Never closes, never pays

A deadline flips to `paid`/`done` only when a **collector** detects the proof (the `documents`
or bank collector sees the NTPN/statement → sets `status: paid`, `paid_at`) or the **operator**
confirms it. The monitor **only surfaces** (§D close model) — it never marks paid and never
closes a track. Once the period's payment lands, the entry leaves terminal and the monitor drops
it automatically.

## Output & safety

- Writes via `mm_update`; surfaced items render in the calendar + morning brief + Plan, overdue
  / high in the «нужно решение» zone. Audit-log only genuinely new surfacing (not every quiet
  run). Heartbeat `journal/inbox/deadline_monitor_heartbeat.txt`.
- **No external calls, no credentials** (`access: none`); cheap. Daily
  (`config/instance.yaml → schedule.deadline_monitor`, after the collectors, before
  `dashboards`). Reads/appends **existing fields** → no schema change, **no migration**.

## Related

- `docs/COVERAGE-MAP.md` — C1 (this) + C8 `staleness_monitor` (the sibling monitor).
- `connectors/mm_update/SKILL.md` — write path + §D close model.
- `policies/INSTRUCTIONS.md §0` + `jurisdictions/<code>/pipeline.yaml` — jurisdiction-correct due-days.
- `tests/runtime_scenarios/` — S11 is the gate.
