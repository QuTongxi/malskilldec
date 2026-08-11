#!/usr/bin/env python3
"""Dynamic validation of a static report.

    uv run python dynamic/pipeline.py --round 3 --tester-recursive 20 \
        --tester-timeout 20 --loop-recursive 50 --loop-timeout 20 \
        --static-report report.json --out results/ --max-parallel 8

Every skill the static layer accused is denoised, given a container, and worked
through claim by claim.  A claim runs generate -> test -> review until the
reviewer confirms the capability or the round budget is spent.  By default the
final judge then decides whether the skill is malicious, which ends the skill,
or benign, which moves on to its next claim.  Pass `--skip-court` to stop after
review and leave judging to `final/court.py`.

Skills run in parallel, claims of one skill run in order, and a skill's
container is destroyed with it.
"""

import argparse
import json
import os
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "final"))

import court
from generator import generator, helper, prepare
from reviewer import reviewer
from tester import build_docker
from tester.tester import Tester

PRINT = threading.Lock()


def log(message):
    with PRINT:
        print(message, flush=True)


def read_skill_md(path):
    for name in ("SKILL.md", "skill.md"):
        marker = Path(path) / name
        if marker.exists():
            return marker.read_text(encoding="utf-8", errors="replace")
    raise FileNotFoundError("no SKILL.md under %s" % path)


MAX_ANCHORS = 8


def anchors(claim):
    """The static matches behind a claim: rule, file, line, matched text.

    The claim record that goes downstream used to keep only the type and the
    behaviour groups, which left the court knowing a claim existed but not where
    in the skill it was matched.  That location is the forensics stage's starting
    coordinate, so it travels with the claim.
    """
    kept = []
    for finding in claim.get("findings", [])[:MAX_ANCHORS]:
        metadata = finding.get("metadata") or {}
        location = finding.get("location") or {}
        kept.append({"rule_id": metadata.get("rule_id"),
                     "description": metadata.get("description"),
                     "file": location.get("file"), "line": location.get("line"),
                     "matched_text": finding.get("matched_text")})
    return kept


def run_claim(claim, skill_md, tester, args):
    """generate -> test -> review, until confirmed or out of rounds."""
    rounds, prior = [], None
    for index in range(1, args.round + 1):
        artefacts = generator.generate(claim, skill_md, prior,
                                       args.loop_timeout, args.loop_recursive)
        log("    round %d  prompt: %s" % (index, artefacts["prompt"][:110].replace("\n", " ")))

        evidence = tester.run(args.tester_timeout, args.tester_recursive, artefacts["prompt"])
        log("    round %d  %d tool calls, %d fs changes, %d network entries"
            % (index, len(evidence["execution"]), len(evidence["filesystem"]),
               len(evidence["network"])))

        verdict = reviewer.review(artefacts["prompt"], artefacts["oracle"], evidence,
                                  skill_md, args.loop_timeout, args.loop_recursive)
        log("    round %d  reviewer: %s" % (index, verdict["verdict"]))

        rounds.append({"round": index, "generator": artefacts,
                       "tester": evidence, "reviewer": verdict})
        if verdict["verdict"] == "confirmed":
            break
        prior = {"round": index, "prompt": artefacts["prompt"], "summary": verdict["summary"]}
    return rounds


def apply_prune(skill, args):
    """Optional claim/finding shrink; unset knobs leave the skill unchanged."""
    before_claims = len(skill["claims"])
    before_findings = sum(len(c["findings"]) for c in skill["claims"])
    pruned = helper.prune_skill(
        skill,
        max_claims=getattr(args, "max_claims", None),
        min_claim_score=getattr(args, "min_claim_score", None),
        max_findings_per_group=getattr(args, "max_findings_per_group", None),
        min_finding_level=getattr(args, "min_finding_level", None),
        max_findings_per_claim=getattr(args, "max_findings_per_claim", None),
        finding_context_chars=getattr(args, "finding_context_chars", None),
    )
    after_claims = len(pruned["claims"])
    after_findings = sum(len(c["findings"]) for c in pruned["claims"])
    if (after_claims, after_findings) != (before_claims, before_findings):
        log("%s: pruned claims %d→%d, findings %d→%d"
            % (skill["skill"], before_claims, after_claims, before_findings, after_findings))
    return pruned


