# Design note — surfacing the payroll roster + BPJS/permit compliance in the dashboard

Status: **LANDED 2026-06-26** (kept as the design record). Scope: render-layer integration for the
per-employee roster (`payroll.json`, migration 0019) and its compliance signals (BPJS coverage,
foreign-worker permit expiry). Companion to the foreign-worker work in `jurisdictions/id/`
(roster slot, `payroll-pph21-bpjs.md §D`, `foreign-worker-tka.md`, `foreign-worker-risk-review.md`).

## 1. The gap this closes

Saldo's contract is: **state is the source of truth; the dashboard is a pure derivation of it.**
Migration 0019 added a new source of truth — `payroll.json → employees[]`. **Now landed:** `render_client_payroll_roster` (`engine/_client_dashboard_v2.py`) derives the roster card + BPJS/permit signals from it. The gap below describes the pre-landing state:

- The operator **cannot see** the roster: who is on staff, each person's BPJS status per kas,
  residency, PPh method, or permit countdown.
- The invariants that guard it (`bpjs_coverage_gap`, `tka_bpjs_unverified`, `permit_expiring`)
  are **dev-facing only** — they go to the `state_lint` CLI gate / `_LINT.json`, never to Mom's
  screen. So the #1 live risk (a worker missing from a BPJS billing) reaches the operator **only
  if the runtime authors a `risks.json` entry**; it is not derived automatically from the roster.

The risk-review's *other* outputs already render — risks via the Risks panel
(`render_client_risks`, with `⚖ linked_law`), permit-renewal deadlines via the tax calendar
(`render_client_financials`). The missing surface is specifically the **roster and its derived
health**.

## 2. The real state shape (use these fields — not `tk/jp/jk/jht`)

`payroll.json` (migration 0019). Per employee:

```
employees[] = {
  id, name,
  foreign_national: bool|null,
  tax_residency:    "id" | "non_id" | null,
  pph_method:       "ter" | "annualisasi" | "pph26" | null,
  bpjs: { kesehatan:       "active"|"missing"|"exempt"|null,
          ketenagakerjaan: "active"|"missing"|"exempt"|null },
  permit: { kitas_expires: ISO|null, rptka_expires: ISO|null, dpkk_paid: bool|null }
}
```

Two BPJS kasses only — `kesehatan` + `ketenagakerjaan`. (`JHT/JKK/JKM/JP` are components *of*
Ketenagakerjaan, not separate roster fields.)

## 3. The three enhancements

### 3.1 Roster panel — `render_client_payroll_roster(payroll)` (priority 1)

A new client-cockpit panel, one row per employee. Model it on `render_client_real_estate`
(`_client_dashboard_v2.py:1149`) — same table-in-a-section shape.

Columns: **Employee** (name; a small chip if `foreign_national`) · **BPJS** (two status pills,
Kesehatan / Ketenagakerjaan) · **Tax / method** (residency → PPh method) · **Permit** (nearest
of kitas/rptka expiry with a days-until countdown; DPKK paid/unknown).

BPJS pill states (semantic tokens, never repurposed):

| value | pill |
|---|---|
| `active` | green (`--accent-green`) |
| `exempt` | neutral/grey |
| `missing` | red (`--accent-red`) — the violation state |
| `null` | yellow (`--accent-yellow`) "не подтверждено" — unverified, not yet a violation |

Method cell: `non_id` + not `pph26` → red hint (a non-resident must be PPh 26); resident +
`ter` for a salaried *pegawai tetap* → yellow hint (should be `annualisasi`). These mirror the
`state_lint` H3 codes so the panel and the lint agree.

Hooks:
- Define `render_client_payroll_roster(payroll)` near the other panel renderers.
- Load it beside the existing `_html` loads (~`_client_dashboard_v2.py:1840`): read
  `payroll.json`; `payroll_html = render_client_payroll_roster(_p)` when `employees` is non-empty,
  else `''` (a non-payroll client shows nothing — additive).
- Insert `+ payroll_html` into the final concat (~line 1937), **after `financials_html`** (it
  belongs to the financial/period zone) — or directly after `risks_html` if we want the roster
  adjacent to the risks it drives. Placement is an open decision (§7).
- Add a small `ROSTER_CSS` block to the `<style>` concat (~line 1931), alongside `KPI_ROW_CSS`.

### 3.2 Roster-derived health — extend `calculate_health` (priority 1)

This is the bridge that puts the lint invariant in front of the operator **without** depending
on the runtime authoring a risk. `calculate_health(client, …)` (`_health.py:29`) already reads
state via `state_ops.state_read(cid, …)` and builds `red`/`yellow` reason lists. Add a roster
read:

