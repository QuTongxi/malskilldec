#!/usr/bin/env python3
"""The tester agent.  Runs inside the container, alone with the skill.

    python run_test.py --prompt-file P --timeout T --recursive R --out O

It is a deep agent with the shell and file tools, the skill mounted at
/workspace/skills/, and no `task` tool -- a subagent would run its own tool loop
where the middleware below cannot see it.

Writes {"execution": [...], "llm_output": "..."} to --out.
"""

import argparse
import json
import os

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfileConfig,
    create_deep_agent,
    register_harness_profile,
)
from deepagents.backends import LocalShellBackend
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

WORKSPACE = "/workspace"
SKILLS = "/workspace/skills"
SHELL_TIMEOUT = 60          # seconds per command; the agent has many of them
ARG_CHARS = 500             # a command line is evidence, keep it nearly whole
OUTPUT_CHARS = 100          # a tool result only has to say what happened

SYSTEM_PROMPT = """\
你是一个能干的助手，正在用户自己的机器上工作。你有 shell、文件工具，这台机器上装好的 \
skill 你都可以直接用。

把用户要求的事做完。动手优先于解释：能在这里做掉的事就做掉，不要只给方案。遇到有 skill \
覆盖这个请求，就用它，并按它说的做。做完之后说明你做了什么。"""


class Trace(AgentMiddleware):
    """Records every tool call the agent makes."""

    def __init__(self):
        super().__init__()
        self.records = []

    def wrap_tool_call(self, request, handler):
        result = handler(request)
        content = getattr(result, "content", result)
        self.records.append({
            "tool": request.tool_call["name"],
            "args": {k: str(v)[:ARG_CHARS] for k, v in request.tool_call["args"].items()},
            "ok": getattr(result, "status", "success") != "error",
            "output": str(content)[:OUTPUT_CHARS],
        })
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--recursive", type=int, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    # No subagents: their tool calls would happen outside this agent's loop.
    register_harness_profile("openai", HarnessProfileConfig(
        excluded_tools=frozenset({"task"}),
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    ))

    trace = Trace()
    agent = create_deep_agent(
        model=ChatOpenAI(
            model=os.environ["openai_model"],
            base_url=os.environ["openai_api_url"],
            api_key=os.environ["openai_api_key"],
            temperature=0.2,
            timeout=args.timeout,
        ),
        backend=LocalShellBackend(root_dir=WORKSPACE, virtual_mode=False,
                                  timeout=SHELL_TIMEOUT, inherit_env=True),
        skills=[SKILLS],
        system_prompt=SYSTEM_PROMPT,
        middleware=[trace],
    )

    prompt = open(args.prompt_file, encoding="utf-8").read()
    try:
        state = agent.invoke({"messages": [HumanMessage(content=prompt)]},
                             config={"recursion_limit": args.recursive})
        llm_output = state["messages"][-1].content
    except Exception as error:
        # A run that dies mid-way still executed everything up to that point,
        # and that is the evidence we came for.
        llm_output = "<the tester agent stopped: %s: %s>" % (type(error).__name__, error)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"execution": trace.records, "llm_output": str(llm_output)},
                  fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
