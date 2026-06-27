# Checklist — foreign-worker risk review (Indonesia + home country)

A repeatable procedure to produce a **structured risk analysis for a foreign worker** on an
Indonesian client's payroll — the kind of cross-border review that spans the host jurisdiction
(Indonesia) and the worker's home country. Run it on onboarding a foreign worker, ahead of an
RPTKA/KITAS renewal, or when the operator asks "is this person fully in order?". The output is
(a) an **operator-facing memo** structured by the sections below, and (b) **structured findings
written into state** — risks into `risks.json`, roster fields into `payroll.json`, and the
renewal deadline into `financials.tax_calendar_<year>` — all via `state_ops`.

This is an **internal operator/advisory** deliverable, not the client one-pager — it never
writes `regime.client_facing`. It is a working risk assessment for orientation, **not** formal
legal or tax advice: state that, and verify every rate/threshold/status **on the date** (they
change). For border cases the operator escalates to a local tax/immigration consultant (host
side) and a home-country tax adviser (home side).

## A. Gather the facts (read state + the client's documents — do not invent)
- [ ] From `payroll.json → employees[<id>]`: `foreign_national`, `tax_residency`, `pph_method`,
      `bpjs.{kesehatan,ketenagakerjaan}`, `permit.{kitas_expires,rptka_expires,dpkk_paid}`.
- [ ] From `identity.json` / the client's documents: the worker's role, work location, salary,
      NPWP, the annual `1721-A1` (the PPh 21 certificate that shows the method actually used),
      and any RPTKA/KITAS scans. Record what is **confirmed by a document** vs **assumed**.
- [ ] Note what you do **not** yet have — it drives §G (open questions). Never fill a gap with a
      guess; an unknown is an open question, not a fact.

## B. The pivot — tax residency (two independent tests)
- [ ] Residency decides everything downstream, and the **host** and **home** 183-day tests are
      **independent** — a worker can be a tax resident of Indonesia and simultaneously not a
      resident of their home country (or both, or neither). Establish, for each calendar year in
      scope, where the worker spent ≥183 days. Set `tax_residency` (`id` / `non_id`) from the
      **host** test; the home-side test belongs to §E (the employee's own zone).

## C. Host-jurisdiction (Indonesia) risks  → most go into `risks.json`
- [ ] **BPJS coverage** (usually the top live risk). A KITAS-holder must be in **both** kasses
      (`foreign-worker-tka.md §C`). A `missing`/unrecorded kas is a **UU 24/2011** violation →
      `risks.json` entry, `severity: red`, `kind: risk`, `category: compliance`, with a
      `next_action` to register before the next billing. Note the **second-order** risk: a BPJS
      gap can block immigration services and **stall the RPTKA/KITAS renewal**.
- [ ] **Work permit + salary floor** (`foreign-worker-tka.md §A/§B`). Confirm RPTKA/IMTA/KITAS
      valid; flag a salary below the ~25–30M expat floor as a **renewal vulnerability**
      (`severity: yellow`), checking the KBLI/region requirement rather than assuming a number.
- [ ] **DPKK levy** unconfirmed (`permit.dpkk_paid` null) → open question or `yellow` risk.
- [ ] **PPh 21 method** (`foreign-worker-tka.md §D`). A salaried *pegawai tetap* must be on
      **annualisasi**, not flat TER (flat TER understates → an accuracy risk and a parity break).
      A **non-resident** is **PPh 26** (20% flat), not PPh 21 — a method/residency mismatch is a
      `red` accuracy risk.

## D. "Not in the reports" — distinguish which report
- [ ] The phrase "the worker isn't in the reports" is ambiguous and the situations are often
      **opposite**, so separate them:
  - **Tax reports** (PPh 21, SPT Masa, `1721-A1`): if a taxed employee is omitted, the company
    as withholding agent owes the unwithheld PPh 21 + penalties (KUP). Usually the worker **is**
    here — confirm and move on.
  - **BPJS**: this is where a foreign worker is typically **missing** — see §C. The criminal
    track (UU 24/2011 art. 55) is for **withholding contributions and not remitting them**, not
    for simple non-registration (which is the administrative track) — do not overstate it.

## E. Home-country side — the employee's own zone, NOT the company's
- [ ] A foreign national has **personal** duties in their home country that depend on the home
      183-day test: personal tax residency, any **double-taxation treaty** relief between the
      two countries, **currency-control / foreign-account reporting**, and a **personal
      income-tax return** on worldwide income if they are a home-country resident. These are the
      **employee's** responsibility, not the company's books.
- [ ] The bookkeeper does **not** file these and does **not** put them on the Indonesian PT's
      records. Produce a short **note flagging them to the employee** (for their own adviser),
      and **never reflex the home country's tax system onto the company's Indonesian filings**.
  > Common case — a **Russian-national** worker: the typical home-side items are СИДН
  > (double-tax treaty) relief, the foreign-account notification + ОДДС under currency control
  > (with the >183-days-abroad exemption), and a personal 3-НДФЛ if they become an RF resident.
  > Treat these as the *instance* of the generic categories above, verified on the date — not as
  > a company obligation, and not as a template for non-RF workers.

## F. What it means for the books / Saldo
- [ ] Translate the findings into state via `state_ops`: write/refresh the `risks.json` entries
      (stable `R-<client>-<slug>` ids, correct `severity`/`kind`), correct the roster fields
      (`pph_method`, `tax_residency`, `bpjs.*`), and write the RPTKA/KITAS **renewal deadline**
      into `financials.tax_calendar_<year>` ahead of expiry (so `deadline_monitor` tracks it),
      sequenced **BPJS-first**. Priority order matches the host risks: BPJS → permit/salary →
      method accuracy.

## G. Open questions to close the analysis
- [ ] List exactly what would make the assessment definitive — e.g. actual days in each country
      per year (residency), the precise KITAS issue/expiry, why a worker is absent from a BPJS
      billing, whether DPKK is paid, and whether the worker intends to remain a host-jurisdiction
      tax resident (often the cleanest scenario — then there are no home-side income duties).
      Each becomes an `open_question` task (or a `risks.json` `kind: question`), not a guess.

## H. Disclaimer (carry it on the memo)
- [ ] State on the output: a working risk assessment for orientation, **not** official legal/tax
      advice; rates/thresholds/statuses (residency, treaty list, expat requirements, BPJS
      sanctions) to be verified on the date of action; border questions go to a local
      *konsultan pajak* / immigration lawyer (host) and a home-country tax adviser (home).

## Operator-facing language
Per `policies/INSTRUCTIONS.md §0.1`, the memo and every `risks.json` title/description/next_action
are written in the operator's locale (Russian) with each Indonesian term glossed from
`jurisdictions/id/glossary.md`. Native terms unglossed only in runtime prompts
(`assist.actions[].prompt`).