- any employee `bpjs.kesehatan=="missing"` or `ketenagakerjaan=="missing"` → **red** reason
  ("BPJS не оформлен: <employee>").
- a foreign worker with a permit **expired** → red; **within the 90-day window** (matching
  `lint.yaml → permit_expiry_warn_days`) → **yellow**.

Effect: the client's avatar ring (`_client_dashboard_v2.py:1788`) and the overview-grid bar go
red/yellow automatically, so the gap is visible on the cross-client overview, not only inside the
client page. Keep the window constant sourced from the pack (`permit_expiry_warn_days`) so render
and lint never drift.

### 3.3 Permit-expiry countdown chip (priority 2)

The roster panel (3.1) carries the per-employee countdown. Add the **nearest** one as a chip in
the hero/KPI band — natural home is the existing "Headcount / net payroll" KPI card
(`render_kpi_row`, the headcount branch ~`_client_dashboard_v2.py:1578`): «до продления KITAS:
NN дн.», red if expired, yellow within the window, hidden otherwise. When the runtime writes the
renewal into `tax_calendar`, `render_client_financials` already renders it; the only add there is
a days-until affordance on the row (the calendar already colours past vs future).

## 4. What NOT to build (kept deliberately out)

No heavy rendered view of the full §A–H risk-review **memo**. Its actionable findings already
surface through Risks + the calendar; the full narrative is better produced as a generated
document on demand. Rendering the prose would duplicate state into the view and bloat the
derived layer — against "the markdown is the program; the dashboard is a thin derivation."

## 5. Taste & design-system constraints (`docs/DESIGN-SYSTEM.md`)

- **Semantic colours are fixed:** `--accent-red` overdue/violation, `--accent-yellow`
  due-soon/unverified/blocked, `--accent-green` good. The dashboard **accent** is indigo
  `#5E6AD2`; navy `#1F4E79` / gold `#B79257` are the *client brand* (one-pager), not panel chrome.
- **No boxy.** Reuse the existing card/section pattern (`--radius-card`, soft shadow, lavender
  `--accent-soft` for any expand), pills not heavy borders, the established chip style. The roster
  is a table-in-a-section like real-estate/accounts, not a new visual language.
- **One avatar / one component.** Reuse `client_avatar()`, the `.an-*` row snippets, and the
  pill/chip classes already in the CSS — do not introduce parallel styles.
- **i18n.** Every new static label goes through `t()` (`from _strings import t`) with a Russian
  entry added to `_strings.py` UI['ru'] — e.g. `Payroll roster → Реестр сотрудников`,
  `BPJS coverage → Покрытие BPJS`, `Permit → Разрешение/виза`, `Residency → Резидентство`.
  Indonesian tax terms (PPh 21, BPJS, KITAS, RPTKA, annualisasi) auto-wrap as glossary `<abbr>`
  tooltips from `jurisdictions/id/glossary.md` (already populated) — do not hand-translate them.

## 6. Verification plan

- `generate.py` → **OK per page + LINT OK**; `state_lint` 0 errors; `system_integrity_check`
  ALL CLEAN (the established gates).
- **Behaviour-preserving for non-roster clients:** byte-diff the dashboards of every client
  *without* a `payroll.json` before/after — must be identical (the panel is additive, gated on a
  non-empty roster). The roster client's page is the only intended diff.
- `ABA_LOCALE=ru` render → no English leaks in the new panel/labels.
- **Demo data:** the example client `kirana` has `has_employees:true` but an empty roster, so the
  panel won't show until it has employees. To demo the panel (and the red BPJS state), `kirana`'s
  roster needs a synthetic populated `employees[]` (synthetic only — Boundary #1). That seeding is
  a demo-fixture decision, separate from this render change.
- **Invariant-0:** a scenario confirming the operator, looking at the rendered page, can *see* the
  BPJS gap and the permit countdown — the view now reflects the state the runtime reasons over.

## 7. Open design decisions (resolve before coding)

1. **Panel placement** — after `financials_html` (period/financial zone) vs right after
   `risks_html` (adjacent to the risks it drives). Leaning: after financials.
2. **BPJS `missing` → red vs yellow health.** It is a legal violation (red by the letter), but a
   brand-new client mid-onboarding may transiently show `missing`. Proposal: **red**, matching the
   `state_lint` severity, and rely on the runtime resolving onboarding quickly. Revisit if it
   creates avatar-ring noise.
3. **Demo fixture** — whether to populate `kirana`'s roster (synthetic) in this change so the panel
   is visible in the bundled demo, or keep that separate.
4. **Counts in KPI** — the headcount KPI reads `identity.headcount_payroll`; once the roster
   exists, should headcount derive from `len(employees)` instead (single source)? Possible later
   consolidation, not required now.
