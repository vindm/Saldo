"""Add the optional `regime.client_facing` block (client-report source of truth).

The owner one-pager (`engine/_owner_report.py`) is the only **client-facing**
surface Saldo renders. Until now it borrowed `regime.business_description` for the
subtitle — but that field is *internal operator prose*: it carries ticket numbers
(`Finkoper #…`), credit codes, open uncertainties (`требуется проверка`) and
recovery-track notes. Sending it to the client leaks the operator's working notes
(the §0.1.a class of problem, one level further out — to the client).

The engine change splits the two audiences: the client report now reads a
dedicated, client-clean field and never touches `business_description`. This
migration declares that field's slot so the operator (and the runtime) have a
place to author client copy:

    regime.client_facing = {
        "summary":        null,   # operator-authored client subtitle (client's
                                  #   language, ZERO internal notes/ticket numbers/
                                  #   uncertainty). null -> the report derives a
                                  #   neutral line from regime.primary + okved.
        "turnover_scope": null,   # optional short caveat on what the headline
                                  #   turnover covers, e.g. "по основному счёту".
                                  #   null -> no caveat shown.
    }

Additive and behaviour-preserving: the engine treats a null `summary` exactly as
"derive", which reproduces a clean subtitle without any stored prose — so applying
this migration changes no rendered output on its own. It only opens the slot;
the runtime/operator fill it later (those writes are real data and never ship
here). Mirrors the additive pattern of 0003 (`ts`) and 0004 (`jurisdiction`).

Idempotent: re-running finds `client_facing` already present and skips. Schema-
level — keyed on the `regime`/`client_facing` field names, no client names — so
the file carries ZERO real data and is safe in the public repo.
"""

ID = "0011"
DESCRIPTION = ("regime: add optional client_facing {summary, turnover_scope} where "
               "absent (client-report source; null = engine derives). Additive, "
               "behaviour-preserving.")

_DEFAULT = {"summary": None, "turnover_scope": None}


def up(api):
    def fix(client_id, data):
        if not isinstance(data, dict):
            return False, ""
        if "client_facing" in data:
            return False, ""  # already present — idempotent no-op
        # Insert a fresh copy so clients never share a dict instance.
        data["client_facing"] = dict(_DEFAULT)
        return True, "added regime.client_facing {summary, turnover_scope} (null)"

    api.for_each_client("regime.json", fix)
