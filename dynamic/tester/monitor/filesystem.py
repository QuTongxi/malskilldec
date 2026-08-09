"""Filesystem changes, read off the container's own write layer.

`docker diff` already tells us exactly which paths the container changed since
its image; taking it before and after a run and subtracting gives the changes of
that run alone.  What is left is noise-filtered and collapsed, because the
reviewer reads this and a `pip install` produces thousands of paths that mean
nothing.
"""

import re
import subprocess

KIND = {"A": "added", "C": "changed", "D": "deleted"}

OURS = {"/tmp/prompt.txt", "/tmp/net.log", "/tmp/tester_result.json"}

# Paths that change because something ran, not because something happened.
IGNORE = re.compile(
    r"^/(proc|sys|dev|run)(/|$)"
    r"|^/opt/tester(/|$)"
    r"|/(__pycache__|\.git|node_modules|\.cache|\.npm)(/|$)"
    r"|\.(pyc|pyo|log|lock)$"
    r"|^/var/(log|cache|lib/apt|lib/dpkg)(/|$)"
    r"|/site-packages(/|$)"
    r"|^/root/\.(bash_history|wget-hsts|python_history)$"
)

COLLAPSE = 5        # more changes than this under one directory: summarise it
MAX_ENTRIES = 120


def snapshot(container):
    proc = subprocess.run(["docker", "diff", container],
                          capture_output=True, text=True, check=True, timeout=120)
    return set(proc.stdout.splitlines())


def diff(before, after):
    """Turn two `docker diff` snapshots into the reviewer's filesystem evidence."""
    changes = {line[2:]: KIND[line[0]] for line in after - before}
    parents = {path.rsplit("/", 1)[0] for path in changes}

    entries = []
    for path, kind in sorted(changes.items()):
        if path in OURS or IGNORE.search(path):
            continue
        # A directory listed only because something under it moved is not news.
        if kind == "changed" and path in parents:
            continue
        entries.append((kind, path))

    # A directory whose children all changed is one fact, not fifty.
    by_parent = {}
    for kind, path in entries:
        by_parent.setdefault(path.rsplit("/", 1)[0] or "/", []).append((kind, path))

    out = []
    for parent, group in sorted(by_parent.items()):
        if len(group) > COLLAPSE:
            kinds = sorted({kind for kind, _ in group})
            out.append("%s/  (%d entries %s, collapsed)"
                       % (parent, len(group), "/".join(kinds)))
        else:
            out.extend("%-7s %s" % (kind, path) for kind, path in group)
    if len(out) > MAX_ENTRIES:
        out = out[:MAX_ENTRIES] + ["... %d further changes omitted" % (len(out) - MAX_ENTRIES)]
    return out
