# Review: horizon-agentic-reviewer

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `horizon-agentic-reviewer` skill package, its normal entry path, and its directly referenced files.

Version identifier: `17658fab5ec1`

GitHub repository: `omonuj/claude-skills`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Modifying System Services

## Executive Assessment

The reviewer is designed to inspect tasks and repositories that may be controlled by third parties, yet its headless invocation disables all permission prompts. The documentation explicitly states that every tool call will pass through. This places hostile review input in the same context as unreviewed write and command capabilities.

## Audited Source Excerpt

```text
claude -p --dangerously-skip-permissions \
  "review horizon task <task_uuid> using the horizon-agentic-reviewer skill"

Skip prompts. With --dangerously-skip-permissions, every tool call goes through.
```

Source: `SKILL.md:298-316`

Location: `SKILL.md:298-316`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The skill first loads the Horizon task and associated project material. It then recommends a print-mode Claude command with `--dangerously-skip-permissions`, and also discusses persistent settings that pre-authorize commands. No external project was reviewed during the audit. The documented invocation fully specifies the unsafe execution state, so live exploitation was not required to confirm reachability.

## Closing Analysis

Review should reduce trust in the target, not grant the target's content a path into an unrestricted agent. A read-only worktree and a deny-by-default tool policy would be consistent with the stated purpose. By doing the opposite, the skill makes code review a practical route to host modification or command execution.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because it disables the principal safety boundary precisely where untrusted review content enters the agent.
- Evidence: `SKILL.md:298-316` and the execution-path analysis above.

## Excluded False Positives

- Headless review is not inherently malicious. The harmful element is the explicit all-tools approval state applied while ingesting potentially adversarial project content.

## Residual and Unresolved Risks

- Persistent allow rules may outlive a single review and affect later tasks, extending the damage beyond the initial invocation.

## Repository and Provenance Findings

- The assessment is scoped to `omonuj/claude-skills` at version `17658fab5ec1` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
A review request loads third-party project content into an agent for which every tool call has already been approved.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because it disables the principal safety boundary precisely where untrusted review content enters the agent.
