"""Add the per-period parity + turnover-provenance slots to `financials.periods[]`.

Two related gaps in how a month is closed today:

1. **Turnover has no single source of truth.** The period's gross turnover lands in
   `periods[].turnover_idr`, but *how* it was derived — which sources, and whether the
   cash takings were reconciled against the POS (Moka vs cash report, the recurring
   completeness failure mode) — is not recorded. The 0.5% final tax is computed on the
   whole turnover, so an unreconciled cash figure silently understates the base.

2. **Parity with the incumbent is not first-class.** While the practice shadows the
   prior accountant, every computed amount is supposed to be checked against the
   accountant's issued billing before the operator acts — but the result of that check
   lives only in free-text `notes` ("сверен … паритет PASS"). Nothing structured lets a
   view show a period as *reconciled* vs *not yet*, so "done" can't be gated on it.

This migration opens four additive slots on every `periods[]` entry:

    turnover_source : null   # how turnover was derived / reconciled, e.g.
                             #   "moka+cash" | "bank+moka+cash". null -> unrecorded.
    cash_reconciled : null   # POS (Moka) takings reconciled to the cash report within
                             #   tolerance for the period? true/false. null -> not checked.
    parity_status   : null   # "pending" | "pass" | "fail" — result of checking the
                             #   computed taxes against the incumbent's issued billing.
                             #   null -> not recorded.
    parity_ref      : null   # the reference used for the parity check (e.g. the
                             #   incumbent billing id). null -> none.

Additive and behaviour-preserving: every backfilled value is `null`, which every
consumer treats as "unrecorded" — applying this migration changes no rendered output on
its own. It only opens the slots; the runtime/operator fill them per
`jurisdictions/id/checklists/monthly-close-pt.md` (Stage 1 writes turnover_source +
cash_reconciled; the parity step sets parity_status/parity_ref before a period is
considered closed). Those later writes are real data and never ship here.

Idempotent: an entry that already carries a key keeps its value; only missing keys are
added, so a partial re-run is safe and a fully-applied re-run is a no-op. Schema-level —
keyed purely on the `financials`/`periods` field names, no client names, no amounts — so
the file carries ZERO real data and is safe in the public repo. Mirrors the additive
pattern of 0003 (`ts`), 0004 (`jurisdiction`) and 0011 (`regime.client_facing`).
"""

ID = "0017"
DESCRIPTION = ("financials.periods[]: add turnover_source, cash_reconciled, parity_status, "
               "parity_ref (null) where absent. Additive, behaviour-preserving.")

_NEW_KEYS = ("turnover_source", "cash_reconciled", "parity_status", "parity_ref")


def up(api):
    def fix(client_id, data):
        if not isinstance(data, dict):
            return False, ""
        periods = data.get("periods")
        if not isinstance(periods, list):
            return False, ""
        touched = 0
        for entry in periods:
            if not isinstance(entry, dict):
                continue
            added = False
            for key in _NEW_KEYS:
                if key not in entry:
                    entry[key] = None
                    added = True
            if added:
                touched += 1
        if not touched:
            return False, ""  # every period already has the slots — idempotent no-op
        return True, (
            "financials.periods[]: +turnover_source/+cash_reconciled/+parity_status/"
            "+parity_ref (null) on %d period(s)" % touched
        )

    api.for_each_client("financials.json", fix)
