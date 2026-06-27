"""
state_ops.py — atomic operations for working with per-client state/.

Architecture (Karpathy-style memory hierarchy):
- mental_model.md — narrative/analytical slice, human-readable
- state/*.json — structured facts, machine-readable
- history.jsonl — append-only log of signals

This module provides the low-level state primitives (read/write/history/mental
model, plus register_client for onboarding a new client). The logic of "what
exactly to update on which signal" lives in the AI agent (Claude), not in code.
Here we only do atomic writes with backup and validation.

Usage pattern:
    from state_ops import state_read, state_write, history_append
    tasks = state_read('<client_id>', 'tasks.json')
    tasks['tasks'].append({...})
    state_write('<client_id>', 'tasks.json', tasks, ctx='add_pp_task')
    history_append('<client_id>', {
        'summary': 'Added a filing task for 30.06',
        'fields_changed': ['tasks[].add'],
        'source': 'manual'
    })

Backup policy: when overwriting an existing file, a .bak_<TS>_<ctx> is created
next to the file. Rotation follows the existing rule (see docs).
"""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

# DATA_DIR — root of the data tree (config-driven). It used to hold a hardcoded
# dict of client surnames; now the id->folder mapping is built at runtime from
# <DATA_DIR>/clients_index.json (each entry has id and folder).
from _config import DATA_DIR

_PLAN_DIR = Path(DATA_DIR)


def _load_client_folders():
    """Build a mapping client_id -> relative path to the client's folder by
    reading <DATA_DIR>/clients_index.json. Cached at module level.

    Each index entry must contain 'id' and 'folder'. If the index is missing
    or broken, return an empty dict (graceful degradation)."""
    index_path = _PLAN_DIR / "clients_index.json"
    if not index_path.exists():
        return {}
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except (ValueError, OSError):
        return {}
    mapping = {}
    for entry in index:
        cid = entry.get("id")
        folder = entry.get("folder")
        if cid and folder:
            mapping[cid] = folder
    return mapping


_CLIENT_FOLDERS = None


def _client_folders():
    """Lazy initialization of the id->folder mapping (read once)."""
    global _CLIENT_FOLDERS
    if _CLIENT_FOLDERS is None:
        _CLIENT_FOLDERS = _load_client_folders()
    return _CLIENT_FOLDERS


def __getattr__(name):
    """Backward-compat shim: legacy callers reference module-level CLIENT_FOLDERS
    (which used to be a hardcoded dict of surnames). It is now a runtime
    id->folder mapping from clients_index.json. PEP 562 module __getattr__."""
    if name == "CLIENT_FOLDERS":
        return _client_folders()
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )


def _client_dir(client_id):
    """Absolute path to the client's folder. Raises KeyError if client_id is unknown."""
    folders = _client_folders()
    if client_id not in folders:
        raise KeyError(
            "Unknown client_id '{}'. Known: {}".format(
                client_id, sorted(folders.keys())
            )
        )
    return _PLAN_DIR / folders[client_id]


def _state_dir(client_id):
    """The client's state/ folder (created on first access)."""
    d = _client_dir(client_id) / 'state'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _backup(path, ctx):
    """Create a .bak next to the file, if the file exists."""
    if not path.exists():
        return None
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = path.with_name(path.name + '.bak_{}_{}'.format(ts, ctx))
    shutil.copy2(path, bak)
    return bak


# ---------- change audit (journal/state_audit.jsonl) ----------
# Every state write records WHICH top-level fields changed (not their values),
# so the operator can review "what moved in the internal state this week" from
# the dashboard changelog. The audit is best-effort: a failure here must never
# break or roll back a successful state write.

def _audit_path():
    return _PLAN_DIR / 'journal' / 'state_audit.jsonl'


def _diff_keys(old, new):
    """Top-level keys added / removed / changed between two state dicts.

    Compares values by canonical JSON so nested dict/list changes are detected.
    Returns (added, removed, changed) as sorted lists of key names. Robust to
    non-dict inputs (treats them as {})."""
    old = old if isinstance(old, dict) else {}
    new = new if isinstance(new, dict) else {}
    ok, nk = set(old), set(new)
    added = sorted(nk - ok)
    removed = sorted(ok - nk)
    changed = []
    for k in sorted(ok & nk):
        try:
            a = json.dumps(old[k], sort_keys=True, ensure_ascii=False)
            b = json.dumps(new[k], sort_keys=True, ensure_ascii=False)
            same = (a == b)
        except (TypeError, ValueError):
            same = (old[k] == new[k])
        if not same:
            changed.append(k)
    return added, removed, changed


