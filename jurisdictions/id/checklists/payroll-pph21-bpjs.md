# Checklist — payroll: PPh 21 + BPJS (Indonesia)

Monthly employee taxes and social contributions for a PT with staff. Figures below are the
**current statutory parameters** (verify against DJP/BPJS before relying — rates change).

## A. PPh 21 — employee income tax (we COMPUTE it; data in `ter.yaml`)
Compute from the gross on the payroll sheet using the pack's `jurisdictions/id/ter.yaml`
(TER tables + PTKP + annual scale, sourced from PP 58/2023 + PMK 168/2023 — **verify on date**):

- [ ] For each employee take **gross** monthly remuneration (basic + extra hours + bonuses)
      from the payroll sheet, and the employee's **PTKP status** from the roster
      (`payroll.json → employees[].ptkp_category`, e.g. `TK/0`). If PTKP is unknown, surface it
      — do **not** assume; most single staff are `TK/0`.
- [ ] **Resident, Masa Jan–Nov = monthly TER.** Resolve the TER category from PTKP
      (`ter.ptkp.ter_category`: TK/0/TK/1/K/0→A, …, K/3→C), then take the **first
      `ter_monthly[<cat>]` bracket whose `up_to` ≥ gross** and apply its `rate`:
      `pph = round(gross × rate)`. Gross ≤ the category's 0% band (A 5.4M / B 6.2M / C 6.6M)
      → `pph = 0` (most therapists on 2–5M land here).
- [ ] **December / final masa = annual true-up** (`ter.annual_scale`): annual PKP =
      annual_gross − biaya_jabatan (5%, cap 6,000,000/yr) − annual PTKP; PPh21_year = the
      progressive `brackets`; December withholding = PPh21_year − Σ(Jan–Nov monthly TER).
- [ ] **Non-resident** (`tax_residency=non_id`): not TER — **PPh 26 flat 20%** of gross
      (`ter.pph26`), no PTKP. **Salaried resident *pegawai tetap*** uses the same TER/annual
      mechanism (this IS "annualisasi"); never flat-TER a non-resident.
- [ ] Sum computed PPh 21 across employees → the month's PPh 21. KAP-KJS **411121-100**.
      Pay by the **15th**; SPT Masa PPh 21 by the **20th**.

## B. BPJS Kesehatan (health) — portal EDABU
- [ ] **5%** of wage (cap wage 12,000,000; floor = local UMK/UMP): **4% employer + 1% employee**.
- [ ] Pay the monthly billing; first billing unlocks EDABU access.

## C. BPJS Ketenagakerjaan (employment) — portal EPS / virtual account
- [ ] **JHT** 5.7% (3.7% employer + 2% employee).
- [ ] **JKK** (work accident) 0.24%–1.74% by risk class — employer.
- [ ] **JKM** (death) 0.3% — employer.
- [ ] **JP** (pension) 3% (2% employer + 1% employee), wage cap applies.
- [ ] **JKP** (job loss) — funded by government / recomposition, no extra employer cost.
- [ ] Pay the monthly contribution (kode iuran / virtual account).

## D. Roster reconciliation — every employee, every kas (state/payroll.json)
The month's BPJS billing is only correct if **everyone who should be covered is in it**. The
per-employee roster lives in `state/payroll.json → employees[]` (slot from migration 0019);
keep it the single source of who is on staff, and reconcile the billing against it.

- [ ] **Ensure the roster exists first.** This client runs payroll, so `regime.has_employees`
      must be `true` and `payroll.json` must exist. Migration 0019 auto-opens the slot for
      clients already flagged, but a client migrated **before** that flag existed (or onboarded
      without it) may have neither — if so, set `regime.has_employees=true` and create the
      roster, **only via `state_ops`** (backup + atomic + UTF-8), never by hand-editing JSON.
      Register one `employees[]` entry per person on the payroll sheet (stable `id`, `name`).
- [ ] For each `employees[]` entry, confirm both kasses: set `bpjs.kesehatan` and
      `bpjs.ketenagakerjaan` to `active` / `missing` / `exempt`. A worker **in the payroll
      sheet but absent from a BPJS billing** is `missing` — that is a UU 24/2011 violation and
      a priority risk, not a rounding note. (`state_lint` flags it as `bpjs_coverage_gap`.)
