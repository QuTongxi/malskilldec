# Review: baoyu-danger-gemini-web

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `baoyu-danger-gemini-web` skill package, its normal entry path, and its directly referenced files.

Version identifier: `3b13b25f`

GitHub repository: `siatwangmin/coco-skills`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Improper Credential Handling

## Executive Assessment

The skill launches a dedicated Chrome profile, extracts the resulting Google and Gemini session cookies through CDP, and persists the full cookie map for later reuse. The cache is created without an explicit restrictive mode, leaving reusable session material readable under ordinary process defaults. Compromise of that file can become compromise of the signed-in Google session.

## Audited Source Excerpt

```text
const args = [
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profileDir}`,
  '--no-first-run',
  '--no-default-browser-check',
  '--disable-popup-blocking',
  'https://gemini.google.com/app',
];
```

Source: `load-browser-cookies.ts:165-179,205-249,276-293; cookie-file.ts:64-79`

Location: `load-browser-cookies.ts:165-179,205-249,276-293; cookie-file.ts:64-79`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

On first use, the user signs in through a visible Chrome window. The loader then reads cookies from the dedicated profile and writes them to a cross-session cache used by subsequent web requests. The audit did not authenticate to a real Google account. An isolated file-creation test using the same write semantics produced mode `0644`, demonstrating that the cache may be readable by other users or processes on the same machine.

## Closing Analysis

Using a dedicated profile distinguishes this design from silently stealing a daily browser profile, but it does not make the extracted cookies harmless. They are still bearer material with account authority. A `0600` file, a protected directory, or an operating-system credential store could preserve the feature without exposing the session.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because normal use persists high-authority session credentials in a form that can expose the user's account.
- Evidence: `load-browser-cookies.ts:165-179,205-249,276-293; cookie-file.ts:64-79` and the execution-path analysis above.

## Excluded False Positives

- Uploading a user-selected reference image to Google and using localhost CDP were excluded from the finding; no evidence shows cookies being sent to the skill author's server.

## Residual and Unresolved Risks

- Cookie scope and lifetime were not reduced before storage, so the impact may extend beyond the immediate Gemini operation.

## Repository and Provenance Findings

- The assessment is scoped to `siatwangmin/coco-skills` at version `3b13b25f` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
A Google login is converted into a reusable plaintext cookie cache with insufficient filesystem protection.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because normal use persists high-authority session credentials in a form that can expose the user's account.
