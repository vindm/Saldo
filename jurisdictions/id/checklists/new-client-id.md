# Checklist — new Indonesia client (UMKM micro)

- [ ] **Legal form — the pivotal fact, settle it first.** Whether the client is an
  **orang pribadi (OP / individual)**, a **PT (badan / company)**, or a **CV / PT Perorangan**
  drives four downstream rules — get it wrong and the whole monthly + annual cycle is wrong:
  1. **0.5% facility time limit** from registration: OP **7 years**, PT **3 years**,
     CV / PT-Perorangan **4 years**. After it lapses the client moves to **PPh Badan 22%**
     (see `regimes.yaml → PPh_BADAN`).
  2. **2026 PP55 revision:** 0.5% becomes *permanent* for OP & PT Perorangan but is being
     *removed for ordinary badan/PT* — a regular PT may lose the facility. Flag it.
  3. **IDR 500M annual turnover relief** (first 500M untaxed) is **OP-only** — a PT/badan
     pays 0.5% on the **whole** turnover, no relief.
  4. **Annual SPT Tahunan deadline:** OP **31 March**, badan **30 April**. (UMKM-final pays
     0.5% monthly but files **no SPT Masa** — only the annual return; Coretax pre-fills it.)
- [ ] Record the form + 16-digit **NPWP** (and **NIB** if a company). If the form is unclear,
  STOP and confirm with the client before building the pipeline — do not assume.
- [ ] Tax regime: UMKM final 0.5% (confirm turnover under IDR 4.8B/yr); PKP? (PPN) usually no.
- [ ] Employees? -> PPh 21 withholding applies.
- [ ] Coretax access (under the client's NPWP).
- [ ] Bank account(s) and how turnover is collected.

## Operator-facing language

When you create or update the operator's tasks, calendar entries or messages from this
checklist, follow `policies/INSTRUCTIONS.md §0.1`: write them in the **operator's locale**
and **gloss every Indonesian term** (PPh 21, BPJS, PP55, unifikasi, kode billing, NTPN,
Coretax, SPT, LKPM, …) with a plain explanation + an analogy from the operator's own system.
Source of glosses: `jurisdictions/id/glossary.md`. Native terms are fine only in prompts
addressed to the runtime/agent (`assist.actions[].prompt`), not in operator-facing fields.

## Quick access — register the COMPLETE service map (state/accounts.json → quick_access)

Per `policies/INSTRUCTIONS.md §0.1`, quick_access must list EVERY external service this client
touches, each with a glossed Russian purpose note and a `cred_status`. For a UMKM PT salon:

- **gdrive** — document archive + monthly intake (Google Drive).
- **coretax** — tax authority portal (DJP): kode billing, SPT, NTPN. Under the company NPWP.
- **bank** — the company's client-bank (statements + payments).
- **moka** — the salon's POS/cash app (source of turnover).
- **edabu** — BPJS Kesehatan portal (employee health insurance).
- **bpjs_tk** — BPJS Ketenagakerjaan portal (employment social security).
- **oss** — OSS portal (NIB, LKPM investment report).
- **email** — the company email (DJP/BPJS notices).

Include the ones whose access must still be requested (`cred_status: missing`) — the map shows
what is needed, not only what is connected.
