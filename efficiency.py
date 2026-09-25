"""Thread-safe timing and LLM-usage metrics for experiment runs.

The experiment has two kinds of time that must not be conflated:

* corpus wall clock (the time a user waits at the configured concurrency), and
* per-skill/per-claim latency (overlapping work when skills run in parallel).

Spans record both.  ``UsageCallback`` records every provider request made by a
LangChain model, including requests caused by an agent's tool loop.  No prompt,
credential, response text, or provider URL is written to the metrics file.
"""

from __future__ import annotations

import json
import math
import statistics
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from langchain_core.callbacks import BaseCallbackHandler


_LOCK = threading.Lock()
_PATH: Path | None = None
_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("efficiency_context", default={})

# Alibaba Cloud list prices published for the Beijing deployment.  The profile
# name carries the documentation date so a future price change cannot silently
# rewrite an old experiment.  K means 1,000 tokens in the provider's table.
PRICING_PROFILES = {
    "qwen3-max-cn-beijing-2026-07-24": {
        "currency": "USD",
        "region": "China (Beijing)",
        "model": "qwen3-max / qwen3-max-2026-01-23",
        "source": "https://www.alibabacloud.com/help/en/model-studio/model-qwen3-max",
        "tiers": [
            {"max_input_tokens": 32_000, "input": 0.359, "output": 1.434,
             "cached_input": 0.072},
            {"max_input_tokens": 128_000, "input": 0.574, "output": 2.294,
             "cached_input": 0.115},
            {"max_input_tokens": 256_000, "input": 1.004, "output": 4.014,
             "cached_input": 0.201},
        ],
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def configure(path, metadata=None, reset=True):
    """Select the JSONL sink and start a run.

    The sink is process-global and protected by a lock because dynamic and
    court workers use thread pools.  A full run configures it once in
    ``main.py``; standalone stage entry points configure their own sink.
    """
    global _PATH
    _PATH = Path(path)
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    if reset:
        _PATH.write_text("", encoding="utf-8")
    record("run_start", metadata=metadata or {})
    return _PATH


def enabled():
    return _PATH is not None


def record(event, **fields):
    """Append one small, prompt-free event to the configured JSONL file."""
    if _PATH is None:
        return
    document = {"event": event, "timestamp": utc_now(), **fields}
    line = json.dumps(document, ensure_ascii=False, sort_keys=True)
    with _LOCK:
        with _PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


@contextmanager
def scope(**fields):
    """Attach stage/skill/claim/round fields to nested provider calls."""
    token = _CONTEXT.set({**_CONTEXT.get(), **{k: v for k, v in fields.items()
                                               if v is not None}})
    try:
        yield
    finally:
        _CONTEXT.reset(token)


@contextmanager
def span(stage, operation, **fields):
    """Measure a wall-clock operation, recording failures without swallowing them."""
    started = time.monotonic()
    started_at = utc_now()
    status, error = "ok", None
    try:
        with scope(stage=stage, operation=operation, **fields):
            yield
    except BaseException as exc:
        status = "error"
        error = "%s: %s" % (type(exc).__name__, exc)
        raise
    finally:
        record(
            "span",
            stage=stage,
            operation=operation,
            started_at=started_at,
            duration_seconds=round(time.monotonic() - started, 6),
            status=status,
            error=error,
            **{k: v for k, v in fields.items() if v is not None},
        )


def _message_chars(messages):
    total = 0
    for batch in messages or []:
        for message in batch if isinstance(batch, (list, tuple)) else [batch]:
            content = getattr(message, "content", message)
            total += len(str(content))
    return total


def _usage(response):
    """Return normalized token usage from current and older LangChain shapes."""
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
              "cached_input_tokens": 0}
    found = False
    for generation_list in getattr(response, "generations", []) or []:
        for generation in generation_list:
            message = getattr(generation, "message", None)
            usage = getattr(message, "usage_metadata", None) or {}
            if usage:
                found = True
                totals["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
                totals["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
                totals["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
                details = usage.get("input_token_details") or {}
                totals["cached_input_tokens"] += int(
                    details.get("cache_read", details.get("cached_tokens", 0)) or 0)
                continue

            metadata = getattr(message, "response_metadata", None) or {}
            usage = metadata.get("token_usage") or metadata.get("usage") or {}
            if usage:
                found = True
                input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
                output_tokens = usage.get(
                    "completion_tokens", usage.get("output_tokens", 0)) or 0
                totals["input_tokens"] += int(input_tokens)
                totals["output_tokens"] += int(output_tokens)
                totals["total_tokens"] += int(
                    usage.get("total_tokens", input_tokens + output_tokens) or 0)
                details = usage.get("prompt_tokens_details") or {}
                totals["cached_input_tokens"] += int(details.get("cached_tokens", 0) or 0)

    if not found:
        llm_output = getattr(response, "llm_output", None) or {}
        usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
        if usage:
            input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
            output_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
            totals.update({
                "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens),
                "total_tokens": int(usage.get(
                    "total_tokens", input_tokens + output_tokens) or 0),
                "cached_input_tokens": int(
                    (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0),
            })
    if not totals["total_tokens"]:
        totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]
    return totals


class UsageCallback(BaseCallbackHandler):
    """Collect one event per actual provider request.

    ``sink`` defaults to the process JSONL recorder.  The tester container uses
    an in-memory list and returns those events with its evidence so the host can
    merge them into the same experiment log.
    """

    def __init__(self, sink: Callable[[dict[str, Any]], None] | None = None,
                 base_fields=None):
        super().__init__()
        self.sink = sink or (lambda event: record(**event))
        self.base_fields = dict(base_fields or {})
        self.started = {}
        self.lock = threading.Lock()

    def _start(self, run_id, input_chars=0, metadata=None):
        fields = {**self.base_fields, **_CONTEXT.get()}
        model = (metadata or {}).get("ls_model_name") or (metadata or {}).get("model_name")
        if model:
            fields["model"] = model
        with self.lock:
            self.started.setdefault(str(run_id),
                                    (time.monotonic(), utc_now(), input_chars, fields))

    def on_llm_start(self, serialized, prompts, *, run_id, metadata=None, **kwargs):
        self._start(run_id, sum(len(str(prompt)) for prompt in prompts or []), metadata)

    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs):
        self._start(run_id, _message_chars(messages), metadata)

    def _finish(self, run_id, status, response=None, error=None):
        with self.lock:
            started = self.started.pop(str(run_id), None)
        if started is None:
            started = (time.monotonic(), utc_now(), 0,
                       {**self.base_fields, **_CONTEXT.get()})
        monotonic, started_at, input_chars, fields = started
        event = {
            "event": "llm_call",
            "started_at": started_at,
            "duration_seconds": round(time.monotonic() - monotonic, 6),
            "status": status,
            "error": error,
            "input_chars": input_chars,
            **fields,
            **(_usage(response) if response is not None else {
                "input_tokens": 0, "output_tokens": 0,
                "total_tokens": 0, "cached_input_tokens": 0}),
        }
        self.sink(event)

    def on_llm_end(self, response, *, run_id, **kwargs):
        self._finish(run_id, "ok", response=response)

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._finish(run_id, "error", error="%s: %s" % (type(error).__name__, error))


def import_events(events, **fields):
    """Merge in-memory provider events returned by the tester container."""
    for event in events or []:
        event = dict(event)
        event.update({k: v for k, v in fields.items() if v is not None})
        event.setdefault("event", "llm_call")
        record(**event)


def _percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return round(ordered[index], 6)


def _distribution(values):
    if not values:
        return None
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 6),
        "p50": round(statistics.median(values), 6),
        "p95": _percentile(values, 0.95),
        "max": round(max(values), 6),
        "sum": round(sum(values), 6),
    }


def _profile_cost(event, profile_name):
    if profile_name not in PRICING_PROFILES:
        raise ValueError("unknown pricing profile %r; choose one of %s"
                         % (profile_name, ", ".join(sorted(PRICING_PROFILES))))
    input_tokens = int(event.get("input_tokens", 0) or 0)
    output_tokens = int(event.get("output_tokens", 0) or 0)
    total_tokens = int(event.get("total_tokens", 0) or 0)
    if total_tokens <= 0:
        return None
    profile = PRICING_PROFILES[profile_name]
    tier = next((row for row in profile["tiers"]
                 if input_tokens <= row["max_input_tokens"]), None)
    if tier is None:
        return None
    cached = min(int(event.get("cached_input_tokens", 0) or 0), input_tokens)
    cost = ((input_tokens - cached) * tier["input"]
            + cached * tier["cached_input"]
            + output_tokens * tier["output"]) / 1_000_000
    return cost


def summarize(path, input_price_per_million=None, output_price_per_million=None,
              cached_input_price_per_million=None, pricing_profile=None):
    """Build a publication-auditable summary from a metrics JSONL file."""
    events = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
              if line.strip()]
    spans = [event for event in events if event.get("event") == "span"]
    calls = [event for event in events if event.get("event") == "llm_call"]

    wall_clock = {}
    for event in spans:
        if event.get("operation") in ("end_to_end", "static_corpus",
                                      "dynamic_corpus", "court_corpus"):
            wall_clock.setdefault(event["operation"], []).append(event["duration_seconds"])

    skill_latency = {}
    for event in spans:
        if event.get("operation") == "skill":
            skill_latency.setdefault(event.get("stage", "unknown"), []).append(
                event["duration_seconds"])

    llm = {}
    for event in calls:
        key = "%s.%s" % (event.get("stage", "unknown"),
                          event.get("operation", "unknown"))
        bucket = llm.setdefault(key, {
            "calls": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0,
            "cached_input_tokens": 0, "total_tokens": 0,
            "calls_with_usage": 0, "calls_without_usage": 0,
            "sum_provider_seconds": 0.0,
            "_profile_costs": [],
        })
        bucket["calls"] += 1
        bucket["errors"] += event.get("status") != "ok"
        for name in ("input_tokens", "output_tokens", "cached_input_tokens", "total_tokens"):
            bucket[name] += int(event.get(name, 0) or 0)
        if int(event.get("total_tokens", 0) or 0) > 0:
            bucket["calls_with_usage"] += 1
        else:
            bucket["calls_without_usage"] += 1
        bucket["sum_provider_seconds"] += float(event.get("duration_seconds", 0) or 0)
        if pricing_profile:
            bucket["_profile_costs"].append(_profile_cost(event, pricing_profile))

    prices = {
        "profile": pricing_profile,
        "profile_details": PRICING_PROFILES.get(pricing_profile),
        "input_per_million": input_price_per_million,
        "output_per_million": output_price_per_million,
        "cached_input_per_million": cached_input_price_per_million,
    }
    for bucket in llm.values():
        bucket["sum_provider_seconds"] = round(bucket["sum_provider_seconds"], 6)
        profile_costs = bucket.pop("_profile_costs")
        if pricing_profile:
            bucket["estimated_cost_usd"] = (
                None if any(cost is None for cost in profile_costs)
                else round(sum(profile_costs), 6))
            continue
        if (input_price_per_million is None or output_price_per_million is None
                or bucket["calls_without_usage"]):
            bucket["estimated_cost_usd"] = None
            continue
        cached = min(bucket["cached_input_tokens"], bucket["input_tokens"])
        cached_price = (cached_input_price_per_million
                        if cached_input_price_per_million is not None
                        else input_price_per_million)
        cost = ((bucket["input_tokens"] - cached) * input_price_per_million
                + cached * cached_price
                + bucket["output_tokens"] * output_price_per_million) / 1_000_000
        bucket["estimated_cost_usd"] = round(cost, 6)

    return {
        "source": str(path),
        "run_start": next((event for event in events if event.get("event") == "run_start"), None),
        "run_end": next((event for event in reversed(events)
                         if event.get("event") == "run_end"), None),
        "wall_clock_seconds": {name: round(sum(values), 6)
                               for name, values in wall_clock.items()},
        "skill_latency_seconds": {stage: _distribution(values)
                                  for stage, values in skill_latency.items()},
        "workloads": [event for event in events if event.get("event") == "workload"],
        "llm": llm,
        "pricing_usd": prices,
        "estimated_api_cost_usd": (None if any(
            bucket["estimated_cost_usd"] is None for bucket in llm.values())
            else round(sum(bucket["estimated_cost_usd"] for bucket in llm.values()), 6)),
        "errors": [event for event in events
                   if event.get("status") == "error"],
    }


def finish(summary_path, input_price_per_million=None, output_price_per_million=None,
           cached_input_price_per_million=None, pricing_profile=None):
    """Close the run and write its derived JSON summary."""
    if _PATH is None:
        return None
    record("run_end")
    summary = summarize(_PATH, input_price_per_million, output_price_per_million,
                        cached_input_price_per_million, pricing_profile)
    path = Path(summary_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
