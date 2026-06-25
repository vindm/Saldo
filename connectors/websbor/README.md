# Skill domain: websbor (statistics portal — websbor.gks.ru / Rosstat)

> Checking each sole proprietor's statistical-reporting obligation on `websbor.gks.ru`.
> Annual (run in January) and on demand. Browser-driven, read-only.

## Skills

| File | Type | What it does |
|---|---|---|
| [`check_annual.md`](check_annual.md) | atomic | Annual check of the obligation to file statistics reporting (after a new INN/OGRNIP, or on the operator's command) |

## Who calls these skills

- On-demand — the functional `stats_portal` connector key resolves to this domain.
- The `news` `stats_reporting` topic flags clients to check here when Rosstat rules change.

## State / access

Read-only portal lookups need no approval. RU-jurisdiction (Rosstat); a non-RU client uses its
own statistics authority per the jurisdiction pack (e.g. ID → BPS).
