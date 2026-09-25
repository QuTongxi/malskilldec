# Review: create-singbox-vpn

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `create-singbox-vpn` skill package, its normal entry path, and its directly referenced files.

Version identifier: `82e713328b`

GitHub repository: `Repository no longer available`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Unverifiable Dependencies / Potential Remote Prompt/Code Execution; Modifying System Services

## Executive Assessment

The deployment workflow installs and enables Docker without a second confirmation, pulls mutable `latest` images, and takes over common web and VPN ports. It does not require a snapshot of the existing host configuration or provide a reliable rollback before changing services. On a server that already carries workloads, an ordinary run can therefore interrupt service and replace trusted network configuration.

## Audited Source Excerpt

```text
If detection fails because Docker or Compose is missing, tell the user briefly that Docker/Compose is not present and that the skill will install it automatically, then run the installer below. Do not ask for confirmation.
$SUDO apt-get install -y ca-certificates curl gnupg docker.io
$SUDO systemctl enable --now docker >/dev/null 2>&1 || true
"${SSH_BASE[@]}" "$DOCKER pull caddy:latest && $DOCKER pull ghcr.io/sagernet/sing-box:latest"
restart: always
network_mode: host
ports:
  - "80:80"
```

Source: `SKILL.md:145-177,198-205; assets/docker-compose.yml:1-24`

Location: `SKILL.md:145-177,198-205; assets/docker-compose.yml:1-24`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

If Docker Compose is absent, the skill explicitly says not to ask for confirmation before installing packages and enabling Docker. It then pulls `caddy:latest` and `sing-box:latest`, uploads its own configuration, and starts always-restarting containers using host networking and fixed ports. No server was contacted during review. Static inspection also confirmed that the subscription token is high entropy and enforced by Caddy; that mechanism is not the basis of this finding.

## Closing Analysis

Deploying a VPN necessarily changes a server, but responsible automation first checks for port conflicts, records the current state, pins artifacts, and gives the operator a recoverable plan. This workflow skips those controls while acting automatically. The resulting availability and configuration damage is a property of normal use, regardless of the author's motive.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its ordinary installation can cause immediate service disruption and persistent network reconfiguration without adequate safeguards.
- Evidence: `SKILL.md:145-177,198-205; assets/docker-compose.yml:1-24` and the execution-path analysis above.

## Excluded False Positives

- The subscription query token was verified as real access control and was not misreported as decorative. The verdict concerns automatic system changes, mutable images, and port takeover.

## Residual and Unresolved Risks

- Reliance on third-party `sslip.io` or `nip.io` names adds certificate, availability, and namespace-control risks for long-lived deployments.

## Repository and Provenance Findings

- The original repository is no longer available. This assessment is limited to the archived sample and the version identifier recorded above.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
A normal deployment installs and enables Docker, pulls mutable images, and replaces network services on fixed ports without first preserving the existing state.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its ordinary installation can cause immediate service disruption and persistent network reconfiguration without adequate safeguards.
