# Checklist — foreign worker (TKA) compliance (Indonesia)

A foreign national on the payroll (`payroll.json → employees[].foreign_national: true`) triggers
a compliance domain **beyond** ordinary PPh 21 + BPJS payroll: a work permit, a residence
permit, a levy, a salary floor, mandatory BPJS, and a residency-driven tax method. Use this
checklist when onboarding a foreign worker, at any RPTKA/KITAS renewal, or when reviewing
whether an existing expat is fully compliant. Browser-driven on the relevant portals
(imigrasi, Kemnaker, BPJS, Coretax). **Statutory parameters below change — verify on the date.**

Record everything onto the worker's `payroll.json → employees[]` entry (the single source);
write only via `state_ops`, never by hand-editing JSON.

## A. Legal-to-work chain (the permits — settle these first)
- [ ] **RPTKA** — the approved plan/permit to employ the foreigner (Kemnaker). Note the
      approval date and validity (commonly 12 months).
- [ ] **IMTA / notifikasi** — the work permit issued under the RPTKA.
- [ ] **KITAS / e-ITAS** — the foreigner's limited-stay (residence) permit. Record the issue
      and **expiry** dates → `permit.kitas_expires` (and `permit.rptka_expires`).
- [ ] Without a valid RPTKA **and** KITAS the employment is not legal — this is the baseline.
      Everything below assumes the chain is in place.

## B. Levy + salary floor
- [ ] **DPKK / DKPTKA** — the foreign-worker compensation levy (~**USD 100 / employee / month**).
      Confirm it is being paid; set `permit.dpkk_paid`.
- [ ] **Expat salary floor.** Many KBLI sectors / regions expect roughly **IDR 25–30M / month**
      for a foreign worker. A salary below that is a **vulnerability at RPTKA renewal or on
      inspection** — flag it (raise a risk), and check the specific requirement for the
      client's KBLI and region; do not assume a single national number.

## C. Mandatory BPJS for a foreign worker
- [ ] A foreign worker employed **> 6 months**, or **within 30 days of KITAS issuance**, **MUST**
      be registered in **BOTH** `BPJS Kesehatan` and `BPJS Ketenagakerjaan`. Reconcile against
      the roster per `payroll-pph21-bpjs.md §D` and set `bpjs.kesehatan` / `bpjs.ketenagakerjaan`.
- [ ] A missing registration is a **UU 24/2011 violation** — and, critically, can trigger a
      **block on immigration services**, which stalls the very KITAS/RPTKA renewal in §A/§E.
      So BPJS for the foreign worker is not just a payroll line; it gates the permit.

## D. Tax — residency drives the method (the fork)
- [ ] Run the **183-day test** for the worker (days in Indonesia vs abroad over the calendar
      year) and record the outcome → `tax_residency`.
  - **Resident (`id`):** withhold **PPh 21** as a *pegawai tetap* — NPWP + PTKP, on the
    **annual progressive scale (annualisasi)**, **not** flat monthly TER. Flat TER-on-salary
    understates the tax and breaks incumbent parity; the worker's **1721-A1** uses annualisasi.
    Set `pph_method: "annualisasi"`.
  - **Non-resident (`non_id`):** withhold **PPh 26** — **20% flat, no PTKP**. Set
    `pph_method: "pph26"`. Do **not** run PPh 21 / PTKP / TER for a non-resident.
- [ ] The **1721-A1** (the annual PPh 21 withholding certificate) is the reference for the
      monthly withholding method and the year-end true-up.

## E. Renewal deadline — plan ahead, BPJS-first
- [ ] The RPTKA/KITAS validity is a **hard deadline**. Write a renewal entry into
      `financials.tax_calendar_<year>` a few months ahead (so it surfaces on the Plan / Calendar
      and `deadline_monitor` tracks it), using `permit.kitas_expires` / `permit.rptka_expires`.
- [ ] **Close any BPJS coverage gap (§C) BEFORE launching the renewal** — an immigration-services
      block can stall it. `state_lint` warns at 90 days (`permit_expiring`); treat that as the
      trigger to start, with the BPJS fix sequenced first.

## F. The worker's own home-country side — NOT the company's
- [ ] A foreign national may have **personal** duties in their home country (tax residency there,
      currency control, a personal income-tax return). That is the **employee's** zone, **not the
      company's books**. Flag it to the employee for their own advisor; never put it on the
      company's filings and never reflex the home country's tax system onto this Indonesian PT.

## Operator-facing language
Per `policies/INSTRUCTIONS.md §0.1`, write every operator task / calendar entry / message in the
operator's locale (Russian) and **gloss every Indonesian term** (TKA, RPTKA, IMTA, KITAS,
DPKK, PPh 21, PPh 26, BPJS, annualisasi, 1721-A1, …) with a plain explanation + an analogy from
the operator's own system. Source of glosses: `jurisdictions/id/glossary.md`. Native terms
unglossed are allowed only in prompts addressed to the runtime (`assist.actions[].prompt`).
