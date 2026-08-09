"""The two finding producers: regex matching and CodeQL."""

import json
import os
import subprocess
import sys

import matchers

CONTEXT_RADIUS = 200          # >= 300 chars of context around every match
MAX_FILE_BYTES = 512 * 1024   # skip generated / vendored blobs
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
              ".gz", ".tgz", ".7z", ".rar", ".woff", ".woff2", ".ttf", ".otf",
              ".mp3", ".mp4", ".wav", ".so", ".dylib", ".dll", ".exe", ".bin"}

CODEQL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codeql")


# --------------------------------------------------------------------------
# Regex worker
# --------------------------------------------------------------------------

def iter_files(skill_dir):
    for root, dirs, names in os.walk(skill_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(names):
            path = os.path.join(root, name)
            if os.path.splitext(name)[1].lower() in BINARY_EXT:
                continue
            if os.path.getsize(path) > MAX_FILE_BYTES:
                continue
            yield path


def line_column(text, offset):
    line = text.count("\n", 0, offset) + 1
    column = offset - (text.rfind("\n", 0, offset) + 1) + 1
    return line, column


def context_of(text, start, end):
    lo = max(0, start - CONTEXT_RADIUS)
    hi = min(len(text), end + CONTEXT_RADIUS)
    if hi - lo < 300:                       # near a file edge: widen the other side
        lo = max(0, hi - 300)
        hi = min(len(text), lo + 300)
    return text[lo:hi]


def regex_scan(skill):
    """Run every compiled pattern over every text file of one skill."""
    findings = []
    for path in iter_files(skill["path"]):
        text = open(path, encoding="utf-8", errors="replace").read()
        rel = os.path.relpath(path, skill["path"])
        for rule_id, group, level, description, pattern in matchers.COMPILED:
            for match in pattern.finditer(text):
                line, column = line_column(text, match.start())
                findings.append({
                    "metadata": {
                        "id": "%s:%s:%s:%d" % (skill["name"], rule_id, rel, line),
                        "source": "regex",
                        "rule_id": rule_id,
                        "description": description,
                        "skill": skill["name"],
                        "skill_path": skill["path"],
                    },
                    "matched_text": match.group(0)[:400],
                    "context": context_of(text, match.start(), match.end()),
                    "location": {"file": rel, "line": line, "column": column},
                    "level": level,
                    "group": group,
                })
    return findings


# --------------------------------------------------------------------------
# CodeQL worker
# --------------------------------------------------------------------------

def codeql_available():
    return os.path.exists(os.path.join(CODEQL_DIR, "codeql", "codeql"))


def run_codeql(root, workdir):
    """Build one database per language over the whole input tree and analyse it.

    Returns the list of SARIF files that were produced.
    """
    script = os.path.join(CODEQL_DIR, "run.sh")
    proc = subprocess.run([script, os.path.abspath(root), os.path.abspath(workdir)],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    sys.stderr.write(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError("codeql run.sh failed with exit code %d" % proc.returncode)
    return [os.path.join(workdir, n) for n in sorted(os.listdir(workdir))
            if n.endswith(".sarif")]


def source_line(path, line):
    """The source line a CodeQL result points at; SARIF carries no snippet."""
    return open(path, encoding="utf-8", errors="replace").read().splitlines()[line - 1].strip()[:400]


def flow_context(result, skill_path, root):
    """Render the source -> sink data flow of a CodeQL result as the context."""
    lines = [result["message"]["text"].splitlines()[0]]
    flows = result.get("codeFlows", [])
    if flows:
        lines.append("")
        lines.append("data flow:")
        for i, step in enumerate(flows[0]["threadFlows"][0]["locations"], 1):
            location = step["location"]
            physical = location["physicalLocation"]
            path = os.path.normpath(os.path.join(root, physical["artifactLocation"]["uri"]))
            lines.append("  %d. %s:%s  %s" % (
                i, os.path.relpath(path, skill_path),
                physical["region"].get("startLine", "?"),
                location.get("message", {}).get("text", "").strip()))
    return "\n".join(lines)


def codeql_findings(sarif_paths, skill_of_path, root):
    """Turn SARIF results into findings, attributed to the owning skill."""
    per_skill = {}
    for sarif_path in sarif_paths:
        sarif = json.load(open(sarif_path, encoding="utf-8"))
        for run in sarif["runs"]:
            titles = {rule["id"]: rule["shortDescription"]["text"]
                      for rule in run["tool"]["driver"]["rules"]}
            for result in run["results"]:
                rule_id = result["ruleId"]
                if rule_id not in matchers.CODEQL_RULES:
                    continue
                group, level = matchers.CODEQL_RULES[rule_id]
                physical = result["locations"][0]["physicalLocation"]
                path = os.path.normpath(os.path.join(root, physical["artifactLocation"]["uri"]))
                skill = skill_of_path(path)
                if skill is None:                       # file outside every skill
                    continue
                region = physical["region"]
                line = region.get("startLine", 1)
                rel = os.path.relpath(path, skill["path"])
                per_skill.setdefault(skill["name"], []).append({
                    "metadata": {
                        "id": "%s:%s:%s:%d" % (skill["name"], rule_id, rel, line),
                        "source": "codeql",
                        "rule_id": rule_id,
                        "description": titles[rule_id],
                        "skill": skill["name"],
                        "skill_path": skill["path"],
                    },
                    "matched_text": source_line(path, line),
                    "context": flow_context(result, skill["path"], root),
                    "location": {"file": rel, "line": line,
                                 "column": region.get("startColumn", 1)},
                    "level": level,
                    "group": group,
                })
    return per_skill
