"""The judge.  Drops the charges that common knowledge explains away.

It gets the indictment and nothing else: no tools, no skill directory, no
testimony.  A skill that talks its way past a reader cannot talk to this stage,
and the price is that whatever the prosecutor failed to quote no longer exists.

The verdict has a suspicious middle state.  A concrete, attributable risk is
kept visible when its identity, authorization, payload, or final effect still
has a specific gap; ordinary capabilities and best-practice concerns are not.

The one exception is attribution: with no quoted passage the action cannot be
told apart from something the test agent invented, and that is enforced here as
well as asked for.
"""

import re
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dynamic"))

import prompts
from llm import chat_model

SYSTEM_PROMPT = prompts.load("judge")
HUMAN_PROMPT = prompts.load("judge", "human")

VERDICTS = ("MALICIOUS", "SUSPICIOUS", "BENIGN")

# The prompt's own rule: a conviction has to rest on a passage the indictment
# quoted, because otherwise the action cannot be told apart from something the
# test agent invented.  The model states the condition and then sentences past
# it often enough that the rule is enforced here instead of only asked for.
# Scoped to the section that carries the quote, so the same phrase appearing
# under "已排除的指控" cannot acquit a charge that was properly quoted.
DECISIVE = re.compile(r"^#+\s*(?:\d+[.、]\s*)?\**\s*决定性片段.*?(?=^#+\s|\Z)",
                      re.MULTILINE | re.DOTALL)
NO_QUOTE = re.compile(r"(?:未|没有|无)(?:能|法)?(?:提供|摘抄|引用)[^\n。]{0,12}原文"
                      r"|无对应原文片段|未提供可引用"
                      r"|全文[^\n。]{0,12}(?:未提及|没有)[^\n。]{0,8}(?:动作|行为|修改|指令|功能)"
                      # Only absence of a quoted source passage defeats
                      # attribution.  A bare "不存在" may describe a missing
                      # payload/file and must not silently reverse a verdict.
                      r"|(?:原文|引用|片段)[^\n。]{0,8}\*{0,2}不存在\*{0,2}"
                      r"|(?:未能|未|找不到)[^\n。]{0,8}(?:找到|引用|原文|片段)")

UNATTRIBUTED = ("\n\n---\n\n> 判决改为 BENIGN：本报告在“决定性片段”一节声明指控"
                "未提供可引用的 Skill 原文，因此被指控的行为无法与测试 Agent 自行发明的行为"
                "区分开。执行证据本身不受影响，已作为存疑记录保留。")

UNREADABLE = ("\n\n---\n\n> 注意：本报告的 `verdict` 字段无法解析为 MALICIOUS、SUSPICIOUS 或 BENIGN，"
              "已按 MALICIOUS 记录以便人工复核。这是一次输出格式故障，不是对证据的判断。")


class Judgement(BaseModel):
    verdict: str = Field(description="MALICIOUS, SUSPICIOUS, or BENIGN; uncertainty about a concrete malicious chain is SUSPICIOUS, not BENIGN")
    report: str = Field(description="the full Markdown judgement, in the order the prompt prescribes")


def adjudicate(indictment, timeout=300, recursive=50):
    """Return {verdict, report}: the sentence passed on the indictment."""
    agent = create_agent(
        chat_model(temperature=0.0, timeout=timeout),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(Judgement),
    )
    state = agent.invoke(
        {"messages": [HumanMessage(content=HUMAN_PROMPT.format(indictment=indictment))]},
        config={"recursion_limit": recursive},
    )
    result = state["structured_response"]

    report = result.report.strip()
    spoken = result.verdict.strip().upper()
    for verdict in VERDICTS:
        if spoken.startswith(verdict):
            break
    else:
        # A verdict we cannot read is a broken output, not a doubt about the
        # skill.  Convicting keeps it visible for review rather than letting a
        # format failure silently acquit.
        verdict, report = "MALICIOUS", report + UNREADABLE

    decisive = DECISIVE.search(report)
    unattributed = (verdict != "BENIGN" and decisive is not None
                    and bool(NO_QUOTE.search(decisive.group(0))))
    if unattributed:
        verdict, report = "BENIGN", report + UNATTRIBUTED
    return {"verdict": verdict, "report": report, "unattributed": unattributed}
