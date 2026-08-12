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

## Other backbones

All three scored the same way: 100 malicious + 100 benign, skills the court never
reached counted BENIGN.  Same prompts and same code throughout; only the backbone
differs.  Every figure is a single run, and single runs on these endpoints move --
two replays of one unmodified judge prompt over the same 124 indictments differed
by six benign verdicts.  Read the columns with that in mind.

| backbone | TP | TN | FP | FN | precision | recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| qwen3-max (`measured-v4`) | 94 | 90 | 10 | 6 | 90.38% | 94.00% | 92.16% |
| deepseek-v3.2 + revised judge | 90 | 91 | 9 | 10 | 90.91% | 90.00% | 90.45% |
| openai/gpt-4o-mini (openrouter) | 79 | 59 | 41 | 21 | 65.83% | 79.00% | 71.82% |

The deepseek row is the malicious half (`judge_deepseek_v2_full`) merged with the
benign half (`judge_deepseek_v2_benign`); the malicious evidence files in
`run_malicious100/` are byte-identical to their counterparts under
`run_100x100/dynamic/`, so the two halves are the same experiment.  Against the
earlier deepseek baseline of 73/100 recall the revised judge is worth a lot, but
that baseline's model is unrecorded and `.env` changed mid-session, so the pair is
not a clean single-variable comparison.

gpt-4o-mini's row describes a failure mode rather than a measurement: it returned
120 MALICIOUS, 1 BENIGN and 36 error over the 157 skills that reached the court,
convicting 99% of what it managed to judge.  Thirty of the 36 errors are the
forensics tool loop hitting the recursion limit.  Note the openrouter base URL
must be `https://openrouter.ai/api/v1`; the `/api/v1/responses` path recorded in
`.env` returns 404 for this client.

### google/gemini-2.5-flash: aborted at 82/157

Non-convergence, the same failure gpt-4o-mini has: 19 of the 82 skills that
finished died on `GraphRecursionError`, the forensics tool loop hitting its limit.
Aborted there rather than paying for the remaining 75.

A six-skill pilot had passed cleanly -- 0 errors, 3/3 malicious convicted, 2/3
benign acquitted -- and a single instrumented forensics run finished in one step
without calling a tool at all.  Both readings were wrong about the population: six
skills was far too small to see a 23% failure rate, and the one-step run was the
good case, not the typical one.  A pilot meant to gate a full run has to be sized
against the failure rate it is looking for.

The 19 failures fall 17 benign / 2 malicious, so the partial results are not a
usable measurement even as a fragment: the errors default to BENIGN and would
flatter precision on exactly the half that was hit.  Of the 63 that did return a
verdict, benign went 26 BENIGN / 16 MALICIOUS and malicious went 19 MALICIOUS /
2 BENIGN.

Cost of the aborted run, from the openrouter key's usage counter: $5.74.
