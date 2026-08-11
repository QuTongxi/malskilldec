"""Image and container lifecycle.

One image for the whole run; one container per skill, because a container that
has already been through one skill is no longer a clean machine.  Claims of the
same skill share it -- that is the point of holding it open.
"""

import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import dotenv

dotenv.load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BUILD = Path(__file__).resolve().parent / "build"
RUN_TEST = Path(__file__).resolve().parent / "run_test.py"
IMAGE = "malskilldet-dynamic:v1"
ENV_KEYS = ("openai_model", "openai_api_url", "openai_api_key")


def env_flags():
    """`docker exec` flags carrying the harness credentials, and only those."""
    return sum((["-e", "%s=%s" % (key, os.environ[key])] for key in ENV_KEYS), [])

NAME_LINE = re.compile(r"^name:.*$", re.MULTILINE)


def docker(*args, timeout=120, check=True):
    proc = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError("docker %s failed: %s" % (args[0], (proc.stderr or proc.stdout).strip()))
    return proc.stdout.strip()


def ensure_image():
    """Build the image once; later runs reuse it."""
    if not docker("images", "-q", IMAGE):
        docker("build", "-t", IMAGE, str(BUILD), timeout=1800)
    return IMAGE


def slug(name):
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def stage(skill_path, into):
    """Copy the skill out under the directory name the agent runtime requires.

    A skill is only loaded when its frontmatter `name` equals its directory name
    and is lowercase-alphanumeric; most real skills fail one or the other, so
    both are normalised to the same slug here.  Nothing but that one line of
    frontmatter is touched.
    """
    source = Path(skill_path)
    marker = source / "SKILL.md"
    if not marker.exists():
        marker = source / "skill.md"
    text = marker.read_text(encoding="utf-8", errors="replace")

    declared = re.search(r"^name:\s*(.+?)\s*$", text, re.MULTILINE)
    name = slug(declared.group(1)) if declared else slug(source.name)

    destination = Path(into) / name
    shutil.copytree(source, destination)
    (destination / marker.name).unlink()
    (destination / "SKILL.md").write_text(
        NAME_LINE.sub("name: %s" % name, text, count=1), encoding="utf-8")
    return name


class Container:
    """A running container with exactly one skill installed."""

    def __init__(self, skill_path):
        self.name = "malskilldet-%s" % uuid.uuid4().hex[:10]
        # The credentials are deliberately not set here.  A container-wide `-e`
        # puts the operator's API key in front of every shell the skill under
        # test can open; they travel on the one `docker exec` that starts the
        # tester agent instead, and that process drops them before it hands a
        # shell to the agent.  See `env_flags` and `run_test.main`.
        self.id = docker("run", "-d", "--name", self.name, IMAGE, "sleep", "infinity")
        with tempfile.TemporaryDirectory(prefix="malskilldet-stage-") as staging:
            self.skill = stage(skill_path, staging)
            docker("cp", "%s/." % staging, "%s:/workspace/skills/" % self.id)
        docker("cp", str(RUN_TEST), "%s:/opt/tester/run_test.py" % self.id)

    def close(self):
        docker("rm", "-f", self.id, check=False)
