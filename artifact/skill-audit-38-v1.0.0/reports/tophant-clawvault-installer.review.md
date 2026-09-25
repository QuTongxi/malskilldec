# Review: tophant-clawvault-installer

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `tophant-clawvault-installer` skill package, its normal entry path, and its directly referenced files.

Version identifier: `0.2.13 / a3d265e51a`

GitHub repository: `tophant-ai/ClawVault`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Malicious Code; Unverifiable Dependencies / Potential Remote Prompt/Code Execution; Modifying System Services

## Executive Assessment

ClawVault's quick installation configures an interception proxy and persistently sets `NODE_TLS_REJECT_UNAUTHORIZED=0` for the OpenClaw gateway. That environment variable disables certificate validation for all Node HTTPS traffic in the service, not only for a narrowly trusted local certificate. The proxy handles prompts and API keys, so loss of upstream authentication has especially serious consequences.

## Audited Source Excerpt

```text
"ssl_verify": False,
"intercept_hosts": [
    "api.openai.com",
    "api.anthropic.com",
    "api.siliconflow.cn",
    "*.openai.azure.com",
    "generativelanguage.googleapis.com"
]
Environment=HTTPS_PROXY=http://127.0.0.1:8765
Environment=NODE_TLS_REJECT_UNAUTHORIZED=0
pip install git+https://github.com/tophant-ai/ClawVault.git@main
```

Source: `clawvault_manager.py:360-373,450-505; SECURITY.md:156-184`

Location: `clawvault_manager.py:360-373,450-505; SECURITY.md:156-184`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The manager installs from a mutable GitHub `main`, generates a configuration with `ssl_verify` disabled, and, when a gateway service is found, injects HTTP and HTTPS proxy variables together with `NODE_TLS_REJECT_UNAUTHORIZED=0`. It then reloads systemd, making the change persistent. No real LLM traffic was intercepted and no service was modified during review. Source tracing confirmed the default configuration and service-environment write.

## Closing Analysis

A security proxy may need to inspect TLS, but it can install a dedicated CA, limit trust to one process, and continue verifying upstream certificates. Globally accepting invalid certificates is not required. The current default allows a man-in-the-middle endpoint to receive prompts and credentials that users believe are protected by HTTPS.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because it weakens HTTPS authentication around prompts and API keys in a persistent and unnecessarily broad way.
- Evidence: `clawvault_manager.py:360-373,450-505; SECURITY.md:156-184` and the execution-path analysis above.

## Excluded False Positives

- Local proxying and systemd integration are consistent with the advertised product. The finding is specifically about the persistent, process-wide TLS verification bypass.

## Residual and Unresolved Risks

- The installer also trusts mutable `main` without a checksum or signature, creating a second supply-chain path into the same sensitive traffic boundary.

## Repository and Provenance Findings

- The package points to the public ClawVault repository, whose own security documentation confirms that the mutable main-branch install lacks a checksum or signature.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Installation routes gateway traffic through a local interceptor while disabling Node's upstream certificate validation for the persistent service.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because it weakens HTTPS authentication around prompts and API keys in a persistent and unnecessarily broad way.