def audit_read():
    """Read journal/state_audit.jsonl into a list of dicts (chronological).

    Never raises: missing file -> []; malformed lines skipped. Each record:
    {ts, client, file, ctx, added[], removed[], changed[], backup}."""
    p = _audit_path()
    if not p.exists():
        return []
    out = []
    try:
        text = p.read_text(encoding='utf-8')
    except OSError:
        return []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _audit_append(client_id, file_name, ctx, added, removed, changed, backup):
    """Append one change record to journal/state_audit.jsonl. Never raises."""
    try:
        if not (added or removed or changed):
            return  # nothing actually changed -> no noise in the log
        rec = {
            'ts': datetime.now().astimezone().isoformat(timespec='seconds'),
            'client': client_id,
            'file': file_name,
            'ctx': ctx,
            'added': added,
            'removed': removed,
            'changed': changed,
            'backup': backup.name if backup else None,
        }
        p = _audit_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception:
        pass  # audit is best-effort; a write must never fail because of it


# ---------- state/*.json ----------

def state_read(client_id, file_name):
    """Read state/<file_name>. If the file is missing, return {}.

    Guarantee: the returned dict can be safely mutated; to persist it back
    you must call state_write explicitly.
    """
    p = _state_dir(client_id) / file_name
    if not p.exists():
        return {}
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def state_write(client_id, file_name, data, ctx='manual'):
    """Atomically write state/<file_name>.

    Sequence:
    1. Read prior version (for the change audit)
    2. Backup (if the file exists)
    3. Serialize -> parse back -> validate correctness
    4. Atomic write via .tmp + rename
    5. UTF-8 validation on write
    6. Append a change record to <DATA_DIR>/journal/state_audit.jsonl

    Returns: Path to written file.
    Raises: ValueError on invalid JSON or UTF-8 problems.
    """
    p = _state_dir(client_id) / file_name

    # prior version, for the field-level audit (best-effort; never fatal)
    old = None
    if p.exists():
        try:
            with open(p, 'r', encoding='utf-8') as f:
                old = json.load(f)
        except (ValueError, OSError):
            old = None

    bak = _backup(p, ctx)

    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
    # roundtrip validation: what we write is valid JSON
    json.loads(text)
    # UTF-8 validation (raises UnicodeEncodeError if something is off)
    payload = text.encode('utf-8')

    tmp = p.with_name(p.name + '.tmp')
    with open(tmp, 'wb') as f:
        f.write(payload)
    os.replace(str(tmp), str(p))

    added, removed, changed = _diff_keys(old, data)
    _audit_append(client_id, file_name, ctx, added, removed, changed, bak)
    return p


# ---------- mental_model.md ----------

def mental_model_read(client_id):
    """Read the client's mental_model.md. If missing, return empty string."""
    p = _client_dir(client_id) / 'mental_model.md'
    if not p.exists():
        return ''
    return p.read_text(encoding='utf-8')


def mental_model_write(client_id, new_content, ctx='manual'):
    """Atomically overwrite mental_model.md.

    Backup + UTF-8 validation + atomic write. Records a change in the audit log
    when the narrative actually changes (best-effort).
    """
    p = _client_dir(client_id) / 'mental_model.md'

    old_txt = None
    if p.exists():
        try:
            old_txt = p.read_text(encoding='utf-8')
        except OSError:
            old_txt = None

    bak = _backup(p, ctx)

    payload = new_content.encode('utf-8')
    tmp = p.with_name(p.name + '.tmp')
    with open(tmp, 'wb') as f:
        f.write(payload)
    os.replace(str(tmp), str(p))

    if old_txt != new_content:
        _audit_append(client_id, 'mental_model.md', ctx, [], [], ['content'], bak)
    return p


# ---------- history.jsonl ----------

def history_append(client_id, entry):
    """Append-only log in history.jsonl.

    entry — dict. If there is no 'ts' key, the current date+time is added.
    Each record is one line of JSON + \\n (jsonl format).

    NEVER rewrites existing records. Append only.
    """
    p = _client_dir(client_id) / 'history.jsonl'
    if 'ts' not in entry:
        entry = dict(entry)  # do not mutate the input dict
        entry['ts'] = datetime.now().astimezone().isoformat(timespec='seconds')
    line = json.dumps(entry, ensure_ascii=False) + '\n'
    with open(p, 'a', encoding='utf-8') as f:
        f.write(line)
    return p


