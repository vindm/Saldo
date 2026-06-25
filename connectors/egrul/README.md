# Skill domain: egrul (company registry — EGRUL / EGRIP)

> Reading the company registry by INN/OGRNIP from `egrul.nalog.ru` — a registration extract
> (выписка) and the active/liquidated status of a company or sole proprietor. Browser-driven
> (Chrome), read-only; a captcha/credential wall → hand to the operator (human fallback).

## Skills

| File | Type | What it does |
|---|---|---|
| [`egrul_vypiska_workflow.md`](egrul_vypiska_workflow.md) | composite | Canonical Chrome pipeline: fetch an EGRIP/EGRUL extract by INN/OGRNIP |

## Who calls these skills

- `question_resolver` — to resolve "ОКВЭД / адрес / status by INN" questions (rung-2 fetch).
- `counterparty_status` — monthly re-check of each counterparty's registry standing.
- On-demand — the functional `registry` connector key resolves to this domain (INSTRUCTIONS §0).

## State / access

Read-only registry lookups need no approval (mm_update §5a). RU registry; for a non-RU client
resolve its own registry per jurisdiction, never RF-reflex.
