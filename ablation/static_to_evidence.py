#!/usr/bin/env python3
"""Component contribution: turn a static report into evidence the court accepts.

    uv run python ablation/static_to_evidence.py --static-report static.json \
        --out pseudo_dynamic/
    uv run python final_v2/court.py --evidence pseudo_dynamic/ --out court_static_only/

The full pipeline is static -> dynamic -> court.  This drops the middle one to
measure what it contributes: every accused claim is written out in the shape
`dynamic/pipeline.py` would have produced, but with the machine records absent
and said to be absent.  The court then decides from the static anchors and
whatever it reads out of the skill directory itself, and the difference against a
full run is the dynamic stage's contribution.

`final_v2/` is not touched by any of this.  The court reads these files through
its ordinary `--evidence` path and cannot tell the difference at load time --
only at read time, which is the point.

Two things this deliberately does not do:

* It does not leave the three record sections empty.  `court.py` renders an
  empty filesystem list as `<nothing changed>`, an empty trace as `<the agent
  called no tools>` and an empty capture as `<no outbound request>` -- all three
  read as *the machine watched and saw nothing*, which is the opposite of *the
  machine never ran*, and would hand the court an acquittal it did not earn.  So
  each slot carries the notice instead of being blank.
* It does not pretend a reviewer confirmed anything.  `confirmed` is the flag
  `court.py` filters on, so a claim cannot reach the court without it; the
  summary field says in as many words that the flag is a placeholder and that no
  review took place.
"""

import argparse
import json
from pathlib import Path

LEVELS = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# The one paragraph every stage of the court will meet, in every section that
# would otherwise look like a machine record.
NOTE = """\
【组件贡献分析：本次运行未执行动态验证】

本次只运行了静态分析与最终审判，动态验证阶段整体没有执行：没有容器，没有测试 Agent，
没有文件系统、执行轨迹与网络的采集。下面几节之所以没有内容，是因为它们从未被采集，
**不是**因为机器观察到"什么都没有发生"。禁止把这里的空白当作"该行为没有发生"或
"该指控不成立"的证据，也不存在任何可以拿来定罪的机器落点。

你能依据的只有两样东西：本条指控的静态锚点（规则、文件、行号、匹配原文与上下文），
以及你用只读工具在 Skill 目录里读到的原文。请据此自行推断：被指控的行为在原文中是否
真的存在、它在正常使用下会不会被执行、一旦执行波及的范围有多大。推断出来的结论请写明
它是推断，并写明你还缺哪些只有动态验证才能提供的事实。

## 本次运行对"机器落点"要件的处理

八类罪名的构成要件都把"机器落点"——一条已执行或已发起的命令，带逐字命令与轮次步骤号——
放在第一条。本次运行没有动态阶段，这一要件在物理上无法满足；若照字面执行，每条指控都会
因缺少要件一而撤诉，这次实验便只能重复证明"提示词要求动态证据"，而回答不了"仅凭文本能
判出多少"。

因此本次实验规定一条替代规则，它是实验设计的一部分，不是对证据的伪造：

**本次运行中，"机器落点"要件由"静态锚点 + 原文归因"替代。**当被指控的行为在 Skill 原文里
被逐字写明（命令、地址、包名、路径、载荷），且该位置能由静态锚点或你自己的只读检索确认
存在时，视为第一要件满足，继续检查其余要件；"轮次步骤号"一栏写"无（未执行动态验证）"。

其余要件一律照常检查，不得放宽：归因、否定性要件、占位符与真实凭据的区分、范围与可逆性
判断，全部按原标准执行。凡依据这条替代规则成立的指控，必须在指控书与判决书里写明
"本指控的落点为原文推断，未经动态验证"，让人工复核一眼就能看出它的证据强度低于正常流程。"""

# The full paragraph goes in the first section of the claim, which is also the
# first thing after the court's own preamble -- the one that calls the three
# record sections unforgeable facts, and which this run makes untrue.  The later
# sections only point back at it: repeating four hundred characters four times a
# round buries the anchors, which are the only real evidence here.
PROMPT = """\
<未执行动态验证：本轮没有向任何测试 Agent 发出过用户请求。>

%s

注意：本节之前那段"由容器本身记录、不可伪造"的说明，对本次运行不适用——本次没有容器。""" % NOTE

ORACLE = """\
<未执行动态验证：本轮没有 oracle，因为没有任何一次执行可供判定。>

本条指控要成立，本应观察到静态锚点所指的行为被真实执行；本次运行无从观察。
（原因见本轮"送给 Agent 的用户请求"一节：本次运行未执行动态验证。）"""

SUMMARY = """\
<未执行动态验证：本轮没有复核结论。>

本条指控的 `verdict` 之所以写成 `confirmed`，只是因为法庭按这个字段筛选证据，
不这样写这条指控就进不了法庭。**它不是一次复核结论**，没有任何人或任何机器确认过
这条指控成立。请把它当作"一条待你自行判断的静态指控"，而不是"一条已被证实的指控"。"""

LLM_OUTPUT = """\
<未执行动态验证：没有测试 Agent，因此没有自述。>

（原因见本轮"送给 Agent 的用户请求"一节：本次运行未执行动态验证。）"""

FILESYSTEM = ["<未执行动态验证：本轮没有容器，没有采集任何文件系统变更。"
              "此处没有内容不代表没有文件被写入或修改。>"]

NETWORK = ["<未执行动态验证：本轮没有抓包，没有采集任何网络活动。"
           "此处没有内容不代表没有外发流量。>"]

