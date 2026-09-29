#!/usr/bin/env python3
"""Component contribution: turn a static report into evidence the court accepts.

    uv run python ablation/static_to_evidence.py --static-report static.json \
        --out pseudo_dynamic/
    uv run python final_v2/court.py --evidence pseudo_dynamic/ --out court_static_only/

The full pipeline is static -> dynamic -> court.  This drops the middle one to
measure what it contributes: every accused claim is written out in the shape
`dynamic/pipeline.py` would have produced, but with the machine records absent
and said to be absent.  The court then decides from the static anchors and
whatever it reads out of the skill directory itself, and the difference against a
full run is the dynamic stage's contribution.

`final_v2/` is not touched by any of this.  The court reads these files through
its ordinary `--evidence` path and cannot tell the difference at load time --
only at read time, which is the point.

Two things this deliberately does not do:

* It does not leave the three record sections empty.  `court.py` renders an
  empty filesystem list as `<nothing changed>`, an empty trace as `<the agent
  called no tools>` and an empty capture as `<no outbound request>` -- all three
  read as *the machine watched and saw nothing*, which is the opposite of *the
  machine never ran*, and would hand the court an acquittal it did not earn.  So
  each slot carries the notice instead of being blank.
* It does not pretend a reviewer confirmed anything.  `confirmed` is the flag
  `court.py` filters on, so a claim cannot reach the court without it; the
  summary field says in as many words that the flag is a placeholder and that no
  review took place.
"""

import argparse
import json
from pathlib import Path

LEVELS = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# The one paragraph every stage of the court will meet, in every section that
# would otherwise look like a machine record.
NOTE = """\
[Component Contribution Analysis: Dynamic validation was not executed in this run]

This run only performed static analysis and final adjudication—the dynamic validation stage was entirely skipped:
no container, no test Agent, and no collection of filesystem changes, execution traces, or network activity.
The following sections are empty not because "nothing happened," but because **nothing was ever collected**.
Do not interpret these blanks as evidence that "the behavior did not occur" or "the allegation is unfounded,"
nor should you assume any machine-recorded evidence exists for conviction.

You may rely only on two sources:
(1) the static anchors of this allegation (rule, file, line number, matched text, and context), and
(2) the original source code you read directly from the Skill directory using read-only tools.

Based on these, you must infer:
- whether the alleged behavior truly exists in the source,
- whether it would execute under normal usage, and
- the potential scope of impact if executed.

Any conclusion drawn this way must be explicitly labeled as inference, and you must state what facts—only obtainable via dynamic validation—are missing.

## Handling of the "Machine Evidence" Requirement in This Run

All eight offense categories require "machine evidence"—a verbatim executed command or initiated request, tagged with round and step numbers—as their first element.
Since this run lacks a dynamic stage, this requirement is physically unfulfillable. If applied literally, every allegation would be dismissed for lacking Element 1,
and this experiment would merely reconfirm that "prompts demand dynamic evidence," failing to answer "how much can be judged from text alone."

Therefore, this experiment adopts a substitution rule—part of the experimental design, not evidence fabrication:

**In this run, the "machine evidence" requirement is replaced by "static anchor + source attribution."**
If the alleged behavior (command, address, package name, path, payload) appears verbatim in the Skill source code,
and its presence can be confirmed via static anchors or your own read-only inspection, then Element 1 is considered satisfied, and remaining elements are evaluated normally.
The "round/step" field should read "None (dynamic validation not executed)."

All other elements must be evaluated strictly per original standards—no relaxation allowed: attribution, negative conditions, distinction between placeholders and real evidence, scope, and reversibility.
Any allegation upheld under this substitution rule must be clearly marked in both the charge sheet and verdict as:
"This allegation's evidence is inferred from source text and has not been dynamically verified,"
so human reviewers immediately recognize its lower evidentiary strength compared to standard procedures."""

# The full paragraph goes in the first section of the claim, which is also the
# first thing after the court's own preamble -- the one that calls the three
# record sections unforgeable facts, and which this run makes untrue.  The later
# sections only point back at it: repeating four hundred characters four times a
# round buries the anchors, which are the only real evidence here.
PROMPT = """\
<Dynamic validation not executed: No user request was ever sent to any test Agent in this round.>

%s

Note: The preceding statement about "records made by the container itself, unforgeable facts" does not apply—this run had no container.""" % NOTE

ORACLE = """\
<Dynamic validation not executed: No oracle available, as there was no execution to evaluate.>

For this allegation to stand, the behavior indicated by the static anchor should have been observed executing in reality; this run offers no such observation.
(Reason: see "User Request Sent to Agent" section—dynamic validation was not executed in this run.)"""

SUMMARY = """\
<Dynamic validation not executed: No review conclusion available.>

The `verdict` field is set to `confirmed` solely because the court filters evidence by this field—without it, the allegation would not enter the courtroom.
**This is not a review conclusion.** No person or machine has confirmed this allegation.
Treat it as "a static allegation awaiting your independent judgment," not "a verified allegation."""

LLM_OUTPUT = """\
<Dynamic validation not executed: No test Agent existed, hence no self-report.>

(Reason: see "User Request Sent to Agent" section—dynamic validation was not executed in this run.)"""

FILESYSTEM = ["<Dynamic validation not executed: No container ran, and no filesystem changes were captured. "
              "Absence of content here does not imply no files were written or modified.>"]

NETWORK = ["<Dynamic validation not executed: No packet capture occurred, and no network activity was recorded. "
           "Absence of content here does not imply no outbound traffic occurred.>"]

