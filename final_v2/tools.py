"""The tools the court hands out.

`read_tools(root)` builds the four read-only tools the forensics stage is given.
`root` lives in the closure and never appears in a tool signature, so the model
can only ever name paths inside the skill it was handed: anything resolving
outside comes back as an error instead of a file.

`guide_tool()` builds the single tool the prosecutor is given: the eight charge
files.  It is a tool rather than part of the prompt because the prosecutor should
read only the categories it is actually considering, and because eight guides
inlined at once would drown the forensics report they are meant to be applied to.

`source_tool()` builds the single tool the judge is given: `sources.yaml`, one
entry per domain saying which of visit / download / upload that domain is allowed
to be on the far end of.  It is a tool rather than prompt text because the list is
long, because most of it is irrelevant to any one indictment, and because a
destination the judge has to ask about is one it cannot quietly reason its way
around -- the note that comes back is a fact it has to answer to.

Every tool returns text, and every tool returns its error as text too -- an agent
that mistypes a path should read the mistake and try again rather than crash the
run.
"""

import re
import sys
from pathlib import Path

import yaml
from langchain_core.tools import tool

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prompts

MAX_LINES = 400          # lines returned by one read_file
MAX_CHARS = 20000        # characters returned by any tool
MAX_ENTRIES = 200        # entries listed by ls / dir_tree
MAX_MATCHES = 60         # matches returned by grep
MAX_FILE_BYTES = 1 << 20  # files larger than this are only read up to here

SOURCES = Path(__file__).resolve().parent / "sources.yaml"
CATEGORIES = ("visit", "download", "upload")
DEFAULT = "DEFAULT"      # the reserved key in sources.yaml, not a domain

SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
        ".pytest_cache", "dist", "build"}


def clip(text):
    if len(text) <= MAX_CHARS:
        return text
    return text[:MAX_CHARS] + "\n<... truncated, %d more characters>" % (len(text) - MAX_CHARS)


def read_text(path):
    """The file as text, or None when it is binary."""
    data = path.read_bytes()[:MAX_FILE_BYTES]
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


def walk(root):
    """Every readable file under root, deterministic order, noise skipped."""
    if root.is_file():
        yield root
        return
    for child in sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name)):
        if child.name in SKIP or child.is_symlink():
            continue
        if child.is_dir():
            yield from walk(child)
        elif child.is_file():
            yield child


def guide_tool():
    """The prosecutor's one tool: the constitutive elements of a charge."""

    @tool
    def read_guide(category: str) -> str:
        """Read the constitutive elements of one charge category.

        Args:
            category: one of prompt_injection, malicious_code, secret_detection,
                suspicious_download, improper_credential_handling,
                modifying_system_services, third_party_content_exposure,
                unverifiable_dependency.
        """
        name = (category or "").strip().lower().replace("-", "_")
        if name not in prompts.CHARGES:
            return ("error: %r is not a charge category. the eight are: %s"
                    % (category, ", ".join(prompts.CHARGES)))
        return clip(prompts.text("charges/%s" % name))

    return [read_guide]


def load_sources(path=SOURCES):
    """Read `sources.yaml` into ({host: entry}, default_note)."""
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    default = str(document.pop(DEFAULT, "")).strip()
    entries = {}
    for host, entry in document.items():
        entry = entry or {}
        entries[str(host).strip().lower().strip(".")] = {
            "permissions": [c for c in CATEGORIES
                            if c in {str(p).strip().lower()
                                     for p in (entry.get("permissions") or [])}],
            "note_passed": (entry.get("note_passed") or "").strip(),
            "note_banned": (entry.get("note_banned") or "").strip(),
        }
    return entries, default


def host_of(url):
    """The bare hostname of a URL, or of a host given without a scheme."""
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", (url or "").strip(), flags=re.IGNORECASE)
    text = re.split(r"[/?#]", text)[0].rsplit("@", 1)[-1]   # path, query, userinfo
    if text.startswith("["):                                # [::1]:8080
        return text[1:].partition("]")[0].strip().lower()
    if text.count(":") == 1:                                # host:port
        text = text.partition(":")[0]
    return text.strip().lower().strip(".")


def lookup(entries, host):
    """The most specific entry for `host`, walking up its parent domains.

    `a.b.example.com` tries itself, then `b.example.com`, then `example.com`, and
    stops before the bare TLD -- so one entry for `vercel.app` covers everything
    under it, while `api.github.com` can still differ from `github.com`.
    """
    labels = host.split(".")
    for i in range(len(labels) - 1):
        candidate = ".".join(labels[i:])
        if candidate in entries:
            return candidate, entries[candidate]
    return (host, entries[host]) if host in entries else (None, None)


