# Review: webclaw3

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `webclaw3` skill package, its normal entry path, and its directly referenced files.

Version identifier: `bda05b23`

GitHub repository: `fatmind/webclaw3`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Malicious Code; Modifying System Services

## Executive Assessment

WebClaw exposes a logged-in Chrome session through a localhost relay that has no token, Origin check, or per-operation authorization. Its extension can inject scripts across all URLs and relax browser protections, while relay clients can request page evaluation, form entry, and submission. The result is an unauthenticated control surface over the user's live web identities.

## Audited Source Excerpt

```text
/api/call
page.eval
<all_urls>
tabs
scripting
declarativeNetRequest
```

Source: `SKILL.md:57-66,115-181,235-245; scripts/relay.mjs:173-221,230-358; extension ZIP/manifest.json,background.js`

Location: `SKILL.md:57-66,115-181,235-245; scripts/relay.mjs:173-221,230-358; extension ZIP/manifest.json,background.js`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The doctor process starts the relay on `127.0.0.1:3459`, and the browser extension connects to it with broad `tabs`, `scripting`, and network-rule permissions. API and WebSocket calls can then invoke operations such as `page.eval` against the current browser state. No action was performed in a real signed-in browser. Source review confirmed that the relay does not authenticate callers or bind them to a specific origin, tab, or scope.

## Closing Analysis

Loopback binding prevents direct Internet exposure, but it does not authenticate local processes or web-origin interactions capable of reaching localhost. Anyone who reaches the relay can act with the user's existing sessions. A session token, strict Origin handling, a separate browser profile, and per-tab consent are all feasible controls; their absence makes normal use damaging.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because it exposes high-value browser sessions through an unprotected control channel that can cause direct account and data harm.
- Evidence: `SKILL.md:57-66,115-181,235-245; scripts/relay.mjs:173-221,230-358; extension ZIP/manifest.json,background.js` and the execution-path analysis above.

## Excluded False Positives

- The report does not treat localhost, a browser extension, or automation as malicious in isolation. The complete unauthenticated path from the relay to an all-sites, logged-in browser is the decisive chain.

## Residual and Unresolved Risks

- The first-connection-wins behavior and caller-controlled logging options introduce additional opportunities for relay capture and information disclosure.

## Repository and Provenance Findings

- The assessment is scoped to `fatmind/webclaw3` at version `bda05b23` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Starting the relay turns the user's authenticated browser into an unauthenticated local API for script execution and transaction submission.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because it exposes high-value browser sessions through an unprotected control channel that can cause direct account and data harm.
