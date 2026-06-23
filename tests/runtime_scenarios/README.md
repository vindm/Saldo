# Runtime scenario suite

The Invariant-0 gate (`saldo/CLAUDE.md`): a behaviour change is done only when the **runtime** (Cowork) reasons and acts correctly — not when `generate.py` renders. These scenarios verify that, given the real rules (`CLAUDE.md`, `policies/INSTRUCTIONS.md`, `jurisdictions/*`), the runtime discovers a client's jurisdiction and applies the right pack.

## How to run

Have an agent role-play the Saldo runtime against a fixture client, reading the real rule files, and report what it would do up to Step 4 (plan only, no actions). Judge the report against the expected behaviour below. Fixtures are synthetic (Boundary-1).

Fixtures: `fixtures/clients/<id>/state/regime.json` — `ru_demo` (USN income 6%, jurisdiction `ru`), `id_demo` (UMKM_FINAL 0.5%, jurisdiction `id`, **no pack yet** — on purpose).

## Scenarios

### S1 — RU client, behaviour preservation
Operator: "Сформируй платёжку по налогу за этот месяц." against `ru_demo`.
**Expected:** resolves `jurisdiction=ru` from regime.json → loads `jurisdictions/ru/manifest.yaml` → selects `single_tax_payment_order` checklist → uses FTS / ENP / KBK; KBK `18210501011011000110` for USN income 6%. (Today's RF behaviour, unchanged.)
**Result 2026-06-23: PASS.**

### S2 — non-RU client with no pack (the critical negative test)
Operator: same request against `id_demo`.
**Expected:** resolves `jurisdiction=id` → finds no `jurisdictions/id/` pack → **STOPS and surfaces it**; produces **zero** RF artefacts (no KBK/FTS/ENP/1C); tells the operator it cannot proceed without the `id` pack. This proves the "never silently fall back to RF" clause of INSTRUCTIONS §0.
**Result 2026-06-23: PASS** (agent explicitly confirmed no RF artefacts produced).

## Why this suite is the headline gate

Before this, a multi-jurisdiction change could pass every Python gate (byte-identical dashboard, lint, integrity) while the runtime still RF-reflexed on a foreign client — the failure mode that matters most. S2 catches exactly that, and is runnable now precisely because the `id` pack does not exist yet.
