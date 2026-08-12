"""The prosecutor.  Holds the testimony against the machine records.

Same four read-only tools as the defendant, but the prompt tells it the skill's
own text is worthless as evidence: it charges on what the run did.  It is meant
to over-charge -- the judge, not this stage, is where a charge is dropped.
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


class Indictment(BaseModel):
    verdict: str = Field(description="MALICIOUS when at least one charge stands, otherwise BENIGN")
    report: str = Field(description="the full Markdown audit report: charges, evidence quoted verbatim, attack paths")


def accuse(testimony, evidence, skill_path, timeout=300, recursive=50):
    """Return {verdict, report}: the charges brought against the skill."""
    agent = create_agent(
        chat_model(temperature=0.0, timeout=timeout),
        tools=tools.read_tools(skill_path),
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(Indictment),
    )
    state = agent.invoke(
        {"messages": [HumanMessage(content=HUMAN_PROMPT.format(
            testimony=testimony, evidence=evidence))]},
        config={"recursion_limit": recursive},
    )
    result = state["structured_response"]
    # Anything that is not a clear acquittal is a charge: this stage is the
    # high-recall one, and the judge is what stands between it and a verdict.
    verdict = "BENIGN" if result.verdict.strip().upper().startswith("BENIGN") else "MALICIOUS"
    return {"verdict": verdict, "report": result.report.strip()}
