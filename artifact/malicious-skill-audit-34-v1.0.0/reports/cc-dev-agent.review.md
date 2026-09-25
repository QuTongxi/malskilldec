# Review: cc-dev-agent

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `cc-dev-agent` skill package, its normal entry path, and its directly referenced files.

Version identifier: `7749ad95547d`

GitHub repository: `immacualate/claude-forge`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Modifying System Services

## Executive Assessment

The development guidance recommends restarting Claude with `--dangerously-skip-permissions` to streamline implementation work. That choice removes review from browser automation, file edits, tests, and shell commands across the entire session. The convenience benefit does not justify the resulting host-wide authority.

## Audited Source Excerpt

```text
claude --dangerously-skip-permissions
```

Source: `references/playwright-agents.md:146`

Location: `references/playwright-agents.md:146`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

A developer following the referenced Playwright workflow reaches a direct recommendation to start Claude with the dangerous flag. From that point, the agent can generate tests, modify the repository, operate a browser, and execute commands without individual confirmation. The audit did not start an unrestricted development session. The location and wording of the recommendation show that it is operational guidance, not a warning or a prohibited example.

## Closing Analysis

Development agents routinely consume project-controlled text and browser content, both of which may be adversarial. Removing the approval layer exposes the host to actions that exceed the user's specific coding request. Tool allowlists or a disposable sandbox would preserve the workflow without creating the same damage path.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its recommended operating mode unnecessarily removes the control that limits harmful development-agent actions.
- Evidence: `references/playwright-agents.md:146` and the execution-path analysis above.

## Excluded False Positives

- The use of Playwright and parallel development is not itself suspicious. The verdict turns on the affirmative recommendation to disable all permission prompts.

## Residual and Unresolved Risks

- The risk grows when the target repository contains hooks, generated scripts, or prompt-like documentation that the agent may follow.

## Repository and Provenance Findings

- The assessment is scoped to `immacualate/claude-forge` at version `7749ad95547d` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Following the recommended setup moves the full development session into a permission-bypassed execution mode.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its recommended operating mode unnecessarily removes the control that limits harmful development-agent actions.
