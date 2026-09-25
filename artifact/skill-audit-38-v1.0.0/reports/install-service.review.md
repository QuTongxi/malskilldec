# Review: install-service

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `install-service` skill package, its normal entry path, and its directly referenced files.

Version identifier: `f0678971c7`

GitHub repository: `Repository no longer available`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Modifying System Services

## Executive Assessment

The skill converts an arbitrary script or inferred manifest into a persistent service and starts it immediately. In freestyle mode it derives the executable and trigger from project-controlled material without validating ownership, trust, or the presence of secrets in environment values. A bad inference or manipulated manifest is therefore promoted into code that runs across reboots.

## Audited Source Excerpt

```text
Cross-platform service installer for AI agents. Installs, manages, and uninstalls background services and scheduled jobs on Linux (systemd), macOS (launchd), and Windows (Task Scheduler).
Use systemd user services (`~/.config/systemd/user/`) unless root/system-wide is explicitly required.
If trigger type cannot be inferred, ask exactly one clarifying question.
```

Source: `SKILL.md:1-20,51-72`

Location: `SKILL.md:1-20,51-72`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

If no service manifest exists, the agent reads the target and infers its name, command, working directory, and trigger. It writes the result to systemd, launchd, or Task Scheduler, embeds supplied environment values, and enables the unit. No service was registered during review. The instructions show no mandatory command allowlist, absolute-path validation, secret-handling rule, ownership check, or install-time diff before activation.

## Closing Analysis

Service managers are legitimate persistence mechanisms, and a user may genuinely want a daemon. The unsafe step is treating unverified, inferred project content as sufficient authority for an automatically restarted program. Once installed, an error or injected command repeats without another user decision and may also expose credentials stored in the unit definition.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because it turns insufficiently validated project content into durable, repeatedly executed host code.
- Evidence: `SKILL.md:1-20,51-72` and the execution-path analysis above.

## Excluded False Positives

- The finding is not based on the words systemd, launchd, Task Scheduler, or persistence. It is based on immediate persistence of unvalidated inferred commands and environment values.

## Residual and Unresolved Risks

- The templates also omit a minimum-privilege policy and a mandatory pre-install backup, increasing the cost of a mistaken service definition.

## Repository and Provenance Findings

- The original repository is no longer available. This assessment is limited to the archived sample and the version identifier recorded above.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Project-derived commands and environment values are written into an auto-starting service that persists across reboots.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because it turns insufficiently validated project content into durable, repeatedly executed host code.
