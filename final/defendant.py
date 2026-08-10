"""The defendant.  Reads the skill and speaks for it.

One agent, the four read-only tools of `tools.py`, and the testimony prompt.
It produces the account the prosecutor will then hold against the machine
records -- so nothing here asks it to be suspicious: a testimony is only useful
as a statement of what the skill says about itself.
"""

import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dynamic"))

import prompts
import tools
from llm import chat_model

SYSTEM_PROMPT = prompts.load("defendant")


HUMAN_PROMPT = prompts.load("defendant", "human")


def testify(skill_path, skill_name, timeout=300, recursive=50):
    """Return the testimony report as Markdown."""
    agent = create_agent(
        chat_model(temperature=0.0, timeout=timeout),
        tools=tools.read_tools(skill_path),
        system_prompt=SYSTEM_PROMPT,
    )
    state = agent.invoke(
        {"messages": [HumanMessage(content=HUMAN_PROMPT.format(skill=skill_name))]},
        config={"recursion_limit": recursive},
    )
    report = state["messages"][-1].content
    if isinstance(report, list):  # some providers return content blocks
        report = "".join(block.get("text", "") for block in report
                         if isinstance(block, dict))
    return str(report).strip()
