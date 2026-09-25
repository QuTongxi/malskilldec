# Review: devops

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `devops` skill package, its normal entry path, and its directly referenced files.

Version identifier: `c52ad1e`

GitHub repository: `H3nSte1n/skills`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Modifying System Services

## Executive Assessment

The recommended server setup creates a persistent SSH principal with two independent routes to root-equivalent control: passwordless unrestricted sudo and membership in the Docker group. This authority is far broader than the bounded operations normally required for log inspection or service management. Compromise of the agent, its key, or its input chain becomes compromise of the entire host.

## Audited Source Excerpt

```text
agentops ALL=(ALL) NOPASSWD:ALL
usermod -aG docker agentops
AllowUsers agentops
```

Source: `README.md:204-281; SKILL.md:87-95; domains/docker.md`

Location: `README.md:204-281; SKILL.md:87-95; domains/docker.md`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The setup creates the `agentops` account, installs a long-lived SSH key, places `agentops ALL=(ALL) NOPASSWD:ALL` in sudo policy, and adds the same account to the Docker group. The SSH configuration also permits that identity to log in remotely. No server configuration was changed during review. The distributed configuration text establishes both privilege-escalation routes without needing to exercise them.

## Closing Analysis

Remote operations can be supported with command-specific sudo rules, audited wrappers, or constrained container interfaces. Granting a general root shell is not a technical prerequisite. Because the skill persistently removes that separation, a later key leak or prompt injection can take over the host without exploiting any additional vulnerability.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its normal setup collapses the server's privilege boundary and makes full host compromise a single-credential event.
- Evidence: `README.md:204-281; SKILL.md:87-95; domains/docker.md` and the execution-path analysis above.

## Excluded False Positives

- SSH, sudo, and Docker are not malicious by themselves. The finding is based on the deliberate combination of remote login, unrestricted NOPASSWD sudo, and Docker-daemon control in one unattended identity.

## Residual and Unresolved Risks

- The broad privilege also weakens forensic attribution because actions can be performed through either sudo or Docker with little interactive evidence.

## Repository and Provenance Findings

- The assessment is scoped to `H3nSte1n/skills` at version `c52ad1e` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Installation leaves an remotely accessible agent account with permanent, non-interactive root-equivalent privileges.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its normal setup collapses the server's privilege boundary and makes full host compromise a single-credential event.
