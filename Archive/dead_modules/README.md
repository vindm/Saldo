# Dead modules (archived)

Modules that were imported by nothing and are not entrypoints, moved here on 2026-06-22
during the Phase 0 cleanup so `system_integrity_check.py` stops flagging them as orphans.
Kept (not deleted) for reference; restore by moving back into `engine/` if ever needed.

- `process_audit.py` — no references anywhere in the codebase.
- `_plan_week.py` — referenced only in a stale comment in `engine/_strings.py`; the weekly
  plan view is not wired into `generate.py`.
