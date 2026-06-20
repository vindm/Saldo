"""Unify the free-text 'registration date needs attention' note onto one key.

Some state carried this note as `reg_date_uncertainty`, others as
`reg_date_note`. Both are free text about the client's registration date; having
two names means any reader keyed on one silently misses the other. Canonical
name: `reg_date_note`.

Schema-level and idempotent: applies to every client whose identity.json still
has `reg_date_uncertainty`, leaves all others untouched. No client names here.
"""

ID = "0001"
DESCRIPTION = "identity: reg_date_uncertainty -> reg_date_note (one canonical reg-date note)"


def up(api):
    api.rename_key("identity.json", "reg_date_uncertainty", "reg_date_note",
                   on_conflict="append")
