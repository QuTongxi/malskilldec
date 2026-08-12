#!/usr/bin/env python3
"""The court.  Turns one skill's confirmed evidence into a verdict.

    uv run python final_v2/court.py --evidence path/to/evidence [--out court_v2/]

Three LLM stages, in order.  Forensics reads the machine records and the skill
and writes down the facts; the prosecutor answers the four questions and files
at most two charges against those facts; the judge -- who sees only the
indictment -- checks completeness, preconditions and precedents, and sentences.

    run_court(units) -> {"verdict": "MALICIOUS" | "BENIGN", ...}

`units` is every confirmed claim of one skill.  The unit of judgement is a
skill, not a claim: one chain routinely spans several claims, and trying them
one at a time both repeats the work and shows each pass a third of the story.

Each unit is one entry of the `claims` list in a `dynamic/pipeline.py` result
file, so `--evidence` takes those files (or the directory holding them) and
keeps only the claims a reviewer actually confirmed.
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import forensics
import judge
import prosecutor

# Forensics is the stage that removes the noise, so it is the one stage that
# should see the raw material at close to full length.  The first version's caps
# were tuned for a prosecutor that had to judge while reading; these are tuned
# so that nothing decisive is cut before anyone has looked at it.
MAX_EXECUTION = 80       # tool calls rendered per round (observed max: 29)
MAX_FILESYSTEM = 60      # path changes (median 4, p90 96)
MAX_NETWORK = 40         # destinations (median 6, p90 17)
MAX_OUTPUT = 1500        # characters of the agent's own account
MAX_ANCHORS = 8          # static findings kept per claim


def render_list(entries, limit):
    if not entries:
        return None
    text = "\n".join(entries[:limit])
    if len(entries) > limit:
        text += "\n<... %d more>" % (len(entries) - limit)
    return text


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


def render_anchors(claim):
    """The static matches behind one claim: rule, file, line, matched text.

    Runs made before the anchors were carried downstream simply have none; the
    forensics stage is told to fall back on the identifiers it lifts out of the
    trace, which is what it does for a mismatched anchor anyway.
    """
    findings = claim.get("findings") or claim.get("anchors") or []
    lines = []
    for finding in findings[:MAX_ANCHORS]:
        metadata = finding.get("metadata") or finding
        location = finding.get("location") or finding
        rule = metadata.get("rule_id") or metadata.get("rule") or "?"
        file = location.get("file") or "?"
        line = location.get("line") or "?"
        matched = (finding.get("matched_text") or finding.get("text") or "").strip()
        lines.append("- `%s`  %s:%s  %s" % (rule, file, line, matched))
    if not lines:
        return "<静态锚点未记录：本次动态输出早于该字段，请用落点动作里的标识符回目录定位>"
    if len(findings) > MAX_ANCHORS:
        lines.append("<... 另有 %d 条同类锚点>" % (len(findings) - MAX_ANCHORS))
    return "\n".join(lines)


EVIDENCE = """\
被审计的 Skill：`{skill}`

静态层对它提出了 {count} 条指控，下面是每一条在动态验证阶段被确认时留下的记录。
`文件系统变更`、`执行轨迹`、`网络活动` 由容器本身记录，是不可伪造的事实；只有 `Agent 自述`
出自被审对象参与的那次对话，不能单独用来证明命令、文件或网络行为。
{claims}"""

CLAIM_BLOCK = """\

===============================================================================

# 指控 {index}/{count}：**{claim_type}**（级别 {level}，得分 {score}）

涉及的行为组：{groups}

## 静态锚点

{anchors}
{rounds}"""

ROUND = """\

---

## 第 {round} 轮验证

### 送给 Agent 的用户请求

{prompt}

### 判定条件 oracle

{oracle}

### 复核结论（verdict: confirmed，这是解释，不是记录）

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


def confirmed_rounds(unit):
    """The rounds a reviewer confirmed; everything else is not evidence."""
    return [r for r in unit.get("rounds", [])
            if r.get("reviewer", {}).get("verdict") == "confirmed"]


def render_evidence(units):
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
            anchors=render_anchors(claim),
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
    return EVIDENCE.format(
        skill=units[0].get("skill", "<unnamed>"), count=len(units),
        claims="".join(blocks))


