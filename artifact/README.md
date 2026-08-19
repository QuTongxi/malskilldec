# Artifact

Everything the paper reports, beyond the implementation in the repository root.

| File | What it holds |
|---|---|
| `labels.csv` | Ground truth for the 200-skill benchmark, one row per skill. |
| `dataset-100x100-v1.0.0.zip` | The 200 skill directories themselves, 100 benign and 100 malicious. |
| `qwen3max-main-run.zip` | Every raw output of the main Qwen3-max configuration. |
| `BASELINES.md` | Source, version, and verdict mapping for each of the nine baselines. |

## `labels.csv`

| Column | Meaning |
|---|---|
| `relative_path` | Path inside the dataset zip, e.g. `malicious/youtube-summarize`. |
| `skill_name` | Directory name. |
| `label` | `benign` or `malicious`. This is the ground truth used for every number in the paper. |
| `malicious_categories` | Behavior categories of Table 1, comma-separated; empty for benign skills. Summing this column reproduces Table 3. |
| `category_evidence` | Where the category assignment came from: the court report of the main run, or a hand reading for the two skills that produced no court report. |

The label of a skill is its directory, `benign/` or `malicious/`. `score.py`
derives ground truth from the layout and nothing else, so moving a directory is
the only way to relabel a skill.

## `dataset-100x100-v1.0.0.zip`

The 100 malicious skills were recovered from four public blocklists, deduplicated,
and kept only when two authors independently judged them malicious. The 100 benign
skills were drawn at random from the 1000 most-starred skills on SkillsMP and
reviewed one at a time. Sampling benign skills by popularity rather than by safety
keeps skills that direct the agent into risky but legitimate operations.

**These skills are live.** Several fetch and execute remote payloads when an agent
follows them. Unpack and run them only inside a disposable container.

## `qwen3max-main-run.zip`

The configuration behind Tables 2, 4, 5 and 7: Qwen3-max, 3 rounds, recursion
limit 60, static threshold 0.

```
static.json            claims and findings for all 200 skills
dynamic/<skill>.json   every round of every claim, with the reviewer's decision
court/<skill>.md       forensic report, indictment, and verdict, as a reader sees it
court/court.json       one structured court result per skill tried
RESULTS_200.csv        per-skill summary: claims, score, where the skill left the pipeline
score.py               recomputes TP/FP/TN/FN, precision, recall, and F1 from court/
label_overrides.json   historical record of six relabelled skills, no longer applied
```

`dynamic/` holds fewer files than the dataset because a skill against which static
analysis raised no claim never enters dynamic verification, and `court/` holds
fewer still because a skill with no confirmed claim never reaches the court. Both
count as `BENIGN` in scoring; `RESULTS_200.csv` records where each skill stopped.

Stack traces in these outputs have had absolute paths rewritten to `/workspace/`.
The credentials that appear in them are the sandbox canaries, planted on realistic
paths under `/workspace/project/secrets/` and accepted by no service, together
with placeholder strings that the audited skills ship themselves.
