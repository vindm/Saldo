# -*- coding: utf-8 -*-
"""_status.py — normalize free-form track statuses to a small canonical vocabulary.

State sometimes carries bespoke status strings (e.g. ``blocked_by_anastasia``,
``scheduled_calc_by_fact``, ``client_notified_08.06_pays_self``). Encoding the
specifics into the status token does not scale and cannot be localized. For
DISPLAY we collapse any raw value to a controlled, localizable set; the
specifics belong in the track's context / type_specific / history, not in the
status token.

This is a DISPLAY-time normalizer (no state is rewritten). Normalizing the
stored values is a separate data-shape change that must ship a migration.
"""
from _strings import t

# Canonical status -> English label (each is also a t() catalog key, so the
# chip localizes with the rest of the chrome).
CANON_LABEL = {
    'active': 'active',
    'in_progress': 'in progress',
    'awaiting': 'waiting',
    'blocked': 'blocked',
    'scheduled': 'scheduled',
    'calculated': 'calculated',
    'paid': 'paid',
    'done': 'done',
    'deferred': 'deferred',
    'dropped': 'dropped',
    'cancelled': 'cancelled',
    'archived': 'archived',
}


def normalize_status(raw):
    """Collapse any raw status string to one canonical token (keyword/prefix
    rules, so unseen variants still bucket sensibly). Empty in -> empty out."""
    s = (raw or '').strip().lower()
    if not s:
        return ''
    if s in CANON_LABEL:
        return s
    # Order matters: more specific signals first.
    if 'cancel' in s:
        return 'cancelled'
    if s.startswith('block'):
        return 'blocked'
    if 'paid' in s:                       # calculated_paid, presumably_paid, paid_by_client_*
        return 'paid'
    if s.startswith('calculated'):
        return 'calculated'
    if s.startswith('scheduled'):
        return 'scheduled'
    if s.startswith('archive'):
        return 'archived'
    if (s.startswith('await') or s.startswith('pending') or 'awaiting' in s
            or 'client_response' in s
            or s in ('unclear', 'decision_required', 'to_check', 'client_zone')):
        return 'awaiting'
    if (s.startswith('dropped') or 'dismiss' in s or 'departed' in s
            or 'departure' in s or 'new_accountant' in s):
        return 'dropped'
    if (s in ('deferred', 'paused', 'frozen', 'dormant')
            or 'long_term' in s or 'background' in s or 'idle' in s
            or s.startswith('expired') or 'not_required' in s or 'not_used' in s):
        return 'deferred'
    if (s in ('done', 'completed', 'resolved', 'reconciled', 'submitted', 'sent', 'closed')
            or s.startswith('closed') or 'auto_passed' in s
            or 'overlapped_by_insurance' in s or 'pays_self' in s):
        return 'done'
    if (s.startswith('in_work') or s.startswith('in_progress') or 'in_progress' in s
            or 'investigation' in s or s.startswith('bank_posted')
            or s.startswith('bank_loaded') or s.startswith('application_drafted')):
        return 'in_progress'
    if s.startswith('active') or s.startswith('current') or s in ('registering', 'onboarding'):
        return 'active'
    return 'active'  # safe default: "in flight"


def status_label(raw):
    """Localized display label for any raw status (normalized first)."""
    canon = normalize_status(raw)
    return t(CANON_LABEL.get(canon, canon)) if canon else ''


# Canonical status -> (bg, fg) pill colours. Single source for every status pill
# (home recently-updated/closed lists, the plan rows, the track modal); mirrors
# the project's semantic palette.
CANON_PILL = {
    'active':      ('#EAF3DE', '#3D6107'),
    'in_progress': ('#E6F1FB', '#185FA5'),
    'awaiting':    ('#E6F1FB', '#185FA5'),
    'blocked':     ('#FCEBEB', '#9B1C1C'),
    'scheduled':   ('#FAEEDA', '#854F0B'),
    'calculated':  ('#E6F1FB', '#185FA5'),
    'paid':        ('#EAF3DE', '#3D6107'),
    'done':        ('#ECEBE6', '#5F5E5A'),
    'deferred':    ('#F1EFE8', '#888780'),
    'dropped':     ('#F1EFE8', '#888780'),
    'cancelled':   ('#F1EFE8', '#888780'),
    'archived':    ('#ECEBE6', '#5F5E5A'),
}


def status_pill(raw):
    """(localized_label, bg, fg) for a raw status (normalized first), or None if empty."""
    canon = normalize_status(raw)
    if not canon:
        return None
    bg, fg = CANON_PILL.get(canon, ('#F1EFE8', '#5F5E5A'))
    return (t(CANON_LABEL.get(canon, canon)), bg, fg)
