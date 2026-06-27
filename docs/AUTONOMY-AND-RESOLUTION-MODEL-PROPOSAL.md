# Design note — autonomy & the resolution model (task = node, asking the human = edge)

Status: **partially landed** — the resolution-edge model shipped (`policies/resolution-model.md`, `connectors/resolution_sweep/SKILL.md`, INSTRUCTIONS §0.6, scenario S29); the autonomy-level posture remains a proposal. Direction note — governs how the runtime decides *whether
to act on its own or surface a task to the operator*, and how the overview presents that. Builds
directly on `ENTITY-LINKING-ARCHITECTURE.md` (tasks are the hub) and the payroll notes
(`PAYROLL-CALCULATION-REVIEW-PROPOSAL.md`, `PAYROLL-REVIEW-COCKPIT-PROPOSAL.md`) as the first
consumer. Frames a setting (autonomy level) that moves from today's cautious testing posture toward
production autonomy without a rewrite.

## 1. The realization

The system should strive to **analyse the situation, decide what tasks exist, and solve them
itself** — turning to the operator (Mom) only when confidence is low, data is genuinely missing, or
the configured autonomy is deliberately conservative. "Ask the operator" is not a *kind of work*.
It is one *way to take the next step* on a piece of work that exists regardless.

So the load-bearing decomposition is:

> **A task is a node (the WHAT). How it advances is an edge (the HOW).** "Ask the human" is one
> possible value of that edge — computed each cycle, not baked into the task.

This dissolves the question Dima raised ("a data gap on an employee — is a human needed or not?").
It stops being a question *about the task* and becomes a question *about the task's current edge*,
which the runtime re-evaluates as data, confidence, and settings change.

## 2. This is a refinement of what already exists — not a new axis

The engine **already** separates "what the task is" from "its interaction state":

