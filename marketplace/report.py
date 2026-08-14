"""What the scan found, against what it cost.

    uv run python marketplace/report.py

Reads the three files the run leaves behind -- the sample manifest, the static
report and the court's results -- and crosses them, because every interesting
number here is a crossing: verdicts against the star stratum they came from,
verdicts against the claim score that queued them, and coverage against the
budget that stopped it.

The one number this deliberately does not print is a market-wide malicious rate.
The sample oversamples the unpopular tail on purpose and the court only ever saw
the top of a score-ordered queue, so any such rate would be two selection effects
wearing a percentage sign.
"""

import argparse
import collections
import json
from pathlib import Path


def band(score):
    for edge in (400, 300, 200, 150, 100, 80, 60):
        if score >= edge:
            return ">=%d" % edge
    return "<60"


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scan", default="marketplace/scan")
    parser.add_argument("--manifest", default="marketplace/manifest.json")
    args = parser.parse_args()

    scan = Path(args.scan)
    static = json.loads((scan / "static.json").read_text(encoding="utf-8"))
    results = json.loads((scan / "results.json").read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    usage = {}
    if (scan / "usage.json").exists():
        usage = json.loads((scan / "usage.json").read_text(encoding="utf-8"))

    stratum = {row["dir"]: row["stratum"] for row in manifest["skills"]}
    stars = {row["dir"]: row["stars"] for row in manifest["skills"]}
    top = {}
    for skill in static["skills"]:
        top[skill["skill"]] = max((c["score"] for c in skill["claims"]), default=0)

    queued = sorted((score for score in top.values() if score >= 60), reverse=True)
    verdicts = collections.Counter(r["verdict"] for r in results)

    print("sample:  %d skills, %d repositories, %d owners"
          % (manifest["kept"], manifest["repos"], manifest["owners"]))
    print("static:  %d accused of something, %d scored >= 60"
          % (sum(1 for s in static["skills"] if s["claims"]), len(queued)))
    print("court:   %d tried  ->  %s" % (len(results), dict(verdicts)))
    if queued:
        print("         %.1f%% of the queue was reached; the cut fell at score %d"
              % (100.0 * len(results) / len(queued),
                 min((top.get(r["skill"], 0) for r in results), default=0)))
    if usage:
        print("cost:    about %.2f CNY over %d calls (%.0fk in, %.0fk out)"
              % (usage["yuan_estimate"], usage["calls"],
                 usage["input_tokens"] / 1000.0, usage["output_tokens"] / 1000.0))
        if results:
            print("         %.2f CNY per skill; the whole queue would be about %.0f CNY"
                  % (usage["yuan_estimate"] / len(results),
                     usage["yuan_estimate"] / len(results) * len(queued)))

    print("\nverdict by claim score")
    by_band = collections.defaultdict(collections.Counter)
    for result in results:
        by_band[band(top.get(result["skill"], 0))][result["verdict"]] += 1
    for name in (">=400", ">=300", ">=200", ">=150", ">=100", ">=80", ">=60", "<60"):
        row = by_band.get(name)
        if row:
            total = sum(row.values())
            print("  %-6s %4d tried   %3d MALICIOUS (%4.1f%%)   %3d BENIGN   %d error"
                  % (name, total, row["MALICIOUS"], 100.0 * row["MALICIOUS"] / total,
                     row["BENIGN"], row["error"]))

    print("\nverdict by star stratum")
    by_stratum = collections.defaultdict(collections.Counter)
    for result in results:
        by_stratum[stratum.get(result["skill"], "?")][result["verdict"]] += 1
    for name in ("S0", "S1", "S2", "S3", "S4", "?"):
        row = by_stratum.get(name)
        if row:
            total = sum(row.values())
            print("  %-3s %4d tried   %3d MALICIOUS (%4.1f%%)   %3d BENIGN   %d error"
                  % (name, total, row["MALICIOUS"], 100.0 * row["MALICIOUS"] / total,
                     row["BENIGN"], row["error"]))

    guilty = [r for r in results if r["verdict"] == "MALICIOUS"]
    guilty.sort(key=lambda r: -top.get(r["skill"], 0))
    print("\n%d convicted, hardest first:" % len(guilty))
    for result in guilty[:40]:
        print("  %-58s score=%-4d stars=%-4s %s"
              % (result["skill"][:58], top.get(result["skill"], 0),
                 stars.get(result["skill"], "?"), result["claim"] or ""))
    if len(guilty) > 40:
        print("  ... and %d more, all in %s" % (len(guilty) - 40, scan / "court"))


if __name__ == "__main__":
    main()
