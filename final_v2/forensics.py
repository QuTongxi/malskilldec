"""The forensics stage.  The only one that sees the raw material.

It reads the machine records and the skill directory and writes down what
happened: where each accused action landed in the trace, which passage of the
skill produced it, how wide it reached -- and, separately, the dangerous actions
whose identifiers appear nowhere in the skill, because those belong to the test
agent rather than to the defendant.

Its report is the only thing the two stages after it will ever see, so it is
graded on accuracy and completeness, not on brevity.  It does not judge.
"""

import re
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dynamic"))

import prompts
import tools
from llm import chat_model

SYSTEM_PROMPT = prompts.load("forensics")
HUMAN_PROMPT = prompts.load("forensics", "human")

# Everything downstream is a function of this report, so a report that comes out
# different on a rerun moves the whole verdict.  The two stages after this one
# reason over prose and gain nothing from a pinned sample; this one enumerates
# records, where a dropped line is a lost conviction, so it is the one stage that
# is pinned.
SEED = 42

# The court stops here when the report holds no chain: with nothing attributed
# there is nothing to charge, and the two stages after this one would only be
# reading an empty page.
CHAIN = re.compile(r"^#{2,4}\s*链条\s*\d+", re.MULTILINE)


def has_chain(report):
    return bool(CHAIN.search(report or ""))


def investigate(skill, evidence, skill_path, timeout=300, recursive=50):
    """Return the Markdown fact report for one skill."""
    agent = create_agent(
        chat_model(temperature=0.0, timeout=timeout, seed=SEED),
        tools=tools.read_tools(skill_path),
        system_prompt=SYSTEM_PROMPT,
    )
    state = agent.invoke(
        {"messages": [HumanMessage(content=HUMAN_PROMPT.format(
            skill=skill, evidence=evidence))]},
        config={"recursion_limit": recursive},
    )
    content = state["messages"][-1].content
    if isinstance(content, list):        # some providers return content blocks
        content = "".join(part.get("text", "") for part in content
                          if isinstance(part, dict))
    return (content or "").strip()
