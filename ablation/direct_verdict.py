#!/usr/bin/env python3
"""Ablation: replace the three-stage Final Court with one verdict LLM.

The expensive Qwen3-max dynamic run is reused verbatim.  One skill is one
judgement unit: all of its confirmed claims are rendered with the same bounded
evidence renderer used by ``final_v2/court.py``, then sent to a single model
call with no tools.  The old per-claim ``judgement`` fields are deliberately
not loaded or rendered.

Example:

    .venv/bin/python ablation/direct_verdict.py \
        --evidence eval_runs/run_100x100/dynamic \
        --out eval_runs/ablation_no_final_court \
        --max-parallel 10
"""

import argparse
import collections
import csv
import json
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "final_v2"))
sys.path.insert(0, str(ROOT / "dynamic"))

import court as evidence_court  # noqa: E402
from llm import chat_model  # noqa: E402

DEFAULT_PROMPT = Path(__file__).with_name("prompts") / "direct_verdict.md"
PRINT = threading.Lock()
SEED, TOP_P = 42, 0.01


class DirectDecision(BaseModel):
    verdict: Literal["MALICIOUS", "BENIGN"] = Field(
        description="One skill-level verdict: exactly MALICIOUS or BENIGN")
    report: str = Field(
        description="A concise Markdown report grounded in the supplied evidence")


def log(message):
    with PRINT:
        print(message, flush=True)


def safe_name(skill):
    return skill.replace("/", "--")


def decide(units, system_prompt, timeout=300, recursive=10):
    """Return one direct verdict over all confirmed claims of one skill."""
    evidence = evidence_court.render_evidence(units)
    agent = create_agent(
        chat_model(temperature=0.0, timeout=timeout, seed=SEED, top_p=TOP_P),
        tools=[],
        system_prompt=system_prompt,
        response_format=ToolStrategy(DirectDecision),
    )
    started = time.monotonic()
    state = agent.invoke(
        {"messages": [HumanMessage(content=(
            "请直接判断下面这个 Skill。输入只包含动态验证材料；不要假设你能读取 Skill "
            "目录，也不要假设有其他审判阶段会补充信息。\n\n" + evidence))]},
        config={"recursion_limit": recursive},
    )
    elapsed = time.monotonic() - started
    decision = state["structured_response"]
    return {
        "verdict": decision.verdict,
        "report": decision.report.strip(),
        "input_chars": len(evidence),
        "elapsed_seconds": round(elapsed, 3),
    }


