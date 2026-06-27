# Skill: staleness_monitor — missing-data & reconciliation watcher (MONITOR)

The second **monitor**: it fetches nothing and derives from state. Where `deadline_monitor`
watches what's *coming due*, this watches what *should have arrived but didn't*, and where the
numbers *don't agree*. It is the proactive successor to the deprecated `analytic` R-rules
(`policies/analytics-rules.md`) — those moved to render-time dashboard widgets (only seen when
someone looks); this brings the *push* back as a scheduled derive.

> Pure compute, no API, no access → **daily**, cheap (cadence-by-cost, `docs/COVERAGE-MAP.md`).

## What it checks (per client — resolve jurisdiction first, §0)

1. **Expected-but-missing artifact.** For the just-closed month, did the recurring source land?
   Cross-reference `financials.json → periods[]` and the collectors' watermarks/inbox: a client
   whose monthly **bank statement** (`documents`/bank watermark), **Moka/POS sales**, or **OFD
   Z-report** has no entry for the period **past its usual arrival window** → flag «ожидаемая
   выписка/продажи за <месяц> не поступили».
2. **Stale period / unfilled estimate.** A `periods[]` turnover still `null` (or only
   `*_estimated` with the actual `null`, or `under_recovery`) **past its close/due window** →
   flag «период <месяц> не закрыт / только оценка».
3. **Reconciliation mismatch.** Where a period has more than one turnover source (bank vs
   OFD/kassa vs declared), or `financials.json → balance_anomalies[]` is non-empty/unresolved
   (e.g. cirrus's Сбер …0000 negative-balance artifact), and they diverge beyond tolerance →
   flag an R-style anomaly with the two numbers and their sources.
   - **Cash-takings gate** (`periods[].cash_reconciled` / `turnover_source`, migration 0017) —
     jurisdiction-agnostic, for any turnover-based regime whose pack declares
     `require_cash_reconciliation` (RU USN-income / AUSN, ID UMKM-final). An **open** month
     with recorded turnover where cash is in play (turnover_source names it, or the client has
     a kassa/OFD/acquiring channel) but `cash_reconciled` is not true → flag «касса/выручка не
     сверена за <месяц>: база налога с оборота может быть занижена» (ID: Moka POS vs the cash
     report; RU: OFD/kassa vs declared). This is the push twin of the `cash_unreconciled`
     publish gate in `state_lint.py` — the base must be complete before the turnover tax is
     settled. Severity escalates by age toward the payment deadline.
4. **Channel silence.** The client's last inbound signal (max of message/email/doc timestamps
   across `behavior.channels` + collector heartbeats) is older than a threshold **while open
   work exists** → flag «тишина по клиенту N дней».

## Logic & output

- Reads `periods[]`, `tax_calendar_<year>`, `balance_anomalies[]`, `behavior.json`, and the
  collectors' `journal/inbox/*`/watermarks. **No fetch.**
- Surfaces via `mm_update` into `risks.json` (`yellow[]`, or `red[]` when material) and/or a
  `🔧`-marked track — **idempotent** (stable id `stale-<client>-<topic>-<period>`; read-modify-
  write; never duplicate, never overwrite the operator's dismissals — honour
  `risks.dismissed[]` exactly like the old R6 rule).
- **Severity by age** (the old R8 idea): a flag lingering past a threshold escalates
  automatically. Stable ids so the operator's "dismiss" survives between runs.
- **Never closes, never fetches.** It only surfaces; a missing artifact clears when the
  collector ingests it; a mismatch clears when reconciled. Audit-log only new/changed flags
  (no-op runs stay silent). Heartbeat `journal/inbox/staleness_monitor_heartbeat.txt`.

## Safety / deployment

- `access: none` (no external calls/credentials). Daily
  (`config/instance.yaml → schedule.staleness_monitor`), after `deadline_monitor`, before
  `dashboards`. A **monitor** → no `connectors.*` entry (scheduler treats it as schedule-only).
- Reads + appends **existing fields** (`risks`/`tasks`/`balance_anomalies`) → no schema change,
  **no migration**.

## Related

- `policies/analytics-rules.md` — the deprecated R-rules (R2 Nth-day, R6 preserve dismissals,
  R8 auto-escalation) whose proactive intent this revives.
- `connectors/deadline_monitor/SKILL.md` — the sibling monitor (due-dates vs missing-data).
- `connectors/{documents,bank,ofd}/…` — the collectors whose arrivals clear flag #1/#3.
- `connectors/mm_update/SKILL.md` — write path + `risks.dismissed[]` protection.
- `docs/COVERAGE-MAP.md` — C8. `tests/runtime_scenarios/` — S12 gates it.
