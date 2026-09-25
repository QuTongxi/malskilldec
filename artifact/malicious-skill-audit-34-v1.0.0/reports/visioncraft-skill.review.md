# Review: visioncraft-skill

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `visioncraft-skill` skill package, its normal entry path, and its directly referenced files.

Version identifier: `f31e7b4`

GitHub repository: `BAI-32/visioncraft-skill`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Improper Credential Handling

## Executive Assessment

The setup instructions verify the Agnes API credential by printing the complete environment-variable value. That output becomes part of the terminal stream and may also be retained in agent transcripts or diagnostic logs. A presence check or masked suffix would provide the same confirmation without creating another plaintext copy of a long-lived secret.

## Audited Source Excerpt

```text
Verify with `echo $env:AGNES_API_KEY`.
```

Source: `SKILL.md:28-40`

Location: `SKILL.md:28-40`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

After the user stores `AGNES_API_KEY`, the skill tells the agent to run `echo $env:AGNES_API_KEY`. This reveals the full credential before any image or video request is made. No genuine key was used during review. Inspection of the business workflow confirmed that it only needs the variable to be present; it does not need the agent to display the value.

## Closing Analysis

Sending a key to the service that issued it is expected authentication. Printing that key into an additional observation and logging channel is not. Because the disclosure occurs in the ordinary configuration path and has a lossless safer replacement, it constitutes direct credential harm.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because normal setup unnecessarily discloses a reusable account credential.
- Evidence: `SKILL.md:28-40` and the execution-path analysis above.

## Excluded False Positives

- The finding does not classify environment variables or Agnes authentication as malicious. It is limited to the unnecessary full-value echo.

## Residual and Unresolved Risks

- Any terminal recording, support bundle, or shared agent transcript may retain the disclosed key after the configuration step completes.

## Repository and Provenance Findings

- The assessment is scoped to `BAI-32/visioncraft-skill` at version `f31e7b4` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Credential verification copies the complete Agnes API key into visible output and potentially persistent logs.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because normal setup unnecessarily discloses a reusable account credential.
