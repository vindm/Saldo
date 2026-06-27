"""Give every quick_access entry a structured `category` (icon-by-type, jurisdiction-neutral).

The «Быстрые доступы» panel picks its tile icon from the service. Until now that
was keyed on a hardcoded RU-centric slug map in the renderer, so newer / non-RU
services (Coretax, EDABU, BPJS, Moka POS, OSS, Google Drive) fell back to a
generic arrow — the icon was not matched by type. The durable fix is a STRUCTURED
field: each entry carries a jurisdiction-neutral `category` (bank / pos /
tax_authority / social_insurance / portal / storage / mail / messenger /
acquiring / accounting / collection / ofd / assistant), and the renderer picks
the icon from the category (`engine/_client_dashboard_v2.py → _qa_icon_name`,
which prefers `category` over the slug). After this, a new service in ANY
jurisdiction renders a type-matched icon with no engine code change — it only
needs a category, which the runtime can assign.

Deterministic part: where the service slug is known public vocabulary, set the
category by the slug→category map below (additive, idempotent). Also retire the
stale, renderer-ignored `icon` field (e.g. a bogus "building-bank" that resolved
to a blank dot) into `icon_legacy` (lossless). The RESIDUE — a service whose slug
is not in the map — is left for the runtime to classify by reading the entry
(see RUNTIME_PASS / migrations/TASK_CLASSIFIER.md). Same shape as the task
classifier, on a different field.

Additive + behaviour-preserving: every category maps to the SAME icon the slug
map already produces for known services, so the rendered icon does not change for
them; only previously-arrow (unknown) services improve, and only once a category
is set. Schema-level — keyed on service slugs + category vocabulary, no client
names, no per-client logic; zero real data.

    tasks irrelevant; operates on accounts.json → quick_access[].category
        (+ icon -> icon_legacy where a stale icon field is present)
"""

ID = "0020"
DESCRIPTION = ("quick_access: add structured category (icon-by-type, jurisdiction-neutral) "
               "from the service slug; retire the stale icon field to icon_legacy")

# Public service-slug → jurisdiction-neutral category. Categories must match the
# keys of engine/_client_dashboard_v2._QA_CAT_ICONS so the icon is type-matched.
_SLUG_CATEGORY = {
    "bank": "bank",
    "fns": "tax_authority", "coretax": "tax_authority",
    "ofd": "ofd",
    "finkoper": "collection",
    "onec": "accounting", "1c": "accounting",
    "prodamus": "acquiring", "cloudpayments": "acquiring", "ukassa": "acquiring",
    "acquiring": "acquiring",
    "moka": "pos",
    "edabu": "social_insurance", "bpjs_tk": "social_insurance",
    "oss": "portal", "rosstat": "portal",
    "gdrive": "storage",
    "mail": "mail", "email": "mail",
    "tg": "messenger", "whatsapp": "messenger", "max": "messenger",
    "assistant": "assistant",
}


def up(api):
    def fix(client_id, data):
        items = data.get("quick_access")
        if not isinstance(items, list):
            return False, ""
        changed = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            touched = False
            # 1) structured category from a known slug (additive, idempotent)
            if not it.get("category"):
                cat = _SLUG_CATEGORY.get((it.get("service") or "").strip())
                if cat:
                    it["category"] = cat
                    touched = True
            # 2) retire the stale, renderer-ignored `icon` field (lossless)
            if "icon" in it and "icon_legacy" not in it:
                it["icon_legacy"] = it.pop("icon")
                touched = True
            if touched:
                changed += 1
        if not changed:
            return False, ""
        return True, "categorized / cleaned %d quick_access entr(ies)" % changed

    api.for_each_client("accounts.json", fix)


# ---------------------------------------------------------------------------
# AI-side surface (RUNTIME_PASS spec). A slice of the shared classifier pattern
# (migrations/TASK_CLASSIFIER.md) on the quick_access field: up() categorizes
# known slugs; preflight surfaces the residue (an unknown service slug) for the
# runtime to classify by reading the entry, so the icon is type-matched without a
# new slug in the engine map.
# ---------------------------------------------------------------------------

def preflight(api):
    """READ step. Read-only: quick_access entries with no category and an unknown
    service slug — runtime candidates to classify into a category."""
    flags = []
    for cid in api.clients():
        data = api.read(cid, "accounts.json")
        if not isinstance(data, dict):
            continue
        items = data.get("quick_access")
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict) or it.get("category"):
                continue
            slug = (it.get("service") or "").strip()
            if slug in _SLUG_CATEGORY:
                continue  # up() handles a known slug
            flags.append({
                "client": cid,
                "service": slug or None,
                "field": "quick_access[].category",
                "label": (it.get("label") or "")[:120],
                "url": it.get("url"),
                "note": (it.get("note") or "")[:160],
                "kind": "needs_category_classification",
            })
            if len(flags) >= 50:
                return flags
    return flags


RUNTIME_PASS = {
    "intent": (
        "For each flagged quick_access entry, read its label / url / note and assign "
        "the jurisdiction-neutral category that fits (bank / pos / tax_authority / "
        "social_insurance / portal / storage / mail / messenger / acquiring / "
        "accounting / collection / ofd / assistant) per migrations/TASK_CLASSIFIER.md, "
        "so the tile renders a type-matched icon. If the service is genuinely "
        "unclassifiable, LEAVE it (the renderer falls back to a neutral arrow). Do "
        "NOT invent services or change cred_status here — completeness is a separate "
        "review."
    ),
    "scope": "accounts.json -> quick_access[].category",
    "escalate": "on_anomaly",
    "guardrails": [
        "only set category on an entry preflight flagged (unknown slug, no category)",
        "use only the known category vocabulary; never invent a category",
        "leave an unclassifiable service without a category",
        "do not touch cred_status / url / label / add or remove services",
    ],
}

EXPECT = {
    "preflight_max": 15,
    "change_kinds": ["needs_category_classification"],
}

SCENARIO = [
    "On a client cockpit, a quick_access service that had no preset slug now carries "
    "a category and its “Быстрые доступы” tile shows a type-matched icon (not the "
    "generic arrow); known services are unchanged; any stale `icon` field is moved "
    "to `icon_legacy`.",
]
