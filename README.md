# MalSkillDet

Three stages. The static one accuses a skill of malicious types; the dynamic one
executes the skill and tries to make the accusation show itself; the final one
tries the accusations the machine confirmed and returns a verdict.

```bash
uv run python main.py <folder> [-o run/] [--disable-codeql] [--round 3]
```

`main.py` is the whole thing: it scans, validates and judges, and needs nothing
but the folder. Everything lands under `--out`:

```
static.json              claims and findings per skill
dynamic/<skill>.json     every round of every claim, with the judgement
dynamic/summary.json     one line per skill
court/<skill>-<claim>.md testimony, indictment and judgement, to read
verdicts.json            one verdict per skill in the folder
```

The stages also stand alone, which is how you re-run one of them without
paying for the others again:

```bash
uv run python static/pipeline.py <folder> [-o report.json] [--disable-codeql]
uv run python dynamic/pipeline.py --static-report report.json --out results/
uv run python final/court.py --evidence results/ --out court/
```

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
                          final judge ──Malicious──> skill done
                                     └──Benign─────> next claim
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
Skills run in parallel, claims run in order.

# Final judgement

The first two stages produce evidence; this one decides what it means. Its input
is *one* claim the reviewer confirmed, and its output is a verdict on the skill.
The two earlier stages are believed here: a confirmed record is a fact, and the
question is only whether the facts amount to an attack.

```bash
uv run python final/court.py --evidence results/ --out court/
```

```
skill dir ──> defendant ──testimony──┐
                                     ├──> prosecutor ──indictment──> judge ──> verdict
confirmed claim ──evidence───────────┘        (no charge: acquitted)
```

- `final/defendant.py` — reads the skill and writes what it says it is: entry
  points, dependencies, install steps, permissions. It is not asked to be
  suspicious; the testimony is only useful as a statement to be held against the
  records.
- `final/prosecutor.py` — sees the testimony and the confirmed evidence, and
  charges. Any disagreement between the two is already grounds, and anything it
  cannot name precisely enough to call harmless is charged. It over-charges by
  design: over 14 runs, including three benign skills, it charged 14 times. Its
  `BENIGN` is a formality kept for completeness — treat the indictment's *charges
  and quotes* as its output, not its verdict, and expect the discrimination to
  happen at the judge.
- `final/judge.py` — never sees the skill, so a skill that talks its way past a
  reader cannot talk to it. It has what the prosecutor does not: common
  knowledge and a whitelist, which is what lets `pypi.org` be dismissed and an
  unknown release asset not be. Acquittal must be earned charge by charge —
  "no evidence it was exploited" is not a refutation, only "it cannot be".
  `MALICIOUS` has to rest on a passage the indictment quoted; a charge carried
  by runtime behaviour alone caps at `SUSPICIOUS`, and that cap is enforced in
  code because the judge states the condition and then sentences past it.
- `final/tools.py` — `read_file`, `grep`, `ls`, `dir_tree` for the two stages
  that may read the skill, closed over the skill directory: the root is never a
  parameter, so a path leading out of it comes back as an error.
- `final/court.py` — the three in order, the CLI, and `run_court(evidence)`,
  which `dynamic/pipeline.py` calls as its final judge.

`MALICIOUS` and `SUSPICIOUS` both end the skill; only `BENIGN` moves on to its
next claim. `--evidence` takes a dynamic result file, a directory of them, or a
single claim, and keeps only the claims a reviewer confirmed. Each stage writes
a whole report in one call, so its budget is `--court-timeout` (300s), not the
20 seconds of the round loop.

