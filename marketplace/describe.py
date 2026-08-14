"""What the drawn sample actually turned out to be.

    uv run python marketplace/describe.py --manifest marketplace/manifest.json

The quota says what was asked for; this says what arrived, which is never the
same thing -- a stratum runs out of repositories, a cap bites, a fifth of a
monorepo turns out to be the same skill copied five times.  The numbers here are
the ones a methodology section has to carry, so they are printed rather than
inferred later from the directory listing.
"""

import argparse
import collections
import json
import os


def quantiles(values):
    ordered = sorted(values)
    if not ordered:
        return None
    return {name: ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]
            for name, fraction in (("p10", .10), ("p25", .25), ("p50", .50),
                                   ("p75", .75), ("p90", .90))}


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default="marketplace/manifest.json")
    args = parser.parse_args()

    document = json.load(open(args.manifest, encoding="utf-8"))
    skills = document["skills"]

    print("%d skills, %d repositories, %d owners  (seed %s, frame %s)"
          % (len(skills), document["repos"], document["owners"],
             document["seed"], document.get("frame_built_at", "?")))
    print("%d repositories failed to download" % document.get("failed_repos", 0))

    print("\nstratum   asked   got   repos   stars p50")
    for name in ("S0", "S1", "S2", "S3", "S4"):
        rows = [s for s in skills if s["stratum"] == name]
        stars = quantiles([s["stars"] for s in rows])
        print("  %-4s %7d %5d %7d %11s"
              % (name, document["quota"].get(name, 0), len(rows),
                 len({s["source"] for s in rows}), stars["p50"] if stars else "-"))

    per_repo = collections.Counter(s["source"] for s in skills)
    per_owner = collections.Counter(s["source"].split("/")[0] for s in skills)
    print("\nskills per repository: %s" % quantiles(list(per_repo.values())))
    print("skills per owner:      %s" % quantiles(list(per_owner.values())))
    print("biggest contributors:  %s" % per_repo.most_common(5))

    installed = [s["installs"] for s in skills if s.get("installs")]
    known = [v.get("installs_2026_01") for v in installed if isinstance(v, dict)]
    known = [v for v in known if v is not None]
    print("\n%d of %d skills carry a marketplace install count" % (len(installed), len(skills)))
    if known:
        print("installs (Jan 2026 listing): %s" % quantiles(known))

    origin = collections.Counter(s.get("origin") for s in skills)
    print("origin: %s" % dict(origin))

    files = quantiles([s["files"] for s in skills])
    print("files per skill: %s" % files)
    bundled = sum(1 for s in skills if s["files"] > 1)
    print("%d skills (%.1f%%) ship more than SKILL.md alone"
          % (bundled, 100.0 * bundled / max(1, len(skills))))

    root = os.path.join(os.path.dirname(args.manifest), "real_dataset_8k")
    if os.path.isdir(root):
        on_disk = sum(1 for name in os.listdir(root)
                      if os.path.isdir(os.path.join(root, name)))
        print("\n%d directories on disk under %s" % (on_disk, root))


if __name__ == "__main__":
    main()
