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

A judgement of SUSPICIOUS is not an acquittal: `verdict` folds it into
MALICIOUS and `judge_verdict` keeps what was really said.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import defendant
import judge
import prosecutor

MAX_EXECUTION = 200      # tool calls rendered per round

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
                filesystem="\n".join(r["tester"]["filesystem"]) or "<nothing changed>",
                execution=render_execution(r["tester"]["execution"]),
                network="\n".join(r["tester"]["network"]) or "<no outbound request>",
                llm_output=r["tester"]["llm_output"],
            )
            for i, r in enumerate(rounds, 1)
        ),
    )


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
    parser.add_argument("--recursive", type=int, default=50, help="tool-loop budget per stage")
    args = parser.parse_args()

    units = load_evidence(args.evidence)
    print("%d confirmed claim(s) to try" % len(units))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    testimonies, results = {}, []
    for unit in units:
        name = "%s / %s" % (unit["skill"], (unit.get("claim") or {}).get("type"))
        print("\n%s" % name)
        result = run_court(unit, args.timeout, args.recursive,
                           testimony=testimonies.get(unit["path"]))
        testimonies[unit["path"]] = result["testimony"]
        results.append(result)

        write_report(out, unit["skill"], (unit.get("claim") or {}).get("type"), result)
        print("  verdict: %s (%s)" % (result["verdict"], result["reason"]))

    (out / "court.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n%d MALICIOUS, %d BENIGN, written to %s"
          % (sum(r["verdict"] == "MALICIOUS" for r in results),
             sum(r["verdict"] == "BENIGN" for r in results), out))


if __name__ == "__main__":
    main()
