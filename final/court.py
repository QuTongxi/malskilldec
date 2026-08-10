#!/usr/bin/env python3
"""The court.  Turns one confirmed accusation into a verdict.

    uv run python final/court.py --evidence path/to/evidence [--out court/]

Three LLM stages, in order: the defendant reads the skill and says what it is,
the prosecutor holds that account against the machine records and charges, the
judge -- who never sees the skill -- drops whatever common knowledge explains.

    run_court(evidence) -> {"verdict": "MALICIOUS" | "BENIGN", ...}

The input unit is one dynamically confirmed claim:

    {"skill": name, "path": skill directory,
     "claim": {"type", "level", "score", "groups"},
     "rounds": [{"round", "generator": {"prompt", "oracle"},
                 "tester": {"filesystem", "execution", "network", "llm_output"},
                 "reviewer": {"verdict", "summary"}}]}

which is exactly one entry of the `claims` list in a `dynamic/pipeline.py`
result file, so `--evidence` takes those files (or the directory holding them)
and keeps only the claims a reviewer actually confirmed.

The judge returns MALICIOUS or BENIGN and nothing in between: it is the only
stage that decides, so a middle grade here would only be folded into one of the
two anyway, and folding is what turned every doubt into a conviction.
"""

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import defendant
import judge
import prosecutor

# What the prosecutor needs is the shape of the run, not every line of it.  The
# tail of a long filesystem or network list is almost always the same host or
# the same cache directory repeated, and `llm_output` is the one channel the
# skill could have written, so it is quoted only far enough to show its tone.
MAX_EXECUTION = 60       # tool calls rendered per round (observed max: 29)
MAX_FILESYSTEM = 40      # path changes (median 4, p90 96)
MAX_NETWORK = 25         # destinations (median 6, p90 17)
MAX_OUTPUT = 800         # characters of the agent's own account (median 1432)


def render_list(entries, limit):
    if not entries:
        return None
    text = "\n".join(entries[:limit])
    if len(entries) > limit:
        text += "\n<... %d more>" % (len(entries) - limit)
    return text

EVIDENCE = """\
被审计的 Skill：`{skill}`

静态层提出的指控类型：**{claim_type}**（级别 {level}，得分 {score}）
涉及的行为组：{groups}

下面是动态验证阶段确认（confirmed）这条指控时留下的记录。`文件系统变更`、`执行轨迹`、
`网络活动` 由容器本身记录，是不可伪造的事实；只有 `Agent 自述` 出自被审对象参与的那次
对话，不能单独用来证明命令、文件或网络行为。
{rounds}"""

ROUND = """\

---

## 第 {round} 轮验证

### 送给 Agent 的用户请求

{prompt}

### 判定条件 oracle

{oracle}

### 复核结论（verdict: confirmed）

{summary}

### 文件系统变更

```
{filesystem}
```

### 执行轨迹

```
{execution}
```

### 网络活动

```
{network}
```

### Agent 自述（不可信）

{llm_output}"""


def confirmed_rounds(evidence):
    """The rounds a reviewer confirmed; everything else is not evidence."""
    return [r for r in evidence.get("rounds", [])
            if r.get("reviewer", {}).get("verdict") == "confirmed"]


def render_execution(execution):
    if not execution:
        return "<the agent called no tools>"
    entries = execution[:MAX_EXECUTION]
    text = "\n".join(
        "%d. %s%s %s\n   -> %s" % (i, entry["tool"], "" if entry["ok"] else " [failed]",
                                   entry["args"], entry["output"])
        for i, entry in enumerate(entries, 1)
    )
    if len(execution) > len(entries):
        text += "\n<... %d more tool calls>" % (len(execution) - len(entries))
    return text