def atomic_json(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def write_report(path, result):
    text = """# {skill}

- ablation: **single direct-verdict LLM; no Final Court**
- verdict: **{verdict}**
- claims: {claim}
- model: {model}
- input characters: {input_chars}
- elapsed seconds: {elapsed_seconds}

---

{report}
""".format(**result)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def load_labels(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    labels = {row["relative_path"]: row["label"] for row in rows}
    if len(labels) != len(rows):
        raise ValueError("duplicate relative_path in %s" % path)
    return labels


def score(results, labels):
    """Score like the paper: an absent/error result defaults to BENIGN."""
    seen = {row["skill"]: row["verdict"] for row in results
            if row.get("verdict") in ("MALICIOUS", "BENIGN")}
    matrix = collections.Counter()
    wrong = {"FP": [], "FN": []}
    for skill, truth in sorted(labels.items()):
        predicted = seen.get(skill, "BENIGN")
        matrix[(truth, predicted)] += 1
        if truth == "benign" and predicted == "MALICIOUS":
            wrong["FP"].append(skill)
        elif truth == "malicious" and predicted == "BENIGN":
            wrong["FN"].append(skill)

    tp = matrix[("malicious", "MALICIOUS")]
    fp = matrix[("benign", "MALICIOUS")]
    tn = matrix[("benign", "BENIGN")]
    fn = matrix[("malicious", "BENIGN")]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "wrong": wrong,
    }


def timing(results):
    values = sorted(row.get("elapsed_seconds", 0) for row in results
                    if row.get("verdict") in ("MALICIOUS", "BENIGN"))
    if not values:
        return {}
    p90_index = min(len(values) - 1, max(0, int(0.9 * len(values)) - 1))
    return {
        "completed_calls": len(values),
        "sum_call_seconds": round(sum(values), 3),
        "median_call_seconds": round(statistics.median(values), 3),
        "p90_call_seconds": round(values[p90_index], 3),
        "max_call_seconds": round(max(values), 3),
    }


def try_groups(groups, out, prompt, model, timeout, recursive, max_parallel,
               force=False):
    out = Path(out)
    records = out / "records"
    reports = out / "reports"
    records.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    prior, pending = {}, []
    for units in groups:
        skill = units[0]["skill"]
        path = records / (safe_name(skill) + ".json")
        if path.exists() and not force:
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
                if document.get("verdict") in ("MALICIOUS", "BENIGN"):
                    prior[skill] = document
                    continue
            except Exception:
                pass
        pending.append(units)

    log("%d confirmed skill(s): %d cached, %d pending, %d at a time" %
        (len(groups), len(prior), len(pending), max_parallel))

    def worker(units):
        head = units[0]
        skill = head["skill"]
        claim_types = sorted({(unit.get("claim") or {}).get("type", "unknown")
                              for unit in units})
        base = {
            "skill": skill,
            "path": head.get("path"),
            "claim": "+".join(claim_types),
            "model": model,
            "ablation": "single direct-verdict LLM; no Final Court",
        }
        try:
            result = base | decide(units, prompt, timeout, recursive)
            result["reason"] = "the direct verdict agent returned %s" % result["verdict"]
        except Exception as error:
            result = base | {
                "verdict": "error",
                "reason": "%s: %s" % (type(error).__name__, error),
                "report": "",
                "input_chars": len(evidence_court.render_evidence(units)),
                "elapsed_seconds": 0,
            }
        atomic_json(records / (safe_name(skill) + ".json"), result)
        write_report(reports / (safe_name(skill) + ".md"), result)
        log("%-55s %-10s %s" %
            (skill, result["verdict"], result["reason"][:70]))
        return result

    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        fresh = list(pool.map(worker, pending))

    by_skill = prior | {row["skill"]: row for row in fresh}
    return [by_skill[units[0]["skill"]] for units in groups]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True,
                        help="directory of dynamic result JSON files")
    parser.add_argument("--out", default="eval_runs/ablation_no_final_court")
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT))
    parser.add_argument("--labels", default=str(ROOT / "artifact/labels.csv"))
    parser.add_argument("--expected-model", default="qwen3-max")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--recursive", type=int, default=10)
    parser.add_argument("--max-parallel", type=int, default=10)
    parser.add_argument("--skills", nargs="*", help="only these full skill IDs")
    parser.add_argument("--limit", type=int, help="first N selected skills")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate and print input sizes without calling the LLM")
    args = parser.parse_args()

    groups = evidence_court.load_evidence(args.evidence)
    if args.skills:
        wanted = set(args.skills)
        groups = [group for group in groups if group[0]["skill"] in wanted]
        missing = wanted - {group[0]["skill"] for group in groups}
        if missing:
            raise SystemExit("no confirmed evidence for: %s" % ", ".join(sorted(missing)))
    if args.limit is not None:
        groups = groups[:args.limit]
    if not groups:
        raise SystemExit("no confirmed skill groups selected")

    prompt = Path(args.prompt).read_text(encoding="utf-8").strip()
    model = os.environ.get("openai_model", "")
    if model != args.expected_model:
        raise SystemExit("expected model %r, but .env selects %r" %
                         (args.expected_model, model))

    sizes = [len(evidence_court.render_evidence(group)) for group in groups]
    print("model=%s; skills=%d; confirmed_claims=%d; input_chars min/median/max=%d/%d/%d" %
          (model, len(groups), sum(len(group) for group in groups), min(sizes),
           int(statistics.median(sizes)), max(sizes)))
    if args.dry_run:
        return

    wall_started = time.monotonic()
    results = try_groups(groups, args.out, prompt, model, args.timeout,
                         args.recursive, args.max_parallel, args.force)
    wall_seconds = round(time.monotonic() - wall_started, 3)
    out = Path(args.out)
    atomic_json(out / "court.json", results)

    metrics = score(results, load_labels(args.labels))
    summary = {
        "ablation": "single direct-verdict LLM; no Final Court",
        "model": model,
        "evidence": str(Path(args.evidence)),
        "skills_with_confirmed_evidence": len(groups),
        "confirmed_claims": sum(len(group) for group in groups),
        "max_parallel": args.max_parallel,
        "wall_seconds": wall_seconds,
        "verdict_counts": dict(collections.Counter(row["verdict"] for row in results)),
        "timing": timing(results),
        "metrics": metrics,
    }
    atomic_json(out / "summary.json", summary)

    print("\nTP/FP/TN/FN = {tp}/{fp}/{tn}/{fn}".format(**metrics))
    print("precision=%.4f recall=%.4f F1=%.4f" %
          (metrics["precision"], metrics["recall"], metrics["f1"]))
    print("wall=%.1fs; results written to %s" % (wall_seconds, out))


if __name__ == "__main__":
    main()
