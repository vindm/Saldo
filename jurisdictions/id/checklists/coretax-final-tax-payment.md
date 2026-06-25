# Checklist — UMKM final PPh (0.5%) payment via Coretax (Indonesia)

For a micro client on the UMKM final regime (PPh final 0.5% of gross monthly turnover,
threshold IDR 4.8B/year). Browser-driven on Coretax under the client's own NPWP.

## Stage 1. Amount
- [ ] Get the month's gross turnover (peredaran bruto) from the client's records / bank.
- [ ] Final PPh = 0.5% x gross turnover. If turnover = 0, no payment this month — note it, stop.

## Stage 2. Billing code (Coretax)
- [ ] Log in to Coretax under the client's 16-digit NPWP.
- [ ] Create a billing code (kode billing) for PPh final UMKM, correct tax period (masa).
- [ ] Verify the MAP-KJS / billing maps to UMKM final PPh, amount = Stage 1.

## Stage 3. Pay + record
- [ ] Pay the billing code (bank / Coretax). Capture the NTPN receipt number.
- [ ] Record the NTPN against the period.

## Stage 4. SPT
- [ ] Monthly turnover feeds the annual **SPT Tahunan** — UMKM-final files **no SPT Masa**,
  only the annual return (Coretax pre-fills it from the monthly payments). Deadline depends on
  the client's legal form: **orang pribadi (OP) — 31 March; badan / PT — 30 April** (see
  `new-client-id.md` legal-form pivot). Do not assume individual.

## Safety
- Do NOT submit/sign on the client's behalf without operator confirmation.
- Coretax actions are browser-driven and require approval (see safety-rules).