- [ ] **Foreign worker (`foreign_national: true`).** A KITAS-holder must be in **both** kasses
      within 30 days / 6 months of the permit. Record:
      - `tax_residency` — outcome of the 183-day test. **`id`** → withhold **PPh 21** as a
        resident (NPWP, PTKP, annual progression). **`non_id`** → withhold **PPh 26** (20%
        flat, no PTKP); set `pph_method: "pph26"`. Do not flat-TER a non-resident.
      - `pph_method` — `annualisasi` for a *pegawai tetap* whose 1721-A1 uses annual
        progression (the correct basis for a salaried expat — flat TER-on-salary understates
        the tax and breaks incumbent parity); `ter` for simple monthly TER.
      - `permit.kitas_expires` / `permit.rptka_expires` / `permit.dpkk_paid` — `state_lint`
        warns at 90 days (`permit_expiring`); plan the RPTKA/KITAS renewal and close any BPJS
        gap **before** launching it (an immigration-services block can stall the renewal).

## E. Record the monthly run on the payroll task (per-employee lines)
The month's payroll is **one task** (`payroll_pph21_bpjs`) per masa; the per-employee calculation
is its payload (see `docs/PAYROLL-CALCULATION-REVIEW-PROPOSAL.md` + `docs/ENTITY-LINKING-ARCHITECTURE.md`).
On that task, via `state_ops` (never hand-edit JSON).

> **Input vs parity reference — keep them separate.** The **client** supplies only the **payroll
> sheet** (the ведомость: gross per employee, days, extra hours, net) — that is our **single input**.
> We **compute PPh 21 and BPJS ourselves** from gross (TER by PTKP / annualisasi for a salaried
> *pegawai tetap* + December true-up; BPJS at the §A–C rates). The **incumbent accountant's** filings
> (e.g. the incumbent's `SPT PPh 21`, `bukti potong`, BPJS billing) are the **parity reference** (`parity_ref`)
> — we **check against them, never copy them**. `parity_status: pass` when our computed figure matches
> the incumbent's; `fail` is a real finding to investigate (e.g. the incumbent withheld a salaried
> resident on flat TER where annualisasi applies — our number is higher, theirs is understated).
> While shadowing the incumbent this parity is mandatory; after cutover it becomes self-review and
> **we** file. Do not treat the incumbent's PDFs as the source of the numbers.

- [ ] Write `type_specific.payroll_lines[]` — one line per employee:
      `{employee_id, gross, method, ptkp_category, ter_rate, pph, bpjs:{kesehatan:{employee,employer},
      ketenagakerjaan:{employee,employer}}, net, source, parity_status, parity_ref}`. `method`
      comes from the roster — a non-resident is `pph26`, a salaried *pegawai tetap* `annualisasi`,
      else `ter` (§A/§D).
- [ ] Set `type_specific.totals = {pph, bpjs, net}` and keep `financials.periods[<masa>].taxes`
      in step: **`sum(payroll_lines[].pph)` MUST equal `taxes.pph21`** (the engine reconciles this —
      `payroll_reconcile`).
- [ ] Link with `type_specific.refs`: `{type:"period", id:"<masa>"}`, plus `{type:"employee",
      id:…}` on any follow-up task that targets a specific person. **Do not** store a reverse
      task-list on the employee — "this employee's tasks" is **derived** (entity-linking architecture).
- [ ] Review: set each line's `parity_status` (`pending`→`pass`) by checking **our computed PPh/BPJS**
      against the **incumbent's** `SPT PPh 21` / `bukti potong` / BPJS billing (`parity_ref` = that
      document's id). A mismatch is `fail` — surface it, don't silently adopt either number. **Closing
      the payroll task is the review gate**; the dependent `tax_pay` is `blocked_by` it and only
      proceeds after close → pay → `payment_ref`.

## Notes
- Employer-borne BPJS Kesehatan (the 4%) is itself part of the PPh 21 gross-up base — keep
  the payroll calc consistent with how the incumbent accountant books it (parity check).
- New hires/leavers: update the roster (`payroll.json`) before billing, or the amount drifts.
- The RF / foreign side of a foreign-national employee (their own tax residency, currency
  control, 3-НДФЛ) is the **employee's personal zone, not the company's** — the bookkeeper
  does not file it. Flag it to the employee; do not RF-reflex the company's Indonesian books.
