"""Draw the stratified sample and put it on disk, one directory per skill.

    uv run python marketplace/download_sample.py --frame marketplace/frame.json \
        --out marketplace/real_dataset_8k --target 8000 --workers 16

Repositories are what can be downloaded; skills are what is being sampled.  So
the draw is two-stage: shuffle the repositories of a stratum with a recorded
seed, fetch them in parallel, and take skills out of each until the stratum's
quota is full.  Fetching is one request per repository -- the codeload tarball,
which is a different host from the API and tolerates real concurrency -- and
never a clone, because a clone pays for history nobody is going to read.

The allocation is deliberately not proportional and deliberately not equal:

    S0  0 stars   2400    S3  20-49    1000
    S1  1-4       2400    S4  50-99      600
    S2  5-19      1600

Proportional allocation would put ~80% of the sample in S0-S1, which is where
the phenomenon lives but leaves the upper bands too thin to show that a trend is
a trend.  Equal allocation would spend a fifth of the budget on S4, which is ~4%
of the frame.  This sits between them, with a floor of 600 per stratum so every
band supports a proportion with a +-4% interval.  No market-wide rate is
estimable from it and none is claimed; Baltes & Ralph (EMSE 2022) is the licence
for that, on the condition the frame, the strata and the seed are all written
down -- which is what `manifest.json` is for.

Three filters run at extraction, and each one is a correction for a way this
ecosystem inflates:

* **content dedup.**  The one prior measurement that reports it found 27%
  duplicates (42447 listed -> 31132 unique).  Forks, vendored copies and
  awesome-list mirrors all republish the same SKILL.md.  Identical normalised
  bytes count once.
* **per-repository cap** (25).  The frame contains a repository with 1211
  skills; uncapped, five monorepos would supply a third of the sample.
* **per-owner cap** (40).  Same failure one level up, where one author spreads a
  template across thirty repositories.
"""

import argparse
import hashlib
import io
import json
import os
import random
import shutil
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import github

CODELOAD = "https://codeload.github.com/%s/tar.gz/refs/heads/%s"
QUOTA = {"S0": 2400, "S1": 2400, "S2": 1600, "S3": 1000, "S4": 600}
SKILL_NAMES = ("SKILL.md", "skill.md")

# A skill is a directory holding SKILL.md, and everything under it -- but a
# repository is not, so these never travel even when they sit inside one.
SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist",
        "build", ".pytest_cache", ".mypy_cache", "target", "vendor"}
MAX_FILE = 2 * 1024 * 1024        # a 2 MB file in a skill is data, not instructions
MAX_SKILL_FILES = 400
# Sixteen tarballs are in memory at once, so one repository that ships a model
# checkpoint would take the run down with it.  A skill repository past this size
# is not carrying skills.
MAX_TARBALL = 150 * 1024 * 1024


def tarball(source, branch, tok):
    """The repository as bytes.  Tries the recorded branch, then the other one."""
    headers = {"User-Agent": "malskilldet-frame"}
    if tok:
        headers["Authorization"] = "Bearer " + tok
    branches = [branch] + [b for b in ("main", "master") if b != branch]
    for candidate in branches:
        for attempt in range(4):
            try:
                request = urllib.request.Request(CODELOAD % (source, candidate), headers=headers)
                with urllib.request.urlopen(request, timeout=180) as response:
                    chunks, total = [], 0
                    while True:
                        chunk = response.read(1 << 20)
                        if not chunk:
                            return b"".join(chunks)
                        total += len(chunk)
                        if total > MAX_TARBALL:
                            return None          # abandoned, not retried
                        chunks.append(chunk)
            except urllib.error.HTTPError as error:
                if error.code in (404, 451, 410):
                    break                       # wrong branch, or the repo is gone
                if error.code in (403, 429):
                    time.sleep(min(60, 2 ** attempt * 5))
                    continue
                break
            except Exception:
                time.sleep(2 ** attempt)
    return None


def skills_in(blob):
    """Every skill inside one tarball: {relative dir: {path: bytes}}.

    The walk mirrors `static/pipeline.py`: a directory holding SKILL.md is a
    skill and the walk does not descend past it, so a bundled sub-skill belongs
    to its parent and is not counted twice.
    """
    try:
        archive = tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz")
    except Exception:
        return {}

    members = {}
    for member in archive.getmembers():
        if not member.isfile():
            continue
        parts = member.name.split("/")[1:]       # drop the "repo-sha" wrapper
        if not parts or any(p in SKIP or p.startswith(".git") for p in parts[:-1]):
            continue
        members["/".join(parts)] = member

    roots = sorted({os.path.dirname(path) for path in members
                    if os.path.basename(path) in SKILL_NAMES},
                   key=lambda p: p.count("/"))
    kept = []
    for root in roots:                            # shallowest wins; no nesting
        if not any(root == outer or root.startswith(outer + "/") for outer in kept):
            kept.append(root)

    skills = {}
    for root in kept:
        prefix = root + "/" if root else ""
        files = {}
        for path, member in members.items():
            if not path.startswith(prefix):
                continue
            if any(path.startswith(prefix + inner + "/") for inner in kept if inner != root):
                continue
            if member.size > MAX_FILE or len(files) >= MAX_SKILL_FILES:
                continue
            try:
                files[path[len(prefix):]] = archive.extractfile(member).read()
            except Exception:
                continue
        if any(name in files for name in SKILL_NAMES):
            skills[root or "."] = files
    archive.close()
    return skills


