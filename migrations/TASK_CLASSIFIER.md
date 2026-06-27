# Shared task-classifier — one runtime contract for task-classification passes

> Status: **SPEC / partial build**. The contract below is what every
> task-classification `RUNTIME_PASS` applies. Migrations 0014 (type), 0015
> (re-type ask-the-client) and 0016 (period) each carry a slice of it; the goal
> is for all task-classification judgment to flow through this one contract
> instead of bespoke logic per migration.

## Why this exists

0014, 0015 and 0016 are three regex slices of **one** task: *classify a task by
reading it* — assign the right `task_type`, the right `type_specific.period`, and
hence the right Plan/Calendar bucket. Each migration's deterministic `up()` keys
on a narrow title/verb shape and catches what it can; the **residue** — where the
right answer needs reading the task's meaning, not matching a shape — is the
runtime's job.

The classification rules are **not new here**. They already live in the runtime:
`policies/task-types.md` (the type vocabulary) and `policies/INSTRUCTIONS.md §0.4`
(type by the *action*, not the framing), applied live by `connectors/mm_update`.
This contract is just the **backfill discipline** for applying those same rules
as a migration pass — so the one-time catch-up uses the same source of truth the
runtime uses continuously, and never drifts into a separate regex dialect.

## The contract (what every task-classification RUNTIME_PASS does)

For each task a migration's `preflight` flags:

1. **Read** the task (`title`, `context`, `next_action`, dates, current
   `task_type` / `type_specific`).
2. **Classify** per `task-types.md` + §0.4 — what operation is this really, and
   (for `service_payment`) which billing period.
3. **Act only when the stored value is wrong AND the right value is clear.**
   Re-type / set the period; otherwise **leave it** — never guess.
4. **Preserve + mark provenance.** Keep the original in `task_type_legacy` /
   write `type_specific.period_source = "runtime_inferred"`, so a
   runtime-classified value is distinguishable and reversible.

## Guardrails (shared)

- Only touch a task `preflight` flagged (a structural candidate); never sweep.
- A value that is genuinely ambiguous is **left as-is**, not fabricated.
- Keep every fact / id / amount; classification changes the *type/period*, not
  the content.
- **Terminal leaf:** `task_type` / `type_specific.period` feed only Plan /
  Calendar / Periods grouping (render). No later *migration* reads them as input,
  so the runtime may write them under the terminal-leaf invariant
  (`RUNTIME_PASS_SPEC.md`). Confirm this stays true before adding a consumer.

## How the slices map

| migration | deterministic `up()` (structure) | `RUNTIME_PASS` residue (meaning) |
|---|---|---|
| 0014 | mode/generic-typed task whose title matches `оплат\w+\s+услуг` → `service_payment` | a service-fee task phrased differently (`оплата за услуги`, reversed order, a synonym) the strict regex missed |
| 0015 | `review_checkpoint` whose `next_action` matches `(уточнить\|спросить\|запросить\|узнать) у` → `client_followup` | a checkpoint resolved by the client but phrased without that exact verb (`ждём ответа от…`, `нужно подтверждение от клиента`) |
| 0016 | `service_payment` with a `Q2 2026` / `1кв 2026` token in the title → `type_specific.period` | period inferable from context / next_action / date (`постфактум`, `за прошлый квартал`) but absent from the title |

`needs_task_classification` (type) and `needs_period_inference` (period) are the
two `kind`s; both run under the same contract and the same autonomy model
(`EXPECT` envelope → apply autonomously; escalate only on anomaly / guardrail
breach / scenario fail).

## The single invocation (built)

The scan logic lives once in `engine/_task_classifier.py`; the three preflights
delegate to it (`type_candidates` / `retype_candidates` / `period_candidates`),
and `migrate.py classify [--json]` does ONE read of the task set returning every
dimension per task. So the runtime judges type + period + routing for a task in a
single read, and a new title/verb variant needs **no new migration** — it is just
more input to the same scan + judgment.

## Applied on another field — `0020` (quick_access category)

`0020` gives each «Быстрые доступы» entry a structured `category` so the
dashboard picks an icon BY TYPE: deterministic for known service slugs, a
`RUNTIME_PASS` classifies unknown ones — the same scan-then-judge shape on a
different field. Renderer `_qa_icon_name` prefers `category`, so a new service in
any jurisdiction is type-matched with no code change. Remaining (separate pass):
derive **missing** services + correct `cred_status` from evidence. See the build
checklist in `RUNTIME_PASS_SPEC.md`.
