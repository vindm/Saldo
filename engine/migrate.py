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
    return {e["id"] for e in ledger.get("applied", []) if isinstance(e, dict) and e.get("id")}


def cmd_status(data_dir):
    ledger = _read_ledger(data_dir)
    applied = _applied_ids(ledger)
    migs = _discover()
    print("data dir : %s" % data_dir)
    print("ledger   : %s" % _ledger_path(data_dir))
    print("")
    for mid, desc, _ in migs:
        mark = "APPLIED" if mid in applied else "pending"
        print("  [%s] %s  %s" % (mid, mark.ljust(7), desc))
    if not migs:
        print("  (no migrations found)")
    pending = [m for m in migs if m[0] not in applied]
    print("\n%d migration(s), %d pending." % (len(migs), len(pending)))


def cmd_up(data_dir, apply, state_ops):
    ledger = _read_ledger(data_dir)
    applied = _applied_ids(ledger)
    pending = [m for m in _discover() if m[0] not in applied]
    if not pending:
        print("Nothing to do - all migrations already applied.")
        return 0

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
            ledger.setdefault("applied", []).append({
                "id": mid,
                "description": desc,
                "applied_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "clients_touched": sorted({c["client"] for c in api.changes}),
                "change_count": len(api.changes),
            })
            _write_ledger(data_dir, ledger)
        print("")

    if not apply:
        print("Dry-run only. Re-run with --apply to write changes.")
    else:
        print("Applied %d migration(s). Now run: python3 engine/state_lint.py" % len(pending))
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
    p_up = sub.add_parser("up", help="run pending migrations")
    p_up.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    p_up.add_argument("--data-dir")
    args = parser.parse_args(argv)

    data_dir = _config.DATA_DIR
    if args.cmd == "status":
        cmd_status(data_dir)
        return 0
    if args.cmd == "up":
        return cmd_up(data_dir, args.apply, state_ops)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
