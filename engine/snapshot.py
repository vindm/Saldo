#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""snapshot.py — snapshot of the system "brain" into tar.gz (a stand-in for git on mounts where unlink is blocked).

Includes only text/code/state: .md .py .json .jsonl
Excludes: secrets, backups (.bak/.tmp/.corrupted/.broken/.before_rerun), __pycache__, _tmp_html, binaries.
Writes to <root>/Archive/snapshots/brain_<ts>.tar.gz

Usage:
  python3 snapshot.py [label]                      # create a snapshot
  python3 snapshot.py --list                       # list existing snapshots
  python3 snapshot.py --restore <snap> [target]    # restore a snapshot (default target: project root)
  python3 snapshot.py --restore <snap> --dry-run   # list what would be restored, change nothing
<snap> may be a full path or a bare filename found in Archive/snapshots/.
Restore overwrites files in place; it does NOT delete files created after the snapshot.
"""
import os, sys, tarfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))          # project root
SNAP_DIR = os.path.join(HERE, '..', 'Archive', 'snapshots')
INCLUDE_EXT = {'.md', '.py', '.json', '.jsonl', '.txt'}
EXCLUDE_SUBSTR = ['/secrets/', '.bak_', '.bak', '.tmp', '_tmp_html/',
                  '__pycache__/', '.corrupted_', '.broken_', '.before_rerun',
                  '_BROKEN_git', '/Archive/snapshots/']

def _included(rel):
    if any(s in rel for s in EXCLUDE_SUBSTR):
        return False
    return os.path.splitext(rel)[1].lower() in INCLUDE_EXT

def make(label='snapshot'):
    os.makedirs(SNAP_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = f'brain_{ts}_{label}.tar.gz'
    out = os.path.join(SNAP_DIR, name)
    tmp = out + '.building'   # write to a temp file, then rename (no unlink needed)
    n = 0; total = 0
    with tarfile.open(tmp, 'w:gz') as tar:
        for dirpath, dirs, files in os.walk(ROOT):
            for fn in files:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, ROOT)
                if _included(rel.replace('\\', '/')):
                    tar.add(full, arcname=rel)
                    n += 1; total += os.path.getsize(full)
    os.replace(tmp, out)   # rename is allowed on the mount
    print(f'snapshot: {name}')
    print(f'files: {n} | source size: {total//1024} KB | archive: {os.path.getsize(out)//1024} KB')
    return out

def lst():
    if not os.path.isdir(SNAP_DIR):
        print('no snapshots'); return
    for f in sorted(os.listdir(SNAP_DIR)):
        if f.endswith('.tar.gz'):
            print(f, '—', os.path.getsize(os.path.join(SNAP_DIR, f))//1024, 'KB')

def _resolve_snapshot(snap):
    """Accept a full path or a bare filename living in Archive/snapshots/."""
    if os.path.exists(snap):
        return snap
    cand = os.path.join(SNAP_DIR, snap)
    if os.path.exists(cand):
        return cand
    return None

def restore(snap, target=None, dry_run=False):
    """Extract a snapshot tar.gz over `target` (default: project ROOT).

    Overwrites files in place. Does not delete files created since the snapshot.
    Guards against path-traversal (members must stay inside target).
    """
    path = _resolve_snapshot(snap)
    if not path:
        print(f'snapshot not found: {snap}')
        print('(try `python3 snapshot.py --list` to see available snapshots)')
        sys.exit(1)
    target = os.path.abspath(target or ROOT)
    with tarfile.open(path, 'r:gz') as tar:
        members = tar.getmembers()
        # path-traversal guard: every member must resolve inside `target`
        for m in members:
            dest = os.path.abspath(os.path.join(target, m.name))
            if dest != target and not dest.startswith(target + os.sep):
                print(f'ABORT: unsafe path in archive: {m.name}')
                sys.exit(1)
        if dry_run:
            for m in members:
                print(m.name)
            print(f'\n(dry run) {len(members)} files would be restored into {target} — nothing changed')
            return
        tar.extractall(target)
    print(f'restored {len(members)} files into {target}')
    print('NOTE: existing files were overwritten in place; files added since the snapshot were left untouched.')

if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == '--list':
        lst()
    elif args and args[0] == '--restore':
        if len(args) < 2:
            print('usage: snapshot.py --restore <snapshot> [target_dir] [--dry-run]')
            sys.exit(2)
        dry = '--dry-run' in args
        tgt = next((a for a in args[2:] if not a.startswith('--')), None)
        restore(args[1], tgt, dry_run=dry)
    else:
        label = args[0] if (args and not args[0].startswith('--')) else 'snapshot'
        make(label)
