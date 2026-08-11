# 38-skill probe

A hard subset of the 100x100 dataset used to tune the court without paying for a
full replay: 18 malicious skills the previous version missed, and 20 benign ones
picked because they sit next to those misses (real credentials in the trace,
persistence, first-party clients under the same brand as a malicious skill,
registry installs).  Both sides are selected for difficulty, so **the ratios here
are not an estimate of the full-set metrics** -- only the direction of a change
transfers.

Evidence comes from `eval_runs/run_100x100/dynamic/`; the static and dynamic
stages are fixed inputs and are not re-run.

Two of the 100 malicious skills (`discord-voicetwhtm`, `sacred-space-protocol`)
carry no confirmed claim, so the court never sees them.  A third,
`landgod-computer-use__6e71004332`, is named for a bare `.whl` from a random
repository that never appears in its confirmed rounds -- the trace holds only a
screenshot.  Full-set recall is therefore capped near 97%.

## The probe cannot resolve a small change

| iteration | TP | FN | FP | TN | precision | recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline (`final_v2_v2_100x100`, restricted to these 38) | 11 | 7 | 3 | 17 | 78.6% | 61.1% | 68.7% |
| 1 | 13 | 5 | 4 | 16 | 76.5% | 72.2% | 74.3% |
| 2 | 15 | 3 | 5 | 15 | 75.0% | 83.3% | 78.9% |
| 3 | 16 | 2 | 8 | 12 | 66.7% | 88.9% | 76.2% |
| 4 | 15 | 3 | 3 | 17 | 83.3% | 83.3% | 83.3% |
| 5 | 14 | 4 | 5 | 15 | 73.7% | 77.8% | 75.7% |
| 6 (seeded) | 11 | 7 | 3 | 17 | 78.6% | 61.1% | 68.8% |

Across those runs **16 of the 38 skills changed verdict at least once**, and any
two adjacent runs disagree on 5 to 10 of them.  Iteration 5 differed from 4 only
by giving the payload tiers names instead of numbers, and it moved 7 skills.

Temperature has been 0 throughout, so this is the provider's own sampling.
Setting `seed=42` did not remove it: a back-to-back rerun of five skills at the
same seed and the same prompts returned a different verdict for three of them.
`top_p` is narrowed to 0.01 for that reason, but the endpoint is not
reproducible, and **a five-point move on 38 samples is not evidence**.

So the probe was useful for what it was actually good at -- it surfaced, in the
reports themselves, the reasoning errors that the prompt edits then fixed -- and
it is not a scoreboard.  Ranking iterations by its F1 would be ranking draws.
Measurement moves to the full set, where the same per-skill flip rate averages
down over 100 malicious skills instead of 18.

## Full-set measurements

Scored with `eval_runs/score.py` over all 200 dataset skills; the 43 without a
confirmed claim keep BENIGN, as the scorer already does.

| version | TP | FN | FP | TN | precision | recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `final_v2_v2_100x100` (previous) | 87 | 13 | 6 | 94 | 93.55% | 87.00% | 90.16% |
| `final_v3_100x100` | 91 | 9 | 10 | 90 | 90.10% | 91.00% | 90.55% |
| `final_v4_100x100` | 94 | 6 | 10 | 90 | 90.38% | 94.00% | 92.16% |
| `final_v5_100x100` | 90 | 10 | 2 | 98 | 97.83% | 90.00% | 93.75% |

v5's six precision fixes worked and then some -- false positives fell 10 -> 2,
far outside the noise band.  Recall fell 4, of which two skills are traceable to
a carve-out being quoted back verbatim in the acquittal, so the two points are
not symmetric: the precision move is measured, part of the recall move is a
identifiable mistake of mine.

## Where this landed, and what is not settled

Three full runs were budgeted and three were spent, in this order:

- `measured-v3` — R 91.0%, P 90.10%, F1 90.55%
- `measured-v4` — R 94.0%, P 90.38%, F1 92.16%  ← best recall, both metrics above 90
- `measured-v5` — R 90.0%, P 97.83%, F1 93.75%  ← best F1 and precision

Each tag is checkoutable.  **No single run met both goals at once**: v4 clears the
recall bar and lands F1 just under 93%, v5 clears F1 and precision by a wide
margin while recall sits exactly at 90%.

HEAD is v5 plus two rule corrections made after the budget was spent, so it is
**unmeasured**.  A 14-skill targeted probe confirmed one of the two fires
(`skilldeck` convicts again) and the other does not (`notion-export` still
acquits: the judge reads an `env` placeholder under a `notion` entry as the
skill's own namespace regardless of whether the entry is new).  That same probe
returned 4 false positives among 11 benign skills, against v5's 2 among 100 --
which is the clearest available reminder that **v5's 97.83% is one draw, not a
property of the prompts**.  Expect HEAD to sit between v4 and v5.

Two ceilings are structural and no prompt reaches them:

- three malicious skills carry no usable evidence (two never reach the court,
  one is named for a `.whl` that never executes), capping recall near 97%;
- the dataset labels the same act both ways -- `curl bun.sh/install | bash` is
  malicious in `gbrain-installation` and benign in `design-consultation`, and
  official-vendor install pipes split about evenly between the two labels.
