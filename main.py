#!/usr/bin/env python3
"""MalSkillDet, end to end: scan a folder of agent skills and judge what it accuses.

    uv run python main.py <folder> [-o run/] [--disable-codeql] [--round 3] ...

Three steps, in order, each finished before the next one starts:

    1 static   every skill is accused of the malicious types its patterns match
    2 dynamic  one container per skill; every claim is generated, run and
               reviewed until the machine records confirm it or the rounds run
               out.  Nothing is judged here.
    3 final    the court reads the evidence of the whole run and tries each
               skill on all of its confirmed claims at once: forensics,
               indictment, judgement

The steps are separate because the court's unit of judgement is a *skill*, not a
claim: one chain routinely spans several claims, so it can only be tried once the
dynamic step has finished all of them.

Each step also has its own entry point (`static/pipeline.py`,
`dynamic/pipeline.py`, `final_v2/court.py`), which is how a single step is
re-run without paying for the others again; this file runs the three in order and
keeps their flags, so a full run needs nothing but the folder.

Everything lands under `--out`:

    static.json          step 1: the static report, claims and findings per skill
    dynamic/<skill>.json step 2: every round of every claim, with the review
    dynamic/summary.json step 2: one line per skill
    court/<skill>.md     step 3: forensics, indictment and judgement, to read
    court/court.json     step 3: one court result per skill tried
    verdicts.json        the answer: one verdict per skill in the folder
    _metrics/events.jsonl  timed spans and per-request token usage
    _metrics/summary.json  stage wall clock, latency distributions and cost
"""

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "final_v2"))

import court
import efficiency
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
    # `recursion_limit` counts graph super-steps, and one tool call costs two of
    # them, so the old default of 20 gave the agent nine shell commands to
    # install a product and then trigger the accused behaviour.  Over the 110x110
    # run it never reached ten: 293 of 387 rounds died on GraphRecursionError,
    # 71% of every not_trigger.  Another 32 died on the 20s model timeout.
    dynamic_group.add_argument("--tester-timeout", type=int, default=45,
                               help="seconds per model call of the agent in the container")
    dynamic_group.add_argument("--tester-recursive", type=int, default=60,
                               help="tool-loop budget of the agent in the container "
                                    "(graph steps; a tool call costs two)")
    dynamic_group.add_argument("--tester-temperature", type=float, default=0.0,
                               help="sampling temperature of the container agent (default 0)")
    dynamic_group.add_argument("--loop-timeout", type=int, default=20,
                               help="seconds per model call of generator and reviewer")
    dynamic_group.add_argument("--loop-recursive", type=int, default=50,
                               help="tool-loop budget of generator and reviewer")
    dynamic_group.add_argument("--max-parallel", type=int, default=8,
                               help="skills tested at once (default 8)")
    dynamic_group.add_argument("--skills", nargs="*",
                               help="only these skills, by name; default is all accused")
    dynamic_pipeline.add_prune_args(parser)

    final_group = parser.add_argument_group("final")
    # A court stage writes a whole report in one call, which the 20 seconds of
    # the round loop cannot cover.
    final_group.add_argument("--court-timeout", type=int, default=300,
                             help="seconds per model call of the court (default 300)")
    final_group.add_argument("--court-recursive", type=int, default=50,
                             help="tool-loop budget per court stage")

    metrics_group = parser.add_argument_group("efficiency metrics")
    metrics_group.add_argument(
        "--metrics-dir",
        help="JSONL events and derived summary (default: <out>/_metrics)")
    metrics_group.add_argument(
        "--starting-balance-usd", type=float,
        help="provider balance immediately before the run, for later bill reconciliation")
    metrics_group.add_argument(
        "--pricing-profile", choices=sorted(efficiency.PRICING_PROFILES),
        help="request-tiered API list-price profile used for estimated cost")
    metrics_group.add_argument("--input-price-per-million", type=float,
                               help="USD per million uncached input tokens")
    metrics_group.add_argument("--output-price-per-million", type=float,
                               help="USD per million output tokens")
    metrics_group.add_argument("--cached-input-price-per-million", type=float,
                               help="USD per million cached input tokens; defaults to input price")

    return parser.parse_args(argv)


