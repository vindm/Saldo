# Skill: counterparty_status — registry re-check of counterparties (collector + monitor)

A **monthly** re-check that each client's counterparties are still in good standing — active in
the registry, and (for self-employed/НПД) still holding that status. It catches a live tax risk:
paying an **НПД** contractor who has **lost** self-employed status (your НПД treatment is now
invalid → withholding/recharacterisation), or booking expenses to a **liquidated** supplier.
A **hybrid**: it *fetches* (EGRUL/НПД check by INN) and then *derives* the risk.

> Cadence **monthly** (`schedule.counterparty_status: { cadence: monthly, day: 1 }`) — registries
> change slowly and each INN is a fetch; no need to run it daily. `access: auto` (read-only
> public registry).

## What it reads + fetches

- `counterparties.json` — `b2b[]` / `agents[]` / `self_employed[]` / `npd[]` (+ `contracts[]`):
  the INNs to check. (Sparse in the snapshot today; the capability matters for `marlin`'s НПД
  payments and any client with agents/suppliers.)
- Per INN, **fetch** the registry status:
  - **EGRUL/EGRIP** via `connectors/egrul` → active / in-liquidation / liquidated / inactive.
  - **Self-employed/НПД** → the FNS self-employed check by INN (`npd.nalog.ru` "проверить статус
    налогоплательщика НПД").
- **Resolve jurisdiction first** (§0): RU registries apply to RU counterparties; a non-RU
  counterparty is checked against its own registry or **skipped + flagged**, never RF-reflexed.

## Logic

For each counterparty with an INN:
- **Active / valid** → write `status: active`, `status_checked_at` on the entry; no flag.
- **Liquidated / in-liquidation / inactive** → risk: expenses/contracts with it are at risk →
  `risks.json` red/yellow, «контрагент <…> ликвидирован/в стадии ликвидации — проверить
  расходы/договор».
- **Self-employed lost НПД status** → 🔴 risk «<…> больше не самозанятый — выплаты как НПД
  недействительны: переквалификация / удержание НДФЛ+взносы» (the `marlin` case).
- Idempotent: re-check monthly, store `status`/`status_checked_at` per counterparty, surface only
  **changes**; honour `risks.dismissed[]`; **never closes** a track.

## Output & safety

- Writes the counterparty's status (a fact → no approval) via `state_ops`, and surfaces risks via
  `mm_update`. Read-only registry fetch; if a check hits a captcha/credential wall → downgrade to
  the operator with a precise reason (like `question_resolver`), don't guess.
- **Schema note:** adds optional `status` / `status_checked_at` to counterparty entries —
  additive and behaviour-preserving (absent = "not yet checked"). It appears as the monitor
  checks each entry; ship a tiny backfill migration only if you want the fields present on every
  existing entry up front (otherwise none needed).

## Related

- `docs/COVERAGE-MAP.md` — C3. `connectors/egrul/` — the registry fetch.
- `connectors/mm_update/SKILL.md` — write path + `risks.dismissed[]`. `INSTRUCTIONS.md §0`.
- `tests/runtime_scenarios/` — S14 gates it.
