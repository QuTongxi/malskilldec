#!/usr/bin/env python3
"""Static malicious-skill detector.

    uv run python static/pipeline.py <folder> [-o report.json] [--disable-codeql]
                                             [--simplify-score]

Walks the folder, treats every directory holding a SKILL.md/skill.md as one
skill, produces regex (and CodeQL) findings, and aggregates them into claims of
the 8 malicious types from report.pdf.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import efficiency
import matchers
import workers


def discover_skills(root):
    """A directory containing SKILL.md/skill.md is a skill; do not descend further."""
    skills = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in workers.SKIP_DIRS)
        if any(n in ("SKILL.md", "skill.md") for n in filenames):
            skills.append({"name": os.path.relpath(dirpath, root).replace(os.sep, "/"),
                           "path": dirpath})
            dirnames[:] = []
    return sorted(skills, key=lambda s: s["name"])


def aggregate(findings):
    """Group findings into claims, one per malicious type."""
    skill_groups = {f["group"] for f in findings}

    by_type = {}
    for finding in findings:
        for claim_type in matchers.GROUP_TYPES[finding["group"]]:
            by_type.setdefault(claim_type, []).append(finding)

    claims = []
    for claim_type, type_findings in by_type.items():
        score, per_group, bonuses = matchers.score_claim(claim_type, type_findings, skill_groups)
        claims.append({
            "type": claim_type,
            "level": matchers.TYPE_LEVEL[claim_type],
            "score": score,
            "metadata": {
                "skill": type_findings[0]["metadata"]["skill"],
                "skill_path": type_findings[0]["metadata"]["skill_path"],
                "groups": {g: lv for g, lv in sorted(per_group.items())},
                "synergies": [{"groups": [a, b], "bonus": lv} for a, b, lv in bonuses],
                "sources": sorted({f["metadata"]["source"] for f in type_findings}),
                "files": sorted({f["location"]["file"] for f in type_findings}),
            },
            "findings": sorted(type_findings,
                               key=lambda f: (-matchers.LEVEL_RANK[f["level"]],
                                              f["location"]["file"], f["location"]["line"])),
        })
    return sorted(claims, key=lambda c: -c["score"])


def _scan(folder, use_codeql=True, log=print, simplify_score=False):
    """Walk the folder and return the report: every skill, its findings, its claims."""
    matchers.set_scoring(simplify_score)
    if simplify_score:
        log("simplified scoring: levels 1/2/3/4, no cross-group bonus")
    root = os.path.abspath(folder)
    skills = discover_skills(root)
    log("%d skills under %s" % (len(skills), root))

    codeql_by_skill = {}
    if use_codeql:
        if not workers.codeql_available():
            raise RuntimeError("CodeQL is not installed in static/codeql/ (see codeql/README.md)")
        with tempfile.TemporaryDirectory(prefix="codeql-out-") as workdir:
            with efficiency.span("static", "codeql", skills=len(skills)):
                sarifs = workers.run_codeql(root, workdir)

            def skill_of_path(path):
                # skills never nest, so at most one of them contains the file
                for skill in skills:
                    if path.startswith(skill["path"] + os.sep):
                        return skill
                return None

            codeql_by_skill = workers.codeql_findings(sarifs, skill_of_path, root)

    report = {"root": root, "codeql": use_codeql,
              "simplify_score": simplify_score, "skills": []}
    for skill in skills:
        # CodeQL runs once over the corpus, so this is deliberately not called
        # per-skill latency; it measures only regex matching and aggregation.
        with efficiency.span("static", "regex_aggregate_skill", skill=skill["name"]):
            findings = workers.regex_scan(skill)
            findings += codeql_by_skill.get(skill["name"], [])
            claims = aggregate(findings)
        report["skills"].append({
            "skill": skill["name"],
            "path": skill["path"],
            "n_findings": len(findings),
            "claims": claims,
        })

        log("\n%s  -  %d claims" % (skill["name"], len(claims)))
        for claim in claims:
            log("    %-30s %-8s score=%-4d findings=%d"
                % (claim["type"], claim["level"].upper(), claim["score"], len(claim["findings"])))
    return report


def scan(folder, use_codeql=True, log=print, simplify_score=False):
    """Measure and run the complete static corpus."""
    with efficiency.span("static", "static_corpus", folder=os.path.abspath(folder),
                         codeql=use_codeql):
        report = _scan(folder, use_codeql, log, simplify_score)
    efficiency.record(
        "workload", stage="static", skills=len(report["skills"]),
        skills_with_claims=sum(bool(skill["claims"]) for skill in report["skills"]),
        findings=sum(skill["n_findings"] for skill in report["skills"]),
        claims=sum(len(skill["claims"]) for skill in report["skills"]),
        codeql=use_codeql,
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", help="folder to scan recursively for skills")
    parser.add_argument("-o", "--output", default="static_report.json", help="JSON report path")
    parser.add_argument("--disable-codeql", action="store_true",
                        help="regex only; by default CodeQL additionally data-flow-analyses "
                             "the ts/js and python files")
    parser.add_argument("--simplify-score", action="store_true",
                        help="score levels 1/2/3/4 and drop the cross-group bonus, so a "
                             "claim scores the plain sum of its groups' worst findings")
    args = parser.parse_args()

    try:
        report = scan(args.folder, not args.disable_codeql,
                      simplify_score=args.simplify_score)
    except RuntimeError as error:
        sys.exit(str(error))

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print("\nreport written to %s" % args.output)


if __name__ == "__main__":
    main()
