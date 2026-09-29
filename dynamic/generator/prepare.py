"""Denoising pass in front of the generator.

The static layer is a pattern matcher, so a share of its findings are matches on
something the pattern does not describe: a filename that looks like a call, a
`venv` directory read as an `.env` file, a tool named inside prose.  One LLM
call per batch of findings drops those and nothing else -- no judgement on how
dangerous a real match is.  Surviving findings are regrouped and re-scored.
"""

import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generator import helper
from llm import chat_model

MAX_FINDINGS = 10

SYSTEM_PROMPT = """\
Your task is to filter out false positives from the results of a regex scan targeting AI agent skills.
Each entry includes a match, the behavior described by the rule, and surrounding source text around the match.

For each entry, you judge only one thing: whether the source text genuinely contains the behavior described by the rule.
Retain all real constructs, instructions, or executable examples. Do not consider intent, safety implications, or severity—these are outside the scope of this task.

Mark an entry as noise **only** when the matched text does **not** express the described behavior:

- The matched string appears merely as part of a filename, directory name, variable, field, or identifier (e.g., `env/`, `venv/`, `download.py`, `install_helper`, a column named `password`);
- The tool or concept is mentioned only in prose, headings, changelogs, or link text, without recommendation, demonstration, or implementation;
- The source explicitly presents the line as a "do not do this" anti-example, or it is inert test data, fixture content, or commented-out code rather than an active instruction;
- The apparent value is clearly a placeholder (e.g., `<YOUR_API_KEY>`, `sk-xxxxxxxx`, `password = "changeme"`), and the rule requires an actual embedded value to be valid;
- The text belongs to a license file, lockfile, or third-party dependency bundled with the package, describing that third-party component rather than the skill itself.

Retain the following: commands shown as part of the skill's workflow, runnable code snippets, installation and initialization steps, and instructions directed at the agent or user.
Even if they appear mundane, require unavailable software or credentials, or would likely fail on the current machine, retain them. When context allows for multiple interpretations, retain the finding.

Return exactly as many results as there are input entries, preserving their order."""

HUMAN_PROMPT = """\
Skill: {skill}

{items}

Interpret the full context—not just the matched keyword. Normal phrasing like "silently ignores", a BOM appearing only at the start of a file, fragments in build artifacts or caches, and routine log clearing/rotation during program startup are all noise—even if the log previously contained runtime data. Only retain such matches when the context explicitly instructs the agent to conceal, inject, or erase an action to hide evidence of its occurrence. For example, `: > "$LOG_FILE"` in an install script, used for ordinary log initialization before actual work begins, counts as noise.

Classify all {count} entries."""


class Judgement(BaseModel):
    index: int = Field(description="The index of the entry being judged")
    noise: bool = Field(description="True if the match does not represent the behavior described by the rule; must be True for cases like ordinary uses of words such as 'silently', BOM markers at file start, build artifacts, or routine log clearing during startup (even if old logs are deleted); retain log-deletion findings only when context explicitly directs hiding an action")
    reason: str = Field(description="A one-sentence explanation")


class Judgements(BaseModel):
    judgements: list[Judgement] = Field(description="One result per entry, in the given order")


def render(findings):
    blocks = []
    for i, f in enumerate(findings):
        blocks.append(
            "[%d] rule: %s -- %s\n"
            "    behaviour group: %s\n"
            "    location: %s:%d\n"
            "    matched: %s\n"
            "    context:\n%s"
            % (i, f["metadata"]["rule_id"], f["metadata"]["description"], f["group"],
               f["location"]["file"], f["location"]["line"],
               f["matched_text"][:200],
               "\n".join("      " + line for line in f["context"].splitlines()[:20]))
        )
    return "\n\n".join(blocks)


def denoise(skill, timeout, recursive):
    """Return the skill with noise findings removed and its claims re-scored."""
    findings = {}
    for claim in skill["claims"]:
        for finding in claim["findings"]:
            findings[finding["metadata"]["id"]] = finding
    findings = list(findings.values())

    agent = create_agent(
        chat_model(temperature=0.0, timeout=timeout),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(Judgements),
    )

    kept, dropped = [], []
    for start in range(0, len(findings), MAX_FINDINGS):
        batch = findings[start:start + MAX_FINDINGS]
        state = agent.invoke(
            {"messages": [HumanMessage(content=HUMAN_PROMPT.format(
                skill=skill["skill"], items=render(batch), count=len(batch)))]},
            config={"recursion_limit": recursive},
        )
        noise = {j.index for j in state["structured_response"].judgements if j.noise}
        for i, finding in enumerate(batch):
            (dropped if i in noise else kept).append(finding)

    return {
        "skill": skill["skill"],
        "path": skill["path"],
        "n_findings": len(kept),
        "n_dropped": len(dropped),
        "dropped": [{"id": f["metadata"]["id"], "rule_id": f["metadata"]["rule_id"],
                     "location": f["location"]} for f in dropped],
        "claims": helper.rebuild_claims(skill, kept),
    }
