"""The judge. Four checks, in order, and then a verdict.

It receives only the indictment—no forensic report, no skill directory.
A skill that can persuade a human reader cannot influence this stage, and the cost
is that anything the prosecutor failed to carry over verbatim no longer exists—
which is why both preceding stages are instructed to preserve quotes unchanged.

Its sole tool is `check_source`, the domain list in `sources.yaml`. This list now
constitutes the court's entire whitelist: the general rules that previously resided
alongside it in `precedents.md` have been integrated into the four steps, because
a rule concerning whether an action occurred at all was never a whitelist entry—it
was a step the judge had already passed before consulting the list.

The verdict is binary. This is the only stage that renders a decision; thus, any
intermediate classification would ultimately be mapped to one of the two outcomes
anyway—and such mapping is precisely what converted every doubt into a conviction
in the initial version.
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

SYSTEM_PROMPT = prompts.load("judge")
HUMAN_PROMPT = prompts.load("judge", "human")

SEED, TOP_P = 42, 0.01  # pinned with the other two stages, see forensics.py

UNREADABLE = ("\n\n---\n\n> Note: The `verdict` field in this report could not be parsed as either MALICIOUS or BENIGN, "
              "so it has been recorded as MALICIOUS for manual review. This is an output formatting failure, not a judgment on the evidence.")


class Judgement(BaseModel):
    verdict: str = Field(description="MALICIOUS or BENIGN, nothing in between")
    report: str = Field(description="the full Markdown judgement, in the order prescribed by the prompt, carrying decisive quotes verbatim")


def adjudicate(indictment, timeout=300, recursive=50):
    """Return {verdict, report}: the sentence passed on the indictment."""
    agent = create_agent(
        chat_model(temperature=0.0, timeout=timeout, seed=SEED, top_p=TOP_P),
        tools=tools.source_tool(),
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
        # An unreadable verdict indicates a broken output, not uncertainty about
        # the skill. Convicting ensures visibility for review rather than allowing
        # a formatting error to silently result in acquittal.
        verdict, report = "MALICIOUS", report + UNREADABLE
    return {"verdict": verdict, "report": report}
