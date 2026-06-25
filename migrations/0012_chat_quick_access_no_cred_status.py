"""Drop the stale `cred_status` from `by_chat` messenger quick-access entries.

`by_chat` providers (Telegram / WhatsApp / Max) have **session-level access only** — one
logged-in operator account reaches every chat and channel by search (username / phone /
peer-id). An individual chat or channel is a **routing pointer, not a credentialed access
point**, so a per-chat `cred_status` is meaningless: it modelled Telegram as if it were a
bank login. In the data that surfaced as spurious «уточнить» chips on TG/WhatsApp/Max cards
(e.g. a client's "TG-канал — обмен документами" flagged `cred_status: unknown` — there is
nothing to request; the operator is simply a member).

The render already ignores `cred_status` for these entries (`engine/_client_dashboard_v2.py`
→ `render_client_quick_access`, suppress the access chip for messenger services/URLs). This
migration cleans the **data** to match: it removes `cred_status` from every `quick_access`
entry that is a messenger chat — by `service` (`tg`/`telegram`/`whatsapp`/`wa`/`max`) or by a
messenger `url` (`telegram.org`, `t.me`, `whatsapp.com`, `wa.me`, `max.ru`).

Behaviour-preserving **given the render change** (the chip is already suppressed for these
entries, so removing the now-ignored field changes no rendered output); it just keeps the
state honest. Idempotent — re-running finds no `cred_status` on chat entries and skips.
Schema-level: keyed on the `quick_access`/`service`/`url` field names and public messenger
domains, **no client names** — zero real data, safe in the public repo. Mirrors the
content-normalization pattern of 0007–0010.

See `connectors/_chat_collector.md` / `connectors/_sources.md` ("Access is session-level,
not per-chat").
"""

ID = "0012"
DESCRIPTION = ("accounts.quick_access: remove stale cred_status from by_chat messenger "
               "entries (tg/whatsapp/max — session-level access, no per-chat credential). "
               "Behaviour-preserving with the render change; idempotent.")

_CHAT_SVC = {"tg", "telegram", "whatsapp", "wa", "max"}
_CHAT_DOM = ("telegram.org", "t.me", "whatsapp.com", "wa.me", "max.ru")


def up(api):
    def fix(client_id, data):
        if not isinstance(data, dict):
            return False, ""
        qa = data.get("quick_access")
        if not isinstance(qa, list):
            return False, ""
        n = 0
        for it in qa:
            if not isinstance(it, dict) or "cred_status" not in it:
                continue
            svc = str(it.get("service") or "").lower()
            url = str(it.get("url") or "").lower()
            is_chat = svc in _CHAT_SVC or any(d in url for d in _CHAT_DOM)
            if is_chat:
                it.pop("cred_status", None)
                n += 1
        if n:
            return True, "removed cred_status from {} by_chat quick_access entr{}".format(
                n, "y" if n == 1 else "ies")
        return False, ""

    api.for_each_client("accounts.json", fix)