def run_skill(skill, args):
    """Denoise, take a container, and walk the claims until one is malicious."""
    skill = apply_prune(skill, args)
    log("%s: %d claims, denoising" % (skill["skill"], len(skill["claims"])))
    if not skill["claims"]:
        return {"skill": skill["skill"], "path": skill["path"],
                "dropped_findings": [], "testimony": None,
                "claims": [], "verdict": "BENIGN"}

    skill = prepare.denoise(skill, args.loop_timeout, args.loop_recursive)
    log("%s: %d claims after denoising (%d findings dropped)"
        % (skill["skill"], len(skill["claims"]), skill["n_dropped"]))
    # Denoise rebuilds claims from surviving findings, so a finding that maps to
    # several types can grow the claim list again.  Re-apply the claim caps.
    if getattr(args, "max_claims", None) is not None or getattr(args, "min_claim_score", None) is not None:
        skill = helper.prune_skill(
            skill,
            max_claims=getattr(args, "max_claims", None),
            min_claim_score=getattr(args, "min_claim_score", None),
        )
        log("%s: %d claims after re-applying claim caps"
            % (skill["skill"], len(skill["claims"])))

    result = {"skill": skill["skill"], "path": skill["path"],
              "dropped_findings": skill["dropped"], "testimony": None,
              "claims": [], "verdict": "BENIGN"}
    if not skill["claims"]:
        return result

    skill_md = read_skill_md(skill["path"])
    container = build_docker.Container(skill["path"])
    tester = Tester(container)
    skip_court = getattr(args, "skip_court", False)
    try:
        for claim in skill["claims"]:
            log("  %s / %s (score %d)" % (skill["skill"], claim["type"], claim["score"]))
            rounds = run_claim(claim, skill_md, tester, args)
            entry = {"type": claim["type"], "level": claim["level"],
                     "score": claim["score"], "groups": claim["metadata"]["groups"],
                     "anchors": anchors(claim), "rounds": rounds}
            if skip_court:
                result["claims"].append(entry)
                continue

            unit = {"skill": skill["skill"], "path": skill["path"],
                    "claim": {"type": claim["type"], "level": claim["level"],
                              "score": claim["score"], "groups": claim["metadata"]["groups"],
                              "anchors": anchors(claim)},
                    "rounds": rounds}
            # The testimony only depends on the directory, so the claims of one
            # skill share the one the first of them paid for.
            judgement = court.run_court(unit, args.court_timeout, args.loop_recursive,
                                        testimony=result["testimony"])
            result["testimony"] = judgement.pop("testimony")
            log("    court: %s (%s)" % (judgement["verdict"], judgement["reason"]))

            entry["judgement"] = judgement
            result["claims"].append(entry)
            if judgement["verdict"] == "MALICIOUS":
                result["verdict"] = "MALICIOUS"
                break
    finally:
        container.close()

    if skip_court:
        confirmed = sum(
            1 for c in result["claims"]
            if c["rounds"] and c["rounds"][-1]["reviewer"]["verdict"] == "confirmed")
        result["verdict"] = "PENDING_COURT"
        result["confirmed_claims"] = confirmed
    return result


