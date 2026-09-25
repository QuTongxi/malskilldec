# Review: chanjing-credentials-guard

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `chanjing-credentials-guard` skill package, its normal entry path, and its directly referenced files.

Version identifier: `fce55367`

GitHub repository: `chanjing-ai/chan-skills`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Improper Credential Handling

## Executive Assessment

The credential helper prints a complete Chanjing bearer token whether it reuses a cached token or obtains a new one. The token can directly authorize account actions, so placing it on stdout exposes it to the calling agent and any transcript or log collector. The helper could instead return the token inside the consuming process.

## Audited Source Excerpt

```text
if token and expire_in > now + BUFFER_SECONDS:
    print(token)
    return 0

data["access_token"] = new_token
print(new_token)
return 0
```

Source: `scripts/chanjing_get_token.py:106,131; SKILL.md:162-184`

Location: `scripts/chanjing_get_token.py:106,131; SKILL.md:162-184`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

On a cache hit, `chanjing_get_token.py` executes `print(token)` and returns. On refresh, it stores the new access token and again prints the full value. The review exercised this path only with `FAKE_TOKEN_DYNAMIC_TEST_ONLY` and a future expiration time; stdout reproduced the fake token exactly. That isolated test confirms reachability without exposing a real account.

## Closing Analysis

Token acquisition from Chanjing's official endpoint is legitimate, but stdout is an unnecessarily broad handoff boundary. Other code in the same repository can call the authentication routine in process, showing that disclosure is not required for functionality. The ordinary helper path therefore creates a concrete and avoidable credential leak.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its routine credential path exposes a live bearer token beyond the process that needs it.
- Evidence: `scripts/chanjing_get_token.py:106,131; SKILL.md:162-184` and the execution-path analysis above.

## Excluded False Positives

- The audit does not treat token refresh, local caching, or communication with Chanjing's official API as malicious; only the complete token disclosure supports the verdict.

## Residual and Unresolved Risks

- A cached token may remain valid after it appears in a transcript, allowing delayed misuse until expiration or revocation.

## Repository and Provenance Findings

- The assessment is scoped to `chanjing-ai/chan-skills` at version `fce55367` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Obtaining or reusing a Chanjing token emits the full bearer credential to stdout.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its routine credential path exposes a live bearer token beyond the process that needs it.
