# Migration runtime — apply migrations autonomously, one at a time, surfacing only surprises

**Who runs this:** the runtime (Cowork / Claude), invoked by the update flow
(`connectors/update/SKILL.md`) once the operator has authorised the upgrade and
a pending migration carries an AI-side step (`preflight` / `RUNTIME_PASS` /
`SCENARIO`). Pure-schema migrations never reach here — `migrate.py up` applies
those itself.

## Principle: autonomous by default, escalate only on a surprise

The operator already said «да» to the upgrade. Do **not** pause on every
migration. Apply each one **autonomously** — including its `RUNTIME_PASS` prose
rewrites — and pull the operator back in **only** when something does not match
the migration's own expectations. Concretely, escalate (stop, show her, wait)
only in these cases:

1. **Anomaly** — `migrate.py next --json` reports `"autonomous": false`
   (its `alignment.status == "anomaly"`): the result is outside the migration's
   declared `EXPECT` envelope — e.g. preflight produced far more flags than
   expected, or a flag kind the migration did not anticipate. This is the
   "something really unexpected" case.
2. **Forced** — the migration's `RUNTIME_PASS.escalate == "always"` (reserved
   for genuinely sensitive changes; most are `"on_anomaly"`).
3. **Guardrail breach** — while doing a `RUNTIME_PASS` rewrite, a proposed write
   would break a stated guardrail (touch an identifier / amount / risk id, drop
   a `<field>_legacy`, Russify an active-jurisdiction term). Do **not** make that
   write; surface it.
4. **Scenario fail** — the `SCENARIO` role-play does not pass.

Everything else runs to `verified` with no human touch, and you report once at
the end.

## The invariant you must not break

A deterministic `up()` never reads a field any prior `RUNTIME_PASS` wrote.
**Judgment outputs are terminal leaves** — operator/client-facing prose that
feeds rendering and behaviour, never a later migration's transform. So the
autonomous rewrites are safe: nothing downstream consumes them as structured
input. If a `RUNTIME_PASS` ever looks like it is producing data a later
migration needs, STOP and tell Dima — the migration was mis-split.

## Paths

```bash
REPO="…/saldo"
DATA_DIR="$(cd "$REPO/engine" && python3 -c 'from _config import DATA_DIR; print(DATA_DIR)')"
M(){ python3 "$REPO/engine/migrate.py" "$@" --data-dir "$DATA_DIR"; }
```

## The loop (repeat until `next` says done)

1. **READ** — next not-yet-verified migration + its read-only preflight +
   alignment verdict. Writes nothing.

   ```bash
   M next --json
   ```

   `done:true` → exit, run `state_lint` + `system_integrity_check`, report.

2. **DECIDE.** If `autonomous` is **false** (anomaly) or the migration forces a
   pause → **ESCALATE**: show the operator, in her locale, the `alignment.reasons`
   and what you were about to do, and wait. Do not apply until she says «да» (or
   skips). If `autonomous` is **true** → proceed without asking.

3. **RUN** — apply exactly this migration's deterministic part. Backed-up /
   atomic / UTF-8 via `state_ops`; sets rung `mechanical_applied`. Refuses if any
   earlier migration is unverified.

   ```bash
   M apply <id> --apply
   ```

4. **AFTERWORK (autonomous).**
   - If the migration has a `RUNTIME_PASS`: do the rewrites on the operator's own
     real data, each write through `engine/state_ops.py`, conservative per
     `runtime_pass.intent` and within every `runtime_pass.guardrails` item. If a
     proposed write would breach a guardrail, **skip it and collect it** as an
     anomaly to surface — do not block the rest. Then:

     ```bash
     M record <id> --rung runtime_pass_done --note "rewrote N fields, skipped K"
     ```

   - **VERIFY**: role-play each `scenario` item (Invariant-0). On PASS:

     ```bash
     M record <id> --rung verified --scenario-result "pass: …"
     ```

     On FAIL: **STOP at this migration** and report to Dima/the operator. Do
     **not** auto-rollback (an AI's say-so is not enough to revert state) and do
     **not** advance — the ledger must stay a truthful prefix (everything before
     this migration fully done and verified; this one halted at a known rung;
     nothing after touched).

5. Only a `verified` rung lets `next` return the following migration. Loop.

## Boundary

The migration in the public repo stays **data-free**. Every `RUNTIME_PASS` write
runs locally on the operator's machine against her real data and never ships.

## Report

When `next` reports done, run `state_lint` + `system_integrity_check`, then tell
the operator, in her locale, which migrations applied, that each was verified,
and — only if any — what you skipped or surfaced for her attention.
