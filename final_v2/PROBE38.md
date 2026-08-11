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
carry no confirmed claim, so the court never sees them: full-set recall is capped
at 98%.

| iteration | TP | FN | FP | TN | precision | recall | F1 | what changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline (`final_v2_v2_100x100`, restricted to these 38) | 11 | 7 | 3 | 17 | 78.6% | 61.1% | 68.7% | -- |
| 1 | 13 | 5 | 4 | 16 | 76.5% | 72.2% | 74.3% | consequence screening decoupled from attribution; per-action checklist; per-write payload grading; payload rubric de-duplicated into `prompts/payload.md`; `seed=42` on forensics |
