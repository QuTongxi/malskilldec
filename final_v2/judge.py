"""The judge.  Three checks, in order, and then a verdict.

It gets the indictment and nothing else: no tools, no forensics report, no skill
directory.  A skill that talks its way past a reader cannot talk to this stage,
and the price is that whatever the prosecutor failed to carry over verbatim no
longer exists -- which is why both stages before it are told to carry quotes
across unchanged.

The verdict is binary.  This is the only stage that decides, so a middle grade
would only be folded into one of the two anyway, and folding is what turned
every doubt into a conviction in the first version.
"""

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

SEED = 42  # pinned with the other two stages, see forensics.py

UNREADABLE = ("\n\n---\n\n> 注意：本报告的 `verdict` 字段无法解析为 MALICIOUS 或 BENIGN，"
              "已按 MALICIOUS 记录以便人工复核。这是一次输出格式故障，不是对证据的判断。")


class Judgement(BaseModel):
    verdict: str = Field(description="MALICIOUS or BENIGN, nothing in between")
    report: str = Field(description="the full Markdown judgement, in the order the prompt prescribes, carrying the decisive quotes over verbatim")


def adjudicate(indictment, timeout=300, recursive=50):
    """Return {verdict, report}: the sentence passed on the indictment."""
    agent = create_agent(
        chat_model(temperature=0.0, timeout=timeout, seed=SEED),
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
    if spoken.startswith("BENIGN"):
        verdict = "BENIGN"
    elif spoken.startswith("MALICIOUS"):
        verdict = "MALICIOUS"
    else:
        # A verdict we cannot read is a broken output, not a doubt about the
        # skill.  Convicting keeps it visible for review rather than letting a
        # format failure silently acquit.
        verdict, report = "MALICIOUS", report + UNREADABLE
    return {"verdict": verdict, "report": report}
