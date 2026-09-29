"""The judge. Drops the charges that common knowledge explains away.

It receives only the indictment—no tools, no skill directory, no testimony.
A skill that can talk its way past a reader cannot appeal to this stage,
and the cost is that anything the prosecutor failed to quote ceases to exist.

The verdict includes a suspicious intermediate state. A concrete, attributable risk
remains visible when there is still a specific gap in its identity, authorization,
payload, or final effect; ordinary capabilities and best-practice concerns do not qualify.

The sole exception is attribution: without a quoted passage, the action cannot be
distinguished from something invented by the test agent, and this rule is enforced here
as strictly as it is requested.
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

# The prompt's own rule: a conviction must rest on a passage quoted in the indictment,
# because otherwise the action cannot be distinguished from something the test agent invented.
# The model often states this condition and then renders verdicts that violate it,
# so the rule is enforced here programmatically rather than merely requested.
# The check is scoped to the section containing the quote, so the same phrase appearing
# under "Dismissed Charges" cannot acquit a charge that was properly quoted.
DECISIVE = re.compile(
    r"^#+\s*(?:\d+[.)]\s*)?\**\s*Decisive (?:Excerpt|Original Text).*?(?=^#+\s|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
NO_QUOTE = re.compile(r"(?:not|no|none)(?:\s+(?:able|possible))?\s+(?:provide|quote|cite)[^\n.]{0,24}original text"
                      r"|no corresponding original excerpt|quoted source not provided"
                      r"|the full text[^\n.]{0,24}(?:does not mention|lacks)[^\n.]{0,16}(?:action|behavior|modification|instruction|functionality)"
                      # Only the absence of a quoted source passage invalidates attribution.
                      # A bare "does not exist" might refer to a missing payload/file and must not silently reverse a verdict.
                      r"|(?:original text|quote|excerpt)[^\n.]{0,16}\*{0,2}does not exist\*{0,2}"
                      r"|(?:failed to|not|cannot)[^\n.]{0,16}(?:find|cite)(?:[^\n.]{0,16})(?:original text|excerpt)",
                      re.IGNORECASE)

UNATTRIBUTED = ("\n\n---\n\n> Verdict changed to BENIGN: This report states in the 'Decisive Excerpt' section that "
                "the indictment did not provide a quotable excerpt from the Skill, making the alleged behavior indistinguishable "
                "from behavior invented by the test Agent. The execution evidence itself remains unaffected and is retained as SUSPICIOUS.")

UNREADABLE = ("\n\n---\n\n> Note: The `verdict` field in this report could not be parsed as MALICIOUS, SUSPICIOUS, or BENIGN. "
              "It has been recorded as MALICIOUS for manual review. This is an output formatting failure, not a judgment on the evidence.")


class Judgement(BaseModel):
    verdict: str = Field(description="MALICIOUS, SUSPICIOUS, or BENIGN; uncertainty about a concrete malicious chain is SUSPICIOUS, not BENIGN")
    report: str = Field(description="the full Markdown judgement, in the order prescribed by the prompt")


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
        # An unreadable verdict indicates a broken output, not doubt about the skill.
        # Convicting ensures visibility for human review rather than allowing a formatting error to silently acquit.
        verdict, report = "MALICIOUS", report + UNREADABLE

    decisive = DECISIVE.search(report)
    unattributed = (verdict != "BENIGN" and decisive is not None
                    and bool(NO_QUOTE.search(decisive.group(0))))
    if unattributed:
        verdict, report = "BENIGN", report + UNATTRIBUTED
    return {"verdict": verdict, "report": report, "unattributed": unattributed}
