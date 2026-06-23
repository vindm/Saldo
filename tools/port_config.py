#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""port_config.py - copy config/instance.yaml to a new location, making any
relative data path absolute first.

Why: the engine resolves a relative `data.dir` / `data.dashboards_dir` against the
config/ directory (see engine/_config.py). If those are relative and the repo is
moved (e.g. Documents -> C:\\Saldo), they would resolve to a different folder and
break. This rewrites them to an absolute path anchored at the ORIGINAL config dir,
so they keep pointing at the same real data after the move. Comments and the rest
of the file are preserved (only the path lines change).

Usage:
    python tools/port_config.py <old_instance.yaml> <new_instance.yaml>

Safe: if the source is missing, or the destination already exists, it does nothing.
"""
import os
import re
import sys

PATH_KEYS = ("dir", "dashboards_dir")  # the data.* keys engine/_config resolves


def _is_absolute(p):
    # Cross-OS: POSIX '/...', Windows drive 'C:\\...' or 'C:/...', or UNC '\\\\srv'.
    return (os.path.isabs(p)
            or (len(p) >= 2 and p[1] == ":")
            or p.startswith("\\\\"))


def _parse_value(rest):
    """Split a YAML scalar line remainder into (value, trailing_comment)."""
    rest = rest.strip()
    if not rest or rest.startswith("#"):
        return "", rest
    if rest[0] in "\"'":
        q = rest[0]
        end = rest.find(q, 1)
        if end > 0:
            return rest[1:end], rest[end + 1:].strip()
        return rest, ""
    if " #" in rest:
        v, c = rest.split(" #", 1)
        return v.strip(), "# " + c.strip()
    return rest, ""


def main():
    if len(sys.argv) < 3:
        print("usage: port_config.py <old.yaml> <new.yaml>")
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    if not os.path.exists(src):
        print("No source config to port (" + src + ") - skipping.")
        return 0
    if os.path.exists(dst):
        print("Config already present at destination - leaving it untouched.")
        return 0

    src_cfg_dir = os.path.dirname(os.path.abspath(src))
    with open(src, encoding="utf-8") as f:
        lines = f.read().splitlines()

    out, in_data, changed = [], False, []
    for ln in lines:
        if re.match(r"^data:\s*(#.*)?$", ln):
            in_data = True
            out.append(ln)
            continue
        # leaving the data: block when a new non-indented key starts
        if in_data and ln and not ln[0].isspace() and ":" in ln:
            in_data = False

        if in_data:
            mk = re.match(r"^(\s+)(dir|dashboards_dir)\s*:\s*(.*)$", ln)
            if mk:
                indent, key, rest = mk.groups()
                val, comment = _parse_value(rest)
                if val and not _is_absolute(val):
                    absp = os.path.normpath(os.path.join(src_cfg_dir, val))
                    newln = '%s%s: "%s"' % (indent, key, absp)
                    if comment:
                        newln += "   " + comment
                    out.append(newln)
                    changed.append("%s: %s -> %s" % (key, val, absp))
                    continue
        out.append(ln)

    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    if changed:
        print("Ported config with absolute data paths:")
        for c in changed:
            print("  " + c)
    else:
        print("Config copied (data paths were already absolute).")
    print("Wrote " + dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