def run_all(skills, args, out):
    """Test every accused skill, one result file each, and return the results.

    `args` carries the budgets: round, tester_timeout, tester_recursive,
    loop_timeout, loop_recursive, court_timeout, max_parallel, and the optional
    prune / skip-court knobs.
    """
    skills = helper.order_skills(skills)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    pending = []
    for skill in skills:
        path = out / ("%s.json" % skill["skill"].replace("/", "-"))
        if path.exists():
            try:
                prior = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pending.append(skill)
                continue
            if prior.get("verdict") == "error":
                pending.append(skill)
            else:
                log("skip %s: already have %s" % (skill["skill"], path.name))
        else:
            pending.append(skill)

    log("%d accused skills (%d left), %d at a time"
        % (len(skills), len(pending), args.max_parallel))
    if not pending:
        results = []
        for skill in skills:
            path = out / ("%s.json" % skill["skill"].replace("/", "-"))
            results.append(json.loads(path.read_text(encoding="utf-8")))
        summary = [{"skill": r["skill"], "verdict": r["verdict"],
                    "claims": [{"type": c["type"],
                                "rounds": len(c["rounds"]),
                                "confirmed": c["rounds"][-1]["reviewer"]["verdict"] == "confirmed",
                                "judgement": (c.get("judgement") or {}).get("verdict")}
                               for c in r.get("claims", [])]}
                   for r in results]
        (out / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return results

    build_docker.ensure_image()

    def worker(skill):
        try:
            result = run_skill(skill, args)
        except Exception:
            log("%s: FAILED\n%s" % (skill["skill"], traceback.format_exc()))
            result = {"skill": skill["skill"], "path": skill["path"],
                      "verdict": "error", "error": traceback.format_exc()}
        (out / ("%s.json" % skill["skill"].replace("/", "-"))).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    with ThreadPoolExecutor(max_workers=args.max_parallel) as pool:
        fresh = list(pool.map(worker, pending))

    # Merge resumed priors with newly finished skills, in the original order.
    by_name = {r["skill"]: r for r in fresh}
    for skill in skills:
        path = out / ("%s.json" % skill["skill"].replace("/", "-"))
        if skill["skill"] not in by_name and path.exists():
            by_name[skill["skill"]] = json.loads(path.read_text(encoding="utf-8"))
    results = [by_name[s["skill"]] for s in skills if s["skill"] in by_name]

    summary = [{"skill": r["skill"], "verdict": r["verdict"],
                "claims": [{"type": c["type"],
                            "rounds": len(c["rounds"]),
                            "confirmed": c["rounds"][-1]["reviewer"]["verdict"] == "confirmed",
                            "judgement": (c.get("judgement") or {}).get("verdict")}
                           for c in r.get("claims", [])]}
               for r in results]
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def add_prune_args(parser):
    """Optional claim/finding shrink knobs; omit them to keep the static report as-is."""
    prune = parser.add_argument_group("prune (optional; unset = original behaviour)")
    prune.add_argument("--max-claims", type=int, default=None,
                       help="keep only the top-N claims by score per skill")
    prune.add_argument("--min-claim-score", type=int, default=None,
                       help="drop claims whose score is below this")
    prune.add_argument("--max-findings-per-group", type=int, default=None,
                       help="keep at most N findings per behaviour group in a claim")
    prune.add_argument("--min-finding-level", choices=helper.LEVELS, default=None,
                       help="drop findings below this severity")
    prune.add_argument("--max-findings-per-claim", type=int, default=None,
                       help="hard cap on findings kept inside one claim")
    prune.add_argument("--finding-context-chars", type=int, default=None,
                       help="truncate each finding's context to this many characters")
    return parser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-report", required=True, help="JSON written by static/pipeline.py")
    parser.add_argument("--out", required=True, help="directory for the per-skill results")
    parser.add_argument("--round", type=int, default=3, help="generate/test/review rounds per claim")
    parser.add_argument("--tester-timeout", type=int, default=20)
    parser.add_argument("--tester-recursive", type=int, default=20)
    parser.add_argument("--loop-timeout", type=int, default=20)
    parser.add_argument("--loop-recursive", type=int, default=50)
    # A court stage writes a whole report in one call and needs longer than the
    # short structured answers of the generate/test/review loop.
    parser.add_argument("--court-timeout", type=int, default=300)
    parser.add_argument("--max-parallel", type=int, default=8, help="skills tested at once")
    parser.add_argument("--skills", nargs="*", help="only these skills, by name")
    parser.add_argument("--skip-court", action="store_true",
                        help="run generate/test/review only; judge later with final/court.py")
    add_prune_args(parser)
    args = parser.parse_args()

    report = json.load(open(args.static_report, encoding="utf-8"))
    skills = [s for s in report["skills"] if s["claims"]]
    if args.skills:
        skills = [s for s in skills if s["skill"] in args.skills]

    run_all(skills, args, args.out)


if __name__ == "__main__":
    main()
