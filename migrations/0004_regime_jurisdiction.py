"""Add `jurisdiction` to regime.json (default "ru").

Phase 2 makes tax-regime logic pluggable per client: the engine no longer
assumes RU but reads a jurisdiction pack (jurisdictions/<code>/) selected by
`regime.jurisdiction`. The reader defaults a missing field to "ru", so this
migration is behaviourally a no-op for existing clients — it simply makes the
field explicit so a client can later be re-tagged (e.g. "id") without ambiguity,
and so state is self-describing rather than relying on an implicit default.

    regime.json -> jurisdiction: "ru"   (added only where absent)

Additive and idempotent: a client that already carries a `jurisdiction` value is
left untouched, so re-running changes nothing and an already-"id" client is never
reset to "ru". Schema-level, no client names, no per-client business logic.
"""

ID = "0004"
DESCRIPTION = "regime: add jurisdiction (default 'ru') where absent - additive, behaviour-preserving"

DEFAULT_JURISDICTION = "ru"


def up(api):
    def fix(client_id, data):
        if data.get("jurisdiction") not in (None, ""):
            return False, ""  # already explicit (e.g. "ru" or "id") - idempotent
        data["jurisdiction"] = DEFAULT_JURISDICTION
        return True, "added jurisdiction=%s" % DEFAULT_JURISDICTION

    api.for_each_client("regime.json", fix)