def fingerprint(files):
    """What makes two skills the same skill: the instructions plus the code.

    Normalised for line endings and trailing whitespace, because a mirror that
    ran the file through a different editor is still a mirror.
    """
    digest = hashlib.sha256()
    for name in sorted(files):
        body = files[name].replace(b"\r\n", b"\n").strip()
        digest.update(name.encode("utf-8", "replace") + b"\0" + hashlib.sha256(body).digest())
    return digest.hexdigest()


def safe_name(source, root, taken):
    """A flat, unique directory name that still says where the skill came from."""
    owner, repo = source.split("/", 1)
    leaf = os.path.basename(root) if root != "." else repo
    stem = "__".join(part.replace("/", "-").replace("..", "-")[:40]
                     for part in (owner, repo, leaf))
    stem = "".join(c if c.isalnum() or c in "-_." else "-" for c in stem).strip("-.")
    name, n = stem, 2
    while name in taken:
        name, n = "%s-%d" % (stem, n), n + 1
    taken.add(name)
    return name


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frame", default="marketplace/frame.json")
    parser.add_argument("--out", default="marketplace/real_dataset_8k")
    parser.add_argument("--target", type=int, default=8000)
    parser.add_argument("--workers", type=int, default=16,
                        help="parallel tarball downloads (codeload, not the API)")
    parser.add_argument("--seed", type=int, default=20260813)
    parser.add_argument("--per-repo", type=int, default=25)
    parser.add_argument("--per-owner", type=int, default=40)
    args = parser.parse_args()

    frame = json.load(open(args.frame, encoding="utf-8"))
    tok = github.token()
    out = args.out
    os.makedirs(out, exist_ok=True)

    scale = args.target / float(sum(QUOTA.values()))
    quota = {name: int(round(value * scale)) for name, value in QUOTA.items()}
    print("target %d  ->  %s" % (args.target, quota))

    by_stratum = {}
    for row in frame["repos"]:
        by_stratum.setdefault(row["stratum"], []).append(row)
    for name in by_stratum:
        random.Random(args.seed + hash(name) % 1000).shuffle(by_stratum[name])

    installs = frame.get("installs", {})
    state = {"seen": set(), "per_owner": {}, "names": set(), "kept": 0}
    manifest, failures = [], []
    lock = threading.Lock()

    for name, _low, _high in [("S0", 0, 0), ("S1", 1, 4), ("S2", 5, 19),
                              ("S3", 20, 49), ("S4", 50, 99)]:
        want = quota.get(name, 0)
        repos = by_stratum.get(name, [])
        got = [0]
        print("\n=== %s: %d repositories available, want %d skills" % (name, len(repos), want))

        def one(row):
            """Download and unpack one repository; returns nothing, writes under lock."""
            if got[0] >= want:
                return
            blob = tarball(row["source"], row.get("default_branch") or "main", tok)
            if blob is None:
                with lock:
                    failures.append({"source": row["source"], "why": "download"})
                return
            try:
                found = skills_in(blob)
            except Exception as error:
                with lock:
                    failures.append({"source": row["source"], "why": str(error)[:80]})
                return

            owner = row["source"].split("/")[0]
            with lock:
                if got[0] >= want:
                    return
                room = min(args.per_repo,
                           args.per_owner - state["per_owner"].get(owner, 0),
                           want - got[0])
                for root in sorted(found):
                    if room <= 0:
                        break
                    files = found[root]
                    mark = fingerprint(files)
                    if mark in state["seen"]:
                        continue
                    state["seen"].add(mark)
                    directory = safe_name(row["source"], root, state["names"])
                    target = os.path.join(out, directory)
                    for relative, body in files.items():
                        destination = os.path.join(target, relative)
                        if not os.path.abspath(destination).startswith(os.path.abspath(target)):
                            continue                     # a path escaping its own skill
                        os.makedirs(os.path.dirname(destination), exist_ok=True)
                        with open(destination, "wb") as fh:
                            fh.write(body)
                    key = "%s/%s" % (row["source"], os.path.basename(root))
                    manifest.append({
                        "dir": directory, "source": row["source"], "path_in_repo": root,
                        "stratum": name, "stars": row["stars"],
                        "installs": installs.get(key), "sha256": mark,
                        "files": len(files), "origin": row.get("origin"),
                        "pushed_at": row.get("pushed_at"),
                    })
                    room -= 1
                    got[0] += 1
                    state["per_owner"][owner] = state["per_owner"].get(owner, 0) + 1
                    state["kept"] += 1
                if got[0] and got[0] % 200 < 25:
                    print("  %s %d/%d skills (%d kept overall)"
                          % (name, got[0], want, len(manifest)), flush=True)

        with ThreadPoolExecutor(args.workers) as pool:
            list(pool.map(one, repos))
        print("  %s done: %d/%d" % (name, got[0], want))

    document = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "frame": os.path.basename(args.frame), "frame_built_at": frame.get("built_at"),
        "seed": args.seed, "target": args.target, "quota": quota,
        "caps": {"per_repo": args.per_repo, "per_owner": args.per_owner},
        "kept": len(manifest),
        "by_stratum": {n: sum(1 for m in manifest if m["stratum"] == n) for n in QUOTA},
        "repos": len({m["source"] for m in manifest}),
        "owners": len({m["source"].split("/")[0] for m in manifest}),
        "failed_repos": len(failures),
        "skills": manifest,
        "failures": failures[:500],
    }
    with open(os.path.join(os.path.dirname(out) or ".", "manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump(document, fh, ensure_ascii=False, indent=1)

    print("\n%d skills in %s, from %d repositories / %d owners, %d repos failed"
          % (len(manifest), out, document["repos"], document["owners"], len(failures)))
    print("by stratum: %s" % document["by_stratum"])


if __name__ == "__main__":
    main()