def render_evidence(evidence, rounds):
    claim = evidence.get("claim") or {}
    groups = claim.get("groups") or {}
    return EVIDENCE.format(
        skill=evidence.get("skill", "<unnamed>"),
        claim_type=claim.get("type", "<unknown>"),
        level=claim.get("level", "?"),
        score=claim.get("score", "?"),
        groups=", ".join("%s (%s)" % (g, lv) for g, lv in sorted(groups.items())) or "<未记录>",
        rounds="".join(
            ROUND.format(
                round=r.get("round", i),
                prompt=r["generator"]["prompt"],
                oracle=r["generator"]["oracle"],
                summary=r["reviewer"]["summary"],
                filesystem=render_list(r["tester"]["filesystem"], MAX_FILESYSTEM)
                           or "<nothing changed>",
                execution=render_execution(r["tester"]["execution"]),
                network=render_list(r["tester"]["network"], MAX_NETWORK)
                        or "<no outbound request>",
                llm_output=r["tester"]["llm_output"][:MAX_OUTPUT],
            )
            for i, r in enumerate(rounds, 1)
        ),
    )


SKILL_EVIDENCE = """\
被审计的 Skill：`{skill}`

静态层对它提出了 {count} 条指控，下面是每一条在动态验证阶段被确认时留下的记录。
`文件系统变更`、`执行轨迹`、`网络活动` 由容器本身记录，是不可伪造的事实；只有 `Agent 自述`
出自被审对象参与的那次对话，不能单独用来证明命令、文件或网络行为。
{claims}"""

CLAIM_BLOCK = """\

===============================================================================

# 指控 {index}/{count}：**{claim_type}**（级别 {level}，得分 {score}）

涉及的行为组：{groups}
{rounds}"""


def render_skill_evidence(units):
    """Every confirmed claim of one skill, as a single body of evidence."""
    blocks = []
    for i, unit in enumerate(units, 1):
        claim = unit.get("claim") or {}
        groups = claim.get("groups") or {}
        blocks.append(CLAIM_BLOCK.format(
            index=i, count=len(units),
            claim_type=claim.get("type", "<unknown>"),
            level=claim.get("level", "?"), score=claim.get("score", "?"),
            groups=", ".join("%s (%s)" % (g, lv) for g, lv in sorted(groups.items()))
                   or "<未记录>",
            rounds="".join(
                ROUND.format(
                    round=r.get("round", j),
                    prompt=r["generator"]["prompt"],
                    oracle=r["generator"]["oracle"],
                    summary=r["reviewer"]["summary"],
                    filesystem=render_list(r["tester"]["filesystem"], MAX_FILESYSTEM)
                               or "<nothing changed>",
                    execution=render_execution(r["tester"]["execution"]),
                    network=render_list(r["tester"]["network"], MAX_NETWORK)
                            or "<no outbound request>",
                    llm_output=r["tester"]["llm_output"][:MAX_OUTPUT],
                )
                for j, r in enumerate(confirmed_rounds(unit), 1)
            ),
        ))
    return SKILL_EVIDENCE.format(
        skill=units[0].get("skill", "<unnamed>"), count=len(units),
        claims="".join(blocks))


def run_court_skill(units, timeout=300, recursive=50, testimony=None):
    """Try one skill on all of its confirmed claims at once.

    The per-claim `run_court` stays as it is -- the dynamic pipeline calls it
    that way.  This is the other entry point: the prosecutor sees everything the
    skill did in one pass, so a charge may rest on evidence from several claims,
    and the skill gets one verdict instead of one per claim.
    """
    units = [u for u in units if confirmed_rounds(u)]
    if not units:
        return None

    types = sorted({(u.get("claim") or {}).get("type") for u in units})
    result = {"skill": units[0].get("skill"), "path": units[0].get("path"),
              "claim": "+".join(t for t in types if t),
              "verdict": "BENIGN", "judge_verdict": None, "reason": "",
              "testimony": testimony, "indictment": None, "judgement": None}

    if result["testimony"] is None:
        result["testimony"] = defendant.testify(
            units[0]["path"], units[0].get("skill") or Path(units[0]["path"]).name,
            timeout, recursive)

    result["indictment"] = prosecutor.accuse(
        result["testimony"], render_skill_evidence(units), units[0]["path"],
        timeout, recursive)

    if result["indictment"]["verdict"] == "BENIGN":
        result["reason"] = "the prosecutor brought no charge"
        return result

    result["judgement"] = judge.adjudicate(result["indictment"]["report"], timeout, recursive)
    result["judge_verdict"] = result["judgement"]["verdict"]
    result["verdict"] = "BENIGN" if result["judge_verdict"] == "BENIGN" else "MALICIOUS"
    result["reason"] = "the judge returned %s" % result["judge_verdict"]
    return result


