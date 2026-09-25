# Review: web-use

## Final Verdict

BENIGN

Confidence: HIGH

Audit object:
The `web-use` skill package, its normal entry path, and its directly referenced files.

Version identifier: `b87ffe67af`

GitHub repository: `Repository no longer available`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Improper Credential Handling; Third-Party Content Exposure

## Executive Assessment

The skill supports remote browser sessions, but it treats token-bearing session URLs as secrets and implements concrete controls around them. One-off extraction is the default; persistent sessions are reserved for repeated same-site work, output is redacted, files are written with mode `0600`, and a stop operation is provided. No path to an unrelated recipient or avoidable local security downgrade was found.

## Audited Source Excerpt

```text
Use Browserless `/session` sparingly. It is not the default for one-off reads.
Use it only when repeated same-site BQL/CDP work genuinely benefits from persisted cookies, localStorage, sessionStorage, or cache. Session URLs include the Browserless token and act as bearer credentials.
Token-bearing URLs stored at 0600; run `stop` when finished.
```

Source: `SKILL.md:65-77,151-157; scripts/browserless_session.py:53-80,118-135,221-236`

Location: `SKILL.md:65-77,151-157; scripts/browserless_session.py:53-80,118-135,221-236`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The agent selects a Browserless session only when stateful work is actually needed. The helper accepts the provider token and session URL, strips them from displayed output, rejects unsafe standard-stream handling, stores state in a restrictive file, and can terminate the remote session. Testing used a fake token: both the token and the token-bearing URL appeared as `<redacted>`, and the created file had mode `0600`. The remote service was not contacted.

## Closing Analysis

Third-party page content can still attempt prompt injection, and a remote browser provider necessarily receives requested browsing traffic. Those are disclosed properties of the chosen service, not hidden damage created by the skill. The observed implementation narrows rather than expands the credential exposure that triggered the original alert.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: USER_EXPLICIT_OPTION
- Security relevance: MEDIUM
- Functional necessity: NECESSARY
- Verdict impact: SUPPORTS_BENIGN
- Assessment: The skill is benign because the reviewed workflow contains the credential and session risks inherent in its declared browser-service function.
- Evidence: `SKILL.md:65-77,151-157; scripts/browserless_session.py:53-80,118-135,221-236` and the execution-path analysis above.

## Excluded False Positives

- Sending a Browserless token to Browserless or using TinyFish at the user's request is expected authentication, not exfiltration to an unrelated party.

## Residual and Unresolved Risks

- The calling agent should still isolate third-party page content from high-impact tools, because redaction does not solve indirect prompt injection.

## Repository and Provenance Findings

- The original repository is no longer available. This assessment is limited to the archived sample and the version identifier recorded above.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Stateful remote browsing is optional, token output is redacted, session state is stored at `0600`, and the user can explicitly stop the session.

Security delta:
Normal use does not establish a concrete path to host, account, or data harm.

## Final Rationale

The skill is benign because the reviewed workflow contains the credential and session risks inherent in its declared browser-service function.
