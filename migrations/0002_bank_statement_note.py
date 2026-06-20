"""Unify the free-text bank-statement note onto one key.

The free-text note about how/when bank statements arrive was stored as
`bank_statement_frequency_note` in some state and as `bank_statement_notes` in
others. Canonical name: `bank_statement_notes`.

NOTE: this migration only touches the free-text NOTE field. The structured
fields `bank_statement_frequency` (a cadence value) and `bank_statement_trigger`
(a trigger value) are DISTINCT fields and are intentionally left alone.

Schema-level and idempotent. No client names.
"""

ID = "0002"
DESCRIPTION = "behavior: bank_statement_frequency_note -> bank_statement_notes (free-text note only)"


def up(api):
    api.rename_key("behavior.json", "bank_statement_frequency_note", "bank_statement_notes",
                   on_conflict="append")
