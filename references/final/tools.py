"""The read-only window onto one skill directory.

`read_tools(root)` builds the four tools the defendant and the prosecutor are
given.  `root` lives in the closure and never appears in a tool signature, so
the model can only ever name paths inside the skill it was handed: anything
resolving outside comes back as an error instead of a file.

Every tool returns text, and every tool returns its error as text too -- an
agent that mistypes a path should read the mistake and try again rather than
crash the run.
"""

import re
from pathlib import Path

from langchain_core.tools import tool

MAX_LINES = 400          # lines returned by one read_file
MAX_CHARS = 20000        # characters returned by any tool
MAX_ENTRIES = 200        # entries listed by ls / dir_tree
MAX_MATCHES = 60         # matches returned by grep
MAX_FILE_BYTES = 1 << 20  # files larger than this are only read up to here

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


def read_tools(root):
    """The four tools, bound to `root`."""
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
