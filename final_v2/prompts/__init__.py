"""Loads the court's prompts from Markdown, so they can be edited as prose.

    from prompts import load
    SYSTEM_PROMPT = load("judge")
    HUMAN_PROMPT = load("judge", "human")

One file per stage: `forensics.md`, `prosecutor.md`, `judge.md`.  Each holds the
system prompt, then a `<!-- HUMAN -->` line, then the human template -- the
marker is an HTML comment so the file still reads as one document.

`text()` returns a whole file instead, for the ones that are not a stage:
`precedents.md` and the eight `charges/*.md`.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER = "<!-- HUMAN -->"
PRECEDENTS = "<!-- PRECEDENTS -->"

CHARGES = ("improper_credential_handling", "malicious_code",
           "modifying_system_services", "prompt_injection", "secret_detection",
           "suspicious_download", "third_party_content_exposure",
           "unverifiable_dependency")


def text(name):
    """Return a whole prompt file, e.g. `precedents` or `charges/malicious_code`."""
    path = HERE / ("%s.md" % name)
    if not path.is_file():
        raise FileNotFoundError("no prompt at %s" % path)
    return path.read_text(encoding="utf-8").strip()


def load(name, part="system"):
    """Return the `system` or `human` half of `<name>.md`."""
    if part not in ("system", "human"):
        raise ValueError("part is 'system' or 'human', not %r" % part)

    body = text(name)
    system, found, human = body.partition(MARKER)
    if part == "human":
        if not found:
            raise ValueError("%s.md has no %s section" % (name, MARKER))
        return human.strip()

    system = system.strip()
    # The judge carries the precedent list inside its system prompt: it is the
    # one place empirical patches are allowed to live, so it is a file of its
    # own rather than another paragraph in the prompt.
    if PRECEDENTS in system:
        system = system.replace(PRECEDENTS, text("precedents"))
    return system
