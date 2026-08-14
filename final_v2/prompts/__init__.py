"""Loads the court's prompts from Markdown, so they can be edited as prose.

    from prompts import load
    SYSTEM_PROMPT = load("judge")
    HUMAN_PROMPT = load("judge", "human")

One file per stage: `forensics.md`, `prosecutor.md`, `judge.md`.  Each holds the
system prompt, then a `<!-- HUMAN -->` line, then the human template -- the
marker is an HTML comment so the file still reads as one document.

`text()` returns a whole file instead, for the ones that are not a stage:
`payload.md` and the eight `charges/*.md`.

`payload.md` is a shared rubric rather than a prompt of its own, and every place
that needs it pulls it in by marker instead of keeping a copy: three near-identical
paraphrases of one rubric is how the three stages came to grade the same payload
differently.

The domain list that used to sit beside it as `precedents.md` is now
`../sources.yaml`, reached through the judge's `check_source` tool; its general
rules -- the ones that were never about a domain -- were folded into the four
steps of `judge.md`.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER = "<!-- HUMAN -->"

# Marker -> the file that replaces it, resolved in `text()` so charge guides read
# through `read_guide` get the same rubric the prompts do.
INCLUDES = {"<!-- PAYLOAD -->": "payload"}

CHARGES = ("improper_credential_handling", "malicious_code",
           "modifying_system_services", "prompt_injection", "secret_detection",
           "suspicious_download", "third_party_content_exposure",
           "unverifiable_dependency")


def text(name):
    """Return a whole prompt file with its includes resolved."""
    path = HERE / ("%s.md" % name)
    if not path.is_file():
        raise FileNotFoundError("no prompt at %s" % path)
    body = path.read_text(encoding="utf-8").strip()
    for marker, include in INCLUDES.items():
        if marker in body:
            body = body.replace(marker, text(include))
    return body


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
    return system.strip()
