# MalSkillDet

Three steps. The static one accuses a skill of malicious types; the dynamic one
executes the skill and tries to make the accusation show itself; the final one
reads the evidence the machine confirmed and returns a verdict.

## Artifacts

Reproducibility materials are indexed in [`artifact/README.md`](artifact/README.md).
They include the benchmark, raw evaluation outputs, marketplace findings, and
the independent harm-based audit of 38 candidate Skills. The 38-Skill audit is
available both as [browsable reports](artifact/skill-audit-38-v1.0.0/README.md)
and as a [ZIP archive](artifact/malskilldet-skill-audit-38-v1.0.0.zip).

**The dynamic step runs to completion first, and only then does the final one
judge.** That is the only order we recommend, and it is not a preference: the
court's unit of judgement is a *skill*, not a claim — one chain routinely spans
several claims (a single `curl | bash` lands `suspicious_download`,
`malicious_code` and `unverifiable_dependency` at once), so trying them one at a
time both repeats the work and shows each pass a third of the story. A skill can
only be tried once every claim of it has been run.

```bash
uv run python main.py <folder> [-o run/] [--disable-codeql] [--round 3]
```

`main.py` runs the three steps in that order and needs nothing but the folder.
Everything lands under `--out`:

```
static.json              step 1: claims and findings per skill
dynamic/<skill>.json     step 2: every round of every claim, with the review
dynamic/summary.json     step 2: one line per skill
court/<skill>.md         step 3: forensics, indictment and judgement, to read
court/court.json         step 3: one court result per skill tried
    verdicts.json            one verdict per skill in the folder
    _metrics/events.jsonl    every timed span and actual provider request
    _metrics/summary.json    stage wall clock, P50/P95 latency, tokens and cost
```

## Efficiency metrics

`main.py` records metrics automatically.  The JSONL file is the source of
truth: each provider request is kept separately so tiered pricing can be
recomputed without rerunning the experiment.  It stores token counts, timing,
stage/skill/claim/round coordinates and errors, but never prompts, responses,
API URLs or credentials.  The summary distinguishes corpus wall clock from
overlapping per-skill latency and reports dynamic pruning/round counts and
court early exits.

For the Qwen3-max Beijing list price published on 2026-07-24, pass
`--pricing-profile qwen3-max-cn-beijing-2026-07-24`.  The profile is an estimate;
the provider bill remains the authoritative charged amount.

## The three steps on their own

Each step is also its own entry point, taking the previous one's output as its
input. This is how you re-run one of them without paying for the others again —
a new prompt in the court, say, costs nothing but step 3.

```bash
# 1. static: a folder of skills -> claims
uv run python static/pipeline.py <folder> [-o report.json] [--disable-codeql]

# 2. dynamic: claims -> machine records, one result file per skill
uv run python dynamic/pipeline.py --static-report report.json --out results/

# 3. final: confirmed records -> a verdict per skill
uv run python final_v2/court.py --evidence results/ --out court_v2/
```

Step 2 no longer judges anything, so every skill it finishes is left
`PENDING_COURT`; step 3 takes the whole `results/` directory and keeps only the
claims a reviewer confirmed. Skills with nothing confirmed never reach it.

# Static analysis

Scans a folder of agent skills and reports, per skill, which of the 8 malicious
types from `report.pdf` it is accused of.

A directory containing `SKILL.md`/`skill.md` is one skill; the walk does not
descend past it, so a bundled sub-skill belongs to its parent.

## Pipeline

```
files ──regex (280 patterns)──┐
                              ├── findings ──group──> claims (8 types, scored)
ts/js/py ──CodeQL (8 queries)─┘
```

- `static/matchers.py` — the regex corpus, the 34 behaviour groups, the
  group→type taxonomy, the synergy table and the scoring model.
- `static/workers.py` — applies the patterns / drives CodeQL, emits findings.
- `static/pipeline.py` — discovery, aggregation, CLI and JSON output.
- `static/codeql/` — CodeQL CLI, query pack, databases, `run.sh` (see its README).

