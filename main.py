#!/usr/bin/env python3
"""MalSkillDet, end to end: scan a folder of agent skills and judge what it accuses.

    uv run python main.py <folder> [-o run/] [--disable-codeql] [--round 3] ...

    static   every skill is accused of the malicious types its patterns match
    dynamic  one container per skill; each claim is generated, run and reviewed
             until the machine records confirm it or the rounds run out
    final    the court tries every confirmed claim: testimony, indictment,
             judgement -- and a skill ends the moment one claim is malicious

The three stages also have their own entry points (`static/pipeline.py`,
`dynamic/pipeline.py`, `final/court.py`); this one runs them in order and keeps
their flags, so a full run needs nothing but the folder.

Everything lands under `--out`:

    static.json          the static report, claims and findings per skill
    dynamic/<skill>.json every round of every claim, with the court's judgement
    dynamic/summary.json one line per skill
    court/<skill>-<claim>.md   testimony, indictment and judgement to read
    verdicts.json        the answer: one verdict per skill in the folder
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "final"))

import court
from dynamic import pipeline as dynamic_pipeline
from static import pipeline as static_pipeline


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="folder to scan recursively for skills")
    parser.add_argument("-o", "--out", default="run", help="directory for everything produced")

    static_group = parser.add_argument_group("static")
    static_group.add_argument("--disable-codeql", action="store_true",
                              help="regex only; by default CodeQL also data-flow-analyses "
                                   "the ts/js and python files")

    dynamic_group = parser.add_argument_group("dynamic")
    dynamic_group.add_argument("--round", type=int, default=3,
                               help="generate/test/review rounds per claim (default 3)")
    dynamic_group.add_argument("--tester-timeout", type=int, default=20,
                               help="seconds per model call of the agent in the container")
    dynamic_group.add_argument("--tester-recursive", type=int, default=20,
                               help="tool-loop budget of the agent in the container")
    dynamic_group.add_argument("--loop-timeout", type=int, default=20,
                               help="seconds per model call of generator and reviewer")
    dynamic_group.add_argument("--loop-recursive", type=int, default=50,
                               help="tool-loop budget of generator and reviewer")
    dynamic_group.add_argument("--max-parallel", type=int, default=8,
                               help="skills tested at once (default 8)")
    dynamic_group.add_argument("--skills", nargs="*",
                               help="only these skills, by name; default is all accused")

    final_group = parser.add_argument_group("final")
    # A court stage writes a whole report in one call, which the 20 seconds of
    # the round loop cannot cover.
    final_group.add_argument("--court-timeout", type=int, default=300,
                             help="seconds per model call of the court (default 300)")

    return parser.parse_args(argv)


def court_reports(results, directory):
    """Write the Markdown of every claim that reached the court."""
    written = 0
    for result in results:
        for claim in result.get("claims", []):
            judgement = claim["judgement"]
            if judgement.get("indictment"):
                court.write_report(directory, result["skill"], claim["type"],
                                   judgement, testimony=result.get("testimony"))
                written += 1
    return written


def collect_verdicts(report, results):
    """One verdict per skill in the folder, accused or not."""
    tested = {r["skill"]: r for r in results}

    verdicts = []
    for skill in report["skills"]:
        result = tested.get(skill["skill"])
        if result is None:
            verdicts.append({
                "skill": skill["skill"], "path": skill["path"], "verdict": "BENIGN",
                "reason": "the static layer raised no claim"
                          if not skill["claims"] else "not selected for this run",
                "claims": [],
            })
            continue

        if result["verdict"] == "error":
            verdicts.append({"skill": skill["skill"], "path": skill["path"],
                             "verdict": "error", "reason": result["error"].strip().splitlines()[-1],
                             "claims": []})
            continue

        claims, decided = [], None
        for claim in result["claims"]:
            judgement = claim["judgement"]
            confirmed = claim["rounds"][-1]["reviewer"]["verdict"] == "confirmed"
            claims.append({"type": claim["type"], "score": claim["score"],
                           "confirmed": confirmed, "court": judgement["verdict"],
                           "judge": judgement["judge_verdict"], "reason": judgement["reason"]})
            if judgement["verdict"] == "MALICIOUS" and decided is None:
                decided = claims[-1]

        verdicts.append({
            "skill": skill["skill"], "path": skill["path"],
            "verdict": result["verdict"],
            "reason": ("%s: %s" % (decided["type"], decided["reason"])) if decided
                      else "no claim survived the court",
            "claims": claims,
        })
    return verdicts


def main():
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 70, "\nstatic\n", sep="")
    try:
        report = static_pipeline.scan(args.folder, not args.disable_codeql)
    except RuntimeError as error:
        sys.exit(str(error))
    (out / "static.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    accused = [s for s in report["skills"] if s["claims"]]
    if args.skills:
        accused = [s for s in accused if s["skill"] in args.skills]

    results = []
    if not accused:
        print("\nno skill was accused; nothing to validate")
    else:
        print("\n" + "=" * 70, "\ndynamic + final\n", sep="")
        results = dynamic_pipeline.run_all(accused, args, out / "dynamic")
        written = court_reports(results, out / "court")
        print("\n%d court report(s) under %s" % (written, out / "court"))

    verdicts = collect_verdicts(report, results)
    (out / "verdicts.json").write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 70, "\nverdicts\n", sep="")
    for verdict in sorted(verdicts, key=lambda v: (v["verdict"] == "BENIGN", v["skill"])):
        print("%-40s %-10s %s" % (verdict["skill"], verdict["verdict"], verdict["reason"]))
    print("\n%d malicious, %d benign, %d error -- written to %s"
          % (sum(v["verdict"] == "MALICIOUS" for v in verdicts),
             sum(v["verdict"] == "BENIGN" for v in verdicts),
             sum(v["verdict"] == "error" for v in verdicts), out))


if __name__ == "__main__":
    main()
