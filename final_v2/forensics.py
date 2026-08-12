"""The forensics stage.  The only one that sees the raw material.

It reads the machine records and the skill directory and writes down what
happened: where each accused action landed in the trace, which passage of the
skill produced it, how wide it reached -- and, separately, the dangerous actions
whose identifiers appear nowhere in the skill, because those belong to the test
agent rather than to the defendant.

Its report is the only thing the two stages after it will ever see, so it is
graded on accuracy and completeness, not on brevity.  It does not judge.
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

SYSTEM_PROMPT = prompts.load("forensics")
HUMAN_PROMPT = prompts.load("forensics", "human")

# Temperature was already 0, and the court still changed its mind about 16 of 38
# probe skills between runs of the same prompts -- so every measurement was a
# measurement of the draw rather than of the prompt.  `seed` alone did not fix it:
# a back-to-back rerun at seed 42 flipped three skills of five, so this endpoint
# does not honour it.  Narrowing top_p is the constraint that does apply.  The two
# stages after this one read both values from here so they cannot drift apart.
SEED, TOP_P = 42, 0.01


def investigate(skill, evidence, skill_path, timeout=300, recursive=50):
    """Return the Markdown fact report for one skill."""
    agent = create_agent(
        chat_model(temperature=0.0, timeout=timeout, seed=SEED, top_p=TOP_P),
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
