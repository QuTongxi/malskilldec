# Review: install-openclaw-to-digitalocean

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `install-openclaw-to-digitalocean` skill package, its normal entry path, and its directly referenced files.

Version identifier: `9ca1d4edf7`

GitHub repository: `CodeAlive-AI/ceo-ai-os`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Improper Credential Handling; Suspicious Downloads; Unverifiable Dependencies / Potential Remote Prompt/Code Execution; Modifying System Services

## Executive Assessment

The guide promises that the DigitalOcean token will not be saved, yet it passes a Full Access token to `doctl auth init`, which creates a persistent local context. It also renders Telegram and LLM credentials into cloud-init user data that remains retrievable from instance metadata during the Droplet's lifetime. The user is therefore given an inaccurate account of where several high-value secrets will persist.

## Audited Source Excerpt

```text
| 0 | **DigitalOcean API token** | Open [cloud.digitalocean.com/account/api/tokens](https://cloud.digitalocean.com/account/api/tokens) → **Generate New Token** → name it `openclaw`, scope **Full Access** (or custom: read+write on Droplet, SSH Key, Firewall), expiry 90 days is fine → copy the `dop_v1_…` string. Asked once in Step 0. |
Я её никуда не сохраняю и не показываю обратно.
doctl auth init --context openclaw --access-token "$DO_TOKEN"
{{TELEGRAM_BOT_TOKEN}}
ANTHROPIC_API_KEY=<key>
OPENROUTER_API_KEY=<key>
```

Source: `SKILL.md:81-87,169-180,277-305; scripts/cloud-init.yaml:490-497`

Location: `SKILL.md:81-87,169-180,277-305; scripts/cloud-init.yaml:490-497`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

Step zero asks for a Full Access DigitalOcean token and says it will be requested only once and neither stored nor echoed. The deployment then initializes a named `doctl` context with that token and embeds additional provider keys in the cloud-init template used to create a paid Droplet. No cloud account was used and no resource was created during review. The persistence behavior follows from `doctl`'s authentication command and from the distributed user-data template.

## Closing Analysis

Creating infrastructure requires authorization, but it does not require a misleading no-storage claim or lifetime-readable metadata containing unrelated long-lived credentials. Scoped tokens, temporary credentials, and post-boot secret injection can accomplish the deployment. The current design creates avoidable account exposure while preventing informed consent.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its normal deployment misrepresents and unnecessarily expands the persistence of powerful cloud and application credentials.
- Evidence: `SKILL.md:81-87,169-180,277-305; scripts/cloud-init.yaml:490-497` and the execution-path analysis above.

## Excluded False Positives

- Droplet creation, systemd services, and cloud fees are declared features and were not used as evidence of maliciousness. The contradiction and secret-persistence paths are decisive.

## Residual and Unresolved Risks

- Mutable NodeSource setup, `openclaw@latest`, and additional remote install scripts further enlarge the deployment-time supply-chain surface.

## Repository and Provenance Findings

- The assessment is scoped to `CodeAlive-AI/ceo-ai-os` at version `9ca1d4edf7` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Deployment persistently stores a broadly scoped cloud token and places several long-lived secrets in instance user data despite saying the token will not be saved.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its normal deployment misrepresents and unnecessarily expands the persistence of powerful cloud and application credentials.
