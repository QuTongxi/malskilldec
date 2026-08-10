"""Loads the court's prompts from Markdown, so they can be edited as prose.

    from prompts import load
    SYSTEM_PROMPT = load("judge")
    HUMAN_PROMPT = load("judge", "human")

One file per stage: `judge.md`, `prosecutor.md`, `defendant.md`.  Each holds the
system prompt, then a `<!-- HUMAN -->` line, then the human template -- the
marker is an HTML comment so the file still reads as one document.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER = "<!-- HUMAN -->"


def load(name, part="system"):
    """Return the `system` or `human` half of `<name>.md`."""
    if part not in ("system", "human"):
        raise ValueError("part is 'system' or 'human', not %r" % part)

    path = HERE / ("%s.md" % name)
    if not path.is_file():
        raise FileNotFoundError("no prompt at %s" % path)

    text = path.read_text(encoding="utf-8")
    system, found, human = text.partition(MARKER)
    if part == "human":
        if not found:
            raise ValueError("%s has no %s section" % (path.name, MARKER))
        return human.strip()
    return system.strip()
