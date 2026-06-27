# _rebuild.md — refresh the dashboard after a state change (always-current, within budget)

Shared by every connector/runbook that changes state. It **replaces** the old
habit of running a full `python3 engine/generate.py` at the end of each daemon:
that full serial render (~0.75s/client + ~4s of shared pages) overruns the
sandbox per-command limit (~45s) on a real operator machine and is **killed
mid-render**, freezing the dashboard — the 2026-06-11→13 "frozen date" incident,
recurring through a timeout instead of a skip.

## The isolation invariant (why a scoped render is correct, not a shortcut)

A **client page is isolated**: `dashboard_<id>.html` / `report_<id>.html` derive
from that client's own `state/*.json` only — nothing about client B can change
client A's page. So when client X's data changes, re-render exactly:

- **X's own page(s)** — `--clients=X`, and
- **every shared "service" page** — overview, the `clients_<group>` lists, plan,
  calendar, periods, changelog, guide, update — because each pools ALL clients
  and therefore reflects X's change (`--aggregates`).

**Unaffected clients' pages are NOT re-rendered** — re-rendering them would be
pure waste and would produce byte-identical files. This is proven: a chunked
render (clients rendered in separate batches) is byte-for-byte identical to a
full run, i.e. each client's page is independent of which others render alongside
it. So "render the affected client(s) + all service pages, skip the rest" is
**exactly equivalent** to a full render, just cheaper.

## The rule — a state change leaves the dashboard current WITHOUT a full render in the collector

Two cheap, in-budget steps:

1. **Lint gate** — `python3 engine/state_lint.py` (optionally `<client>`). On an
   error, fix the state before publishing. This is the safety check the old
   `generate.py` step gave you, minus the render cost.

2. **Scoped render** — render only what changed:
   - the affected client(s): `python3 engine/generate.py --clients=<id1,id2,...>`
     (~1s/client; batch by ~8 if many), then
   - the cross-client views (overview / plan / calendar / periods — they reflect
     every client): `python3 engine/generate.py --aggregates`.

   Both fit the per-command budget. The chunked output is **byte-identical** to a
   full run (verified): client batches write the same `dashboard_*`/`report_*`
   pages, and `--aggregates` rewrites the shared pages + strips emoji exactly as
   the full run does. `--aggregates` also runs `state_lint` and is where
   `✅ LINT OK` must appear (a `--clients` batch deliberately skips lint).

A collector that touched **no** client still closes with `--aggregates` (refreshes
today's date / overdue / "in N days" in the shared views).

## Who keeps the per-client date fresh — the daily full render (07:45)

Time-dependent content on a *client card* (header date, overdue, "in N days")
rolls over at the day boundary. The dedicated **`dashboards` job — 07:45, declared
in `config/instance.yaml → schedule`** — runs an unconditional full
`python3 engine/generate.py` each morning. This is the **relocated home of the
"unconditional render" guard** from the frozen-date incident: it is the single
place a full render runs on a timer, and it is parallel (per-client render across
processes, `ABA_GEN_SERIAL=1` to force serial) so it stays in budget. Intraday the
date does not change, so cards rendered today by a `--clients` step stay current.

## Never

- **Never** run a bare full `python3 engine/generate.py` as a collector's closing
  step — that is what froze the dashboard. The full render belongs only to the
  `dashboards` job (07:45) and to native, uncapped contexts (`tools/update.py`, a
  Windows terminal — no sandbox cap there).
- **Never** loop all `--clients` batches inside one shell command — that
  re-creates the timeout. One command per batch (each its own ≤45s budget).