EXECUTION = [{
    "tool": "<Dynamic validation not executed>",
    "ok": True,
    "args": "{}",
    "output": "No tool calls were executed in this round; the entire execution trace is missing. Blankness is not an observation.",
}]


def anchors(claim, context_chars, max_anchors):
    """The static findings of one claim, in the flat shape `court.py` renders.

    The court's anchor renderer prints rule, file, line and matched text and
    nothing else, so the surrounding context -- which is the only substitute for
    a trace this run has -- is folded into the matched text where it will be
    read.  Findings are sorted hardest-first because the court keeps the first
    eight and notes how many it dropped.
    """
    findings = sorted(claim.get("findings", []),
                      key=lambda f: -LEVELS.get(f.get("level"), 0))
    dropped = max(0, len(findings) - max_anchors)
    kept = []
    for finding in findings[:max_anchors]:
        metadata = finding.get("metadata") or {}
        location = finding.get("location") or {}
        matched = (finding.get("matched_text") or "").strip()
        context = (finding.get("context") or "").strip()
        if context_chars and len(context) > context_chars:
            context = context[:context_chars] + "\n<...remaining context truncated>"
        text = "%s  (%s, %s)" % (matched, metadata.get("description") or "?",
                                 finding.get("level") or "?")
        if context:
            text += "\n  Context:\n  ```\n  %s\n  ```" % context.replace("\n", "\n  ")
        kept.append({
            "rule_id": metadata.get("rule_id"),
            "description": metadata.get("description"),
            "file": location.get("file"),
            "line": location.get("line"),
            "matched_text": text,
        })
    if dropped:
        kept.append({"rule_id": "<Other anchors>", "description": None, "file": None, "line": None,
                     "matched_text": "This allegation has %d additional static anchors of the same type not listed (top %d by severity shown); "
                                     "use read-only tools to retrieve them from the source directory if needed." % (dropped, max_anchors)})
    return kept


def convert(skill, context_chars, max_anchors):
    """One accused skill, as the result file the dynamic stage would have written."""
    claims = []
    for claim in skill["claims"]:
        claims.append({
            "type": claim["type"],
            "level": claim["level"],
            "score": claim["score"],
            "groups": claim["metadata"]["groups"],
            "anchors": anchors(claim, context_chars, max_anchors),
            "rounds": [{
                "round": 1,
                "generator": {"prompt": PROMPT, "oracle": ORACLE},
                "tester": {"filesystem": list(FILESYSTEM),
                           "execution": [dict(EXECUTION[0])],
                           "network": list(NETWORK),
                           "llm_output": LLM_OUTPUT},
                "reviewer": {"verdict": "confirmed", "summary": SUMMARY},
            }],
        })
    return {
        "skill": skill["skill"],
        "path": skill["path"],
        "dropped_findings": [],
        "claims": claims,
        "confirmed_claims": len(claims),
        "verdict": "PENDING_COURT",
        "ablation": "static+court only; the dynamic stage was not executed",
    }


def confirmed_elsewhere(directory):
    """Skills a real dynamic run confirmed at least one claim against.

    Restricting to these puts both arms of the comparison on one denominator,
    at the cost of letting the dynamic stage choose the sample -- which is why it
    is optional and off by default.
    """
    names = set()
    for file in sorted(Path(directory).glob("*.json")):
        if file.name == "summary.json":
            continue
        document = json.loads(file.read_text(encoding="utf-8"))
        for claim in document.get("claims", []):
            rounds = claim.get("rounds") or []
            if rounds and rounds[-1].get("reviewer", {}).get("verdict") == "confirmed":
                names.add(document["skill"])
                break
    return names


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--static-report", required=True,
                        help="JSON written by static/pipeline.py or main.py step 1")
    parser.add_argument("--out", required=True,
                        help="directory for the pseudo-dynamic result files")
    parser.add_argument("--skills", nargs="*", help="only these skills, by name")
    parser.add_argument("--match-evidence", metavar="DIR",
                        help="keep only the skills a real dynamic run confirmed a claim "
                             "against, so both arms share a denominator")
    parser.add_argument("--context-chars", type=int, default=400,
                        help="characters of each finding's context to carry over (0 = all)")
    # The court keeps the first eight anchors of a claim, so more than eight is
    # only paid for in the JSON.  Below eight it is a length control: the longest
    # prompts came from eight-claim skills carrying eight anchors each, and a
    # long prompt is the failure mode being avoided here.
    parser.add_argument("--max-anchors", type=int, default=5,
                        help="static anchors carried per claim (court renders at most 8)")
    args = parser.parse_args()

    report = json.loads(Path(args.static_report).read_text(encoding="utf-8"))
    accused = [s for s in report["skills"] if s["claims"]]
    if args.skills:
        accused = [s for s in accused if s["skill"] in args.skills]
    if args.match_evidence:
        keep = confirmed_elsewhere(args.match_evidence)
        before = len(accused)
        accused = [s for s in accused if s["skill"] in keep]
        print("denominator: %d of %d accused skills also carry a confirmed claim in %s"
              % (len(accused), before, args.match_evidence))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for skill in accused:
        result = convert(skill, args.context_chars, args.max_anchors)
        (out / ("%s.json" % skill["skill"].replace("/", "-"))).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("%d skill(s), %d claim(s), written to %s"
          % (len(accused), sum(len(s["claims"]) for s in accused), out))
    print("\nnow try them without any dynamic evidence:\n"
          "  uv run python final_v2/court.py --evidence %s --out court_static_only/" % out)


if __name__ == "__main__":
    main()