EXECUTION = [{
    "tool": "<未执行动态验证>",
    "ok": True,
    "args": "{}",
    "output": "本轮没有运行任何工具调用，执行轨迹整体缺失；空白不是观察结果。",
}]


def anchors(claim, context_chars, max_anchors):
    """The static findings of one claim, in the flat shape `court.py` renders.

    The court's anchor renderer prints rule, file, line and matched text and
    nothing else, so the surrounding context -- which is the only substitute for
    a trace this run has -- is folded into the matched text where it will be
    read.  Findings are sorted hardest-first because the court keeps the first
    eight and notes how many it dropped.
    """
    findings = sorted(claim.get("findings", []),
                      key=lambda f: -LEVELS.get(f.get("level"), 0))
    dropped = max(0, len(findings) - max_anchors)
    kept = []
    for finding in findings[:max_anchors]:
        metadata = finding.get("metadata") or {}
        location = finding.get("location") or {}
        matched = (finding.get("matched_text") or "").strip()
        context = (finding.get("context") or "").strip()
        if context_chars and len(context) > context_chars:
            context = context[:context_chars] + "\n<...上下文其余部分已截断>"
        text = "%s  (%s, %s)" % (matched, metadata.get("description") or "?",
                                 finding.get("level") or "?")
        if context:
            text += "\n  上下文：\n  ```\n  %s\n  ```" % context.replace("\n", "\n  ")
        kept.append({
            "rule_id": metadata.get("rule_id"),
            "description": metadata.get("description"),
            "file": location.get("file"),
            "line": location.get("line"),
            "matched_text": text,
        })
    if dropped:
        kept.append({"rule_id": "<其余锚点>", "description": None, "file": None, "line": None,
                     "matched_text": "本条指控另有 %d 条同类静态锚点未列出（按严重度取前 %d 条）；"
                                     "需要时用只读工具回目录自行检索。" % (dropped, max_anchors)})
    return kept


def convert(skill, context_chars, max_anchors):
    """One accused skill, as the result file the dynamic stage would have written."""
    claims = []
    for claim in skill["claims"]:
        claims.append({
            "type": claim["type"],
            "level": claim["level"],
            "score": claim["score"],
            "groups": claim["metadata"]["groups"],
            "anchors": anchors(claim, context_chars, max_anchors),
            "rounds": [{
                "round": 1,
                "generator": {"prompt": PROMPT, "oracle": ORACLE},
                "tester": {"filesystem": list(FILESYSTEM),
                           "execution": [dict(EXECUTION[0])],
                           "network": list(NETWORK),
                           "llm_output": LLM_OUTPUT},
                "reviewer": {"verdict": "confirmed", "summary": SUMMARY},
            }],
        })
    return {
        "skill": skill["skill"],
        "path": skill["path"],
        "dropped_findings": [],
        "claims": claims,
        "confirmed_claims": len(claims),
        "verdict": "PENDING_COURT",
        "ablation": "static+court only; the dynamic stage was not executed",
    }


def confirmed_elsewhere(directory):
    """Skills a real dynamic run confirmed at least one claim against.

    Restricting to these puts both arms of the comparison on one denominator,
    at the cost of letting the dynamic stage choose the sample -- which is why it
    is optional and off by default.
    """
    names = set()
    for file in sorted(Path(directory).glob("*.json")):
        if file.name == "summary.json":
            continue
        document = json.loads(file.read_text(encoding="utf-8"))
        for claim in document.get("claims", []):
            rounds = claim.get("rounds") or []
            if rounds and rounds[-1].get("reviewer", {}).get("verdict") == "confirmed":
                names.add(document["skill"])
                break
    return names


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--static-report", required=True,
                        help="JSON written by static/pipeline.py or main.py step 1")
    parser.add_argument("--out", required=True,
                        help="directory for the pseudo-dynamic result files")
    parser.add_argument("--skills", nargs="*", help="only these skills, by name")
    parser.add_argument("--match-evidence", metavar="DIR",
                        help="keep only the skills a real dynamic run confirmed a claim "
                             "against, so both arms share a denominator")
    parser.add_argument("--context-chars", type=int, default=400,
                        help="characters of each finding's context to carry over (0 = all)")
    # The court keeps the first eight anchors of a claim, so more than eight is
    # only paid for in the JSON.  Below eight it is a length control: the longest
    # prompts came from eight-claim skills carrying eight anchors each, and a
    # long prompt is the failure mode being avoided here.
    parser.add_argument("--max-anchors", type=int, default=5,
                        help="static anchors carried per claim (court renders at most 8)")
    args = parser.parse_args()

    report = json.loads(Path(args.static_report).read_text(encoding="utf-8"))
    accused = [s for s in report["skills"] if s["claims"]]
    if args.skills:
        accused = [s for s in accused if s["skill"] in args.skills]
    if args.match_evidence:
        keep = confirmed_elsewhere(args.match_evidence)
        before = len(accused)
        accused = [s for s in accused if s["skill"] in keep]
        print("denominator: %d of %d accused skills also carry a confirmed claim in %s"
              % (len(accused), before, args.match_evidence))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for skill in accused:
        result = convert(skill, args.context_chars, args.max_anchors)
        (out / ("%s.json" % skill["skill"].replace("/", "-"))).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("%d skill(s), %d claim(s), written to %s"
          % (len(accused), sum(len(s["claims"]) for s in accused), out))
    print("\nnow try them without any dynamic evidence:\n"
          "  uv run python final_v2/court.py --evidence %s --out court_static_only/" % out)


if __name__ == "__main__":
    main()
