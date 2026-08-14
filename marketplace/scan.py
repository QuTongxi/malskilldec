"""Scan the sample: static on everything, the court on what scores highest.

    uv run python marketplace/scan.py --dataset marketplace/real_dataset_8k \
        --out marketplace/scan --min-score 60 --budget 600

Three things this does that `court.py --evidence <dir>` on its own does not, all
of them consequences of the run being long and paid for by the token:

* **Order.**  Skills are tried hardest-first, by the score of their strongest
  claim.  A run that stops early then stops having already judged the skills most
  likely to be malicious, instead of the ones whose filename sorted first.
* **Resume.**  A skill whose report is already on disk is never tried twice, so
  the run can be killed and restarted, and a crash costs one skill.
* **A floor under the account.**  When the endpoint answers "insufficient
  balance" the run stops immediately rather than converting the rest of the
  queue into error reports at one failed request each.

The claim-score cut is what makes the court affordable at all.  On
`eval_runs/run_100x100`, being accused of *something* is nearly no evidence --
78% of the benign skills are -- while the strongest claim's score separates:

    >= 60   88% of the malicious, 20% of the benign
    >= 80   74% of the malicious,  7% of the benign
    >= 100  69% of the malicious,  3% of the benign

Everything the court sees is built by `ablation/static_to_evidence.py`, unmodified
and at its defaults (400 characters of context, 5 anchors per claim) -- the
operating point at which the 95.45% precision this pipeline is quoted at was
actually measured.
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# `static/` and `dynamic/` both hold a `pipeline.py`, so neither directory goes
# on the path under that name -- the static one is loaded by file below.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "final_v2"))
sys.path.insert(0, str(ROOT / "dynamic"))
sys.path.insert(0, str(ROOT / "ablation"))


def load_static_pipeline():
    """`static/pipeline.py`, under a name that cannot collide with the dynamic one."""
    import importlib.util
    sys.path.insert(0, str(ROOT / "static"))          # its own `matchers`/`workers`
    spec = importlib.util.spec_from_file_location(
        "static_pipeline", str(ROOT / "static" / "pipeline.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Telling "the account is empty" from "you are going too fast" is the whole
# game here, and DashScope makes it hard: throughput throttling comes back as
# `429 insufficient_quota` with a message about *billing details* that links to
# the token-limit page.  Matching that string as arrearage stopped a 1326-skill
# run after one skill while the account was fine.
#
# So the strings only propose, and a probe disposes: on a suspected failure the
# run sends one five-token request, and if that succeeds the account can pay and
# the failure was throughput.
ARREARS = re.compile(
    r"arrearage|欠费|余额不足|账户.{0,6}(停机|冻结)|"
    r"account.{0,30}(in arrears|suspended|expired|frozen|deactivated)", re.I)
THROTTLED = re.compile(
    r"rate.?limit|429|insufficient[_ ]?quota|throttl|too many requests|"
    r"requests? per (minute|second)|tpm|rpm", re.I)

# qwen3-max on DashScope, yuan per million tokens at the shortest-context tier.
#
# PRICE_CACHED is the one that decides whether this estimate is usable at all.
# The forensics loop re-sends its whole conversation every round, so the prefix
# is identical up to sixty times and the endpoint serves nearly all of it from
# cache -- a measured 4352 of 4424 input tokens on the second call of a repeated
# prefix.  Billing those at the full input rate overstated a 139-skill run as
# ~600 CNY when it actually cost ~100, and the run stopped itself at a sixth of
# the real budget.  Cache reads are counted separately now.
PRICE_IN, PRICE_OUT, PRICE_CACHED = 12.0, 36.0, 1.2


def account_can_pay():
    """One five-token request.  True if the endpoint still serves this key.

    This is the arbiter, not the error string: a 429 that this survives was
    throughput, and a 429 that this reproduces is the account.
    """
    import llm
    try:
        model = llm.original_chat_model(temperature=0.0, timeout=60)
        model.invoke("hi")
        return True, ""
    except Exception as error:
        return False, "%s: %s" % (type(error).__name__, error)


class Meter:
    """Token usage across every stage and every thread of the run."""

    def __init__(self):
        self.lock = threading.Lock()
        self.tokens_in = 0
        self.tokens_out = 0
        self.tokens_cached = 0
        self.calls = 0

    def add(self, usage):
        with self.lock:
            self.tokens_in += usage.get("input_tokens", 0) or 0
            self.tokens_out += usage.get("output_tokens", 0) or 0
            self.tokens_cached += usage.get("cached_tokens", 0) or 0
            self.calls += 1

    def yuan(self):
        fresh = max(0, self.tokens_in - self.tokens_cached)
        return (fresh * PRICE_IN + self.tokens_cached * PRICE_CACHED
                + self.tokens_out * PRICE_OUT) / 1e6

    def snapshot(self):
        with self.lock:
            return {"calls": self.calls, "input_tokens": self.tokens_in,
                    "cached_input_tokens": self.tokens_cached,
                    "output_tokens": self.tokens_out,
                    "cache_hit_rate": round(self.tokens_cached / max(1, self.tokens_in), 3),
                    "yuan_estimate": round(self.yuan(), 2)}


def install_meter(meter):
    """Count tokens without touching `final_v2/`.

    `court.py` takes no callback and builds its model through `dynamic/llm.py`,
    so the meter is attached where the model is made: the factory is wrapped once
    here, and every stage that asks for a model gets one that reports back.
    """
    import llm
    from langchain_core.callbacks import BaseCallbackHandler

    class Handler(BaseCallbackHandler):
        def on_llm_end(self, response, **kwargs):
            # Two places, because which one is populated depends on who called:
            # a bare ChatOpenAI fills `llm_output["token_usage"]`, while the
            # agent loop `create_agent` builds hands back generations whose
            # message carries `usage_metadata` and leaves llm_output empty.
            usage = (response.llm_output or {}).get("token_usage") or {}
            if usage:
                details = usage.get("prompt_tokens_details") or {}
                meter.add({"input_tokens": usage.get("prompt_tokens"),
                           "output_tokens": usage.get("completion_tokens"),
                           "cached_tokens": details.get("cached_tokens")})
                return
            for batch in response.generations or []:
                for generation in batch:
                    message = getattr(generation, "message", None)
                    metadata = getattr(message, "usage_metadata", None) or {}
                    if metadata:
                        # langchain renames DashScope's `cached_tokens` on the way through
                        details = metadata.get("input_token_details") or {}
                        meter.add({"input_tokens": metadata.get("input_tokens"),
                                   "output_tokens": metadata.get("output_tokens"),
                                   "cached_tokens": details.get("cache_read")})

    original = llm.chat_model
    llm.original_chat_model = original          # the probe needs an unmetered one

    def metered(*args, **kwargs):
        model = original(*args, **kwargs)
        # `.with_config(callbacks=...)` wraps the model in a RunnableBinding, and
        # `create_agent` calls `bind_tools` on what it is given -- which rebuilds
        # from the underlying model and drops the wrapper, so the first run
        # metered exactly nothing across seven skills.  `callbacks` is a field on
        # the model itself, and fields survive `bind_tools`.
        model.callbacks = [Handler()]
        return model

    llm.chat_model = metered


def run_static(dataset, out, use_codeql):
    """Step one, on every skill in the sample.  Cached: it is slow and free."""
    report_path = out / "static.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        print("static: reusing %s (%d skills)" % (report_path, len(report["skills"])))
        return report

    pipeline = load_static_pipeline()
    print("static: scanning %s ..." % dataset)
    started = time.time()
    report = pipeline.scan(str(dataset), use_codeql)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("static: %d skills in %.0f s -> %s"
          % (len(report["skills"]), time.time() - started, report_path))
    return report


def rank(report, min_score):
    """Accused skills, hardest first, above the cut."""
    ranked = []
    for skill in report["skills"]:
        if not skill["claims"]:
            continue
        top = max(claim["score"] for claim in skill["claims"])
        if top >= min_score:
            ranked.append((top, skill))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["skill"]))
    return ranked


def build_evidence(ranked, directory, context_chars, max_anchors):
    """Render each accused skill as the file the dynamic stage would have written.

    `ablation/static_to_evidence.py` is imported rather than copied, so the
    notice the court reads -- that no dynamic validation ran, and that a blank
    record section is not an observation -- is the same text the ablation used.
    """
    import static_to_evidence as bridge

    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for _score, skill in ranked:
        path = directory / ("%s.json" % skill["skill"].replace("/", "-"))
        if not path.exists():
            path.write_text(json.dumps(bridge.convert(skill, context_chars, max_anchors),
                                       ensure_ascii=False, indent=1), encoding="utf-8")
        paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="marketplace/real_dataset_8k")
    parser.add_argument("--out", default="marketplace/scan")
    parser.add_argument("--min-score", type=int, default=60,
                        help="try only skills whose strongest claim scores at least this")
    parser.add_argument("--budget", type=float, default=None,
                        help="stop when the estimated spend in yuan passes this. Off by "
                             "default: the estimate is an estimate, and the first run of "
                             "this priced cache reads as fresh input, overstated a 100 CNY "
                             "run as 600 and stopped itself at a sixth of the budget. The "
                             "account refusing to serve is the honest stopping condition")
    parser.add_argument("--reports", choices=("malicious", "all"), default="malicious",
                        help="write a report file for convictions only, or for every skill")
    # Eight skills at once is three concurrent stages each, and the prompts are
    # long enough that this alone exceeded the endpoint's tokens-per-minute.
    parser.add_argument("--max-parallel", type=int, default=4)
    parser.add_argument("--retries", type=int, default=5,
                        help="attempts per skill when the endpoint is throttling")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--recursive", type=int, default=60)
    parser.add_argument("--context-chars", type=int, default=400)
    parser.add_argument("--max-anchors", type=int, default=5)
    parser.add_argument("--disable-codeql", action="store_true")
    parser.add_argument("--static-only", action="store_true",
                        help="scan and rank, then stop before spending anything")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    reports = out / "court"
    reports.mkdir(exist_ok=True)

    report = run_static(Path(args.dataset), out, not args.disable_codeql)
    ranked = rank(report, args.min_score)
    accused = sum(1 for s in report["skills"] if s["claims"])
    print("\n%d skills scanned, %d accused of something, %d score >= %d"
          % (len(report["skills"]), accused, len(ranked), args.min_score))
    if ranked:
        print("score range of the queue: %d (highest) .. %d (lowest)"
              % (ranked[0][0], ranked[-1][0]))
    if args.static_only or not ranked:
        return

    evidence = build_evidence(ranked, out / "evidence", args.context_chars, args.max_anchors)

    meter = Meter()
    install_meter(meter)
    import court

    results_path = out / "results.json"
    results = (json.loads(results_path.read_text(encoding="utf-8"))
               if results_path.exists() else [])
    # Resume keys off `results.json`, not off the report files.  Only MALICIOUS
    # skills get a report written, so a skill tried and acquitted leaves no `.md`
    # behind -- keying off the directory would buy every acquittal twice.
    done = {result["skill"] for result in results}
    print("%d skills already tried, %d to go\n" % (len(done), len(ranked) - len(done)))

    stop = threading.Event()
    lock = threading.Lock()
    started = time.time()

    def try_one(item):
        score, skill, path = item
        if stop.is_set():
            return None
        units = court.load_evidence(path)
        if not units:
            return None

        result, text = None, ""
        for attempt in range(args.retries):
            if stop.is_set():
                return None
            try:
                result = court.run_court(units[0], args.timeout, args.recursive)
                break
            except Exception as error:
                text = "%s: %s" % (type(error).__name__, error)
                if ARREARS.search(text):
                    stop.set()
                    print("\n!! the account is in arrears:\n   %s" % text[:300], flush=True)
                    return None
                if THROTTLED.search(text):
                    if attempt == args.retries - 1:
                        # Out of patience: ask the account directly whether this
                        # was throughput or money, and only stop for money.
                        alive, why = account_can_pay()
                        if not alive:
                            stop.set()
                            print("\n!! the endpoint refuses a five-token probe, so this is "
                                  "the account and not the pace:\n   %s" % why[:300], flush=True)
                            return None
                        break
                    time.sleep(min(180, 20 * (attempt + 1)))
                    continue
                break                                  # a real failure of this skill
        if result is None:
            result = {"skill": skill["skill"], "path": skill["path"], "claim": None,
                      "verdict": "error", "judge_verdict": None, "reason": text,
                      "forensics": None, "indictment": None, "judgement": None}
        result["top_score"] = score
        # Only convictions get a report file: an acquittal is not audited by
        # hand, and its forensics and indictment survive in `results.json`
        # anyway.  At a 38% conviction rate this is also most of the writing.
        if args.reports == "all" or result["verdict"] == "MALICIOUS":
            court.write_report(reports, result)
        with lock:
            results.append(result)
            results_path.write_text(json.dumps(results, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
            # Written every skill, not just at the end: a run that is killed
            # rather than finished should still be able to say what it spent.
            (out / "usage.json").write_text(json.dumps(meter.snapshot(), indent=1),
                                            encoding="utf-8")
            spent = meter.yuan()
            print("%-58s %-9s score=%-4d  %6.2f CNY  %d/%d"
                  % (result["skill"][:58], result["verdict"], score, spent,
                     len(results), len(ranked)), flush=True)
            if args.budget and spent >= args.budget:
                stop.set()
                print("\n!! estimated spend %.2f CNY reached the %.2f budget" % (spent, args.budget))
        return result

    queue = [(score, skill, path) for (score, skill), path in zip(ranked, evidence)
             if ("%s" % skill["skill"].replace("/", "-")) not in done]

    # Batched rather than one big map, so `stop` is honoured within a batch or
    # two instead of after the whole queue has been handed to the pool.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(args.max_parallel) as pool:
        for start in range(0, len(queue), args.max_parallel * 4):
            if stop.is_set():
                break
            list(pool.map(try_one, queue[start:start + args.max_parallel * 4]))

    verdicts = {}
    for result in results:
        verdicts[result["verdict"]] = verdicts.get(result["verdict"], 0) + 1
    usage = meter.snapshot()
    (out / "usage.json").write_text(json.dumps(usage, indent=1), encoding="utf-8")
    print("\n%s in %.0f min" % (verdicts, (time.time() - started) / 60))
    print("tokens: %(input_tokens)d in, %(output_tokens)d out over %(calls)d calls"
          " -- about %(yuan_estimate)s CNY" % usage)
    print("reports in %s, results in %s" % (reports, results_path))
    if stop.is_set():
        print("STOPPED EARLY: %d of %d skills were tried" % (len(results), len(ranked)))


if __name__ == "__main__":
    main()
