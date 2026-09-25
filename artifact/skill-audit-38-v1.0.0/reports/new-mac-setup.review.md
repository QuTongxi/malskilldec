# Review: new-mac-setup

## Final Verdict

BENIGN

Confidence: HIGH

Audit object:
The `new-mac-setup` skill package, its normal entry path, and its directly referenced files.

Version identifier: `c2a83dc060276b83ce6ce22cf74d316bb5d35b2d`

GitHub repository: `biyearly-mesothelioma790/skills`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Unverifiable Dependencies / Potential Remote Prompt/Code Execution; Modifying System Services

## Executive Assessment

This skill performs broad system changes, but those changes are the stated purpose of a new-machine setup and are selected after an initial interview. The scripts are organized as idempotent stages, and no hidden upload, unrelated payload, or covert persistence was identified. The remaining weaknesses are configuration-quality issues rather than evidence that use of the skill harms the machine.

## Audited Source Excerpt

```text
Fully automated new Mac setup for fullstack web developers and AI engineers. Generates and executes idempotent shell scripts to install dev tools, CLI utilities, GUI apps, AI/ML tooling, shell config, and macOS preferences.
ssh-keygen -t ed25519 -C "shawnthe1@gmail.com" -f "$HOME/.ssh/id_ed25519" -N ""
```

Source: `new-mac-setup/SKILL.md:3-20,41-80; scripts/04-dev-environment.sh:31-41`

Location: `new-mac-setup/SKILL.md:3-20,41-80; scripts/04-dev-environment.sh:31-41`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The workflow asks for the user's Git identity, hardware profile, and tools to omit before generating eight setup scripts. Those scripts install declared packages, update dotfiles and macOS preferences, and create an SSH key when execution is requested. The complete workflow was not run on the non-macOS audit host. Static inspection found the actions consistent with the advertised workstation bootstrap and found no unrelated network destination or payload substitution.

## Closing Analysis

The passwordless SSH key and hard-coded author email should be corrected, particularly on shared machines. They do not, on the present evidence, form a hidden or severe damage chain. Because the user is explicitly asking to configure a new Mac and is shown the scope first, the high level of system access is proportionate to the task.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: USER_EXPLICIT_OPTION
- Security relevance: MEDIUM
- Functional necessity: PARTIALLY_NECESSARY
- Verdict impact: SUPPORTS_BENIGN
- Assessment: The skill is benign because its normal effects match the requested machine setup and no concealed harmful path was found.
- Evidence: `new-mac-setup/SKILL.md:3-20,41-80; scripts/04-dev-environment.sh:31-41` and the execution-path analysis above.

## Excluded False Positives

- Package installation, `defaults` changes, and dotfile replacement were not treated as malicious because they are disclosed, expected outputs of the requested bootstrap.

## Residual and Unresolved Risks

- The generated key lacks a passphrase and may receive the wrong comment email; both are genuine hardening defects that should be fixed.

## Repository and Provenance Findings

- The assessment is scoped to `biyearly-mesothelioma790/skills` at version `c2a83dc060276b83ce6ce22cf74d316bb5d35b2d` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
A user-approved bootstrap installs the selected development stack and applies disclosed workstation preferences through staged scripts.

Security delta:
Normal use does not establish a concrete path to host, account, or data harm.

## Final Rationale

The skill is benign because its normal effects match the requested machine setup and no concealed harmful path was found.
