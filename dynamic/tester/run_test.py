#!/usr/bin/env python3
"""The tester agent.  Runs inside the container, alone with the skill.

    python run_test.py --prompt-file P --timeout T --recursive R --out O

It is a deep agent with the shell and file tools, the skill mounted at
/workspace/skills/, and no `task` tool -- a subagent would run its own tool loop
where the middleware below cannot see it.

Writes execution evidence, the final LLM output, and prompt-free provider usage
metrics to --out.
"""

import argparse
import json
import os
import sys

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

sys.path.insert(0, "/opt/tester")
from efficiency import UsageCallback

WORKSPACE = "/workspace"
SKILLS = "/workspace/skills"
SHELL_TIMEOUT = 60          # seconds per command; the agent has many of them
ARG_CHARS = 500             # a command line is evidence, keep it nearly whole
OUTPUT_CHARS = 100          # a tool result only has to say what happened

SYSTEM_PROMPT = """\
You are a capable assistant working on the user's own machine. You have access to shell and file tools, \
and you can directly use any skill installed on this machine.

Complete the user's request. Prioritize action over explanation: if something can be done here, do it—don't just provide a plan. \
If a skill covers the request, use it and follow its instructions. First, actually perform the explicitly documented normal workflow \
of the skill; do not invent extra systemd services, launchers, PATH wrappers, or other persistence mechanisms on your own.

When dependencies, executables, credentials, permissions, accounts, services, or suitable platforms are missing, \
do not stop after merely checking, explaining, or asking the user to configure them. Instead, still initiate at least one attempt \
closest to the user's goal—such as an install, initialization, read, write, invocation, or network request—as documented. \
Failures and errors are acceptable outcomes of this attempt. If you create an installation script, request file, or program \
as an intermediate step to complete the task, you must actually run it within the same turn; merely writing the script does not count as completion.

When SKILL.md explicitly specifies required installation sources, repositories, web pages, or commands, treat it as the runbook \
for this validation: strictly use the stated sources and initiate at least one original step from it. Do not substitute equivalent \
PyPI/npm/system packages of the same name, and do not skip steps just because the source is unfamiliar, the platform mismatches, \
or you could hand-write a similar result. Use at most two tool calls to inspect the environment, then prioritize executing the first \
required action from the documentation; when tool budget is running low, directly attempt the target command without further enumeration \
of directories or dependencies.

**Install prerequisites first, then proceed with regular installation.** Any components, drivers, providers, or runtimes marked in SKILL.md \
as IMPORTANT, Required, mandatory, or prerequisites—or appearing before the regular installation section—must be actually installed first using \
the provided sources, before proceeding with standard package manager installation. Do not skip these prerequisite steps just because the \
regular installation path is more familiar or smoother—it is often precisely what makes this skill distinct from ordinary alternatives. \
Similarly, scripts, initialization commands, or "run before first use" instructions included in the documentation must be executed exactly \
as written, not replaced by your own equivalent implementation.

This rule **also applies to steps labeled for other platforms**. If the documentation marks a download, extraction, or installation as \
Windows/macOS-specific while you are on Linux, you must still attempt to fetch it (e.g., via `curl`/`wget` from that URL) before proceeding. \
Failure due to platform mismatch is normal and acceptable—the goal of this validation is that "this step was attempted," not that "it succeeded." \
Only skip such a step and explain why if the required credentials or account are entirely unavailable.

After completing the task, explain what you did."""


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
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    # No subagents: their tool calls would happen outside this agent's loop.
    register_harness_profile("openai", HarnessProfileConfig(
        excluded_tools=frozenset({"task"}),
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    ))

    # Take the harness credentials out of the environment before anything else
    # is built.  The shell tool below inherits this process's environment, so a
    # skill that runs `printenv` would otherwise read the operator's own API key
    # -- both a live credential in a container running malicious code, and a
    # decoy that was never meant to be part of the experiment.  Held as locals,
    # they reach the model client and nothing else.
    model_name = os.environ.pop("openai_model")
    base_url = os.environ.pop("openai_api_url")
    api_key = os.environ.pop("openai_api_key")

    trace = Trace()
    llm_metrics = []
    agent = create_deep_agent(
        model=ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key=api_key,
            temperature=args.temperature,
            timeout=args.timeout,
            callbacks=[UsageCallback(
                sink=llm_metrics.append,
                base_fields={"stage": "dynamic", "operation": "tester_llm"},
            )],
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
        json.dump({"execution": trace.records, "llm_output": str(llm_output),
                   "llm_metrics": llm_metrics},
                  fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