def run_court(units, timeout=300, recursive=50):
    """Try one skill on all of its confirmed claims and return the verdict."""
    units = [u for u in units if confirmed_rounds(u)]
    if not units:
        return None

    head = units[0]
    types = sorted({(u.get("claim") or {}).get("type") for u in units})
    result = {"skill": head.get("skill"), "path": head.get("path"),
              "claim": "+".join(t for t in types if t),
              "verdict": "BENIGN", "judge_verdict": None, "reason": "",
              "forensics": None, "indictment": None, "judgement": None}

    result["forensics"] = forensics.investigate(
        head.get("skill") or Path(head["path"]).name,
        render_evidence(units), head["path"], timeout, recursive)

    result["indictment"] = prosecutor.accuse(result["forensics"], timeout, recursive)
    if result["indictment"]["verdict"] == "BENIGN":
        result["reason"] = "the prosecutor brought no charge"
        return result

    result["judgement"] = judge.adjudicate(result["indictment"]["report"], timeout, recursive)
    result["judge_verdict"] = result["judgement"]["verdict"]
    result["verdict"] = result["judge_verdict"]
    result["reason"] = "the judge returned %s" % result["judge_verdict"]
    return result


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

REPORT = """\
# {skill}

- verdict: **{verdict}**
- claims: {claim}
- judge: {judge_verdict}
- reason: {reason}

---

# 一、取证报告

{forensics}

---

# 二、指控书（检察官，{indictment_verdict}）

{indictment}

---

# 三、判决书（法官，{judge_verdict}）

{judgement}
"""


def write_report(directory, result):
    """Write the three reports of one skill as one Markdown file; return its path."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("%s.md" % result["skill"]).replace("/", "-")
    path.write_text(REPORT.format(
        skill=result["skill"], claim=result["claim"] or "<none>",
        verdict=result["verdict"],
        judge_verdict=result["judge_verdict"] or "<not reached>",
        reason=result["reason"],
        forensics=result.get("forensics") or "<not produced>",
        indictment_verdict=(result["indictment"] or {}).get("verdict", "<not reached>"),
        indictment=(result["indictment"] or {}).get("report", "<not reached>"),
        judgement=(result["judgement"] or {}).get("report", "<not reached>"),
    ), encoding="utf-8")
    return path


def load_evidence(path):
    """Read `--evidence` into per-skill groups of confirmed claim units.

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
                        "claim": {k: claim.get(k) for k in
                                  ("type", "level", "score", "groups", "findings", "anchors")},
                        "rounds": claim.get("rounds", []),
                    })
            elif "rounds" in document:
                units.append(document)
            elif document.get("verdict") == "error":
                # A skill whose dynamic run died carries no evidence to retry.
                print("skipping %s: the dynamic stage errored (%s)"
                      % (document.get("skill", file.name),
                         (document.get("error") or "").strip().splitlines()[-1][:120]))
            else:
                raise SystemExit("%s is neither a skill result nor a claim unit" % file)

    grouped = {}
    for unit in units:
        if confirmed_rounds(unit):
            grouped.setdefault(unit["path"], []).append(unit)
    return list(grouped.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--evidence", required=True,
                        help="a dynamic result file, a directory of them, or one claim unit")
    parser.add_argument("--out", default="court_v2", help="directory for the reports")
    parser.add_argument("--timeout", type=int, default=300, help="seconds per LLM request")
    parser.add_argument("--recursive", type=int, default=50,
                        help="tool-loop budget per stage")
    parser.add_argument("--max-parallel", type=int, default=10,
                        help="skills tried at once (default 10)")
    args = parser.parse_args()

    groups = load_evidence(args.evidence)
    print("%d skill(s) to try, %d confirmed claim(s) between them"
          % (len(groups), sum(len(g) for g in groups)))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    def try_one(units):
        head = units[0]
        try:
            result = run_court(units, args.timeout, args.recursive)
        except Exception as error:                       # one skill, not the run
            result = {"skill": head.get("skill"), "path": head.get("path"),
                      "claim": None, "verdict": "error", "judge_verdict": None,
                      "reason": "%s: %s" % (type(error).__name__, error),
                      "forensics": None, "indictment": None, "judgement": None}
        write_report(out, result)
        print("%-55s %-10s %s" % (result["skill"], result["verdict"],
                                  result["reason"][:60]), flush=True)
        return result

    with ThreadPoolExecutor(max_workers=args.max_parallel) as pool:
        results = list(pool.map(try_one, groups))

    (out / "court.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n%d MALICIOUS, %d BENIGN, %d error, written to %s"
          % (sum(r["verdict"] == "MALICIOUS" for r in results),
             sum(r["verdict"] == "BENIGN" for r in results),
             sum(r["verdict"] == "error" for r in results), out))


if __name__ == "__main__":
    main()
