"""Runs one prompt against one skill and returns what the machine saw.

A `Tester` is bound to a container for the lifetime of one skill.  Every run
takes the three things the experiment varies -- timeout, recursion budget,
prompt -- and returns the four evidence channels plus metadata.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tester.build_docker import docker, env_flags
from tester.monitor import filesystem, network

PROMPT_FILE = "/tmp/prompt.txt"
RESULT_FILE = "/tmp/tester_result.json"


class Tester:
    def __init__(self, container):
        self.container = container
        self.round = 0

    def run(self, timeout, recursive, prompt, temperature=0.0):
        self.round += 1
        cid = self.container.id

        docker("exec", cid, "rm", "-f", PROMPT_FILE, RESULT_FILE, check=False)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8") as handle:
            handle.write(prompt)
            handle.flush()
            docker("cp", handle.name, "%s:%s" % (cid, PROMPT_FILE))

        provider = network.start(cid)
        before = filesystem.snapshot(cid)

        # Worst case the agent spends its whole recursion budget waiting on the
        # model; past that it is wedged and the evidence is whatever it produced.
        # The credentials ride on this one exec, not on the container, so no
        # other shell in there ever sees them.
        agent = subprocess.run(
            ["docker", "exec", *env_flags(), cid, "python", "/opt/tester/run_test.py",
             "--prompt-file", PROMPT_FILE, "--timeout", str(timeout),
             "--recursive", str(recursive), "--temperature", str(temperature),
             "--out", RESULT_FILE],
            capture_output=True, text=True, timeout=timeout * recursive + 300)

        after = filesystem.snapshot(cid)
        captured = network.stop(cid)

        written = docker("exec", cid, "cat", RESULT_FILE, check=False)
        result = json.loads(written) if written else {
            "execution": [],
            "llm_output": "<the tester agent produced nothing: %s>"
                          % (agent.stderr or agent.stdout).strip()[-1000:],
        }

        return {
            "filesystem": filesystem.diff(before, after),
            "execution": result["execution"],
            "llm_output": result["llm_output"],
            "network": network.parse(captured, provider),
            "llm_metrics": result.get("llm_metrics", []),
            "metadata": {"skill": self.container.skill, "container": self.container.name,
                         "round": self.round, "timeout": timeout, "recursive": recursive,
                         "temperature": temperature},
        }
