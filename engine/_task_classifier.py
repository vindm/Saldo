#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_task_classifier.py - shared structural prescreen for task-classification passes.

ONE place for the loose/strict signals behind migrations 0014 (type), 0015
(re-type ask-the-client) and 0016 (period). Each migration's preflight delegates
here, so the three regex slices stop diverging and a single read of the task set
can surface every classification dimension at once (`migrate.py classify`).

This is a read-only STRUCTURAL prescreen - it only proposes CANDIDATES; the
runtime makes the judgment per policies/task-types.md + INSTRUCTIONS §0.4 and the
contract in migrations/TASK_CLASSIFIER.md. The deterministic up() in each
migration keeps its OWN strict regexes and never imports this module, so the
deterministic core has no dependency on the prescreen.
"""
import re

# -- strict shapes the deterministic up() already handles (so we EXCLUDE them) --
_FEE_STRICT = re.compile(r'оплат\w*\s+услуг|service\s+payment|client\s+payment', re.I)
_ASK_STRICT = re.compile(r'(уточнить|спросить|запросить|узнать)\s+у\s', re.I)
_Q_TOKEN = re.compile(r'\bQ[1-4]\s*\d{4}|\b[1-4]\s*кв\.?\s*\d{4}', re.I)

# -- loose signals: broader than strict, surfaced for the runtime to judge -------
_PAY = re.compile(r'оплат|\bплат\w|счёт\s*за|вознагражд|абонентск', re.I)
_OURSVC = re.compile(r'услуг|сопровожд|обслуживан|бухгалтерск|абонентск|ведени\w*\s+учёт', re.I)
_NOTFEE = re.compile(r'банк|налог|поставщик|аренд|зарплат|страхов|взнос', re.I)
_ASK_LOOSE = re.compile(
    r'(жд[ёе]м|дожида\w*|ожида\w*)\s+ответ'
    r'|ответ\w*\s+(от|клиента)'
    r'|подтвержд\w*\s+(от|клиента)'
    r'|согласовать\s+с\s+клиент'
    r'|написать\s+\w+.*\s+(выяснит|уточнит|спросит)', re.I)

_MODE_OR_GENERIC = {"client_followup", "client_action", "awaiting_external",
                    "awaiting_external_then_action", "other"}


def _blob(tk, *keys):
    return " ".join(str(tk.get(k) or "") for k in keys)


def dims_for_task(tk):
    """All classification dimensions a single task is a CANDIDATE for. Returns a
    dict possibly containing 'type' / 'retype' / 'period'; empty if none apply."""
    if not isinstance(tk, dict):
        return {}
    tt = (tk.get("task_type") or "").strip()
    out = {}

    # TYPE (0014): a practice service-fee receivable mis-typed, phrased beyond strict.
    if tt != "service_payment":
        b = _blob(tk, "title", "what", "context", "next_action")
        if not _FEE_STRICT.search(b) and _PAY.search(b) and _OURSVC.search(b) and not _NOTFEE.search(b):
            out["type"] = {"to": "service_payment", "from": tt}

    # RETYPE (0015): a review_checkpoint resolved by the client, phrased beyond strict.
    if tt == "review_checkpoint":
        b = _blob(tk, "next_action", "context", "title", "what")
        if not _ASK_STRICT.search(b) and _ASK_LOOSE.search(b):
            out["retype"] = {"to": "client_followup", "from": tt}

    # PERIOD (0016): a service_payment with no period and no quarter token in title.
    if tt == "service_payment":
        ts = tk.get("type_specific")
        has_period = isinstance(ts, dict) and ts.get("period")
        if not has_period and not _Q_TOKEN.search(tk.get("title") or tk.get("what") or ""):
            out["period"] = {"infer": True}

    return out


def _iter_tasks(api):
    for cid in api.clients():
        data = api.read(cid, "tasks.json")
        if not isinstance(data, dict):
            continue
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            continue
        for tk in tasks:
            if isinstance(tk, dict):
                yield cid, tk


def _snip(tk, k, n=140):
    return (str(tk.get(k) or ""))[:n]


# -- per-dimension flag lists (the shape each migration's preflight returns) ------
def type_candidates(api, limit=50):
    out = []
    for cid, tk in _iter_tasks(api):
        d = dims_for_task(tk)
        if "type" in d:
            out.append({"client": cid, "task": tk.get("id"), "field": "task_type",
                        "current_type": d["type"]["from"], "title": _snip(tk, "title", 120),
                        "context": _snip(tk, "context"), "kind": "needs_task_classification"})
            if len(out) >= limit:
                break
    return out


def retype_candidates(api, limit=50):
    out = []
    for cid, tk in _iter_tasks(api):
        d = dims_for_task(tk)
        if "retype" in d:
            out.append({"client": cid, "task": tk.get("id"), "field": "task_type",
                        "current_type": "review_checkpoint", "title": _snip(tk, "title", 120),
                        "next_action": _snip(tk, "next_action"), "kind": "needs_task_classification"})
            if len(out) >= limit:
                break
    return out


def period_candidates(api, limit=50):
    out = []
    for cid, tk in _iter_tasks(api):
        d = dims_for_task(tk)
        if "period" in d:
            out.append({"client": cid, "task": tk.get("id"), "field": "type_specific.period",
                        "title": _snip(tk, "title", 120), "context": _snip(tk, "context", 160),
                        "next_action": _snip(tk, "next_action", 120), "kind": "needs_period_inference"})
            if len(out) >= limit:
                break
    return out


def scan(api, limit=200):
    """ONE consolidated read: every task that is a candidate in ANY dimension,
    with all its dimensions together. Backs `migrate.py classify` - the runtime
    judges type + period + routing for a task in a single read."""
    out = []
    for cid, tk in _iter_tasks(api):
        d = dims_for_task(tk)
        if d:
            out.append({"client": cid, "task": tk.get("id"),
                        "title": _snip(tk, "title", 120),
                        "current_type": (tk.get("task_type") or "").strip(),
                        "dims": d})
            if len(out) >= limit:
                break
    return out