## Model

A **finding** is one match: `metadata`, `matched_text`, `context` (≥300 chars,
or the CodeQL data flow), `location`, `level`, `group`.

Findings are grouped by *behaviour* (`untrusted_host`, `credential_read`,
`pipe_to_shell`, …), not by malicious type. Each group feeds one or more types,
each type is fed by several groups — that mapping is the aggregation.

A **claim** is one malicious type for one skill: `metadata`, `level` (fixed by
the report's taxonomy), `score`, `type`, `findings`.

Scoring is count-independent: within a group only the highest level counts
(`low` 5, `medium` 12, `high` 25, `critical` 40), and the group scores are
summed. Groups that mean more together than apart add a bonus (`low` 8,
`high` 20) — e.g. credential reads plus an outbound channel, or a password
protected archive plus an untrusted host.

## Install CodeQL

Enabled by default; `--disable-codeql` runs the regex layer alone (seconds
instead of a minute). Setup is in `static/codeql/README.md`; the extractor for
TypeScript also needs the bundled `static/codeql/node/`.

# Dynamic validation

Static analysis proves a construct is *present*. Dynamic validation asks whether
it *acts*: the skill is handed to a real agent on a real machine, given an
ordinary-looking user request, and everything the machine does is recorded.

```bash
uv run python dynamic/pipeline.py --round 3 \
    --tester-recursive 20 --tester-timeout 20 \
    --loop-recursive 50 --loop-timeout 20 \
    --static-report report.json --out results/ --max-parallel 8
```

```
claim ──> generator ──prompt──> tester ──evidence──> reviewer ──┐
   ^                                                            │
   └────────────────── not_trigger, summary ────────────────────┘
                       confirmed / rounds spent
                                  │
                                  v
                        next claim of the skill
                                  │
                                  v
                    every claim run ──> PENDING_COURT
```

- `dynamic/generator/prepare.py` — one LLM pass that drops pattern matches on
  things the pattern does not describe (a `venv` read as an `.env`, a filename
  read as a call). Survivors are regrouped and re-scored.
- `dynamic/generator/guides/` — one prompt per malicious type: what the category
  means, how to combine findings from several behaviour groups, a template for
  the user turn, a template for the oracle, and what is forbidden.
- `dynamic/generator/generator.py` — sees the guide, `SKILL.md` and the findings'
  contexts, and writes `prompt` + `oracle`. Sheds `low` then `medium` findings if
  the context window overflows.
- `dynamic/generator/helper.py` — the taxonomy and scoring model (copied from
  the static layer so this stage runs standalone), plus the regex gate that
  rejects prompts carrying code, commands, paths or test semantics.
- `dynamic/tester/` — the container. `build/` is the image and the canary home;
  `build_docker.py` is its lifecycle; `run_test.py` is the deep agent that runs
  *inside* it; `monitor/` reads the filesystem (`docker diff`) and the network
  (`tcpdump`, requests only).
- `dynamic/reviewer/reviewer.py` — checks the oracle against the evidence.
  The tester's own report is the one channel the skill could have written, so it
  never overrides the machine records. An attempt counts as confirmed.

The tester returns four channels — `filesystem`, `execution`, `llm_output`,
`network` — and every one is trimmed for the reviewer: collapsed directories,
build noise dropped, tool output cut to 100 characters, network reduced to the
names resolved and the addresses connected to.

One container per skill, destroyed with it; the claims of one skill share it.
Skills run in parallel, claims run in order. Every claim is run — this step never
stops early on a verdict, because it produces no verdict. The static anchors
(`rule_id`, `file:line`, the matched line) travel with each claim into the result
file: they are the coordinate the court's forensics stage starts from.

# Final judgement

The first two steps produce evidence; this one decides what it means. Its input
is *every* claim of one skill that a reviewer confirmed, and its output is a
verdict on the skill. The two earlier steps are believed here: a confirmed record
is a fact, and the question is only whether the facts amount to an attack.

```bash
uv run python final_v2/court.py --evidence results/ --out court_v2/
```

```
skill dir ─────────────┐
                       ├──> forensics ──facts──> prosecutor ──indictment──> judge ──> verdict
confirmed claims ──────┘                       (no charge: acquitted)
```

Three stages, and each one's output is the next one's only input. Whatever a
stage fails to carry across stops existing there.

- `final_v2/forensics.py` — the only stage that sees raw material: the machine
  records and the skill directory. It writes down what happened — where each
  accused action landed in the trace, which passage of the skill produced it, how
  wide it reached — and, separately, the dangerous actions whose identifiers
  appear *nowhere* in the skill, because those belong to the test agent and not
  to the defendant. Method is machine-first: find the landing action, then take
  its identifiers (domain, package, path, flag) back to the text, where "not
  found" is provable. It does not judge, and it is graded on accuracy and
  completeness rather than brevity.
- `final_v2/prosecutor.py` — sees the forensics report and nothing else. It
  answers the four questions of maliciousness and files at most two charges. Its
  one tool is `read_guide`, the constitutive elements of the eight charge
  categories, and those elements — a conjunction of necessary conditions, one
  missing and the charge is dropped — are its only convergence mechanism. It
  holds no whitelist and grants no exemption from experience. It may return
  `BENIGN`, which ends the court right there. Its most load-bearing field is
  *preconditions*: the facts outside the evidence that the charge depends on
  (is `openclawcli.forum` related to OpenClaw, is this value a real credential),
  which turn the judge's question from "is this dangerous" into "is this
  precondition true".
- `final_v2/judge.py` — gets the indictment and nothing else: no forensics
  report, no skill directory. A skill that talks its way past a reader cannot
  talk to this stage; the price is that a quote the prosecutor failed to carry
  over verbatim is gone, which is why both earlier stages are told to carry
  quotes across unchanged. Four checks in order — attribution and closure,
  preconditions, sources, harm — and then a binary verdict; a middle grade would
  only be folded into one of the two, and folding is what turned every doubt into
  a conviction in the first version. Its one tool is `check_source`, which
  answers a question the judge used to answer from impression: is this domain
  allowed to be visited, downloaded from, or uploaded to.
- `final_v2/sources.yaml` — that tool's backing list, one entry per domain, each
  granting some subset of visit / download / upload and carrying a note that
  travels back with the answer. It is the whole of the court's whitelist: the
  rules that used to sit beside it in `precedents.md` were never about a domain,
  and now live in the four steps of `judge.md` where they are actually applied.
- `final_v2/tools.py` — `read_file`, `grep`, `ls`, `dir_tree` for forensics,
  closed over the skill directory: the root is never a parameter, so a path
  leading out of it comes back as an error. Plus `read_guide` for the prosecutor
  and `check_source` for the judge.
- `final_v2/prompts/` — `forensics.md`, `prosecutor.md`, `judge.md`,
  `payload.md`, and `charges/` (one file per malicious type). The prompts are
  the design; `references/DESIGN.md` is the reasoning behind them, down to the
  32 errors of the first version that each rule answers.
- `final_v2/court.py` — the three in order, the evidence rendering, the CLI, and
  `try_skills(groups, out)`, which `main.py` calls as its third step.

Three design rules run through all of it: the skill's own text can convict but
never acquit ("it is the declared feature" is not a defence, since a malicious
skill necessarily declares its attack); attribution is a hard gate (an action
shown to be the test agent's invention cannot convict); and only forensics sees
the raw material.

`--evidence` takes a dynamic result file, a directory of them, or a single claim
unit, and keeps only the claims a reviewer confirmed, grouped by skill. Each
stage writes a whole report in one call, so its budget is `--timeout` (300s), not
the 20 seconds of the round loop.

The first version — testimony / cross-examination / sentencing, one *claim* per
trial — is kept under `references/final/` for comparison, along with the design
notes that replaced it.
