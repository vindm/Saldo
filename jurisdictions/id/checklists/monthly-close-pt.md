# Checklist — monthly close for a UMKM-final PT with employees (Indonesia)

For a **badan (PT)** on the UMKM final regime (PP55/PP23, PPh final **0.5%** of gross
turnover) that **runs payroll**. This is the master monthly checklist; it fans out to the
payroll and withholding checklists. Everything is browser-driven on **Coretax** under the
**company's** 16-digit NPWP. Currency IDR.

> badan, not orang pribadi: the 0.5% applies to the **whole** monthly turnover — there is
> **no** IDR 500M annual relief (that is OP-only). Annual return is **SPT Tahunan Badan,
> due 30 April** (not 31 March).

## Stage 1 — collect the month's inputs
- [ ] **POS / sales report** (e.g. Moka) → gross turnover (peredaran bruto) for the month.
- [ ] **Cash report** → reconcile cash takings against the POS cash line. **Flag any
      discrepancy** (a recurring failure mode: POS vs cash mismatch) and resolve before
      computing tax — turnover must be complete.
- [ ] **Bank statement** (primary account) → cross-check inflows.
- [ ] **Expense documents** (rent invoice, supplier invoices, operational receipts).
- [ ] **Payroll sheet** for the month (headcount, gross per employee).
- [ ] **Record to state** (`financials.json → periods[<masa>]`): set `turnover_idr` and its
      provenance — `turnover_source` (e.g. `"moka+cash"` / `"bank+moka+cash"`) and
      `cash_reconciled` (`true` once the Moka takings tie to the cash report within tolerance;
      `false`/`null` **blocks the tax compute** — turnover must be complete). This period entry
      is the **single source** the 0.5% calc reads — never re-derive turnover from the
      spreadsheet downstream. (Slots from migration `0017_period_parity_turnover`.)

## Stage 2 — compute each monthly tax (masa = this month)
- [ ] **PP55 — UMKM final 0.5%.** `0.5% × gross turnover`. KAP-KJS **411128-420**.
      If turnover = 0 → no PP55 this month (note, skip).
- [ ] **PPh 21 — payroll withholding.** → `payroll_pph21_bpjs` checklist. KAP-KJS **411121-100**.
- [ ] **Unifikasi — withholding.** → `unifikasi_withholding` checklist:
      PPh 4(2) final on rent (10%, KAP-KJS **411128-403**) + PPh 23 on services
      (KAP-KJS **411124-100**), combined into one unifikasi billing.
- [ ] **BPJS Kesehatan** and **BPJS Ketenagakerjaan** → `payroll_pph21_bpjs` checklist
      (separate portals, not Coretax billing).

## Stage 3 — billing + pay (deadline: the **15th** of next month)
- [ ] In Coretax, under the company NPWP, create a **kode billing** for each tax
      (PP55, PPh 21, unifikasi), correct masa, amount = Stage 2. Verify KAP-KJS per tax.
- [ ] Pay each billing (bank / Coretax) **by the 15th**. Capture the **NTPN** for each.
- [ ] Pay BPJS Kesehatan (EDABU) and Ketenagakerjaan (EPS / virtual account).

## Stage 4 — report + record (SPT Masa deadline: the **20th**)
- [ ] File **SPT Masa** for PPh 21 and Unifikasi by the 20th (PP55 has **no** SPT Masa —
      payment only; it pre-fills the annual return).
- [ ] Record every NTPN against the period — on the matching `financials.json →
      tax_calendar_<year>[]` entry (`status: paid`, `paid_at`, `payment_ref` = the NTPN; the documents collector
      does this automatically when the receipt lands). These feed the **SPT Tahunan Badan** (30 April).
- [ ] **Parity check (while shadowing the incumbent).** Compare each computed amount
      (PP55 / PPh 21 / unifikasi) to the incumbent's **issued billing** for the masa. Record
      the result on the period (`financials.json → periods[<masa>]`): `parity_status = "pass"`
      only when they match (else `"fail"` + note the delta), `parity_ref` = the incumbent
      billing id used. A period is **not closed** until `parity_status = "pass"` — this is the
      go-live gate, a structured field, not a free-text comment. (Slots from migration `0017`.)

## Safety
- **Prepare only.** Computing and drafting billing is fine; **paying, submitting, or
  e-signing requires operator approval** (safety-rules, browser deny-list).
- Parity mode: while shadowing the incumbent accountant, compare each computed amount to
  their issued billing before the operator acts.

## Operator-facing language

When you create or update the operator's tasks, calendar entries or messages from this
checklist, follow `policies/INSTRUCTIONS.md §0.1`: write them in the **operator's locale**
and **gloss every Indonesian term** (PPh 21, BPJS, PP55, unifikasi, kode billing, NTPN,
Coretax, SPT, LKPM, …) with a plain explanation + an analogy from the operator's own system.
Source of glosses: `jurisdictions/id/glossary.md`. Native terms are fine only in prompts
addressed to the runtime/agent (`assist.actions[].prompt`), not in operator-facing fields.
