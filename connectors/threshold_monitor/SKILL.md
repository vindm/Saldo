# Skill: threshold_monitor — turnover-limit & facility-expiry watcher (MONITOR)

The third **monitor** (no fetch, derives from state). It watches each client's YTD / annualized
turnover against the regime's **thresholds**, and time-limited tax **facilities** against their
**expiry** — so a warning lands *before* a crossing forces a regime change (VAT registration,
loss of USN, the end of a reduced-rate facility), not after.

> Pure compute → cheap. Turnover updates monthly, so it runs **weekly**
> (`schedule.threshold_monitor: { cadence: weekly, weekday: mon }`) — enough to catch a crossing
> well before it bites, without daily churn.

## Thresholds & facilities it watches (resolve jurisdiction + regime first, §0)

- **RU / USN** — the VAT-on-USN turnover threshold (a USN payer must start charging VAT), the
  USN income ceiling (cross it → OSNO), indexed limits — from `jurisdictions/ru/regimes.yaml`
  where declared, else the pack's documented limits.
- **ID / UMKM_FINAL** — the **PKP/PPN threshold** (peredaran bruto **4 800 000 000 IDR** → must
  register PKP and charge PPN) and the **0.5% PP55 facility time limit** (after it lapses →
  normal PPh Badan 22%; `jurisdictions/id/regimes.yaml` notes the time limit / 2026 PP55
  revision). This is exactly `melati`'s standing «следить за окончанием льготы 0,5%».
- General: any regime with a declared turnover ceiling or a time-boxed facility.

## What it reads (no fetch)

- `financials.json → periods[]` (monthly turnover: `turnover_idr` / `income_usn` / `income_ausn`
  …) and **`yearly_pace_<year>`** (`turnover_ytd_*`, `avg_month_*`, `estimated_annual_*`,
  `*_threshold`, `*_warning`).
- `regime.json` (regime, jurisdiction, and the facility grant/start date if present).
- `jurisdictions/<code>/regimes.yaml` (threshold values + facility duration).

## Logic

- **Turnover proximity.** `pct = estimated_annual / threshold` (use `yearly_pace.estimated_*`;
  else `YTD × 12 / months_elapsed`). Tiers: **≥80%** info · **≥90%** medium · **≥100% /
  projected to cross** high → «оборот N% от порога <PKP/УСН-НДС>; при пересечении — <последствие:
  регистрация PKP+PPN / переход на ОСНО>».
- **Facility expiry.** `expiry = regime.since + facility.duration_years[<legal form>]`, where the
  durations are the pack's `regimes.yaml → <regime>.facility.duration_years` (ID UMKM_FINAL: OP 7 /
  badan 3 / CV·PT-Perorangan 4), resolved by the client's legal form (`regime.entity_type` /
  identity legal form). Within the lead window (90 / 60 / 30 days) → «льгота 0,5% истекает <дата>;
  затем <facility.after, e.g. PPh Badan 22%> — подготовить переход». The nominal duration is an
  **upper bound**: when `facility.revision_2026_ends_for_ordinary_pt` is true and the client is an
  ordinary badan/PT, the 2026 PP55 revision may end it **earlier** — surface both (the dated 3-year
  mark AND the revision watch), never only the later one. Jurisdiction-agnostic: any pack that
  declares a `facility` block gets the same countdown.
- **Reconcile `yearly_pace`.** Where it already carries `*_threshold`/`*_warning` (e.g.
  melati's `pkp_warning`), refresh it to stay honest rather than recomputing blindly.
- Idempotent stable id `limit-<client>-<threshold>`; refresh not duplicate; honour
  `risks.dismissed[]`; **never closes**; jurisdiction-correct (ID = PKP / PP55, never USN).

## Output & safety

- Surfaces to `risks.json` (`yellow[]` → `red[]` by tier) via `mm_update`; renders in the «нужно
  решение» zone + the client card. `access: none`, no credentials. Daily
  (`schedule.threshold_monitor`), after the other monitors, before `dashboards`. Reads/appends
  existing fields → **no migration**.

## Related

- `docs/COVERAGE-MAP.md` — C2. Siblings: `deadline_monitor`, `staleness_monitor`.
- `jurisdictions/<code>/regimes.yaml` — threshold/facility source; `INSTRUCTIONS.md §0`.
- `connectors/mm_update/SKILL.md` — write path + `risks.dismissed[]` protection.
- `tests/runtime_scenarios/` — S13 gates it.
