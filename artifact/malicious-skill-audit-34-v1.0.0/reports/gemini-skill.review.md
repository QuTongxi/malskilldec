# Review: gemini-skill

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `gemini-skill` skill package, its normal entry path, and its directly referenced files.

Version identifier: `13681441c4b4`

GitHub repository: `pcx-wave/gemini-skill`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Modifying System Services

## Executive Assessment

The delegation helper defaults implementation requests to Gemini's `--yolo` mode. As a result, the delegated model can write files and invoke tools without a separate approval, even when the caller did not explicitly request that safety mode. The dangerous behavior is therefore part of the default implementation path.

## Audited Source Excerpt

```text
MODE="${4:-impl}"
APPROVAL_FLAG="--yolo"
MODE_LABEL="impl (yolo)"
gemini -p "$PROMPT" $APPROVAL_FLAG -o stream-json
```

Source: `tools/gemini-delegate:29,46-47; SKILL.md:116`

Location: `tools/gemini-delegate:29,46-47; SKILL.md:116`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

When the fourth argument is omitted, `gemini-delegate` selects `impl`, assigns `--yolo` to the approval flag, and runs the Gemini CLI with that flag. The wrapper then streams the delegated model's activity and reports the resulting changes. No real repository was modified during review. The default value and final command line establish that an ordinary implementation call reaches the automatic-approval mode.

## Closing Analysis

Delegating a coding task does not authorize every action the second model may infer from it. The same feature could use a sandbox, a bounded tool set, or explicit approval for proposed changes. Making `--yolo` the default transfers too much authority and creates a direct path from model error or injected content to local damage.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because the default delegation mode grants an external model unsupervised authority to change the user's workspace.
- Evidence: `tools/gemini-delegate:29,46-47; SKILL.md:116` and the execution-path analysis above.

## Excluded False Positives

- The verdict does not rest on using Gemini or on model delegation. It rests on the helper's default, unconditional approval of the delegated model's tools.

## Residual and Unresolved Risks

- The streamed output may make activity visible after the fact, but observability does not restore the missing pre-execution control.

## Repository and Provenance Findings

- The assessment is scoped to `pcx-wave/gemini-skill` at version `13681441c4b4` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
A normal implementation delegation launches Gemini with automatic approval for its tool and file operations.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because the default delegation mode grants an external model unsupervised authority to change the user's workspace.