def collect_verdicts(report, results, judged):
    """One verdict per skill in the folder, accused or not.

    `results` is what step 2 produced, `judged` what step 3 did.  A skill only
    reaches step 3 if a reviewer confirmed at least one of its claims, so the
    skills missing from `judged` are the ones nothing was confirmed against.
    """
    tested = {r["skill"]: r for r in results}
    tried = {r["path"]: r for r in judged}

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

        claims = [{"type": claim["type"], "score": claim["score"],
                   "confirmed": claim["rounds"][-1]["reviewer"]["verdict"] == "confirmed"}
                  for claim in result["claims"]]

        court_result = tried.get(skill["path"])
        if court_result is None:
            verdict = "BENIGN"
            reason = ("no claim was confirmed by the dynamic step"
                      if not any(c["confirmed"] for c in claims)
                      else "confirmed claims, but the court did not try the skill")
        else:
            verdict = court_result["verdict"]
            reason = "%s: %s" % (court_result["claim"] or "<none>", court_result["reason"])

        verdicts.append({
            "skill": skill["skill"], "path": skill["path"],
            "verdict": verdict,
            "reason": reason,
            "claims": claims,
            "judge": (court_result or {}).get("judge_verdict"),
        })
    return verdicts


def run_pipeline(args, out):
    """Run the three stages.  Metrics are configured by ``main``."""
    print("=" * 70, "\nstep 1/3  static\n", sep="")
    try:
        report = static_pipeline.scan(args.folder, not args.disable_codeql)
    except RuntimeError as error:
        sys.exit(str(error))
    (out / "static.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    accused = [s for s in report["skills"] if s["claims"]]
    if args.skills:
        accused = [s for s in accused if s["skill"] in args.skills]

    results, judged = [], []
    if not accused:
        print("\nno skill was accused; nothing to validate")
    else:
        print("\n" + "=" * 70, "\nstep 2/3  dynamic\n", sep="")
        results = dynamic_pipeline.run_all(accused, args, out / "dynamic")

        print("\n" + "=" * 70, "\nstep 3/3  final\n", sep="")
        groups = court.load_evidence(out / "dynamic")
        if not groups:
            print("no claim was confirmed; the court has nothing to try")
        else:
            print("%d skill(s) to try, %d confirmed claim(s) between them\n"
                  % (len(groups), sum(len(g) for g in groups)))
            judged = court.try_skills(groups, out / "court", args.court_timeout,
                                      args.court_recursive, args.max_parallel)

    verdicts = collect_verdicts(report, results, judged)
    (out / "verdicts.json").write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 70, "\nverdicts\n", sep="")
    for verdict in sorted(verdicts, key=lambda v: (v["verdict"] == "BENIGN", v["skill"])):
        print("%-40s %-10s %s" % (verdict["skill"], verdict["verdict"], verdict["reason"]))
    print("\n%d malicious, %d benign, %d error -- written to %s"
          % (sum(v["verdict"] == "MALICIOUS" for v in verdicts),
             sum(v["verdict"] == "BENIGN" for v in verdicts),
             sum(v["verdict"] == "error" for v in verdicts), out))


def runtime_metadata(args):
    """Reproducibility metadata; deliberately excludes credentials and API URLs."""
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        revision, dirty = None, None
    return {
        "command": sys.argv,
        "git_revision": revision,
        "git_dirty": dirty,
        "model": os.environ.get("openai_model"),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "fixed_model_sampling": {
            "generator_temperature": 0.2,
            "reviewer_temperature": 0.0,
            "court_temperature": 0.0,
            "court_top_p": 0.01,
        },
        "config": vars(args),
    }


def main():
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    metrics_dir = Path(args.metrics_dir) if args.metrics_dir else out / "_metrics"
    efficiency.configure(
        metrics_dir / "events.jsonl", metadata=runtime_metadata(args), reset=True)
    try:
        with efficiency.span("pipeline", "end_to_end", skills_root=str(Path(args.folder).resolve())):
            run_pipeline(args, out)
    finally:
        summary = efficiency.finish(
            metrics_dir / "summary.json",
            args.input_price_per_million,
            args.output_price_per_million,
            args.cached_input_price_per_million,
            args.pricing_profile,
        )
        if summary is not None:
            print("efficiency metrics written to %s" % metrics_dir)


if __name__ == "__main__":
    main()
