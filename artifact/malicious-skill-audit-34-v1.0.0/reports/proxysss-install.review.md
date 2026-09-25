# Review: proxysss-install

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `proxysss-install` skill package, its normal entry path, and its directly referenced files.

Version identifier: `2606da3876`

GitHub repository: `neko233-com/proxysss`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Suspicious Downloads; Unverifiable Dependencies / Potential Remote Prompt/Code Execution; Improper Credential Handling; Modifying System Services

## Executive Assessment

The one-click path downloads the mutable `main` installer and sends it directly to Bash or PowerShell. It then initializes configuration, installs a service that takes over the existing web entry points, and creates a fresh administrative account with the published credentials `root/root`. These defaults can disrupt an existing site and leave a predictable local control identity.

## Audited Source Excerpt

```text
& ([ScriptBlock]::Create((irm https://raw.githubusercontent.com/neko233-com/proxysss/main/scripts/install.ps1))) -Action install -Version latest
curl -fsSL https://raw.githubusercontent.com/neko233-com/proxysss/main/scripts/install.sh | bash
Admin credentials in fresh dev config: root / root
```

Source: `SKILL.md:10-30,62-69`

Location: `SKILL.md:10-30,62-69`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

When no checkout exists, the skill uses `curl | bash` or `irm` followed by dynamic PowerShell execution. The workflow initializes proxysss unless preservation is explicitly requested, then starts its service and reports the public and administrative endpoints. The installer was not run on the audit host. A read-only check of the referenced repository confirmed that the admin interface currently binds to loopback by default, but local processes can still reach it and the installation still changes the machine's active web configuration.

## Closing Analysis

Loopback binding reduces direct Internet exposure, but it does not make a fixed privileged password safe against local malware, lower-privilege users, or later binding mistakes. More importantly, the normal path executes unpinned remote code before replacing service configuration. The combination creates concrete integrity and availability harm even without proving a malicious current upstream payload.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its ordinary installation can disrupt existing services and weakens control of the replacement service.
- Evidence: `SKILL.md:10-30,62-69` and the execution-path analysis above.

## Excluded False Positives

- Neither GitHub nor localhost was treated as malicious. The verdict depends on mutable code execution, default service takeover, and a known administrative credential occurring together.

## Residual and Unresolved Risks

- If the administrative listener is later exposed beyond loopback, the default credential becomes an immediate remote takeover condition.

## Repository and Provenance Findings

- The skill was compared read-only with neko233-com/proxysss at the recorded revision; current loopback binding does not remove the installer and default-credential findings.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
One-click installation executes mutable remote code, replaces web-service configuration, and leaves a privileged `root/root` administrative login.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its ordinary installation can disrupt existing services and weakens control of the replacement service.
