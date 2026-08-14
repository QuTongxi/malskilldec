"""A GitHub client that survives 8000 requests.

The interesting part is not the requests, it is the two limits GitHub enforces
and only one of which it documents in a header:

* the **primary** limit, 5000 requests an hour, reported in `x-ratelimit-*` and
  handled by sleeping until `x-ratelimit-reset`;
* the **secondary** limit, an undocumented concurrency/burst rule that answers
  403 with no counter moved -- `used: 0` on `/rate_limit` while a third of the
  fleet is failing.  Ten threads trips it within a minute.  There is no header
  to read: the only fix is fewer threads and a longer wait, so 403 without a
  spent budget backs off geometrically and the pool stays small.

`get` returns `None` for the codes that mean *this repository is not coming
back* (404 deleted, 451 DMCA, 410 gone), because a frame builder wants to record
those as holes rather than retry them.
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
DEAD = (404, 410, 451)

# One lock for the whole process: when the primary budget runs out every thread
# has to wait, and they may as well wait on the same clock.
_sleep_lock = threading.Lock()


def token():
    """The PAT from the project's .env, or None for anonymous (60 req/h)."""
    if os.environ.get("gh_token"):
        return os.environ["gh_token"]
    env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env):
        with open(env, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("gh_token="):
                    return line.split("=", 1)[1].strip()
    return None


def get(path, tok, tries=8):
    """One GET against the REST API. Returns parsed JSON, or None if dead."""
    url = path if path.startswith("http") else API + path
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "malskilldet-frame"}
    if tok:
        headers["Authorization"] = "Bearer " + tok

    for attempt in range(tries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=headers), timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in DEAD:
                return None
            if error.code in (403, 429):
                # Primary limit: the reset time is authoritative, so wait it out.
                # Secondary limit: nothing to read, so back off and hope.
                remaining = error.headers.get("x-ratelimit-remaining")
                retry_after = error.headers.get("retry-after")
                if remaining == "0":
                    reset = int(error.headers.get("x-ratelimit-reset", time.time() + 60))
                    with _sleep_lock:
                        time.sleep(max(1, reset - time.time()) + 2)
                elif retry_after:
                    time.sleep(int(retry_after) + 1)
                else:
                    time.sleep(min(60, 2 ** attempt))
                continue
            if 500 <= error.code < 600:
                time.sleep(min(30, 2 ** attempt))
                continue
            raise
        except Exception:
            time.sleep(min(30, 2 ** attempt))
    return None


def search_repos(query, tok, cap=1000):
    """Repository search, paged out to GitHub's hard 1000-result ceiling.

    Search returns whole repository objects, so this is also the cheapest way to
    learn a repository's star count: 100 repositories per request instead of one.
    Queries expected to exceed `cap` must be sliced by the caller (by stars, by
    creation date) -- results past 1000 are simply not served.
    """
    found, page = [], 1
    while len(found) < cap:
        result = get("/search/repositories?q=%s&per_page=100&page=%d&sort=updated"
                     % (query, page), tok)
        if not result or not result.get("items"):
            break
        found += result["items"]
        if len(result["items"]) < 100:
            break
        page += 1
        # Search allows 30 requests a minute and answers the 31st with a 403
        # whose reset is up to a minute away -- so pacing at 20/min is not
        # politeness, it is three times faster than pacing at 28/min.
        time.sleep(3.0)
    return found[:cap]


# Scalars only.  Adding `repositoryTopics(first: 20)` to a batch of this size
# times the query out at GitHub's gateway -- topics are not worth a 504.
GRAPHQL_FIELDS = """{
      nameWithOwner stargazerCount forkCount diskUsage isFork isArchived
      pushedAt createdAt defaultBranchRef { name }
    }"""


def repos_batch(sources, tok, size=30):
    """Star counts for many repositories at once, over GraphQL.

    REST has no batch form -- 3630 repositories is 3630 requests, which is what
    tripped the secondary limit in the first place.  GraphQL takes a hundred
    aliased `repository` nodes in one POST, and it is a different endpoint with
    a different limiter, so it keeps working while `/repos/{owner}/{repo}` is
    still cooling down.  Deleted repositories come back as a null alias
    alongside an `errors` array; the row is simply absent from the result.
    """
    rows = {}
    for start in range(0, len(sources), size):
        chunk = sources[start:start + size]
        parts = []
        for index, full in enumerate(chunk):
            owner, _, name = full.partition("/")
            parts.append("a%d: repository(owner: %s, name: %s) %s"
                         % (index, json.dumps(owner), json.dumps(name), GRAPHQL_FIELDS))
        body = json.dumps({"query": "{\n%s\n}" % "\n".join(parts)}).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "malskilldet-frame"}
        if tok:
            headers["Authorization"] = "Bearer " + tok

        for attempt in range(6):
            try:
                request = urllib.request.Request(API + "/graphql", data=body,
                                                 headers=headers, method="POST")
                with urllib.request.urlopen(request, timeout=90) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as error:
                if error.code in (403, 429) or 500 <= error.code < 600:
                    time.sleep(min(60, 2 ** attempt * 3))
                    continue
                raise
            except Exception:
                time.sleep(min(30, 2 ** attempt))
        else:
            continue

        for node in (payload.get("data") or {}).values():
            if not node:
                continue
            rows[node["nameWithOwner"]] = {
                "source": node["nameWithOwner"],
                "stars": node.get("stargazerCount", 0),
                "forks": node.get("forkCount", 0),
                "size_kb": node.get("diskUsage") or 0,
                "fork": bool(node.get("isFork")),
                "archived": bool(node.get("isArchived")),
                "pushed_at": node.get("pushedAt"),
                "created_at": node.get("createdAt"),
                "default_branch": (node.get("defaultBranchRef") or {}).get("name") or "main",
                "topics": [t["topic"]["name"]
                           for t in (node.get("repositoryTopics") or {}).get("nodes", [])],
            }
        time.sleep(1)
    return rows


def repo_row(document):
    """The fields the frame keeps, from either a search hit or a repo lookup."""
    return {
        "source": document["full_name"],
        "stars": document.get("stargazers_count", 0),
        "forks": document.get("forks_count", 0),
        "size_kb": document.get("size", 0),
        "fork": bool(document.get("fork")),
        "archived": bool(document.get("archived")),
        "pushed_at": document.get("pushed_at"),
        "created_at": document.get("created_at"),
        "default_branch": document.get("default_branch") or "main",
        "topics": document.get("topics") or [],
    }
