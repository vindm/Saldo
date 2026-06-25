"""Backfill & normalize quick_access (the client's external-service map) — RU.

The quick-access panel is meant to be the client's COMPLETE map of external
services (bank, OFD, acquiring, 1C, Finkoper, FNS, Rosstat), each with an access
status the dashboard renders as a badge. Two things had drifted in stored state:
  - many entries carried cred_status "na"/null  -> the dashboard shows no badge;
  - some services the client clearly uses (acquiring, 1C) had no entry at all.

For RU-jurisdiction clients this migration deterministically:
  1) normalizes a missing/"na" cred_status to a derived value — "connected" when a
     positive signal exists in the client's OWN state (the practice's Finkoper, a
     1C:Fresh base, a bank with full access), else "unknown" (the dashboard then
     shows an "уточнить" badge prompting a real status);
  2) backfills entries for services the client clearly has but that are absent from
     quick_access, derived from existing structured fields.

It never invents access the data doesn't show, never overwrites an explicit status,
and is idempotent (re-running changes nothing). Labels/notes are produced through the
engine locale layer (t()), so an EN instance gets English and a RU instance Russian.
Schema-level: no client names, no per-client business logic — each client's services
come from that client's own state. Non-RU clients are skipped: their service map is
owned by their jurisdiction pack + runtime (policies/INSTRUCTIONS.md §0.1).

The precise status (granted vs request) and human wording stay the runtime's job;
this migration only gives every RU client a complete, badge-bearing skeleton.

    accounts.quick_access[]: cred_status na/null -> derived; + missing services
"""

ID = "0006"
DESCRIPTION = "quick_access: normalize cred_status (na->derived) + backfill RU service map (idempotent)"

# services that are the practice's own tools -> connected when present in state
_DERIVE_CONNECTED = {"finkoper", "onec", "1c"}


def up(api):
    from _strings import t

    def _read(cid, fname):
        try:
            return api._ops.state_read(cid, fname) or {}
        except Exception:
            return {}

    def _has(qa, svc):
        return any(isinstance(e, dict) and e.get("service") == svc for e in qa)

    def fix(client_id, data):
        reg = _read(client_id, "regime.json")
        juris = (str(reg.get("jurisdiction") or "ru").strip().lower()) or "ru"
        if juris != "ru":
            return False, ""                      # other packs own their own map

        qa = data.get("quick_access")
        if not isinstance(qa, list):
            qa = []
            data["quick_access"] = qa
        contour = reg.get("contour") or {}
        bank_access = data.get("bank_access") or {}
        bank_full = bank_access.get("access_level") == "full"
        changed = []

        # 1) normalize missing / "na" cred_status on existing entries
        for e in qa:
            if not isinstance(e, dict):
                continue
            if e.get("cred_status") in (None, "", "na"):
                svc = e.get("service")
                if svc in _DERIVE_CONNECTED or (svc == "bank" and bank_full):
                    e["cred_status"] = "connected"
                else:
                    e["cred_status"] = "unknown"
                changed.append("status:%s" % svc)

        # 2) backfill missing structural services from existing fields
        def add(svc, label, note, cred):
            if _has(qa, svc):
                return
            qa.append({"service": svc, "label": label, "url": None, "note": note,
                       "cred_status": cred, "status": "active"})
            changed.append("add:%s" % svc)

        if str(contour.get("tasks_system") or "").lower() == "finkoper":
            add("finkoper", t("Finkoper — client card"),
                t("Finkoper: tasks, chat, client documents."), "connected")

        if (contour.get("accounting_system_1c") or contour.get("fresh_base_id")) \
                and not (_has(qa, "onec") or _has(qa, "1c")):
            base = contour.get("fresh_base_id")
            add("onec", t("1C:Fresh") + ((" " + str(base)) if base else ""),
                t("1C:Fresh: posting primary docs and reporting."),
                "connected" if base else "unknown")

        bank = bank_access.get("primary_bank")
        if not bank:
            for ba in (data.get("bank_accounts") or []):
                if ba.get("is_primary") and ba.get("bank_name"):
                    bank = ba.get("bank_name")
                    break
        if bank:
            add("bank", t("Bank — portal") + " " + str(bank),
                t("Bank portal: statements and payment orders."),
                "connected" if bank_full else "unknown")

        add("fns", t("FNS — personal cabinet"),
            t("FNS cabinet: ENS reconciliation, notices, demands."), "unknown")

        if data.get("ofd") or (data.get("kassas") or []):
            add("ofd", t("OFD — fiscal data operator"),
                t("OFD cabinet: receipts and cash reports."), "unknown")

        if data.get("acquiring_channels") and not any(
                _has(qa, s) for s in ("acquiring", "prodamus", "cloudpayments", "ukassa")):
            add("acquiring", t("Acquiring"),
                t("Acquiring: reconcile acquiring inflows."), "unknown")

        if reg.get("statotchet"):
            add("rosstat", t("Rosstat — statistics portal"),
                t("Rosstat: statistics reporting."), "unknown")

        if not changed:
            return False, ""
        seen = []
        for c in changed:
            if c not in seen:
                seen.append(c)
        return True, "quick_access: " + ", ".join(seen[:14])

    api.for_each_client("accounts.json", fix)
