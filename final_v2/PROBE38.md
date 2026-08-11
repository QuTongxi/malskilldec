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