def source_tool(path=SOURCES):
    """The judge's one tool: what this destination is allowed to be used for."""
    entries, default = load_sources(path)

    def render(host, matched, category, result, permissions, note):
        lines = ["host: %s" % host,
                 "matched entry: %s" % (matched or "<none, DEFAULT applies>"),
                 "category: %s" % category,
                 "result: %s" % result]
        if matched:
            lines.append("permissions: %s" % (", ".join(permissions) or "<none>"))
        if note:
            lines.append("note: %s" % note)
        return "\n".join(lines)

    @tool
    def check_source(category: str, url: str) -> str:
        """Look up one network destination in the court's source list.

        Args:
            category: visit to fetch content that will only be read or parsed,
                download to fetch something that will be executed or loaded,
                upload to send local data, files or credentials outwards.
            url: the destination, a full URL or a bare hostname.
        """
        want = (category or "").strip().lower()
        if want not in CATEGORIES:
            return ("error: %r is not a category. the three are: %s"
                    % (category, ", ".join(CATEGORIES)))

        host = host_of(url)
        if not host:
            return "error: no hostname in %r" % url

        matched, entry = lookup(entries, host)
        if entry is None:
            return render(host, None, want, "NOT LISTED", [], default)
        allowed = want in entry["permissions"]
        return render(host, matched, want, "PERMITTED" if allowed else "BANNED",
                      entry["permissions"],
                      entry["note_passed"] if allowed else entry["note_banned"])

    return [check_source]


def read_tools(root):
    """The four read-only tools, bound to `root`."""
    root = Path(root).resolve()

    def inside(path):
        """The skill directory is the whole world; everything else is an error."""
        target = (root / str(path or ".").lstrip("/")).resolve()
        if target != root and root not in target.parents:
            raise ValueError("%r is outside the skill directory" % path)
        if not target.exists():
            raise FileNotFoundError("%r does not exist" % path)
        return target

    @tool
    def ls(path: str = ".") -> str:
        """List one directory of the skill.

        Args:
            path: directory relative to the skill root, "." for the root itself.
        """
        try:
            target = inside(path)
        except Exception as error:
            return "error: %s" % error
        if not target.is_dir():
            return "error: %r is a file, use read_file" % path
        entries = []
        for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name)):
            if child.name in SKIP:
                continue
            entries.append("%s/" % child.name if child.is_dir()
                           else "%s  (%d bytes)" % (child.name, child.stat().st_size))
        if not entries:
            return "<empty directory>"
        return clip("\n".join(entries[:MAX_ENTRIES]))

    @tool
    def dir_tree(path: str = ".", max_depth: int = 4) -> str:
        """Show the file tree of the skill.

        Args:
            path: directory relative to the skill root, "." for the root itself.
            max_depth: how many levels below `path` to descend.
        """
        try:
            target = inside(path)
        except Exception as error:
            return "error: %s" % error
        if not target.is_dir():
            return "error: %r is a file, use read_file" % path

        lines, budget = [], [MAX_ENTRIES]

        def descend(directory, depth, prefix):
            if depth > max_depth or budget[0] <= 0:
                return
            for child in sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name)):
                if child.name in SKIP or budget[0] <= 0:
                    continue
                budget[0] -= 1
                if child.is_dir():
                    lines.append("%s%s/" % (prefix, child.name))
                    descend(child, depth + 1, prefix + "    ")
                else:
                    lines.append("%s%s  (%d bytes)" % (prefix, child.name,
                                                      child.stat().st_size))

        descend(target, 1, "")
        if budget[0] <= 0:
            lines.append("<... more entries than %d, listing stopped>" % MAX_ENTRIES)
        return clip("\n".join(lines)) or "<empty directory>"

    @tool
    def read_file(path: str, offset: int = 1, limit: int = MAX_LINES) -> str:
        """Read a text file of the skill, one numbered line per line.

        Args:
            path: file relative to the skill root.
            offset: first line to return, counting from 1.
            limit: how many lines to return.
        """
        try:
            target = inside(path)
        except Exception as error:
            return "error: %s" % error
        if target.is_dir():
            return "error: %r is a directory, use ls or dir_tree" % path
        text = read_text(target)
        if text is None:
            return "<binary file, %d bytes>" % target.stat().st_size

        lines = text.splitlines()
        offset = max(1, offset)
        limit = max(1, min(limit, MAX_LINES))
        window = lines[offset - 1:offset - 1 + limit]
        if not window:
            return "<no such lines: the file has %d lines>" % len(lines)

        body = "\n".join("%5d| %s" % (offset + i, line) for i, line in enumerate(window))
        tail = offset - 1 + len(window)
        if tail < len(lines):
            body += "\n<... %d more lines, continue at offset %d>" % (len(lines) - tail, tail + 1)
        return clip(body)

    @tool
    def grep(pattern: str, path: str = ".", max_results: int = MAX_MATCHES) -> str:
        """Search the skill's text files for a regular expression.

        Args:
            pattern: Python regular expression, case-insensitive.
            path: file or directory to search, relative to the skill root.
            max_results: how many matching lines to return.
        """
        try:
            target = inside(path)
            regex = re.compile(pattern, re.IGNORECASE)
        except Exception as error:
            return "error: %s" % error

        results, limit = [], max(1, min(max_results, MAX_MATCHES))
        for file in walk(target):
            text = read_text(file)
            if text is None:
                continue
            name = file.relative_to(root).as_posix()
            for number, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    results.append("%s:%d: %s" % (name, number, line.strip()[:300]))
                    if len(results) >= limit:
                        return clip("\n".join(results) + "\n<... stopped at %d matches>" % limit)
        return clip("\n".join(results)) or "<no match>"

    return [dir_tree, ls, read_file, grep]
