"""The prosecutor.  Answers the four questions and files the charges.

It sees the forensics report and nothing else: no skill directory, no machine
records.  Its one tool is `read_guide`, the constitutive elements of the eight
charge categories -- and those elements, not a whitelist, are what makes it drop
a charge.  It holds no whitelist and grants no exemption from experience; the
judge is where those live.

It may return BENIGN.  That is what happens when every candidate chain fails an
element, and it ends the court right there.
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
import tools
from llm import chat_model

SYSTEM_PROMPT = prompts.load("prosecutor")
HUMAN_PROMPT = prompts.load("prosecutor", "human")

SEED, TOP_P = 42, 0.01  # pinned with the other two stages, see forensics.py


class Indictment(BaseModel):
    verdict: str = Field(description="MALICIOUS when at least one charge is filed, otherwise BENIGN")
    report: str = Field(description="the Markdown indictment: charges, chains, evidence carried over verbatim, the four questions, the preconditions")


def accuse(forensics, timeout=300, recursive=50):
    """Return {verdict, report}: the charges brought against the skill."""
    agent = create_agent(
        chat_model(temperature=0.0, timeout=timeout, seed=SEED, top_p=TOP_P),
        tools=tools.guide_tool(),
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(Indictment),
    )
    state = agent.invoke(
        {"messages": [HumanMessage(content=HUMAN_PROMPT.format(forensics=forensics))]},
        config={"recursion_limit": recursive},
    )
    result = state["structured_response"]
    verdict = "BENIGN" if result.verdict.strip().upper().startswith("BENIGN") else "MALICIOUS"
    return {"verdict": verdict, "report": result.report.strip()}