def history_read(client_id):
    """Read history.jsonl into a list of dicts (one per line).

    Returns []: if the file is missing, empty, or every line is malformed.
    Malformed lines are skipped silently (never raises). Order preserved
    (chronological, as written — newest last).
    """
    try:
        p = _client_dir(client_id) / 'history.jsonl'
    except KeyError:
        return []
    if not p.exists():
        return []
    out = []
    try:
        text = p.read_text(encoding='utf-8')
    except OSError:
        return []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


# ---------- helpers for the generator ----------

def state_exists(client_id, file_name):
    """True if state/<file_name> exists. Cheap check without reading."""
    try:
        d = _client_dir(client_id) / 'state'
    except KeyError:
        return False
    return (d / file_name).exists()


def list_state_files(client_id):
    """List of *.json in the client's state/. Useful for debug/inventory."""
    try:
        d = _client_dir(client_id) / 'state'
    except KeyError:
        return []
    if not d.exists():
        return []
    return sorted([p.name for p in d.glob('*.json')])


# ---------- client registration (onboarding) ----------

def register_client(client_id, name_short, name_full='', group='direct',
                    folder=None, extra=None, ctx='onboard'):
    """Register a NEW client in clients_index.json and create its folder tree.

    This is the one safe path to ADD a client; the per-client state/*.json are
    then written by the caller via state_write (identity.json, regime.json, …).
    It mirrors state_write's guarantees on the registry file:

      - atomic     — written via .tmp + os.replace
      - backed up  — the prior clients_index.json is copied to .bak first
      - UTF-8 safe — a Cyrillic name round-trips through json.dumps(
                     ensure_ascii=False) + an explicit utf-8 encode, so the
                     Edit/Write-truncates-Cyrillic hazard never applies here
      - idempotent — re-registering an existing id is a no-op (returns False)
      - cache-safe — the module-level id->folder cache is invalidated, so a
                     state_write to the new client works in the SAME process

    Purely additive: it never reshapes an existing entry, so it needs no
    migration. It writes no state/*.json itself.

    Returns True if a new entry was created, False if the id already existed.
    Raises ValueError on a missing id or a JSON/UTF-8 problem.
    """
    cid = (client_id or '').strip()
    if not cid:
        raise ValueError('register_client: client_id is required')

    index_path = _PLAN_DIR / 'clients_index.json'
    index = []
    if index_path.exists():
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
        except (ValueError, OSError):
            raise ValueError('register_client: clients_index.json is unreadable')
    if not isinstance(index, list):
        raise ValueError('register_client: clients_index.json is not a JSON list')

    if any(isinstance(e, dict) and e.get('id') == cid for e in index):
        return False  # already registered — idempotent no-op

    rel_folder = folder or ('clients/' + cid)
    entry = {
        'id': cid,
        'name_short': name_short or cid,
        'name_full': name_full or '',
        'folder': rel_folder,
        'group': group or 'direct',
    }
    if isinstance(extra, dict):
        entry.update(extra)

    new_index = index + [entry]

    # Backup the prior index, then atomic + UTF-8-validated write.
    bak = _backup(index_path, ctx)
    text = json.dumps(new_index, ensure_ascii=False, indent=2, sort_keys=False)
    json.loads(text)                # JSON round-trip validation
    payload = text.encode('utf-8')  # raises on any UTF-8 problem
    tmp = index_path.with_name(index_path.name + '.tmp')
    with open(tmp, 'wb') as f:
        f.write(payload)
    os.replace(str(tmp), str(index_path))

    # Create the folder tree so the first state_write has a home.
    (_PLAN_DIR / rel_folder / 'state').mkdir(parents=True, exist_ok=True)

    # Invalidate the id->folder cache so state_write(cid, …) resolves now.
    global _CLIENT_FOLDERS
    _CLIENT_FOLDERS = None

    # Best-effort audit line (never fatal).
    try:
        _audit_append(cid, 'clients_index.json', ctx, ['id', 'folder'], [], [], bak)
    except Exception:
        pass

    return True
