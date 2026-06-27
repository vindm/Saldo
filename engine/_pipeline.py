"""_pipeline.py — declared recurring CYCLES (a VIEW over state).

Pure functions, NO writes, NO rendering. A jurisdiction declares one or more
**cycles** — the monthly close (primary) plus, for RU, payroll / quarterly-tax /
AUSN — each an ordered set of stages. Cycles are read from
`jurisdictions/<j>/cycles/*.yaml`; a pack that still ships a single legacy
`jurisdictions/<j>/pipeline.yaml` is wrapped as one `monthly_close` cycle (RU
also has an embedded fallback if PyYAML is absent). For a client's tasks it
answers:
  - which cycle+stage a task_type belongs to (`locate_stage`, across all cycles),
  - the per-stage open/done counts and the client's current stage.

Cycles cover ONLY the recurring task_types. Tasks whose task_type maps to no stage
(open_question, awaiting_external, ad-hoc) are "off-pipeline" and must stay visible
elsewhere — they are returned separately so nothing is lost.
"""
import os

# Embedded RU fallback — kept in sync with jurisdictions/ru/cycles/monthly_close.yaml
# (used only when PyYAML is absent and no cycles/ or pipeline.yaml can be read).
_DEFAULT_STAGES = [
    {"code": "primary_collection", "title": {"ru": "Сбор первички", "en": "Collect source docs"}, "task_types": ["primary_collection"]},
    {"code": "posting_1c",        "title": {"ru": "Разноска в 1С", "en": "Post to 1C"}, "task_types": ["kudir_posting", "technical_1c"]},
    {"code": "month_close",       "title": {"ru": "Закрытие месяца", "en": "Month close"}, "task_types": ["month_close", "period_close"]},
    {"code": "month_audit",       "title": {"ru": "Аудит месяца", "en": "Month audit"}, "task_types": ["month_audit"]},
    {"code": "tax_pp",            "title": {"ru": "Расчёт + уведомление + ПП", "en": "Calc + notice + payment order"}, "task_types": ["pp_to_form", "notification"]},
    {"code": "sign_pay",          "title": {"ru": "Подпись / оплата", "en": "Sign / pay"}, "task_types": ["pp_sign"]},
]

DONE_STATUSES = {"done", "completed", "cancelled", "dropped", "dismissed", "closed", "resolved", "deferred", "paid"}

_CACHE = {}


def _pipeline_path(jurisdiction):
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "jurisdictions", jurisdiction, "pipeline.yaml"))


def _cycles_dir(jurisdiction):
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "jurisdictions", jurisdiction, "cycles"))


def _norm(j):
    return ((j or "ru").strip().lower() or "ru")


def _stage_list(raw_stages):
    return [{"code": s["code"], "title": s.get("title") or {}, "task_types": s.get("task_types") or [],
             "icon": s.get("icon"), "glyph": s.get("glyph")}
            for s in (raw_stages or [])]


