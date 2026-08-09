#!/usr/bin/env python3
"""Dynamic validation of a static report.

    uv run python dynamic/pipeline.py --round 3 --tester-recursive 20 \
        --tester-timeout 20 --loop-recursive 50 --loop-timeout 20 \
        --static-report report.json --out results/ --max-parallel 8

Every skill the static layer accused is denoised, given a container, and worked
through claim by claim.  A claim runs generate -> test -> review until the
reviewer confirms the capability or the round budget is spent; the final judge
then decides whether the skill is malicious, which ends the skill, or benign,
which moves on to its next claim.

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


def run_skill(skill, args):
    """Denoise, take a container, and walk the claims until one is malicious."""
    log("%s: %d claims, denoising" % (skill["skill"], len(skill["claims"])))
    skill = prepare.denoise(skill, args.loop_timeout, args.loop_recursive)
    log("%s: %d claims after denoising (%d findings dropped)"
        % (skill["skill"], len(skill["claims"]), skill["n_dropped"]))

    result = {"skill": skill["skill"], "path": skill["path"],
              "dropped_findings": skill["dropped"], "testimony": None,
              "claims": [], "verdict": "BENIGN"}
    if not skill["claims"]:
        return result

    skill_md = read_skill_md(skill["path"])
    container = build_docker.Container(skill["path"])
    tester = Tester(container)
    try:
        for claim in skill["claims"]:
            log("  %s / %s (score %d)" % (skill["skill"], claim["type"], claim["score"]))
            rounds = run_claim(claim, skill_md, tester, args)
            unit = {"skill": skill["skill"], "path": skill["path"],
                    "claim": {"type": claim["type"], "level": claim["level"],
                              "score": claim["score"], "groups": claim["metadata"]["groups"]},
                    "rounds": rounds}
            # The testimony only depends on the directory, so the claims of one
            # skill share the one the first of them paid for.
            judgement = court.run_court(unit, args.court_timeout, args.loop_recursive,
                                        testimony=result["testimony"])
            result["testimony"] = judgement.pop("testimony")
            log("    court: %s (%s)" % (judgement["verdict"], judgement["reason"]))

            result["claims"].append({"type": claim["type"], "level": claim["level"],
                                     "score": claim["score"], "groups": claim["metadata"]["groups"],
                                     "rounds": rounds, "judgement": judgement})
            if judgement["verdict"] == "MALICIOUS":
                result["verdict"] = "MALICIOUS"
                break
    finally:
        container.close()
    return result


def run_all(skills, args, out):
    """Test every accused skill, one result file each, and return the results.

    `args` carries the budgets: round, tester_timeout, tester_recursive,
    loop_timeout, loop_recursive, court_timeout, max_parallel.
    """
    skills = helper.order_skills(skills)
    log("%d accused skills, %d at a time" % (len(skills), args.max_parallel))

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
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
        results = list(pool.map(worker, skills))

    summary = [{"skill": r["skill"], "verdict": r["verdict"],
                "claims": [{"type": c["type"],
                            "rounds": len(c["rounds"]),
                            "confirmed": c["rounds"][-1]["reviewer"]["verdict"] == "confirmed",
                            "judgement": c["judgement"]["verdict"]}
                           for c in r.get("claims", [])]}
               for r in results]
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


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
    args = parser.parse_args()

    report = json.load(open(args.static_report, encoding="utf-8"))
    skills = [s for s in report["skills"] if s["claims"]]
    if args.skills:
        skills = [s for s in skills if s["skill"] in args.skills]

    run_all(skills, args, args.out)
    log("\nwritten to %s" % args.out)


if __name__ == "__main__":
    main()
