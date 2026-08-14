"""Freeze the sampling frame for the market-scale scan.

    uv run python marketplace/build_frame.py -o marketplace/frame.json

The frame is the set of *repositories* we are willing to sample skills from,
each carrying the two popularity axes and the stratum it falls in.  Writing it
down is the point: a scan of "8000 skills off the internet" is not reproducible,
a scan of a named frame with a recorded seed is.

Two sources, because neither alone covers the population:

* **skills.sh**, the marketplace.  Its index gives skill-level `installs`, the
  only adoption metric that describes a *skill* rather than the repository it
  happens to sit in.  Two slices of it are enumerable -- the MIT snapshot
  bundled in `mastra-ai/skills-api` (34k skills, Jan 2026) and the live all-time
  endpoint -- and the second one is a *leaderboard*: today its 9.6k rows have a
  median of 2331 installs and nothing between 100 and 999.  It is the head, by
  construction, so it cannot supply the tail this study is about.
* **GitHub topic search**, star-banded.  This is the tail: `topic:agent-skills`
  alone holds ~12k repositories at 0-4 stars.  Search returns the star count in
  the hit, so banding the query is both the enumeration and the stratification.

A repository enters the frame only under the ceiling (`--max-stars`, default
100).  The argument for a ceiling is not that popular skills are safe; it is
that a malicious skill with mass adoption would have had to fool the whole
community, which is a different and much rarer event than the one being measured
-- and the one measurement that exists points the same way: skills above 1000
installs are flagged at 16.2% against 19.3% overall (arXiv:2603.16572).
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import github

SNAPSHOT = ("https://raw.githubusercontent.com/mastra-ai/skills-api/main/"
            "src/registry/scraped-skills.json")
LIVE = "https://skills.sh/api/skills/all-time/%d"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) malskilldet-frame"}

# The topics the ecosystem actually tags itself with.  Measured today:
# agent-skills 14871 repos, claude-skills 6798, claude-skill 4379,
# claude-code-skills 1442, skill-md 1124.
TOPICS = ["agent-skills", "claude-skills", "claude-skill",
          "claude-code-skills", "skill-md", "agent-skill"]

# Log-spaced, because the star distribution is heavy-tailed: across the 3630
# skills.sh source repositories the quartiles are 3 / 32 / 453.  Equal-width
# bands would put nine tenths of the frame in one bucket.
STRATA = [("S0", 0, 0), ("S1", 1, 4), ("S2", 5, 19), ("S3", 20, 49), ("S4", 50, 99)]


def stratum(stars):
    for name, low, high in STRATA:
        if low <= stars <= high:
            return name
    return None


def fetch_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def skills_sh_index(cache):
    """The marketplace's own listing: skill -> installs, and the repos behind it.

    The snapshot and the live leaderboard are unioned rather than merged: they
    are seven months apart and their install counts are not on the same scale
    (the top skill went from 70k to 2.9M), so each install figure is kept with
    the date it was read.
    """
    path = os.path.join(cache, "scraped-skills.json")
    if not os.path.exists(path):
        print("fetching the skills.sh snapshot ...")
        with open(path, "wb") as fh:
            with urllib.request.urlopen(urllib.request.Request(SNAPSHOT, headers=UA),
                                        timeout=120) as response:
                fh.write(response.read())
    snapshot = json.load(open(path, encoding="utf-8"))

    live_path = os.path.join(cache, "live_alltime.json")
    if os.path.exists(live_path):
        live = json.load(open(live_path, encoding="utf-8"))
    else:
        print("fetching the skills.sh all-time leaderboard ...")
        live, page = [], 0
        while True:
            data = fetch_json(LIVE % page)
            live += data["skills"]
            if not data.get("hasMore"):
                break
            page += 1
            time.sleep(0.3)
        json.dump(live, open(live_path, "w", encoding="utf-8"))

    listed = {}
    for skill in snapshot["skills"]:
        listed[(skill["source"], skill["skillId"])] = {"installs_2026_01": skill["installs"]}
    for skill in live:
        listed.setdefault((skill["source"], skill["skillId"]), {})["installs_2026_08"] = \
            skill["installs"]
    print("skills.sh: %d listed skills across %d repositories (snapshot %s)"
          % (len(listed), len({k[0] for k in listed}), snapshot["scrapedAt"][:10]))
    return listed


def repo_metadata(sources, tok, cache, cached_only=False):
    """Star counts for the skills.sh repositories, one lookup each, checkpointed.

    This is the slow half of the build -- there is no batch endpoint for "these
    3630 repositories" -- so it writes through to disk and resumes, and it runs
    on three threads because ten trips the secondary limit within a minute.
    """
    path = os.path.join(cache, "repo_meta.json")
    known = {}
    if os.path.exists(path):
        known = {row["source"]: row for row in json.load(open(path, encoding="utf-8"))}
    todo = [s for s in sources if s not in known]
    if cached_only or not todo:
        return known
    print("looking up %d repositories over GraphQL (%d cached) ..." % (len(todo), len(known)))

    # One POST per hundred, checkpointed, so a limit landing mid-run costs the
    # last batch rather than all of them.
    for start in range(0, len(todo), 500):
        batch = github.repos_batch(todo[start:start + 500], tok)
        known.update(batch)
        json.dump(list(known.values()), open(path, "w", encoding="utf-8"))
        print("  %d/%d resolved" % (min(start + 500, len(todo)), len(todo)), flush=True)
    for full in todo:
        known.setdefault(full, {"source": full, "stars": None, "gone": True})
    json.dump(list(known.values()), open(path, "w", encoding="utf-8"))
    return known


def topic_repos(tok, cache, max_stars):
    """The tail, harvested from GitHub topics in star bands.

    Search serves at most 1000 results per query, so each topic is asked once per
    stratum instead of once; the bands are the same ones the sampling uses, which
    means a band that overflows 1000 is visible as `hit the ceiling` rather than
    silently truncated.
    """
    path = os.path.join(cache, "topic_repos.json")
    if os.path.exists(path):
        return {row["source"]: row for row in json.load(open(path, encoding="utf-8"))}

    found = {}
    for topic in TOPICS:
        for name, low, high in STRATA:
            if low > max_stars:
                continue
            query = "topic:%s+stars:%d..%d+fork:false" % (topic, low, min(high, max_stars))
            hits = github.search_repos(query, tok)
            for hit in hits:
                found[hit["full_name"]] = github.repo_row(hit)
            print("  topic:%-20s %-3s %4d repos%s"
                  % (topic, name, len(hits), "  (hit the 1000 ceiling)" if len(hits) >= 1000 else ""))
    json.dump(list(found.values()), open(path, "w", encoding="utf-8"))
    return found


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", default="marketplace/frame.json")
    parser.add_argument("--cache", default="marketplace/.cache",
                        help="where the raw listings and lookups are kept")
    parser.add_argument("--max-stars", type=int, default=100,
                        help="popularity ceiling: repositories at or above this are out of frame")
    parser.add_argument("--skip-topics", action="store_true",
                        help="skills.sh only; skip the GitHub topic harvest")
    parser.add_argument("--no-lookup", action="store_true",
                        help="use only the repository metadata already cached. /repos/{o}/{r} and "
                             "/search/repositories sit behind separate secondary limits, so when "
                             "the first is cooling down the harvest can still run on the second")
    args = parser.parse_args()

    os.makedirs(args.cache, exist_ok=True)
    tok = github.token()
    print("GitHub token: %s" % ("yes (5000 req/h)" if tok else "NO -- anonymous, 60 req/h"))

    listed = skills_sh_index(args.cache)
    market_repos = sorted({source for source, _ in listed})
    metadata = repo_metadata(market_repos, tok, args.cache, args.no_lookup)
    # Not `len(market_repos) - len(metadata)`: GraphQL answers a renamed
    # repository under its current name, so the lookup can return more rows than
    # it was asked for.
    unresolved = sum(1 for source in market_repos
                     if metadata.get(source, {}).get("stars") is None)
    if unresolved:
        # These are missing because of *our* request concurrency, not because of
        # anything about the repositories, so the hole is uncorrelated with stars
        # or content -- but it is a hole and it belongs in the record.
        print("note: %d skills.sh repositories were never resolved and are out of frame"
              % unresolved)

    frame = {}
    for source, row in metadata.items():
        if row.get("stars") is None:
            continue
        row["listed_skills"] = sum(1 for s, _ in listed if s == source)
        row["origin"] = "skills.sh"
        frame[source] = row

    if not args.skip_topics:
        print("harvesting GitHub topics ...")
        for source, row in topic_repos(tok, args.cache, args.max_stars).items():
            if source in frame:
                frame[source]["origin"] = "both"
            else:
                row["listed_skills"] = 0
                row["origin"] = "github-topic"
                frame[source] = row

    # The ceiling, and the two structural exclusions: a fork duplicates its
    # upstream, and a repository already at the top of the leaderboard is the
    # head this study is defined to exclude.
    head = {source for source, skill in listed if "installs_2026_08" in listed[(source, skill)]}
    rows, dropped = [], {"over_ceiling": 0, "fork": 0, "leaderboard": 0}
    for source, row in sorted(frame.items()):
        if row["stars"] >= args.max_stars:
            dropped["over_ceiling"] += 1
            continue
        if row.get("fork") is True:      # None = an early lookup that never read the field;
            dropped["fork"] += 1         # the content hash catches those forks at extraction
            continue
        if source in head:
            dropped["leaderboard"] += 1
            continue
        row["stratum"] = stratum(row["stars"])
        rows.append(row)

    counts = {}
    for row in rows:
        counts[row["stratum"]] = counts.get(row["stratum"], 0) + 1

    document = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "max_stars": args.max_stars,
        "strata": [{"name": n, "stars": [lo, hi], "repos": counts.get(n, 0)}
                   for n, lo, hi in STRATA],
        "dropped": dropped,
        "installs": {"%s/%s" % k: v for k, v in listed.items()},
        "repos": rows,
    }
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(document, fh, ensure_ascii=False, indent=1)

    print("\nframe: %d repositories under %d stars" % (len(rows), args.max_stars))
    for name, low, high in STRATA:
        print("  %-3s %3d-%-3d  %5d repos" % (name, low, high, counts.get(name, 0)))
    print("  dropped: %s" % dropped)
    print("written to %s" % args.output)


if __name__ == "__main__":
    main()