def _read_pipeline_yaml(j):
    """Legacy single-pipeline form: jurisdictions/<j>/pipeline.yaml -> (stages, feeders).
    The embedded RU fallback applies only to 'ru'."""
    st, feeders = None, []
    try:
        import yaml
        with open(_pipeline_path(j), encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if data.get("stages"):
            st = _stage_list(data["stages"])
            feeders = data.get("feeders") or []
    except Exception:
        st = None
    if st is None:
        st = _DEFAULT_STAGES if j == "ru" else []
    return st, feeders


def cycles(jurisdiction="ru"):
    """Ordered cycle dicts {code,cadence,title,primary,order,stages,feeders}.
    Reads jurisdictions/<j>/cycles/*.yaml (one file per cycle). If that directory is
    absent, wraps the legacy single pipeline.yaml as one 'monthly_close' cycle, so the
    'id' pack and any single-pipeline jurisdiction keep working unchanged. Render order
    is primary-first, then declared `order`, then code."""
    j = _norm(jurisdiction)
    key = "cycles:" + j
    if key in _CACHE:
        return _CACHE[key]
    out = []
    d = _cycles_dir(j)
    try:
        import yaml
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if not fn.endswith((".yaml", ".yml")):
                    continue
                with open(os.path.join(d, fn), encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if not data.get("stages"):
                    continue
                out.append({
                    "code": data.get("code") or fn.rsplit(".", 1)[0],
                    "cadence": data.get("cadence") or "monthly",
                    "title": data.get("title") or {},
                    "primary": bool(data.get("primary")),
                    "order": data.get("order", 999),
                    "stages": _stage_list(data["stages"]),
                    "feeders": data.get("feeders") or [],
                })
    except Exception:
        out = []
    if not out:
        st, feeders = _read_pipeline_yaml(j)
        if st:
            out = [{"code": "monthly_close", "cadence": "monthly",
                    "title": {"ru": "Учётный цикл", "en": "Bookkeeping cycle"},
                    "primary": True, "order": 0, "stages": st, "feeders": feeders}]
    out.sort(key=lambda c: (0 if c.get("primary") else 1, c.get("order", 999), c.get("code", "")))
    _CACHE[key] = out
    return out


def stages(jurisdiction="ru", cycle=None):
    """Ordered stage dicts for one cycle. Default = the primary cycle (the monthly
    close) — preserving the single-pipeline contract for callers that pass only a
    jurisdiction. Pass `cycle=<code>` for a specific cycle."""
    cs = cycles(jurisdiction)
    if cycle is not None:
        c = next((x for x in cs if x.get("code") == cycle), None)
        return c["stages"] if c else []
    return cs[0]["stages"] if cs else []


def _type_to_stage(jurisdiction="ru"):
    """task_type -> stage index WITHIN the primary cycle (backward-compatible)."""
    j = _norm(jurisdiction)
    key = "t2s:" + j
    if key in _CACHE:
        return _CACHE[key]
    m = {}
    for i, s in enumerate(stages(j)):
        for tt in s["task_types"]:
            m[tt] = i
    _CACHE[key] = m
    return m


def _type_locator(jurisdiction="ru"):
    """task_type -> (cycle_code, stage_code) across ALL cycles. Stage codes are
    globally unique, so the mapping is unambiguous (a type seen twice keeps the
    primary-first occurrence)."""
    j = _norm(jurisdiction)
    key = "loc:" + j
    if key in _CACHE:
        return _CACHE[key]
    m = {}
    for c in cycles(j):
        for s in c["stages"]:
            for tt in s["task_types"]:
                m.setdefault(tt, (c["code"], s["code"]))
    _CACHE[key] = m
    return m


def locate_stage(task_type, jurisdiction="ru"):
    """(cycle_code, stage_code) the task_type maps to across all cycles, or None."""
    return _type_locator(jurisdiction).get((task_type or "").strip())


def cycle_of_stage(stage_code, jurisdiction="ru"):
    """Which cycle a stage code belongs to, or None."""
    for c in cycles(jurisdiction):
        if any(s.get("code") == stage_code for s in c["stages"]):
            return c["code"]
    return None


def stage_index_of(task_type, jurisdiction="ru"):
    """Index of the stage a task_type belongs to within the PRIMARY cycle, or None."""
    return _type_to_stage(jurisdiction).get((task_type or "").strip())


def _all_stages(jurisdiction):
    for c in cycles(jurisdiction):
        for s in c["stages"]:
            yield s


def stage_attr(code, jurisdiction="ru", key="icon", default=None):
    """A stage's declared attribute (e.g. icon/glyph) from the pack, searched across
    all cycles. RU stages declare none -> default, preserving the icon-map fallback."""
    for s in _all_stages(jurisdiction):
        if s.get("code") == code:
            return s.get(key) if s.get(key) is not None else default
    return default


def stage_title(code_or_idx, locale="ru", jurisdiction="ru"):
    if isinstance(code_or_idx, int):
        st = stages(jurisdiction)
        s = st[code_or_idx] if 0 <= code_or_idx < len(st) else None
    else:
        s = next((x for x in _all_stages(jurisdiction) if x["code"] == code_or_idx), None)
    if not s:
        return ""
    return (s.get("title") or {}).get(locale) or (s.get("title") or {}).get("en") or s["code"]


def client_pipeline(tasks, jurisdiction="ru"):
    """For one client's task list, return:
      {'stages': [{code,title_ru,title_en,total,open,done,status}], 'current': idx|None,
       'on_pipeline': [tasks...], 'off_pipeline': [tasks...]}.
    status per stage: 'done' (has tasks, all terminal), 'active' (has open),
    'pending' (no tasks yet — earlier/later), computed over the whole list.
    """
    st = stages(jurisdiction)
    buckets = [{"total": 0, "open": 0, "done": 0} for _ in st]
    on, off = [], []
    for t in tasks or []:
        idx = stage_index_of(t.get("task_type"), jurisdiction)
        if idx is None:
            off.append(t)
            continue
        on.append(t)
        b = buckets[idx]
        b["total"] += 1
        if (t.get("status") or "").lower() in DONE_STATUSES:
            b["done"] += 1
        else:
            b["open"] += 1
    out_stages = []
    current = None
    for i, s in enumerate(st):
        b = buckets[i]
        if b["total"] == 0:
            status = "pending"
        elif b["open"] == 0:
            status = "done"
        else:
            status = "active"
            if current is None:
                current = i
        out_stages.append({
            "code": s["code"], "title_ru": stage_title(i, "ru", jurisdiction), "title_en": stage_title(i, "en", jurisdiction),
            "total": b["total"], "open": b["open"], "done": b["done"], "status": status,
        })
    return {"stages": out_stages, "current": current, "on_pipeline": on, "off_pipeline": off}
