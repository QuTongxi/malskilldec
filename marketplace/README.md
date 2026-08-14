# marketplace — the market-scale scan

Eight thousand real skills off a real marketplace, scanned with the static stage
and the court and nothing in between. This directory holds the sample, the two
scripts that produced it, and the record that makes it reproducible.

```bash
uv run python marketplace/build_frame.py -o marketplace/frame.json
uv run python marketplace/download_sample.py --frame marketplace/frame.json \
    --out marketplace/real_dataset_8k --target 8000 --workers 16
```

```
frame.json                 the sampling frame: every in-scope repository, its
                           stars, its stratum, and the marketplace's install
                           counts
manifest.json              the realised sample: one row per skill, with the
                           repository, the stratum, the content hash and the
                           seed that drew it
real_dataset_8k/<skill>/   the skills themselves, one directory each
.cache/                    the raw listings and lookups, so a rebuild is cheap
```

## The market

**skills.sh**, with GitHub topic search filling in the tail.

It is the largest of the marketplaces anyone has measured — 125,928 skills in
[arXiv:2603.16572](https://arxiv.org/html/2603.16572v2), against ClawHub's
16,755 and SkillsDirectory's 17,611 — and it is the one the ecosystem actually
runs on, since `npx skills` ([vercel-labs/skills](https://github.com/vercel-labs/skills))
installs from it. Its index is open in two enumerable slices: the MIT snapshot
bundled in [mastra-ai/skills-api](https://github.com/mastra-ai/skills-api)
(34,311 skills / 2,843 repositories, January 2026) and the live all-time
endpoint. Nothing is authenticated and no key was applied for.

It is also the only marketplace carrying `installs`, which is an adoption count
for a *skill*. Stars describe the repository a skill happens to sit in, and the
frame contains a repository with 1,211 skills in it — the two numbers are not
measuring the same thing, and only one of them is about the skill.

The live endpoint is a **leaderboard, not a listing**: today its 9,616 rows have
a median of 2,331 installs and nothing at all between 100 and 999. It is the
head by construction, so the tail this study is about has to come from the
repository side, which is where the GitHub topic harvest comes in
(`topic:agent-skills` alone holds ~12,000 repositories at 0–4 stars).

## The frame, and why it has a ceiling

In scope: a repository under **100 stars**, not a fork, and not already on the
marketplace's all-time leaderboard.

The ceiling is not a claim that popular skills are safe. It is that a malicious
skill with mass adoption would have had to fool the entire community — a rarer
and different event than the one being measured, and not one a scanner is going
to be the first to catch. The single measurement that exists points the same
way: skills above 1,000 installs are flagged at 16.16% against 19.29% overall
([arXiv:2603.16572](https://arxiv.org/html/2603.16572v2)). And inverting the
star filter is standard practice read backwards — MSR studies filter *for*
50–100 stars to find engineered projects (Munaiah et al., *Curating GitHub for
engineered software projects*, EMSE 2017), so below that line is precisely the
population nobody has curated.

## The strata, and why the allocation is neither of the obvious two

Bands are log-spaced because stars are heavy-tailed: across the 3,630 skills.sh
source repositories the quartiles are 3 / 32 / 453, so equal-width bands would
put nine tenths of the frame in one bucket.

| stratum | stars | quota | share |
| :-- | :-- | --: | --: |
| S0 | 0 | 2,400 | 30% |
| S1 | 1–4 | 2,400 | 30% |
| S2 | 5–19 | 1,600 | 20% |
| S3 | 20–49 | 1,000 | 12.5% |
| S4 | 50–99 | 600 | 7.5% |

Proportional allocation would land ~80% of the sample in S0–S1 — that is where
the phenomenon lives, but it leaves the upper bands too thin to show that a
trend is a trend. Equal allocation would spend a fifth of the budget on S4,
which is about 4% of the frame. This sits between them, with a floor of 600 per
band so every one of them supports a proportion to about ±4%.

**No market-wide malicious rate is estimable from this sample and none is
claimed.** Disproportionate stratified sampling is legitimate when population
estimation is not the goal, on the condition that the frame, the strata and the
seed are all written down (Baltes & Ralph, *Sampling in Software Engineering
Research*, EMSE 2022) — `frame.json` and `manifest.json` are that condition
being met.

## Three filters at extraction

Each one corrects a way this ecosystem inflates its own size.

- **Content dedup.** The one prior measurement that reports it found 27%
  duplicates (42,447 listed → 31,132 unique). Forks, vendored copies and
  awesome-list mirrors republish the same SKILL.md. Identical normalised bytes
  count once.
- **25 skills per repository.** The frame holds a repository with 1,211 skills;
  uncapped, five monorepos would supply a third of the sample.
- **40 skills per owner.** The same failure one level up, where one author
  spreads a template across thirty repositories.

A skill is a directory holding `SKILL.md`, and the walk does not descend past
one — the same definition [static/pipeline.py](../static/pipeline.py) uses, so
the sample and the scanner agree on what they are counting.

## Downloading

One `codeload.github.com` tarball per repository, 16 at a time, unpacked in
memory. Not a clone: history is paid for and never read. Files over 2 MB are
data rather than instructions and are skipped, as are `node_modules` and the
rest of the build detritus.

No API key was applied for. The marketplace endpoints are anonymous; the
GitHub token in `.env` only raises the rate limit and reads star counts, and the
tarballs are public either way. The one operational catch is GitHub's
*secondary* limit, which answers 403 with the documented budget untouched:
`api.github.com` gets three threads, `codeload` gets sixteen.

## Scanning it

Static on everything, the court on the top of the pile. On
`eval_runs/run_100x100`, having any claim at all is nearly useless as a filter —
78% of the benign skills are accused of something — while the top claim's score
separates cleanly:

| filter | of the malicious | of the benign |
| :-- | --: | --: |
| any claim | 100% | 78% |
| top score ≥ 60 | 88% | 20% |
| top score ≥ 80 | 74% | 7% |
| top score ≥ 100 | 69% | 3% |

```bash
uv run python static/pipeline.py marketplace/real_dataset_8k -o marketplace/static.json
uv run python ablation/static_to_evidence.py --static-report marketplace/static.json \
    --out marketplace/pseudo_dynamic/
uv run python final_v2/court.py --evidence marketplace/pseudo_dynamic/ \
    --out marketplace/court/ --recursive 60 --max-parallel 10
```

`static_to_evidence.py` defaults — `--context-chars 400 --max-anchors 5` — are
the operating point the 95.45% precision / 84.00% recall in
[eval_runs/ablation_static_only](../eval_runs/ablation_static_only/README.md)
were measured at. Changing them moves the operating point off the measured one,
so the reported precision would no longer be the reported precision.

## What it costs

Measured on qwen3-max at `--recursive 60`: **about ¥5.2 per skill**, almost all
of it input. The reports themselves average 8.4k characters, so the spend is not
the writing — it is the forensics tool loop, where each of up to sixty rounds
re-sends the whole conversation so far, and cost grows with the square of the
round count while the output stays flat.

So a queue of 1,326 skills is roughly **¥6,900**, and a ¥600 budget reaches
about 115 of them. That is the reason `scan.py` queues hardest-first: a run that
stops at a budget should stop having judged the most suspicious skills, not an
alphabetical prefix. If the whole queue has to fit a fixed budget, raise
`--min-score` — that trades recall for coverage at a *known* operating point,
which lowering `--recursive` or the anchor count does not.

Two failure modes of the endpoint are worth knowing before a long run:

- **`429 insufficient_quota` is throughput, not money.** DashScope words its
  rate limiting as a complaint about "your plan and billing details" and links
  it to the token-limit page. Reading that as arrearage stopped a 1,326-skill
  run after one skill. `scan.py` now settles it with a five-token probe rather
  than a regex: if the probe answers, the account is fine and the run backs off.
- **`data_inspection_failed` is content moderation.** A real marketplace skill
  can trip the input filter; it comes back as a 400, it is not retryable, and it
  is recorded as `error`. The curated eval set never produced one.
