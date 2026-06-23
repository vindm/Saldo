"""_pipeline.py — deterministic monthly-close pipeline (a VIEW over state).

Pure functions, NO writes, NO rendering. Reads the declared stage config
(config/pipelines/monthly_close.yaml; falls back to an embedded copy if PyYAML is
absent) and answers, for a client's tasks:
  - which canonical stage a task belongs to (by task_type),
  - the per-stage open/done counts and the client's current stage.

The pipeline covers ONLY the monthly-cycle task_types. Tasks whose task_type maps
to no stage (open_question, awaiting_external, ad-hoc) are "off-pipeline" and must
stay visible elsewhere — they are returned separately so nothing is lost.
"""
import os

# Embedded fallback — kept in sync with config/pipelines/monthly_close.yaml.
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


def _norm(j):
    return ((j or "ru").strip().lower() or "ru")


def stages(jurisdiction="ru"):
    """Ordered stage dicts {code,title,task_types} for a jurisdiction's pipeline.
    Reads jurisdictions/<j>/pipeline.yaml; the embedded RU fallback applies only
    to 'ru' (other jurisdictions with no pipeline.yaml get [] -> their tasks are
    all off-pipeline)."""
    j = _norm(jurisdiction)
    key = "stages:" + j
    if key in _CACHE:
        return _CACHE[key]
    st = None
    try:
        import yaml
        with open(_pipeline_path(j), encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if data.get("stages"):
            st = [{"code": s["code"], "title": s.get("title") or {}, "task_types": s.get("task_types") or [],
                   "icon": s.get("icon"), "glyph": s.get("glyph")}
                  for s in data["stages"]]
    except Exception:
        st = None
    if st is None:
        st = _DEFAULT_STAGES if j == "ru" else []
    _CACHE[key] = st
    return st


def _type_to_stage(jurisdiction="ru"):
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


def stage_index_of(task_type, jurisdiction="ru"):
    """Index of the stage a task_type belongs to, or None if off-pipeline."""
    return _type_to_stage(jurisdiction).get((task_type or "").strip())


def stage_attr(code, jurisdiction="ru", key="icon", default=None):
    """A stage's declared attribute (e.g. icon/glyph) from the pack, or default.
    RU stages declare none -> default, preserving the engine's icon-map fallback."""
    for s in stages(jurisdiction):
        if s.get("code") == code:
            return s.get(key) if s.get(key) is not None else default
    return default


def stage_title(code_or_idx, locale="ru", jurisdiction="ru"):
    st = stages(jurisdiction)
    s = st[code_or_idx] if isinstance(code_or_idx, int) else next((x for x in st if x["code"] == code_or_idx), None)
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
