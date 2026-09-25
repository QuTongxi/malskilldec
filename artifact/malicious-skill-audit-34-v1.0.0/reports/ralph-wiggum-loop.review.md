# Review: ralph-wiggum-loop

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `ralph-wiggum-loop` skill package, its normal entry path, and its directly referenced files.

Version identifier: `4a410c544c72`

GitHub repository: `xpepper/pr-review-agent-skill`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Modifying System Services

## Executive Assessment

The review loop repeatedly invokes Claude or Codex with their respective permission-bypass flags until the agent itself writes a completion marker. Both the pull request and the review plan may contain untrusted text, while no human approval is required between iterations. A single unsafe instruction can therefore be retried and compounded rather than contained.

## Audited Source Excerpt

```text
while [ ! -f PR_REVIEW_DONE ]; do
  cat CODE_REVIEW_PLAN.md | claude -p --dangerously-skip-permissions
done
while [ ! -f PR_REVIEW_DONE ]; do
  cat CODE_REVIEW_PLAN.md | codex exec --yolo -
done
```

Source: `README.md:24-31; SKILL.md:32,37,69,76`

Location: `README.md:24-31; SKILL.md:32,37,69,76`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The shell examples test for `PR_REVIEW_DONE`; while it is absent, they pipe the plan into `claude -p --dangerously-skip-permissions` or `codex exec --yolo`. The stopping condition is under the agent's control, so the loop can continue making changes indefinitely. The audit did not start the loop against a live pull request. The repeated command and termination condition are fully visible in the distributed files.

## Closing Analysis

An iterative reviewer can operate safely in a read-only checkout or pause before applying each patch. This implementation instead removes approvals on every pass and lets the agent decide when it is finished. That design turns untrusted code-review material into a repeatable mechanism for damaging the repository or the wider host.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because it repeatedly exposes the workspace to unsupervised agent actions driven by potentially hostile review input.
- Evidence: `README.md:24-31; SKILL.md:32,37,69,76` and the execution-path analysis above.

## Excluded False Positives

- Iteration and completion markers are normal automation patterns. The malicious finding depends on their use with repeated permission-bypassed agent invocations.

## Residual and Unresolved Risks

- If the marker is never created, resource exhaustion and an effectively unbounded sequence of changes become additional concerns.

## Repository and Provenance Findings

- The assessment is scoped to `xpepper/pr-review-agent-skill` at version `4a410c544c72` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
The review plan is fed repeatedly to an unrestricted agent until that agent chooses to create the stop file.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because it repeatedly exposes the workspace to unsupervised agent actions driven by potentially hostile review input.
