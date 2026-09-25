# Review: itr-prep-skill

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `itr-prep-skill` skill package, its normal entry path, and its directly referenced files.

Version identifier: `96859bc1e03a`

GitHub repository: `NidheeshJain/itr-prep-skill`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Modifying System Services

## Executive Assessment

The tax-preparation workflow instructs the user to launch Claude with all permission checks disabled from a directory containing identity, income, and tax records. That flag applies to the entire session rather than to a narrow document-reading operation. A mistake or injected instruction can consequently reach sensitive files and system tools without another approval boundary.

## Audited Source Excerpt

```text
cd ~/Desktop/ITR
claude --dangerously-skip-permissions
```

Source: `README.md:43`

Location: `README.md:43`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The documented setup changes into the tax workspace and invokes `claude --dangerously-skip-permissions`. Once started, the agent may read and organize the requested records, but any later tool call receives the same unrestricted treatment. The review did not open a real tax directory or start such a session. The quoted command is sufficient to establish the permission state that normal use would create.

## Closing Analysis

Preparing a return requires access to selected documents, not unconditional authority over every tool for the life of the session. The skill turns a narrowly scoped administrative task into an unrestricted agent session in one of the user's most sensitive directories. That avoidable security degradation creates a concrete risk of local data loss or disclosure.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious under the stated standard because its normal setup removes the safeguards that would otherwise contain harmful actions around highly sensitive records.
- Evidence: `README.md:43` and the execution-path analysis above.

## Excluded False Positives

- The verdict is not based on tax documents being sensitive by themselves; it is based on the explicit session-wide permission bypass used while those documents are in scope.

## Residual and Unresolved Risks

- The exact downstream damage depends on later prompts and files, but the missing approval boundary is already established by the launch command.

## Repository and Provenance Findings

- The assessment is scoped to `NidheeshJain/itr-prep-skill` at version `96859bc1e03a` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
A routine tax-preparation request launches an unrestricted agent inside the user's tax-record directory.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious under the stated standard because its normal setup removes the safeguards that would otherwise contain harmful actions around highly sensitive records.
