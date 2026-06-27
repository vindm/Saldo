# Migration runtime pass — spec (the AI-side half)

> Status: **SPEC / DRAFT**. The deterministic runner half (`next` / `apply` /
> `record` + the rung ledger) is **built** in `engine/migrate.py`. The runtime
> orchestration described here (`connectors/migration_runtime/SKILL.md`) is
> **not wired yet** — this file is the design to build against.

## Why this exists

A migration is no longer "done" the moment its deterministic `up()` returns.
Some migrations have a judgment step the deterministic transform cannot do — the
"left for a runtime prose rewrite" cases in 0007–0011. We want that judgment to
run **interleaved, in order**: for each migration — read it, do prework, run the
script, do afterwork, verify, *then* move to the next. Not "apply all scripts,
then run all prompts" (that advances every deterministic shape before any of
them is verified, leaves the ledger lying, and widens the blast radius of a
failed approval).

So the **AI runtime is the outer loop** and `migrate.py` is step-wise — apply
exactly one and stop. This is the same inversion as the rest of Saldo (the
runtime is the AI; the engine renders a view), now applied to migrations.

## The one invariant that keeps deterministic steps deterministic

**A deterministic `up()` may never read a field that any prior migration's
`RUNTIME_PASS` wrote. Judgment outputs are terminal leaves** — they feed
rendering and runtime behaviour (operator/client-facing prose, the dashboard),
never a later migration's transform.

If a later migration seems to *need* the judgment-cleaned value as structured
input, that is the smell that the "judgment" was actually deriving schema and
should itself be deterministic — i.e. the migration was mis-split. Hold this
line and two operators (or two model versions) can never diverge on a step that
must be reproducible.

## Migration module contract (additions — all optional)

A module is still `ID` / `DESCRIPTION` / `up(api)`. Three optional members add
the AI surface; a migration with none of them is pure-schema and flows through
the batch `up` path untouched.

```python
ID = "0020"
DESCRIPTION = "one line, schema-level, no client names"

def up(api):
    # the SAFE, deterministic part — shape-matched, idempotent, as today
    ...

def preflight(api):
    """READ step. Deterministic Python. Read-only (api.read only), NO model.
    A structural pre-scan that returns plain dicts: anomalies + the cases the
    deterministic up() deliberately left for judgment. Surfaced by `next`."""
    flags = []
    for cid in api.clients():
        data = api.read(cid, "tasks.json")
        ...  # append {"client":..., "field":..., "value":..., "kind":...}
    return flags

RUNTIME_PASS = {                       # AFTERWORK: the "something on top"
    "intent": "natural-language description of the judgment work, conservative "
              "rules stated (identifiers / risk-ids / machine tags stay)",
    "scope": "tasks[].title, tasks[].context",
    "escalate": "on_anomaly",          # default; "always" forces a per-migration pause
    "guardrails": [                    # a proposed write breaking one is skipped + surfaced
        "only modify a field preflight flagged",
        "preserve the original in <field>_legacy",
        "never touch identifiers / risk-ids / amounts / machine annotations",
    ],
}

EXPECT = {                             # the "normal application" envelope
    "preflight_max": 40,               # more flags than this = anomaly -> escalate
    "change_kinds": ["needs_prose_rewrite"],
}

SCENARIO = [                           # VERIFY: Invariant-0 role-play
    "Open the Plan for an affected client; confirm <expected behaviour> and "
    "zero RF artefacts for a non-RU client.",
]
```

- `preflight` is the **prework** input — read-only, runs before anything is
  written, the cheap place to abort.
- `EXPECT` is the **autonomy envelope** — the engine (`migrate.py next`) compares
  preflight against it and emits an `alignment` verdict (`aligned` / `anomaly`).
- `RUNTIME_PASS` is **data, not code** — a handoff the runtime acts on, writing
  through `state_ops`. Terminal-leaf per the invariant above.
- `SCENARIO` is the **post-flight gate** — the runtime role-plays it and records
  pass/fail. A failure HALTS (it does not auto-rollback; an AI's say-so is not
  enough to revert state — surface to Dima).

## Autonomy model — apply most migrations with no human touch

