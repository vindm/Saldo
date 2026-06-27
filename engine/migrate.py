#!/usr/bin/env python3
"""migrate.py - schema/state migration runner for Saldo data directories.

Why this exists
---------------
The engine (this repo) is developed centrally; each practice runs it on its own
machine against its own private data dir (config: data.dir). When an engine
change touches the shape of state (rename a field, move a fact to a single
source, drop a duplicated key), the data on every user's machine must be
reshaped to match - but every user has a DIFFERENT set of clients, with
different names and different fields present.

So migrations are written against the SCHEMA (field names), never against
specific clients. A migration says "wherever key X exists, do Y" and the runner
applies it to whatever clients the local clients_index.json lists. It works the
same for 3 clients or 50, whatever they are named.

Guarantees
----------
- Deterministic & idempotent: re-running an applied migration is a no-op.
- Every write goes through engine/state_ops (backup + atomic + UTF-8).
- Dry-run by default: nothing is written until you pass --apply.
- A ledger of applied migrations lives WITH THE DATA, not in the repo:
  <DATA_DIR>/journal/schema_migrations.json
- Every change is also logged to the client's history.jsonl.

Usage
-----
    python3 engine/migrate.py status                 # what is applied / pending
    python3 engine/migrate.py up                      # dry-run all pending
    python3 engine/migrate.py up --apply              # apply pending migrations
    python3 engine/migrate.py up --data-dir PATH      # target a specific data dir
    python3 engine/migrate.py up --data-dir PATH --apply

A migration module lives in migrations/NNNN_slug.py and exposes:
    ID          : str   e.g. "0001"  (zero-padded, defines order)
    DESCRIPTION : str   one line, schema-level (no client names)
    def up(api): ...    uses api.* helpers; never imports state_ops directly
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, ".."))
_MIGRATIONS_DIR = os.path.join(_REPO, "migrations")


# ---------------------------------------------------------------------------
# Migration API handed to every migration's up(api). Migrations touch state
# ONLY through these helpers, so the dry-run / write / log / ledger discipline
# is enforced centrally and uniformly.
# ---------------------------------------------------------------------------
class MigrationAPI:
    def __init__(self, state_ops, data_dir, dry, migration_id):
        self._ops = state_ops
        self.data_dir = data_dir
        self.dry = dry
        self.migration_id = migration_id
        self.changes = []   # list of dict: {client, file, action}
        self.warnings = []  # list of str

    def clients(self):
        """Client ids from the local clients_index.json (whatever this user has)."""
        idx = os.path.join(self.data_dir, "clients_index.json")
        if not os.path.exists(idx):
            return []
        try:
            with open(idx, encoding="utf-8") as f:
                entries = json.load(f)
        except (ValueError, OSError):
            return []
        return [e["id"] for e in entries if isinstance(e, dict) and e.get("id")]

    def _record(self, client, state_file, action):
        self.changes.append({"client": client, "file": state_file, "action": action})

    def warn(self, msg):
        self.warnings.append(msg)

    def read(self, client, state_file):
        """Read-only accessor for preflight / inspection.

        Never writes, regardless of dry/apply mode. This is what a migration's
        optional preflight(api) uses to look at the operator's REAL data and
        surface flags BEFORE anything is applied. Deterministic Python - no
        model involved here; preflight is a structural pre-scan, not judgment.
        """
        return self._ops.state_read(client, state_file)

    def _commit(self, client, state_file, data, action):
        if not self.dry:
            self._ops.state_write(client, state_file, data, ctx="migrate_%s" % self.migration_id)
            self._ops.history_append(client, {
                "summary": "migration %s: %s" % (self.migration_id, action),
                "fields_changed": [action],
                "source": "migration",
                "migration_id": self.migration_id,
            })
        self._record(client, state_file, action)

    # -- high-level, schema-level operations --------------------------------

    def rename_key(self, state_file, old_key, new_key, on_conflict="skip"):
        """Rename a top-level key wherever it exists.

        on_conflict (when BOTH old_key and new_key are present in a client):
          - "skip"   : leave the client untouched, emit a warning (default)
          - "append" : free-text-safe; append old value to new with ' | ' sep
        Clients lacking old_key are untouched. Idempotent: once old_key is gone
        everywhere, re-running does nothing.
        """
        for cid in self.clients():
            data = self._ops.state_read(cid, state_file)
            if not isinstance(data, dict) or old_key not in data:
                continue
            if new_key in data and data[new_key] not in (None, ""):
                if on_conflict == "append":
                    merged = "%s | %s" % (data[new_key], data[old_key])
                    data[new_key] = merged
                    del data[old_key]
                    self._commit(cid, state_file, data,
                                 "%s merged into existing %s" % (old_key, new_key))
                else:
                    self.warn("%s/%s: both '%s' and '%s' present - skipped (resolve by hand)"
                              % (cid, state_file, old_key, new_key))
                continue
            data[new_key] = data.pop(old_key)
            self._commit(cid, state_file, data, "%s -> %s" % (old_key, new_key))

    def for_each_client(self, state_file, fn):
        """Generic escape hatch for non-trivial migrations.

        fn(client_id, data) -> (changed: bool, action: str). The api handles
        read, dry/apply write, history and recording. fn must mutate `data`
        in place and return whether it changed anything.
        """
        for cid in self.clients():
            data = self._ops.state_read(cid, state_file)
            if not isinstance(data, dict):
                continue
            changed, action = fn(cid, data)
            if changed:
                self._commit(cid, state_file, data, action)


# ---------------------------------------------------------------------------
# Runner internals
# ---------------------------------------------------------------------------
def _discover():
    """All migration modules, ordered by numeric ID prefix."""
    out = []
    if not os.path.isdir(_MIGRATIONS_DIR):
        return out
    for fn in sorted(os.listdir(_MIGRATIONS_DIR)):
        m = re.match(r"^(\d+)_.*\.py$", fn)
        if not m:
            continue
        path = os.path.join(_MIGRATIONS_DIR, fn)
        spec = importlib.util.spec_from_file_location(fn[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mid = getattr(mod, "ID", m.group(1))
        out.append((str(mid), getattr(mod, "DESCRIPTION", ""), mod))
    out.sort(key=lambda t: t[0])
    return out


def _ledger_path(data_dir):
    return os.path.join(data_dir, "journal", "schema_migrations.json")


def _read_ledger(data_dir):
    p = _ledger_path(data_dir)
    if not os.path.exists(p):
        return {"applied": []}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {"applied": []}


def _write_ledger(data_dir, ledger):
    p = _ledger_path(data_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    text = json.dumps(ledger, ensure_ascii=False, indent=2)
    json.loads(text)  # roundtrip validation
    tmp = p + ".tmp"
    with open(tmp, "wb") as f:
        f.write(text.encode("utf-8"))
    os.replace(tmp, p)


def _applied_ids(ledger):
    """Ids that have a ledger entry at ANY rung (mechanical part has run)."""
    return {e["id"] for e in ledger.get("applied", []) if isinstance(e, dict) and e.get("id")}


# --- rung state machine ----------------------------------------------------
# A migration is not "done" the moment its deterministic up() returns. Full
# completion walks three rungs:
#     mechanical_applied  -> the deterministic up() has written state
#     runtime_pass_done   -> the optional AI judgment pass (RUNTIME_PASS) is done
#     verified            -> the SCENARIO role-play confirmed behaviour (Invariant-0)
# Only `verified` lets the sequence advance to the next migration, so the ledger
# is always a TRUTHFUL PREFIX: everything up to migration K is fully done and
# behaviour-verified; nothing after K has touched the data.
_RUNGS = ["mechanical_applied", "runtime_pass_done", "verified"]


def _entry_of(ledger, mid):
    for e in ledger.get("applied", []):
        if isinstance(e, dict) and e.get("id") == mid:
            return e
    return None


def _rung_of(ledger, mid):
    """Current rung of a migration, or None if it has not been applied at all.

    Backward compat: a LEGACY entry (written before rungs existed - it has
    `applied_at` and no `rung`) is treated as fully `verified`. Pre-rung
    migrations were deterministic-only, so 'mechanically applied' == 'done'.
    """
    e = _entry_of(ledger, mid)
    if e is None:
        return None
    return e.get("rung", "verified")


def _is_verified(ledger, mid):
    return _rung_of(ledger, mid) == "verified"


def _alignment(mod, flags):
    """Compare preflight findings against the migration's declared EXPECT
    envelope. Returns {status: aligned | anomaly | no_expectations, reasons:[...]}.

    OBJECTIVE checks only - the engine never makes the judgment call, it just
    decides whether the result sits INSIDE the envelope the migration declared.
    Inside (or no envelope) -> the runtime applies autonomously; outside -> the
    runtime escalates to the operator ("something really unexpected"). This is
    what lets most migrations run with no human touch while genuine surprises
    still surface.
    """
    expect = getattr(mod, "EXPECT", None)
    if not isinstance(expect, dict):
        return {"status": "no_expectations", "reasons": []}
    reasons = []
    pmax = expect.get("preflight_max")
    if isinstance(pmax, int) and len(flags) > pmax:
        reasons.append("preflight produced %d flag(s), above expected max %d" % (len(flags), pmax))
    kinds = expect.get("change_kinds")
    if isinstance(kinds, list) and kinds:
        bad = sorted({f.get("kind") for f in flags
                      if isinstance(f, dict) and f.get("kind") not in kinds})
        if bad:
            reasons.append("unexpected flag kind(s): %s (expected: %s)"
                           % (", ".join(map(str, bad)), ", ".join(map(str, kinds))))
    if any(isinstance(f, dict) and f.get("kind") == "preflight_error" for f in flags):
        reasons.append("preflight raised an error")
    return {"status": "anomaly" if reasons else "aligned", "reasons": reasons}


def _has_runtime_work(mod):
    """True if a migration declares any AI-side step (preflight / RUNTIME_PASS /
    SCENARIO). Such migrations must go through the stepwise next/apply/record
    flow, not the deterministic batch `up --apply`."""
    return (hasattr(mod, "preflight")
            or hasattr(mod, "RUNTIME_PASS")
            or hasattr(mod, "SCENARIO"))


def _upsert_entry(ledger, mid, **fields):
    """Create or update the ledger entry for mid, merging fields."""
    e = _entry_of(ledger, mid)
    if e is None:
        e = {"id": mid}
        ledger.setdefault("applied", []).append(e)
    e.update(fields)
    return e


def cmd_status(data_dir):
    ledger = _read_ledger(data_dir)
    migs = _discover()
    print("data dir : %s" % data_dir)
    print("ledger   : %s" % _ledger_path(data_dir))
    print("")
    for mid, desc, mod in migs:
        rung = _rung_of(ledger, mid)
        if rung is None:
            mark = "pending"
        elif rung == "verified":
            mark = "verified"
        else:
            mark = rung  # mechanical_applied / runtime_pass_done = in progress
        tag = "  *runtime*" if _has_runtime_work(mod) else ""
        print("  [%s] %s  %s%s" % (mid, mark.ljust(18), desc, tag))
    if not migs:
        print("  (no migrations found)")
    pending = [m for m in migs if not _is_verified(ledger, m[0])]
    print("\n%d migration(s), %d not yet verified." % (len(migs), len(pending)))
    if pending:
        print("Next: python3 engine/migrate.py next")


def cmd_up(data_dir, apply, state_ops, force=False):
    """Deterministic BATCH path: apply every pending pure-schema migration.

    Refuses (unless --force) when a pending migration declares any AI-side step
    (preflight / RUNTIME_PASS / SCENARIO): those must walk the sequential
    next -> apply -> record flow so the judgment + verification happen in order,
    not in a deferred lump. A pure-schema migration has no afterwork, so the
    batch marks it `verified` immediately.
    """
    ledger = _read_ledger(data_dir)
    pending = [m for m in _discover() if _rung_of(ledger, m[0]) is None]
    if not pending:
        print("Nothing to do - all migrations already applied.")
        return 0

    runtime_ones = [m for m in pending if _has_runtime_work(m[2])]
    if runtime_ones and not force:
        print("STOP: %d pending migration(s) need the stepwise runtime flow:" % len(runtime_ones))
        for mid, desc, _ in runtime_ones:
            print("    [%s] %s" % (mid, desc))
        print("\nThese have a preflight / RUNTIME_PASS / SCENARIO and must be applied one")
        print("at a time so prework, the script, and verification stay in order. Run:")
        print("    python3 engine/migrate.py next")
        print("(or `up --apply --force` to apply only the deterministic part, NOT advised).")
        # Distinct exit code 2 = "stepwise runtime flow needed" (not a generic error),
        # so tools/update.py can hand off to connectors/migration_runtime cleanly.
        return 2

    mode = "APPLY" if apply else "DRY-RUN"
    print("== migrate up (%s) ==  data dir: %s\n" % (mode, data_dir))
    for mid, desc, mod in pending:
        api = MigrationAPI(state_ops, data_dir, dry=not apply, migration_id=mid)
        mod.up(api)
        print("[%s] %s" % (mid, desc))
        if api.changes:
            for ch in api.changes:
                print("    - %s / %s : %s" % (ch["client"], ch["file"], ch["action"]))
        else:
            print("    (no matching data - nothing to change)")
        for w in api.warnings:
            print("    ! %s" % w)
        if apply:
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            # No afterwork on a pure-schema migration (or forced): mechanical == done.
            rung = "mechanical_applied" if _has_runtime_work(mod) else "verified"
            _upsert_entry(
                ledger, mid,
                description=desc,
                applied_at=now,
                mechanical_applied_at=now,
                rung=rung,
                verified_at=(now if rung == "verified" else None),
                clients_touched=sorted({c["client"] for c in api.changes}),
                change_count=len(api.changes),
            )
            _write_ledger(data_dir, ledger)
        print("")

    if not apply:
        print("Dry-run only. Re-run with --apply to write changes.")
    else:
        print("Applied %d migration(s). Now run: python3 engine/state_lint.py" % len(pending))
    return 0


def cmd_next(data_dir, state_ops, as_json=False):
    """READ step: the next migration not yet `verified`, plus its read-only
    preflight findings. Writes nothing - safe as `status`."""
    ledger = _read_ledger(data_dir)
    nxt = None
    for mid, desc, mod in _discover():
        if not _is_verified(ledger, mid):
            nxt = (mid, desc, mod)
            break

    if nxt is None:
        if as_json:
            print(json.dumps({"done": True}, ensure_ascii=False))
        else:
            print("All migrations verified - nothing pending.")
        return 0

    mid, desc, mod = nxt
    rung = _rung_of(ledger, mid)  # None | mechanical_applied | runtime_pass_done

    # read-only preflight scan against REAL data (dry api never writes)
    flags = []
    if hasattr(mod, "preflight"):
        api = MigrationAPI(state_ops, data_dir, dry=True, migration_id=mid)
        try:
            flags = mod.preflight(api) or []
        except Exception as exc:  # a preflight bug must not block the runner
            flags = [{"kind": "preflight_error", "error": repr(exc)}]

    align = _alignment(mod, flags)
    rp = getattr(mod, "RUNTIME_PASS", None)
    escalate = isinstance(rp, dict) and rp.get("escalate") == "always"
    info = {
        "id": mid,
        "description": desc,
        "rung": rung,                     # where this migration currently sits
        "stage": "afterwork" if rung == "mechanical_applied"
                 else "verify" if rung == "runtime_pass_done"
                 else "prework",          # not started -> prework then apply
        "has_runtime_pass": hasattr(mod, "RUNTIME_PASS"),
        "runtime_pass": rp,
        "scenario": getattr(mod, "SCENARIO", None),
        "expect": getattr(mod, "EXPECT", None),
        "preflight": flags,
        "alignment": align,
        # The runtime may apply this autonomously (no operator pause) when the
        # result is inside the declared envelope and the migration does not force
        # a pause. Escalate only on anomaly / forced / (later) a scenario fail.
        "autonomous": (align["status"] != "anomaly") and not escalate,
    }

    if as_json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0

    print("next migration : [%s] %s" % (mid, desc))
    print("current rung   : %s" % (rung or "pending (not applied)"))
    print("stage          : %s" % info["stage"])
    if flags:
        print("preflight (%d flag(s)):" % len(flags))
        for f in flags:
            print("    - %s" % json.dumps(f, ensure_ascii=False))
    else:
        print("preflight      : (none / no preflight defined)")
    if info["runtime_pass"]:
        print("RUNTIME_PASS   : %s" % json.dumps(info["runtime_pass"], ensure_ascii=False))
    if info["scenario"]:
        print("SCENARIO       : %s" % json.dumps(info["scenario"], ensure_ascii=False))
    print("alignment      : %s%s" % (
        align["status"],
        (" — " + "; ".join(align["reasons"])) if align["reasons"] else ""))
    print("autonomous     : %s" % ("yes (apply without asking)" if info["autonomous"]
                                   else "NO — escalate to the operator"))
    print("\nApply this one: python3 engine/migrate.py apply %s --apply" % mid)
    return 0


def cmd_apply(data_dir, mid, apply, state_ops):
    """RUN step: apply EXACTLY one migration's deterministic up(). Refuses to
    skip ahead - every migration before `mid` must already be `verified`."""
    migs = {m[0]: m for m in _discover()}
    if mid not in migs:
        print("Unknown migration id: %s" % mid)
        return 1
    ledger = _read_ledger(data_dir)

    # sequencing gate: no prior migration may be left unverified
    for omid, _, _ in _discover():
        if omid >= mid:
            break
        if not _is_verified(ledger, omid):
            print("STOP: migration [%s] is not verified yet - cannot apply [%s] before it."
                  % (omid, mid))
            print("Finish the earlier one first: python3 engine/migrate.py next")
            return 1

    cur = _rung_of(ledger, mid)
    if cur is not None:
        print("[%s] already applied (rung=%s) - up() is idempotent, skipping re-run." % (mid, cur))
        if cur != "verified":
            print("Pending afterwork: python3 engine/migrate.py next")
        return 0

    _, desc, mod = migs[mid]
    api = MigrationAPI(state_ops, data_dir, dry=not apply, migration_id=mid)
    mod.up(api)
    mode = "APPLY" if apply else "DRY-RUN"
    print("[%s] %s  (%s)" % (mid, desc, mode))
    if api.changes:
        for ch in api.changes:
            print("    - %s / %s : %s" % (ch["client"], ch["file"], ch["action"]))
    else:
        print("    (no matching data - nothing to change)")
    for w in api.warnings:
        print("    ! %s" % w)

    if not apply:
        print("\nDry-run only. Re-run with --apply to write.")
        return 0

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    runtime = _has_runtime_work(mod)
    _upsert_entry(
        ledger, mid,
        description=desc,
        applied_at=now,
        mechanical_applied_at=now,
        rung="mechanical_applied",
        verified_at=None,
        clients_touched=sorted({c["client"] for c in api.changes}),
        change_count=len(api.changes),
    )
    _write_ledger(data_dir, ledger)
    print("\n-> rung: mechanical_applied")
    if runtime:
        print("Afterwork pending (RUNTIME_PASS / SCENARIO). The migration-runtime skill")
        print("does the gated writes + scenario, then calls:")
        print("    python3 engine/migrate.py record %s --rung verified" % mid)
    else:
        print("No afterwork. Verify behaviour, then:")
        print("    python3 engine/migrate.py record %s --rung verified" % mid)
    return 0


def cmd_record(data_dir, mid, rung, scenario_result=None, note=None):
    """Advance the ledger rung after the AI side finishes a step. Writes the
    LEDGER only - never client state."""
    if rung not in _RUNGS:
        print("Unknown rung: %s (expected one of %s)" % (rung, ", ".join(_RUNGS)))
        return 1
    ledger = _read_ledger(data_dir)
    e = _entry_of(ledger, mid)
    if e is None:
        print("Migration [%s] has not been applied yet - run `apply %s --apply` first." % (mid, mid))
        return 1

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    fields = {"rung": rung}
    if rung == "runtime_pass_done":
        fields["runtime_pass"] = {"status": "done", "at": now, "note": note}
    elif rung == "verified":
        fields["verified_at"] = now
        if scenario_result is not None:
            fields["scenario_result"] = scenario_result
        if note:
            fields["verify_note"] = note
    _upsert_entry(ledger, mid, **fields)
    _write_ledger(data_dir, ledger)
    print("[%s] -> rung: %s" % (mid, rung))
    return 0


def cmd_classify(data_dir, state_ops, as_json=False):
    """ONE consolidated read of the task set across every task-classification
    dimension (type / re-type / period) via the shared engine classifier. This is
    the 'single invocation' the runtime uses to judge a task holistically, instead
    of three separate per-migration preflight rounds. Read-only - writes nothing.
    """
    try:
        import _task_classifier as _tc
    except Exception as exc:
        print("task classifier unavailable: %r" % exc)
        return 1
    api = MigrationAPI(state_ops, data_dir, dry=True, migration_id="classify")
    rows = _tc.scan(api)
    if as_json:
        print(json.dumps({"candidates": rows}, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("No task-classification candidates - nothing to reclassify.")
        return 0
    print("Task-classification candidates (%d) — read once, judge per "
          "migrations/TASK_CLASSIFIER.md:\n" % len(rows))
    for r in rows:
        dims = ", ".join(sorted(r["dims"]))
        print("  [%s] %s/%s  (now: %s)  -> %s" % (
            dims, r["client"], r["task"], r["current_type"] or "—", r["title"]))
    return 0


def _parse_data_dir_early(argv):
    """data.dir override must be set in the env BEFORE _config/state_ops import."""
    for i, a in enumerate(argv):
        if a == "--data-dir" and i + 1 < len(argv):
            return os.path.abspath(argv[i + 1])
        if a.startswith("--data-dir="):
            return os.path.abspath(a.split("=", 1)[1])
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    override = _parse_data_dir_early(argv)
    if override:
        os.environ["ABA_DATA_DIR"] = override

    # import only now, so ABA_DATA_DIR is honored
    sys.path.insert(0, _HERE)
    import _config
    import state_ops

    parser = argparse.ArgumentParser(prog="migrate.py", description="Saldo state migration runner")
    sub = parser.add_subparsers(dest="cmd")
    p_status = sub.add_parser("status", help="list applied/pending migrations")
    p_status.add_argument("--data-dir")
    p_up = sub.add_parser("up", help="batch-run pending PURE-SCHEMA migrations")
    p_up.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    p_up.add_argument("--force", action="store_true",
                      help="apply only the deterministic part even past runtime-work migrations (not advised)")
    p_up.add_argument("--data-dir")

    p_next = sub.add_parser("next", help="show the next not-yet-verified migration + preflight (read-only)")
    p_next.add_argument("--json", action="store_true", help="machine-readable handoff for the runtime")
    p_next.add_argument("--data-dir")

    p_apply = sub.add_parser("apply", help="apply EXACTLY one migration's deterministic up()")
    p_apply.add_argument("id", help="migration id, e.g. 0019")
    p_apply.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    p_apply.add_argument("--data-dir")

    p_record = sub.add_parser("record", help="advance a migration's rung (ledger only)")
    p_record.add_argument("id", help="migration id, e.g. 0019")
    p_record.add_argument("--rung", required=True, choices=_RUNGS)
    p_record.add_argument("--scenario-result")
    p_record.add_argument("--note")
    p_record.add_argument("--data-dir")

    p_classify = sub.add_parser("classify",
                                help="one read of all task-classification candidates (type/retype/period)")
    p_classify.add_argument("--json", action="store_true")
    p_classify.add_argument("--data-dir")

    args = parser.parse_args(argv)

    data_dir = _config.DATA_DIR
    if args.cmd == "status":
        cmd_status(data_dir)
        return 0
    if args.cmd == "up":
        return cmd_up(data_dir, args.apply, state_ops, force=args.force)
    if args.cmd == "next":
        return cmd_next(data_dir, state_ops, as_json=args.json)
    if args.cmd == "apply":
        return cmd_apply(data_dir, args.id, args.apply, state_ops)
    if args.cmd == "record":
        return cmd_record(data_dir, args.id, args.rung,
                          scenario_result=args.scenario_result, note=args.note)
    if args.cmd == "classify":
        return cmd_classify(data_dir, state_ops, as_json=args.json)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
