# Review: evaluating-llms-harness

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `evaluating-llms-harness` skill package, its normal entry path, and its directly referenced files.

Version identifier: `b00510e`

GitHub repository: `immacualate/claude-forge`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Improper Credential Handling

## Executive Assessment

The authentication troubleshooting guide tells the agent to echo complete OpenAI and Anthropic API keys. This is presented as the response to an ordinary authentication failure, not as a redacted example. The procedure turns a connectivity problem into disclosure of two high-value credentials.

## Audited Source Excerpt

```text
Check API key:
echo $OPENAI_API_KEY  # Should print sk-...
echo $ANTHROPIC_API_KEY  # Should print sk-ant-...
```

Source: `references/api-evaluation.md:411-419`

Location: `references/api-evaluation.md:411-419`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

When an evaluation request fails authentication, the referenced guide proposes `echo $OPENAI_API_KEY` and `echo $ANTHROPIC_API_KEY`, with comments indicating the expected secret prefixes. A following agent would capture the exact values in its tool output before continuing diagnosis. No real credentials were echoed during this audit. The literal commands and their troubleshooting context are sufficient to establish the disclosure path.

## Closing Analysis

Authentication can be diagnosed by testing whether variables are set, checking length, or showing a masked suffix. None of those methods requires the full secret. Because the unsafe command is part of a common failure branch, use of the skill can directly leak production API access.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its documented diagnostic path needlessly exposes long-lived API credentials.
- Evidence: `references/api-evaluation.md:411-419` and the execution-path analysis above.

## Excluded False Positives

- The verdict is not based on the existence of API keys or on invoking provider APIs; it is based on revealing complete secret values during routine diagnosis.

## Residual and Unresolved Risks

- If both variables are configured, a single troubleshooting step may compromise accounts at two providers at once.

## Repository and Provenance Findings

- The assessment is scoped to `immacualate/claude-forge` at version `b00510e` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
An authentication error leads the agent to print complete OpenAI and Anthropic keys into its observable output.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its documented diagnostic path needlessly exposes long-lived API credentials.
