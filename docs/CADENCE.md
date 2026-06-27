# Cadence — derived from the regime, not from a per-client flag

> Status: **landed** (2026-06-26). Step 1 (the DECLARATION layer) is **landed + verified**:
> `jurisdictions/ru/obligations.yaml` now declares the streams below. Promotion was proven
> behaviour-preserving on `saldo-migrated_data` — all 45 pages byte-identical modulo the
> wall-clock timestamp; generate 0/0, state_lint 0 error / 0 warn / 26 info (unchanged from
> baseline), integrity clean. Step 1b (the DERIVATION) is also **landed + tested**:
> `engine/_cadence.py` — pure `resolve_bookkeeping_cadence(obligations, state, period)` with
> as-of-period predicate resolution — and `tests/test_cadence.py` (9/9). Verified on
> saldo-migrated_data (18 clients, 0 errors: 15 USN -> quarterly, 2 AUSN -> monthly, 1 id-client
> -> None by design) and confirmed inert for the render (imported by nothing). All CONSUMERS now landed: the render (cadence sub-bands in the
> timeline + a «Доска» board view, `engine/_periods.py`), the runtime rule that the task generator
> derives cadence from the regime not the flag (`policies/INSTRUCTIONS.md §0.5`), the
> `delivery_looser_than_cadence` lint, and scenario **S28**. The planned field-retiring migration was
> REASSESSED as largely unwarranted — see "How this lands" §2.) Step 3 (the LINT) is **landed + tested**: `_cadence.delivery_cadence` /
> `is_delivery_looser` (unit-tested) + `state_lint.py` H5 `delivery_looser_than_cadence` — verified
> 0/0/26 on saldo-migrated_data (no false positives) and fires on a synthetic monthly-floor client
> delivering quarterly. See "How this lands".

## The smell

The Periods page showed a half-year row (`1 П/Г 2026`) and quarter rows (`2 Кв 2026`) inside
the **monthly** bookkeeping cycle ("Учётный цикл"). First read: a data bug. It is not. The tasks
are honest — they are genuinely quarter/half-year-scoped bookkeeping batches:

- a `USN income` client whose bank statements arrive **quarterly**, so collection + posting is a
  quarterly act (books only need to be ready for the quarterly advance);
- a newly-onboarded `USN income` client whose first posting covers H1 as a catch-up batch.

The real defect is in the **model**, not the data:

1. `monthly_close.yaml` hardcodes `cadence: monthly`. The bookkeeping conveyor is treated as
   always-monthly, so a quarterly batch looks misplaced under it.