def run_court(evidence, timeout=300, recursive=50, testimony=None):
    """Try one confirmed claim and return the verdict.

    `testimony` lets a caller reuse the defendant's report across the claims of
    one skill: it only ever depends on the skill directory.
    """
    result = {"skill": evidence.get("skill"), "path": evidence.get("path"),
              "claim": (evidence.get("claim") or {}).get("type"),
              "verdict": "BENIGN", "judge_verdict": None, "reason": "",
              "testimony": testimony, "indictment": None, "judgement": None}

    rounds = confirmed_rounds(evidence)
    if not rounds:
        result["reason"] = "no confirmed round: the dynamic stage never made the claim act"
        return result

    if result["testimony"] is None:
        result["testimony"] = defendant.testify(
            evidence["path"], evidence.get("skill") or Path(evidence["path"]).name,
            timeout, recursive)

    result["indictment"] = prosecutor.accuse(
        result["testimony"], render_evidence(evidence, rounds), evidence["path"],
        timeout, recursive)

    if result["indictment"]["verdict"] == "BENIGN":
        # Nothing was charged, so there is nothing for the judge to dismiss.
        result["reason"] = "the prosecutor brought no charge"
        return result

    result["judgement"] = judge.adjudicate(result["indictment"]["report"], timeout, recursive)
    result["judge_verdict"] = result["judgement"]["verdict"]
    result["verdict"] = "BENIGN" if result["judge_verdict"] == "BENIGN" else "MALICIOUS"
    result["reason"] = "the judge returned %s" % result["judge_verdict"]
    return result


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

REPORT = """\
# {skill} / {claim}

- verdict: **{verdict}**
- judge: {judge_verdict}
- reason: {reason}

---

# 一、证言（被告）

{testimony}

---

# 二、指控（检察官，{indictment_verdict}）

{indictment}

---

# 三、判决（法官，{judge_verdict}）

{judgement}
"""


