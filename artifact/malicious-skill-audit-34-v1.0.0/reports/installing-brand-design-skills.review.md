# Review: installing-brand-design-skills

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `installing-brand-design-skills` skill package, its normal entry path, and its directly referenced files.

Version identifier: `d021309693`

GitHub repository: `Repository no longer available`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Unverifiable Dependencies / Potential Remote Prompt/Code Execution; Improper Credential Handling

## Executive Assessment

The skill asks users to execute an unpinned `npx design-like` package and let it write directly into agent instruction directories. The sampled distribution is also materially inconsistent with that description: it contains a complete hotel-chat application whose browser code can load an OpenAI key. The unexplained content mismatch makes the source unsuitable for modifying an agent trust root.

## Audited Source Excerpt

```text
npx design-like <brand>
/*
 * OpenAI Integration Module
 * Hilton Chat Widget
 */
let OPENAI_API_KEY = 'YOUR_OPENAI_API_KEY_HERE';
const PROXY_URL = '/api/chat';
```

Source: `SKILL.md:16-34,38-70; openai.js:1-13,54-82`

Location: `SKILL.md:16-34,38-70; openai.js:1-13,54-82`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

Normal guidance runs the latest `design-like` package from a project root and targets `.claude/skills`, `.cursor/rules`, `.vscode/instructions`, or `.agent/skills`. The same archived sample contains numerous unrelated hotel UI modules, including a client-side configuration path for an OpenAI key. The audit did not run the npx package or insert a real credential. Offline inventory confirmed that the package identity and distributed contents cannot be reconciled from the available provenance.

## Closing Analysis

The placeholder string is not itself a leaked key, and unrelated files are not automatically executable. The serious issue is that an unidentified, mismatched distribution requests live remote execution and writes its output into locations future agents trust automatically. That installation result can alter subsequent agent behavior and expose credentials through the bundled client design.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because normal installation gives unverifiable, inconsistently packaged content control over future agent instructions.
- Evidence: `SKILL.md:16-34,38-70; openai.js:1-13,54-82` and the execution-path analysis above.

## Excluded False Positives

- `YOUR_OPENAI_API_KEY_HERE` was treated as a placeholder, not as a secret. The verdict relies on the provenance mismatch, mutable execution, and trust-root destination.

## Residual and Unresolved Risks

- The original repository and a fixed `design-like` package version are unavailable, so the reason for bundling the hotel application cannot be resolved.

## Repository and Provenance Findings

- No trustworthy source repository could be identified for the archived distribution, and its contents materially differ from the stated brand-skill purpose.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
An unpinned remote package from a mismatched distribution writes new instructions into the user's agent and IDE trust directories.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because normal installation gives unverifiable, inconsistently packaged content control over future agent instructions.
