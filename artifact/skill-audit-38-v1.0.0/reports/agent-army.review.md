# Review: agent-army

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `agent-army` skill package, its normal entry path, and its directly referenced files.

Version identifier: `4b15618eec45`

GitHub repository: `amjad1233/claude-skills`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Modifying System Services

## Executive Assessment

The autonomous launcher adds `--dangerously-skip-permissions` to every worker it starts. This multiplies one approval bypass across several concurrent agents, each of which can modify files, run commands, and use the network. Parallelism amplifies both the probability and the impact of a bad instruction.

## Audited Source Excerpt

```text
CMD="claude --dangerously-skip-permissions --model $MODEL $RESUME \"\$(cat '$PROMPT_FILE')\""
Autonomous runs use `--dangerously-skip-permissions` — a real security trade-off; only for trusted, sandboxed work.
```

Source: `scripts/launch-agent.sh:62; SKILL.md:132`

Location: `scripts/launch-agent.sh:62; SKILL.md:132`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The front-door workflow creates task and prompt files, after which the launcher builds a command for each worker. In autonomous mode the dangerous flag is part of the constructed command rather than an incidental example. The documentation acknowledges the trade-off, but the mode still removes per-action review for every child process. No workers were launched during the audit; the command construction was inspected statically.

## Closing Analysis

A multi-agent system can run with isolated worktrees, constrained tools, or supervised approvals. It does not need to grant every worker unreviewed host access. Here, a single request to run autonomously creates several unsupervised principals at once, so a prompt error or injection can produce broad and concurrent damage.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its ordinary autonomous path scales an unrestricted execution context across multiple agents.
- Evidence: `scripts/launch-agent.sh:62; SKILL.md:132` and the execution-path analysis above.

## Excluded False Positives

- The report does not treat multi-agent orchestration or concurrency as malicious. The decisive behavior is the systematic removal of approvals from all autonomous workers.

## Residual and Unresolved Risks

- The launcher may also create race conditions between workers, but that reliability issue is secondary to the explicit permission bypass.

## Repository and Provenance Findings

- The assessment is scoped to `amjad1233/claude-skills` at version `4b15618eec45` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Autonomous mode launches multiple concurrent agents with host-level actions automatically approved.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its ordinary autonomous path scales an unrestricted execution context across multiple agents.