def write_report(directory, skill, claim_type, result, testimony=None):
    """Write the three reports of one claim as one Markdown file; return its path.

    `testimony` is for callers that keep it outside the result, as the dynamic
    pipeline does: the claims of one skill share a single testimony.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("%s-%s.md" % (skill, claim_type)).replace("/", "-")
    path.write_text(REPORT.format(
        skill=skill, claim=claim_type,
        verdict=result["verdict"],
        judge_verdict=result["judge_verdict"] or "<not reached>",
        reason=result["reason"],
        testimony=testimony or result.get("testimony") or "<not produced>",
        indictment_verdict=(result["indictment"] or {}).get("verdict", "<not reached>"),
        indictment=(result["indictment"] or {}).get("report", "<not reached>"),
        judgement=(result["judgement"] or {}).get("report", "<not reached>"),
    ), encoding="utf-8")
    return path


def interleave(units):
    """Round-robin the claims by skill so parallel workers land on different ones.

    Evidence arrives grouped by skill, which puts the first ten workers on about
    four skills: the claims of one skill share a testimony, so nine of them sit
    on the same lock waiting for one defendant call.  Dealing them out one skill
    at a time gives ten workers ten skills.
    """
    groups = {}
    for unit in units:
        key = unit[0]["skill"] if isinstance(unit, list) else unit["skill"]
        groups.setdefault(key, []).append(unit)

    dealt = []
    while groups:
        for skill in list(groups):
            dealt.append(groups[skill].pop(0))
            if not groups[skill]:
                del groups[skill]
    return dealt


def load_evidence(path):
    """Read `--evidence` into single-claim units, confirmed ones only.

    Accepts a `dynamic/pipeline.py` result file, a directory of them, or a file
    already holding one claim unit (or a list of either).
    """
    path = Path(path)
    files = ([p for p in sorted(path.glob("*.json")) if p.name != "summary.json"]
             if path.is_dir() else [path])
    if not files:
        raise SystemExit("no evidence JSON under %s" % path)

    units = []
    for file in files:
        documents = json.loads(file.read_text(encoding="utf-8"))
        for document in documents if isinstance(documents, list) else [documents]:
            if "claims" in document:
                for claim in document["claims"]:
                    units.append({
                        "skill": document["skill"], "path": document["path"],
                        "claim": {k: claim.get(k) for k in ("type", "level", "score", "groups")},
                        "rounds": claim.get("rounds", []),
                    })
            elif "rounds" in document:
                units.append(document)
            elif document.get("verdict") == "error":
                # A skill whose dynamic run died carries no evidence to retry.
                # Refusing the whole directory over it would make the stored
                # evidence unreplayable, which is the point of keeping it.
                print("skipping %s: the dynamic stage errored (%s)"
                      % (document.get("skill", file.name),
                         (document.get("error") or "").strip().splitlines()[-1][:120]))
            else:
                raise SystemExit("%s is neither a skill result nor a claim unit" % file)

    return [u for u in units if confirmed_rounds(u)]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--evidence", required=True,
                        help="a dynamic result file, a directory of them, or one claim unit")
    parser.add_argument("--out", default="court", help="directory for the reports")
    # Each stage writes a whole report in one call, which the 20 seconds of the
    # generate/test/review loop cannot cover.
    parser.add_argument("--timeout", type=int, default=300, help="seconds per LLM request")
    parser.add_argument("--recursive", type=int, default=120,
                        help="tool-loop budget per stage")
    parser.add_argument("--max-parallel", type=int, default=10,
                        help="units tried at once (default 10)")
    parser.add_argument("--by-skill", action="store_true",
                        help="try each skill once on all of its confirmed claims, "
                             "instead of once per claim")
    args = parser.parse_args()

    units = load_evidence(args.evidence)
    if args.by_skill:
        grouped = {}
        for unit in units:
            grouped.setdefault(unit["path"], []).append(unit)
        units = list(grouped.values())
        print("%d skill(s) to try, %d confirmed claim(s) between them"
              % (len(units), sum(len(g) for g in units)))
    else:
        print("%d confirmed claim(s) to try" % len(units))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # The unit of work is one confirmed claim, so that is what runs in parallel.
    # Testimony is the exception: it depends only on the skill directory, so the
    # first claim of a skill produces it and the rest of that skill wait for it.
    testimonies, locks, guard = {}, {}, threading.Lock()

    def testify(path, skill):
        with guard:
            lock = locks.setdefault(path, threading.Lock())
        with lock:
            if path not in testimonies:
                testimonies[path] = defendant.testify(
                    path, skill or Path(path).name, args.timeout, args.recursive)
            return testimonies[path]

    def try_one(unit):
        head = unit[0] if args.by_skill else unit
        claim_type = ("skill" if args.by_skill
                      else (unit.get("claim") or {}).get("type"))
        try:
            testimony = testify(head["path"], head.get("skill"))
            result = (run_court_skill(unit, args.timeout, args.recursive, testimony)
                      if args.by_skill
                      else run_court(unit, args.timeout, args.recursive, testimony))
        except Exception as error:                       # one unit, not the run
            result = {"skill": head.get("skill"), "path": head.get("path"),
                      "claim": claim_type, "verdict": "error", "judge_verdict": None,
                      "reason": "%s: %s" % (type(error).__name__, error),
                      "testimony": None, "indictment": None, "judgement": None}
        else:
            write_report(out, head["skill"], claim_type, result)
        print("%-55s %-10s %s" % ("%s / %s" % (head["skill"], claim_type),
                                  result["verdict"], result["reason"][:60]), flush=True)
        return result

    with ThreadPoolExecutor(max_workers=args.max_parallel) as pool:
        results = list(pool.map(try_one, interleave(units)))

    (out / "court.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n%d MALICIOUS, %d BENIGN, %d error, written to %s"
          % (sum(r["verdict"] == "MALICIOUS" for r in results),
             sum(r["verdict"] == "BENIGN" for r in results),
             sum(r["verdict"] == "error" for r in results), out))


if __name__ == "__main__":
    main()
