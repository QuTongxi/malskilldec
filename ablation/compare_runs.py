#!/usr/bin/env python3
"""Compare dynamic runs that differ only in their budgets.

    uv run python ablation/compare_runs.py \
        baseline=eval_runs/run_100x100 round1=eval_runs/ablation_round1 ...

Each argument is `label=directory`, where the directory holds `dynamic/` and,
once it has been tried, `court/court.json`.  The point of the table is to keep
the two questions apart:

    what the dynamic stage confirmed      -- rounds, tool calls, confirmations
    what the whole system then concluded  -- the court's verdicts, scored

A budget change can move the first without moving the second (a claim confirmed
in round 2 instead of round 1 is the same claim), which is exactly what the
round / tester-budget ablation is trying to find out.
"""

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval_runs"))

RECURSION = "Recursion limit"


def read_dynamic(directory):
    """Per-claim facts of one dynamic run."""
    claims, skills = [], 0
    for file in sorted(Path(directory).glob("*.json")):
        if file.name == "summary.json":
            continue
        document = json.loads(file.read_text(encoding="utf-8"))
        if document.get("verdict") == "error":
            skills += 1
            continue
        skills += 1
        for claim in document.get("claims", []):
            rounds = claim.get("rounds") or []
            if not rounds:
                continue
            last = rounds[-1]
            claims.append({
                "skill": document["skill"],
                "type": claim["type"],
                "confirmed": last["reviewer"]["verdict"] == "confirmed",
                "rounds": len(rounds),
                "calls": [len(r["tester"]["execution"]) for r in rounds],
                "exhausted": sum(RECURSION in (r["tester"]["llm_output"] or "")
                                 for r in rounds),
            })
    return skills, claims


def summarise(label, directory):
    root = Path(directory)
    skills, claims = read_dynamic(root / "dynamic")
    confirmed = [c for c in claims if c["confirmed"]]
    calls = [n for c in claims for n in c["calls"]]
    n_rounds = sum(len(c["calls"]) for c in claims)

    row = {
        "label": label,
        "skills": skills,
        "claims": len(claims),
        "confirmed": len(confirmed),
        "rate": len(confirmed) / len(claims) if claims else 0.0,
        "rounds": n_rounds,
        "calls_median": sorted(calls)[len(calls) // 2] if calls else 0,
        "calls_max": max(calls) if calls else 0,
        "exhausted": sum(c["exhausted"] for c in claims),
        # Of the claims that were confirmed, how many needed more than one round?
        # This is the number the round budget actually buys.
        "late": sum(1 for c in confirmed if c["rounds"] > 1),
        "court": None,
    }

    court = root / "court" / "court.json"
    if court.exists():
        rows = json.loads(court.read_text(encoding="utf-8"))
        row["court"] = collections.Counter(r["verdict"] for r in rows)
        try:
            import score
            row["score"] = score.score(str(court))
        except Exception as error:
            row["score"] = None
            print("could not score %s: %s" % (label, error), file=sys.stderr)
    return row, claims


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    rows, per_run = [], {}
    for argument in sys.argv[1:]:
        label, _, directory = argument.partition("=")
        if not directory:
            sys.exit("expected label=directory, got %r" % argument)
        row, claims = summarise(label, directory)
        rows.append(row)
        per_run[label] = {(c["skill"], c["type"]): c for c in claims}

    print("\n== dynamic stage ==\n")
    print("%-12s %6s %7s %10s %7s %8s %9s %9s %10s"
          % ("run", "skills", "claims", "confirmed", "rate", "rounds", "calls~", "callsmax", "exhausted"))
    for r in rows:
        print("%-12s %6d %7d %10d %6.1f%% %8d %9d %9d %10d"
              % (r["label"], r["skills"], r["claims"], r["confirmed"], 100 * r["rate"],
                 r["rounds"], r["calls_median"], r["calls_max"], r["exhausted"]))

    print("\nconfirmed claims that needed more than one round "
          "(what the round budget buys):")
    for r in rows:
        print("   %-12s %d of %d" % (r["label"], r["late"], r["confirmed"]))

    if any(r["court"] for r in rows):
        print("\n== court ==\n")
        print("%-12s %10s %8s %6s   %9s %9s %9s"
              % ("run", "MALICIOUS", "BENIGN", "error", "precision", "recall", "F1"))
        for r in rows:
            if not r["court"]:
                continue
            s = r.get("score")
            tail = ("%8.2f%% %8.2f%% %8.2f%%" % (100 * s["precision"], 100 * s["recall"],
                                                 100 * s["f1"])) if s else "   <not scored>"
            print("%-12s %10d %8d %6d   %s"
                  % (r["label"], r["court"]["MALICIOUS"], r["court"]["BENIGN"],
                     r["court"]["error"], tail))

    # Which claims one run confirmed and another did not: the concrete effect of
    # the budget, claim by claim, rather than a difference of two totals.
    if len(rows) > 1:
        base = rows[0]["label"]
        print("\n== claims confirmed under %s but not elsewhere ==\n" % base)
        for other in [r["label"] for r in rows[1:]]:
            lost = [k for k, c in per_run[base].items()
                    if c["confirmed"] and not per_run[other].get(k, {}).get("confirmed", False)]
            gained = [k for k, c in per_run[other].items()
                      if c["confirmed"] and not per_run[base].get(k, {}).get("confirmed", False)]
            print("%s -> %s: %d lost, %d gained" % (base, other, len(lost), len(gained)))
            for skill, type_ in sorted(lost)[:12]:
                print("     lost   %s / %s" % (skill, type_))
            if len(lost) > 12:
                print("     ... %d more" % (len(lost) - 12))


if __name__ == "__main__":
    main()
