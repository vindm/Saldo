# Checklist — LKPM (investment activity report, OSS)

For an **investment-registered** company (PMDN/PMA). Filed in **OSS** (the online business-
licensing system) under the company **NIB**. **Cadence is scale-driven** (BKPM 5/2025 §285) —
resolve the client's `skala_usaha` first, never assume:

- **Usaha Kecil → per SEMESTER**: Semester I (Jan–Jun) due **15 July**; Semester II (Jul–Dec)
  due **15 January** of the next year.
- **Usaha Menengah / Besar → per QUARTER** (triwulan).

(FaceProtocol is Usaha Kecil → semester. The cadence is declared in
`jurisdictions/id/obligations.yaml` and derived per client — do not hand-key a fixed cadence.)

## Stage 1 — gather the period's realization
- [ ] **Investment realization** for the period — additional capex / fixed assets, from the books.
- [ ] **Employment** — headcount, Indonesian vs foreign workers (TKA).
- [ ] **Production / operational value** if applicable to the KBLI.
- [ ] **Even with NO new investment, an UMKM still must file** — submit a nil / no-change report,
      do not skip the period.

## Stage 2 — fill & submit in OSS
- [ ] Log in to OSS under the company **NIB**.
- [ ] Open **LKPM** for the correct period (the scale-correct semester/quarter), enter the realization.
- [ ] Submit.

## Stage 3 — capture the proof
- [ ] Capture the **receipt** (tanda terima / BPE) and **report number** (e.g. `LK…`) onto the
      matching `financials.json → tax_calendar_<year>[]` entry: `status: submitted`, `paid_at` =
      the receipt date, `payment_ref` = the report number. (The documents collector does this
      automatically when the receipt lands in Drive.)

## Watch — a scale change flips the cadence
- [ ] If the company grows past **Usaha Kecil**, LKPM becomes **quarterly**. The cadence is
      derived from `skala_usaha`, so keep that field current — the day the scale changes, the
      calendar (and the `obligation_cadence_mismatch` lint) follows.

## Safety
- **Prepare only.** Submitting in OSS / e-signing requires operator approval (browser deny-list).

## Operator-facing language

When you create or update the operator's tasks, calendar entries or messages from this checklist,
follow `policies/INSTRUCTIONS.md §0.1`: write them in the **operator's locale** and **gloss every
term** (LKPM, OSS, NIB, PMDN/PMA, realisasi, tanda terima/BPE, Usaha Kecil) with a plain
explanation + an analogy from the operator's own system. Source of glosses:
`jurisdictions/id/glossary.md`.
