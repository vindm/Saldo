"""Add the optional `payment_ref` slot to every `tax_calendar_<year>[]` entry.

The proof that a tax was paid — a receipt / transaction reference — is what closes a
payment deadline and what pre-fills the annual return ("confirm all N periods are present
and paid"). This is **not** an Indonesia-only idea: every jurisdiction issues such a
reference. The term differs — Indonesia's **NTPN** (nomor transaksi penerimaan negara),
Russia's **платёжное поручение №** / the ЕНС operation (УИН identifies the *charge*, not
the payment) — but the slot is the same. So the **state field is jurisdiction-neutral**
(`payment_ref`); the local term lives in the pack glossary, not the schema.

Until now a calendar entry could be flipped to `status:paid` + `paid_at`, but the receipt
reference itself was lost — and the checklists' *"record the receipt against the period"*
had nowhere to land. This opens that slot on each `tax_calendar_<year>[]` entry:

    payment_ref : null   # the payment-proof reference(s) for this entry. A string for a
                         # single billing, or a list when the date bundles several (e.g.
                         # ID PP55 + PPh 21 + unifikasi each get their own NTPN). The
                         # jurisdiction term (NTPN / платёжное поручение) is a gloss only.
                         # null -> not yet captured.

Additive and behaviour-preserving: every backfilled value is `null` and no engine Python
reads the key yet, so dashboards are byte-identical. The consumer is the **documents
collector** (per its SKILL): when a payment receipt for a period lands in the client's
Drive folder, it matches the entry, sets `status:paid` + `paid_at` + `payment_ref`, and
the deadline_monitor then drops the now-terminal entry automatically — closing the loop
that deadline_monitor (the surfacing half) opens.

Idempotent and self-healing: an entry that already carries `payment_ref` is left
untouched; a legacy `ntpn` key (from an earlier draft of this migration) is **renamed** to
`payment_ref`, carrying its value; otherwise the null slot is added. Only missing keys are
added, so a partial re-run is safe and a fully-applied re-run is a no-op. Walks the
year-suffixed keys generically (`tax_calendar_2025`, `tax_calendar_2026`, …) so it ages
with the data. Schema-level — keyed purely on the `tax_calendar_*`/`payment_ref`/`ntpn`
field names, no client names, no amounts, no receipt numbers — ZERO real data. Mirrors the
additive slot pattern of 0017 (`financials.periods[]`) / 0011 / 0013.
"""

ID = "0018"
DESCRIPTION = ("financials.tax_calendar_<year>[]: add payment_ref (null) where absent "
               "(rename any legacy ntpn -> payment_ref) — the jurisdiction-neutral "
               "payment-proof reference slot. Additive, behaviour-preserving.")


def up(api):
    def fix(client_id, data):
        if not isinstance(data, dict):
            return False, ""
        touched = 0
        keys = 0
        for key, val in data.items():
            if not (key.startswith("tax_calendar_") and isinstance(val, list)):
                continue
            keys += 1
            for entry in val:
                if not isinstance(entry, dict):
                    continue
                if "payment_ref" in entry:
                    continue  # already migrated — idempotent
                if "ntpn" in entry:
                    entry["payment_ref"] = entry.pop("ntpn")  # rename legacy slot, keep value
                    touched += 1
                else:
                    entry["payment_ref"] = None
                    touched += 1
        if not touched:
            return False, ""  # every entry already has the slot — idempotent no-op
        return True, ("tax_calendar_*[]: +payment_ref (null) / ntpn->payment_ref on %d "
                      "entr(y/ies) across %d calendar year(s)" % (touched, keys))

    api.for_each_client("financials.json", fix)
