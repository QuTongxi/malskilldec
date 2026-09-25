# Review: codymaster

## Final Verdict

BENIGN

Confidence: HIGH

Audit object:
The `codymaster` skill package, its normal entry path, and its directly referenced files.

Version identifier: `14cd03c9b12b3087494371e5ccef81005182dcaa`

GitHub repository: `tody-agent/codymaster`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Unverifiable Dependencies / Potential Remote Prompt/Code Execution; Modifying System Services

## Executive Assessment

The repository contains powerful installation and agent-management features, but the inspected package does not reveal a concealed payload or an automatic safety bypass. Its guardian component explicitly detects destructive command patterns, including recursive deletion and hard resets. Repository-wide alerts that originated in test material or defensive regular expressions do not establish malicious behavior.

## Audited Source Excerpt

```text
npm install -g codymaster && cm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
/\brm\s+-rf\b/i,
/\bcurl\s+.*\|\s*(ba)?sh\b/i,
/\bgit\s+reset\s+--hard\b/,
/\bDROP\s+TABLE\b/i,
```

Source: `README.md:57-92; scripts/install.sh:87-140; src/guardian-core.ts:14-31`

Location: `README.md:57-92; scripts/install.sh:87-140; src/guardian-core.ts:14-31`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The installer checks for Node and npm, uses a versioned NVM installer when necessary, installs the declared package, and deploys the selected skills. The audit did not perform the global npm installation. Offline inspection of the repository's large archive found readable Python, HTML, configuration, and matching bytecode rather than an unexplained executable loader. Searches also found no normal-use chain that replaces trusted downloads with an unrelated payload.

## Closing Analysis

The framework has supply-chain exposure because it installs packages, but that is not the same as demonstrated damage. The strongest suspicious strings occur in security tests or in rules intended to block harmful commands. With approval and guardian controls present, the current evidence does not support a malicious verdict.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: MEDIUM
- Functional necessity: PARTIALLY_NECESSARY
- Verdict impact: SUPPORTS_BENIGN
- Assessment: The skill is benign because the reviewed distribution aligns with its stated function and the suspected indicators resolve to tests or defensive controls.
- Evidence: `README.md:57-92; scripts/install.sh:87-140; src/guardian-core.ts:14-31` and the execution-path analysis above.

## Excluded False Positives

- XSS examples are test fixtures, and the `curl|bash`, `rm -rf`, and `git reset --hard` strings shown in guardian code are deny patterns rather than commands the skill executes.

## Residual and Unresolved Risks

- Use of a latest npm package and a mutable upstream installer still warrants pinning and integrity verification.

## Repository and Provenance Findings

- The identified repository revision and its large archive were inspected offline; no deceptive link replacement or unexplained native loader was found.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Installation deploys the declared coding-agent framework and enables a guardian that screens known destructive command patterns.

Security delta:
Normal use does not establish a concrete path to host, account, or data harm.

## Final Rationale

The skill is benign because the reviewed distribution aligns with its stated function and the suspected indicators resolve to tests or defensive controls.