The operator authorises the upgrade once (the `update` flow's single «да»).
After that the runtime applies each migration **autonomously**, including its
`RUNTIME_PASS` rewrites, and escalates back to her **only on a surprise**:

1. **anomaly** — `migrate.py next --json` reports `"autonomous": false`
   (`alignment.status == "anomaly"`): the result is outside `EXPECT`;
2. **forced** — `RUNTIME_PASS.escalate == "always"`;
3. **guardrail breach** — a proposed rewrite would break a `guardrails` item
   (that write is skipped + surfaced, the rest proceed);
4. **scenario fail** — the `SCENARIO` role-play does not pass (halts).

Everything else runs straight to `verified`. This is the same exception-based
autonomy the daemons already use (write state, surface only what needs a human).

## Re-run safety (idempotency) — three layers

Migrations must be safe to re-run; the non-deterministic runtime half does NOT
change that, because of three layers:

1. **The ledger gates re-runs.** It lives with the data
   (`<data.dir>/journal/schema_migrations.json`). `up --apply` skips any
   migration with a rung; `apply <id>` refuses to re-run `up()` once a rung is
   set; `next` never returns a `verified` migration. So a fully-applied migration
   (deterministic + runtime + verify) is never touched again.

2. **The preflight makes the RUNTIME_PASS idempotent.** Every `preflight` must
   surface ONLY the *un-done residue* — a value still missing / still wrong.
   Once the runtime writes the fix, that item is no longer flagged, so re-running
   the pass (after an interrupted upgrade, or even a lost ledger) is a no-op on
   already-done items: it only continues on what remains. Writes must preserve
   the original via `setdefault(<field>_legacy, …)` — **never overwrite** a
   `*_legacy` on re-run. This is the runtime-half analogue of `up()`'s
   "skip if already done" guard.

3. **The terminal-leaf invariant prevents cascading divergence.** A runtime
   pass's output never feeds a later deterministic `up()`, so non-determinism
   cannot propagate or compound across migrations.

**This is a contract, not an automatic guarantee.** The engine enforces layer 1;
layers 2–3 are the author's responsibility — a `preflight` that re-flags a
done item, or a write that clobbers `*_legacy`, would break idempotency. So:
write the `preflight` as a residue scan, and the `RUNTIME_PASS` writes as
`setdefault`-preserving. (Verified by re-running a pass against already-fixed
data and confirming zero flags.)

## Python vs runtime — which half of a migration is which

The dividing rule, applied when authoring or reviewing a migration:

> **Matching on STRUCTURE → Python. Matching on MEANING → runtime.**

A migration that keys on field names, shapes, null-slots, or a hard rule ("a
terminal task has no `next_action`") is deterministic Python: reproducible,
reviewable as a diff, identical on every machine. A migration that keys on the
*meaning of natural-language text* — classifying a task, inferring a period from
context, rewriting operator prose, deciding which services a client actually
uses — is doing lossy pattern-matching as a proxy for judgment. That half
belongs in a `RUNTIME_PASS`: the Python opens/normalizes the slot (and may do the
high-confidence shape cases), the runtime does the broad judgment on the residue,
under `EXPECT` / guardrails / `SCENARIO` and the terminal-leaf invariant.

Reviewed against this rule (Mom's commit `abd7a6c` ships 0001–0005):
- **Pure structure → stay Python:** 0007, 0008, 0012, 0017, 0018; the slot-open
  of 0011/0013/0019 (their prose is already runtime-authored — correct split).
- **Meaning → carry a runtime pass:** 0009, 0010 (operator prose), 0016 (period
  inference) — built.
- **Meaning, still to unify:** 0014 (task type), 0015 (re-type ask-the-client),
  0016 (period) are three regex slices of ONE task — *classify a task by reading
  it*. The classification rules already live in the runtime (INSTRUCTIONS §0.4 +
  `task-types.md`, applied live by `mm_update`), so these one-time backfills
  should collapse into a single **shared task-classifier** `RUNTIME_PASS` that
  applies those same rules, instead of regex in three files drifting from policy.
  0016's pass is the first slice; 0006 (derive a client's real service map from
  evidence) is the same shape.

## Runner surface (built, in `engine/migrate.py`)

```
migrate.py status                       # rung per migration (legacy entries read as verified)
migrate.py next [--json]                # READ: next not-yet-verified migration + preflight; writes nothing
migrate.py apply <id> [--apply]         # RUN: exactly one up(); refuses to skip ahead of an unverified prior
migrate.py record <id> --rung R [--scenario-result S] [--note N]   # advance the ledger rung
migrate.py up [--apply] [--force]       # BATCH pure-schema path; REFUSES when a pending migration has runtime work
migrate.py classify [--json]            # ONE read of all task-classification candidates (type/retype/period together)
```

`classify` is the **single invocation** behind the shared task-classifier
(`migrations/TASK_CLASSIFIER.md`): one read of the task set surfacing every
classification dimension per task, so the runtime judges type + period + routing
in a single pass instead of three per-migration preflight rounds. The scan logic
lives once in `engine/_task_classifier.py`; 0014/0015/0016 preflights delegate to
it (guarded, so a helper issue never breaks discovery).

Rung ledger (`<data.dir>/journal/schema_migrations.json`), per migration:
`mechanical_applied → runtime_pass_done → verified`. Only `verified` lets the
sequence advance, so the ledger is always a **truthful prefix**: everything up
to migration K is fully done and behaviour-verified; nothing after K has touched
the data. Legacy entries (no `rung`) are read as `verified` — backward-compatible.

## The skill: `connectors/migration_runtime/SKILL.md` (TO BUILD)

Same shape as `connectors/update` / `onboarding` / `scheduler`: thin engine
primitive (the subcommands above) + the AI does the orchestration. The outer
loop, in natural language:

```
loop:
  info = migrate.py next --json
  if info.done: stop, run state_lint + integrity, report
  # DECIDE: escalate to the operator ONLY on a surprise; else proceed autonomously
  if not info.autonomous:                # alignment=anomaly, or escalate=="always"
      show info.alignment.reasons to the operator and wait for «да» (or skip)
  migrate.py apply <id> --apply          # RUN — deterministic, backed-up/atomic/UTF-8 via state_ops
  # AFTERWORK (autonomous):
  #   if info.runtime_pass: rewrite on the operator's OWN real data, each write
  #     through state_ops, within every guardrail; a write that would breach one
  #     is SKIPPED + collected (not applied); then
  #     migrate.py record <id> --rung runtime_pass_done --note "rewrote N, skipped K"
  #   role-play each info.scenario item; on PASS:
  #     migrate.py record <id> --rung verified --scenario-result "..."
  #   on scenario FAIL: STOP at this migration, report — no auto-rollback
  # only a `verified` rung lets the loop advance
```

Boundary note: the migration in the public repo stays **data-free**; the
`RUNTIME_PASS` writes run locally on the operator's machine against their real
data and never ship. That is what keeps the clean/real boundary intact while
still letting AI handle the mess.

## Build checklist (when wiring the skill)

- [x] `connectors/migration_runtime/SKILL.md` implementing the loop above. (2026-06-26)
- [x] Retrofit a real `preflight` + `RUNTIME_PASS` onto `0009` and `0010` —
      done 2026-06-26 (these are the two operator-prose normalizations that
      explicitly left judgment "for a runtime prose rewrite"). Both preflights
      are high-precision: 0009 flags only runs of ≥2 consecutive English words
      (so `PDF`/`Finkoper`/`tbank.ru`/`Anna Nazarova` are NOT flagged); 0010
      flags only machine-labelled parentheticals that survived the strip
      (`(mental_model)`/`(state)`), not daemon tags or Cyrillic asides. Both
      keep active-jurisdiction terms (`kode billing`, `NTPN`, `Usaha Kecil`).
      Migrations 0006–0008, 0011–0019 reviewed (Mom's commit `abd7a6c` ships
      0001–0005): no runtime pass needed — additive null-slots populated by the
      normal runtime/collectors, complete deterministic normalizations, or
      structured re-typings where deterministic-only is the safer choice.
- [x] A `runtime_scenarios/` scenario that role-plays the loop end-to-end — S6.
- [ ] Index the skill in `policies/INSTRUCTIONS.md` (alongside §1.5 update flow).
- [ ] Wire the skill into the update flow: `migrate.py up` already refuses
      runtime-work migrations and points at `next`; `connectors/update` should
      hand off to `connectors/migration_runtime` on that refusal.
- [x] Operator UX for approval — decided 2026-06-26: **autonomy by default**.
      One up-front «да» authorises the upgrade; migrations then apply (incl.
      RUNTIME_PASS) with no per-migration pause, escalating only on an `EXPECT`
      anomaly / `escalate:"always"` / a guardrail breach / a scenario fail. The
      Windows icon hands runtime-work migrations to the Cowork chat (exit 2).
- [x] **Shared task-classifier** — contract `migrations/TASK_CLASSIFIER.md`;
      scan logic centralized in `engine/_task_classifier.py`; 0014 (type) / 0015
      (re-type) / 0016 (period) preflights delegate to it; folded into a single
      invocation `migrate.py classify` (type + period + routing in one read). All
      apply the live policy rules (`task-types.md`, INSTRUCTIONS §0.4) as the
      single source of truth, so a new title/verb variant needs **no new
      migration** — it is just more input to the same scan + judgment.
- [x] `0020` — quick_access `category` (icon-by-type, jurisdiction-neutral):
      deterministic up() categorizes known service slugs + retires the stale
      `icon` field to `icon_legacy`; a `RUNTIME_PASS` classifies unknown-slug
      services into a category (same classifier pattern). The renderer
      (`_qa_icon_name`) prefers `category` over the slug, so a new service in any
      jurisdiction is type-matched with no engine change. Behaviour-preserving
      (category→same icon as the slug map; dashboards byte-identical, verified).
- [ ] quick_access **completeness** — derive missing services + correct
      `cred_status` from evidence (statements / tasks / counterparties). Left out
      of 0020 (which only categorizes); a separate evidence-derivation pass.
- [ ] *Optional precision refinement:* preflight could also skip the active
      jurisdiction pack's own Latin terms (id: `kode billing`, `NTPN`) to cut
      judgment load. Not required — the RUNTIME_PASS already handles them
      correctly (locale ≠ jurisdiction: an id-term is kept, not Russified), as
      S6 demonstrates with the synthetic `kirana` `kode billing` flag.

## What is NOT changing

No client-state schema change here, so **no `NNNN_` migration file** is needed
for this work: the rung fields live in the journal ledger (metadata, with the
data), and the reader treats pre-rung entries as `verified`. The deterministic
guarantees of `up()` — idempotent, reviewable diff, zero real data — are
untouched; `migrate.py` still never calls a model.