2. The cadence's source of truth is a per-client flag (`behavior.json → bank_statement_frequency`)
   that **no engine code reads** (`grep` over `engine/` returns nothing) — it is an instruction the
   AI updater is meant to honour. Stored that way it looks like a client *preference* ("the client
   likes quarterly"), when it is actually a *consequence of the tax regime*.

Tax/reporting cadence is fixed by **law** (regime + activity), never by client whim. Bookkeeping
cadence is **derived** from it. This doc makes that explicit.

## The model

A client has one or more **obligation streams**, each with a legally-fixed cadence:

| Regime / fact            | Stream            | Cadence (RU)                         |
|--------------------------|-------------------|--------------------------------------|
| USN (income / inc−exp)   | income tax        | quarterly advances (Q1→H1→9M) + annual return |
| AUSN                     | income tax        | monthly (bank computes), no annual return |
| OSNO, or USN over threshold | VAT            | quarterly                            |
| has employees            | payroll           | monthly (НДФЛ/взносы/перс. свед.) + quarterly РСВ/6-НДФЛ |
| active patent (PSN)      | patent payment    | per patent term (1–12 months)        |

The **bookkeeping conveyor** (collect → post → close → audit) has **no legal deadline of its own**.
Its required frequency is the tightest downstream consumer:

```
active_streams      = obligations whose `applies_when` holds for the client in the period
bookkeeping_cadence = min_period(active_streams)        # monthly < quarterly < semester < annual
```

You must have the books ready for the **soonest** filing — never less often than that, optionally
more often (volume). So:

- `USN income`, no staff → only stream is the quarterly advance → **quarterly** books. (Our two
  clients. Quarterly is the legal floor, not a preference.)
- `USN income` **+ employees** → monthly payroll stream switches on → **monthly** books, regardless
  of USN being quarterly.
- `AUSN` → monthly tax → **monthly** books.

Subtlety to keep: the bookkeeping period is **incremental** (post this quarter's documents) while the
USN advance is **cumulative** year-to-date (Q1 → H1 → 9M). They align in cadence but are not the same
period object — bookkeeping cadence is its own derived value, aligned to but distinct from the filing
schedule.

## 1 · Where cadence is declared (pack)

This pattern **already exists for `id`**: `jurisdictions/id/obligations.yaml` declares recurring
obligations with `cadence` / `cadence_by_scale`; the engine *derives* each client's occurrences
(deadline_monitor materializes them into `tax_calendar_<year>`; `state_lint.py` checks them via
`obligation_cadence_mismatch`). Its own header: *"any jurisdiction declares the same."* RU simply
never authored an `obligations.yaml` — so its cadence leaked into the per-client flag.

The fix is **pure pack data** (no engine Python, no migration): `jurisdictions/ru/obligations.yaml`
(landed 2026-06-26) declares the streams above. And `monthly_close.yaml`
**stops hardcoding `cadence: monthly`** — the bookkeeping cadence becomes derived, not declared.

`regimes.yaml` stays display-only (it maps regime → label string); cadence lives in `obligations.yaml`.

## 2 · How the client inherits it

The binding already exists: `state/regime.json → primary.type` + `jurisdiction`. Nothing new to store.
The engine derives, as a **pure function** of `(regime + client facts: has_employees / vat_liable /
active patents) × pack.obligations`:

- the set of active streams and each stream's cadence + periods,
- `bookkeeping_cadence = min_period(active_streams)`.

Per `migrations/RUNTIME_PASS_SPEC.md` (structure → deterministic, meaning → runtime):

- **Declare + derive = deterministic.** The regime→cadence table and the min-period resolution are a
  pure function of state + pack. The engine computes them at generate/render time.
- **Judge = runtime.** Tightening below the legal floor for volume, and resolving an unsettled
  onboarding client, are judgments the AI makes from policy + client state, written with a rationale.

## 3 · Disposition of `bank_statement_frequency`

The flag conflates two different facts:

- **(a) work cadence** — how often the books must be done. This is now *derived* (§2), not stored.
  For the quarterly USN client the derived value *equals* what the flag said, so the flag is
  redundant, not authoritative.
- **(b) client logistics** — how often the client actually delivers statements. A real operational
  fact — keep it (`bank_statement_trigger` + the free-text note), but make it **answerable to (a)**.

New lint `delivery_looser_than_cadence`: a client whose statements arrive **less often** than the
derived cadence is flagged (you cannot post monthly on quarterly statements). Quarterly delivery for a
quarterly client → OK. Quarterly delivery for a `USN + employees` (monthly floor) client → warning.

Migration: retire `bank_statement_frequency` as a source of truth. If kept for a transition, a lint
asserts `flag == derived_cadence` so it can never silently contradict the regime. The trigger and note
survive as logistics + rationale. This reshapes state → a versioned migration (behaviour-preserving
where possible, zero real data, proven on `saldo-migrated_data`).

## Edge cases

- **Employees appear mid-year** → monthly payroll stream switches on → bookkeeping cadence tightens to
  monthly *from that period*. Cadence is **as-of-period (time-varying)**, not a static client attribute.
- **USN crosses the VAT threshold** (2025+) → a quarterly VAT stream switches on. (Same VAT/PKP path
  gap already noted for `id`; RU needs it too.)
- **PSN** → cadence follows each patent's term — not a clean monthly/quarterly enum. Reinforces that
  cadence is **per-stream**, and the bookkeeping floor is `min` across streams.
- **Onboarding** (logistics not yet settled) → floor is known from the regime (e.g. quarterly from USN);
  delivery is flagged TBD as a followup, not blocked.
- **Regime change mid-year** (e.g. loses AUSN → moves to USN) → a cadence break on the timeline.

## Render implications (secondary)

Once cadence is regime-derived:

- The bookkeeping section stays **cadence-neutral** ("Учётный цикл" / "Ведение учёта"). Renaming it to
  "Закрытие месяца" is **rejected** — the conveyor is not monthly for quarterly clients; a quarter batch
  under a "month close" header would be *more* misleading.
- Each period row carries a **cadence chip** (monthly / quarterly / semester) so the eye reads why a row
  is not monthly. The quarter/H1 rows are expected, not phantom.
- The generic tax bucket "Налоги: квартал / год" is a separate, legitimate cleanup: split into cadence
  sub-bands (Квартал / Полугодие / Год), each with its own stage set — render-only, no state change.
- Optional follow-up: for a fully-quarterly client, show the bookkeeping quarter and the tax quarter as
  one coherent quarterly pipeline instead of two cards. Not core.

## How this lands (discipline)

1. **Pack authoring** — `jurisdictions/ru/obligations.yaml` + drop `cadence: monthly` from
   `monthly_close.yaml`. Pure data, **no migration**.
2. **State reshape** — REASSESSED (2026-06-26): largely unwarranted. `bank_statement_frequency` is
   never read by Python (the work cadence is derived) and remains as a delivery-logistics fact made
   answerable by the H5 lint — nothing to delete. `has_employees` is a primary declaration to keep;
   `has_patent` is vestigial (unset on the snapshot). So no lossy field-retiring migration. Any future
   migration here is optional cleanup (drop the dead `has_patent`, or add an additive `cadence_override`
   slot) — additive, behaviour-preserving, proven on `saldo-migrated_data`.
3. **Behaviour change** — the AI updater now derives cadence from `obligations.yaml`, not the flag →
   verify by **scenario** (`tests/runtime_scenarios/`): a `USN income` client resolves to quarterly
   bookkeeping from its regime; a `USN + employees` client resolves to monthly; a quarterly-delivery
   client on a monthly floor trips the lint. Resolving unsettled / override clients is judgment on
   meaning → a migration **RUNTIME_PASS**.
4. **Lints** — add `delivery_looser_than_cadence`; extend the existing `obligation_cadence_mismatch`
   coverage to the RU streams.

## Predicate resolution — three tiers (fact derives, narrative prompts, override decides)

The `applies_when` predicates (`has_employees`, `vat_liable`, `has_active_patent`) and the
bookkeeping cadence they drive are **derived, not stored**, and they resolve **as-of-period** —
the facts are dynamic (a sole proprietor may hire mid-year; turnover may cross the VAT threshold).
The resolver is `resolve(client, period)`, evaluating each predicate against structured state as of
that period (roster hire dates, turnover-to-date vs threshold, patent term), never against a global
client boolean. So a client who hires in August is quarterly Jan–Jul and monthly from August.

The test for store-vs-derive is **"conclusion or primary fact?"** A value determined by other state
is a conclusion → derive it. A value that is an input, a decision, or evidence found nowhere else is
a primary fact → store it. The drift smell was `bank_statement_frequency` *treated as the work
cadence*; but it is also a real delivery-logistics fact, so it stays (reclassified, made answerable by
the lint), not deleted. The `regime.json` booleans turned out NOT to be caches when checked against the
data (2026-06-26): `has_employees` is the operator's primary DECLARATION, reconciled to the roster by an
existing lint (the roster may lag it, so it carries information the roster does not — keep it; the cadence
derivation honours it as a fallback when the roster is empty), and `has_patent` is vestigial (unset in
practice — the live signal is the `patents` list). So the roster / thresholds / patents are the structured
facts, with `has_employees` a kept declaration above them.

Three tiers, kept distinct:

1. **Structured state** (roster, thresholds, patents) — the cadence derivation reads ONLY this,
   as-of-period. A hunch never flips the cadence. Enforced by the JSON-first rule from `0013`: the
   engine never parses `mental_model.md` for behaviour — and a legal cadence floor is behaviour.
2. **Narrative** (`mental_model` -> `assist.hypothesis`) — soft, leading, not-yet-structured
   knowledge ("looks like they are hiring", "turnover trending toward the VAT threshold"). Its
   output is a **prompt / check**, not a behaviour change: "looks like hiring -> confirm and add to
   the roster." The hire flips the cadence only once it is a roster record. The hunch drives the
   *check*; the fact drives the *behaviour*.
3. **Explicit override** — the one value worth storing as a new fact: a human DECISION not derivable
   from law (e.g. "keep monthly books though USN allows quarterly", for volume). A `cadence_override`,
   **tighten-only**, with a rationale. Primary information, not a cache.

The "intermediate / temporary status" is real, but it is tier 2 (narrative -> prompt) and optionally
tier 3 (override decision) — never a cached `has_employees` boolean.

## Open questions

- Should the bookkeeping conveyor and the tax cycle merge into one timeline when their cadences
  coincide (a fully-quarterly client), or always stay two cycles?