- `task_type` = the operation (`payroll_pph21_bpjs`, `tax_pay`, `period_close`, …). Stable.
- `status` ∈ `active | awaiting | deferred` = interaction state. Explicitly **not** carried by
  `task_type` (INSTRUCTIONS §0.4: "the interaction state is carried by `status`, not by
  `task_type`").
- `assist.confidence` (`низкая | средняя | высокая`) + `assist.updated_at` already ride every
  track and render under its title.
- `client_followup` («Запрос у клиента») is already the pattern "the resolving step is a question"
  — for the **client** audience. A standing reusable bucket (`_REUSABLE_OP_TYPES`), normalized by
  migrations `0014`/`0015`, classified by `_task_classifier`.
- The overview already renders an `auto_close_widget`.

What is missing is small and specific: making **"who acts next" an explicit, computed routing**
instead of the implicit always-operator default, and adding the operator-facing twin of
`client_followup`.

## 3. `resolution_mode` — the computed edge (PROPOSED)

A derived routing on each open task, recomputed every runtime cycle (never hand-set):

```
resolution_mode ∈ { auto | needs_operator | wait_external }
```

- `auto` — the runtime can and should take the next step itself (reversible, above confidence
  threshold). It does, and logs it.
- `needs_operator` — the next step requires the operator's judgment or approval. Surfaces in the
  unblock queue (§5). This is the operator-audience twin of `client_followup`; call the existing
  client case `needs_client`. Same mechanism, different audience.
- `wait_external` — blocked on data/a counterparty the system is already chasing; nothing for the
  operator to do yet. Maps onto today's `status: awaiting`.

`resolution_mode` is **derived, like every reverse link** (the engine's law: dashboards/derivations
are pure functions of state; ENTITY-LINKING "the link's single source of truth lives on the task").
It is computed from: the task's `assist.confidence`, the **reversibility class** of its next action
(§4), the unmet `blocked_by` dependencies, and the instance autonomy threshold (§4). Because it is
derived, it cannot drift and needs no lint to keep it honest — and the **same task flips edges for
free** when a collector lands the missing datum or the operator raises autonomy.

Do **not** mint a separate "human task" entity per gap — that would explode the plan with
duplicates and reintroduce two sources of truth. One task; the edge moves.

## 4. The autonomy gate is two-dimensional (confidence × reversibility)

A single "0–100% autonomy" slider is a trap. The gate must weigh two axes:

1. **Confidence** — `assist.confidence`. Already present; the calibration target (§6).
2. **Reversibility of the next action** — its blast radius:
   - **reversible** — a `state` write. Every write goes through `state_ops` (backup + atomic +
     UTF-8), so it is *auditable and undoable*. Safe to automate early.
   - **irreversible** — send to client, pay, browser submit. The three existing approval gates
     (safety-rules) live here.

The autonomy **level** is then a threshold map, not a number:

```
reversible   action  +  confidence ≥ θ_reversible    → auto
irreversible action                                  → needs_operator  (always)
otherwise                                            → needs_operator
missing input the system is fetching                 → wait_external
```

"Full production autonomy" therefore is **not** "the system does everything". It is "the system
does everything *reversible* above the confidence bar, and **always stops before the irreversible**
(send / pay / submit)". The dial lowers `θ_reversible`; the irreversible gate never opens to auto.
Today's posture = high `θ` (almost everything queues) — deliberately, for §6.

## 5. The overview = three lanes + a "where we stopped" summary

Maps Dima's sketch onto three views answering three different questions:

1. **Unblock queue** — *"what does the system need from you right now to keep moving?"* Only
   `needs_operator` tasks, ordered by urgency, each with a one-/two-click quick action carrying its
   reasoning (the `assist.actions` + «Разобрать» prompt-modal pattern already built). This is the
   push-notification source. Empty = a normal, healthy day.
2. **Plan** — *"what does the system know is coming?"* Future tasks, dependencies, waves. Already
   built (`_plan_*`); this lane is visibility, not action.
3. **Execution log (job runner)** — *"what did the system do on its own while you were away?"*
   Auto-closed/updated tasks. This is **not** decoration: it is the **trust ledger and the undo
   surface**. It is what lets Dima raise the dial empirically — he can audit that auto-decisions
   were right — and, because every auto-write went through `state_ops`, each entry is reversible.
   Extends the existing `auto_close_widget`.

Plus a short **"where we stopped"** summary: the nearest urgent nodes whose edge is currently
`needs_operator` under the active settings — the precise places a human is the bottleneck *now*.

## 6. Why low-autonomy-first is correct (not just caution)

The whole gate rests on the system **honestly knowing when it is unsure**. Two failure modes:

- **Over-confidence** → silent wrong auto-actions. The dangerous one, because it is invisible.
- **Under-confidence** → everything queues; zero autonomy gain.

Starting at a high `θ` is therefore not timidity — it is **collecting calibration data**. The
execution log is the dataset: as it accumulates correct auto-decisions, `θ_reversible` is lowered
on evidence. You build the trust ledger *before* you trust it.

## 7. Worked case — payroll, end to end

A data gap on an employee (no gross, or `pph_method: null` like the expat `emp_elizaveta`):

1. A task **is created regardless** — `payroll_pph21_bpjs` for the period, `refs:
   [{employee}, {period}]` (ENTITY-LINKING standard).
2. The runtime computes its edge. Can it fetch the gross itself (the `documents` collector off the
   payroll sheet) and compute via `ter.yaml`? Reversible + confident → `auto`: it computes, writes
   the per-employee line, logs it.
3. Where it can't, or confidence is low because the *basis* is contested (expat → annualisasi, not
   flat TER; getting it wrong breaks incumbent parity — high cost of error) → edge `needs_operator`:
   the task surfaces in the unblock queue with reasoning and a recommended action.
4. A collector lands the datum, or Dima raises autonomy → the **same task** flips back to `auto`.
   Node unchanged; only the edge moved.

This is exactly the `status: awaiting → active` precedent generalized: who acts next becomes an
explicit, computed routing rather than an implicit always-operator default.

## 8. Open decisions (need a call before code)

- **Confidence calibration** (§6) — the hardest. How `assist.confidence` is set, and how the
  execution log feeds threshold tuning. Everything rests here.
- **`resolution_mode`: derived-only, or persisted snapshot?** Leaning **derived** (engine law, no
  drift). A persisted snapshot would need a lint like `risk_link`. Decide before wiring.
- **Reversibility class — where declared?** Per `task_type`? Per action in `assist.actions`? A
  small static table vs a field on each action. Per-action is finer but heavier.
- **`θ` granularity** — one instance-wide threshold, or per `task_type` / per jurisdiction? Start
  global; leave room to refine.
- **Notification policy** — what promotes a `needs_operator` task to an actual push vs. waiting for
  the next dashboard open (urgency, deadline proximity).

## 9. What this does NOT change

- No new top-level schema and no migration to start: `resolution_mode` is derived; `status`,
  `assist.confidence`, `refs`, and `_task_classifier` already exist. First slices are render +
  policy (what the runtime reads) — the behavioural-change rule applies: edit the markdown the
  runtime reads and verify by scenario, not just by green gates.
- The three irreversible approval gates stay exactly as they are.
- One mechanism, not N: `needs_operator` / `needs_client` are the same routing at different
  audiences — the `client_followup` pattern, generalized, not duplicated.
