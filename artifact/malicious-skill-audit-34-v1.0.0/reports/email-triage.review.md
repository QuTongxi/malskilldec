# Review: email-triage

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `email-triage` skill package, its normal entry path, and its directly referenced files.

Version identifier: `a1ad42be327c`

GitHub repository: `huifeideyu-1121/email-triage`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Modifying System Services

## Executive Assessment

The skill combines a persistent LaunchAgent with a headless Claude invocation that disables permission checks. Email is untrusted external input, and the scheduled job runs when the user may not be present to review what that input causes the agent to do. This creates a durable, unattended route from incoming messages to an unrestricted local agent.

## Audited Source Excerpt

```text
cp launchd/com.example.email-triage.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.example.email-triage.plist
"$CLAUDE" -p "$PROMPT" --dangerously-skip-permissions >> "$LOG" 2>&1
```

Source: `README.md:93-95; scripts/run_daily.sh:21`

Location: `README.md:93-95; scripts/run_daily.sh:21`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The installation instructions copy a plist into the user's LaunchAgents directory and load it with `launchctl`. On each scheduled run, `run_daily.sh` invokes Claude with `--dangerously-skip-permissions` to read recent mail, classify it, write a digest, and optionally change message state. No mailbox or launch service was touched during review. The plist and runner nevertheless establish that the unsafe mode recurs automatically across sessions.

## Closing Analysis

A daily digest can be implemented with a limited mailbox token and a fixed, non-agentic processor. This design instead gives externally supplied mail content influence over an unattended process with broad local authority. The persistent scheduling is not the problem on its own; the harm comes from what it repeatedly launches.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because normal installation establishes an unattended and persistent execution channel from untrusted email to a fully empowered local agent.
- Evidence: `README.md:93-95; scripts/run_daily.sh:21` and the execution-path analysis above.

## Excluded False Positives

- LaunchAgents and email automation are legitimate mechanisms. The finding depends on their combination with untrusted mail content and a recurring permission-bypassed agent.

## Residual and Unresolved Risks

- Optional actions such as marking messages read may create additional integrity loss, although the broader unrestricted execution path is already decisive.

## Repository and Provenance Findings

- The assessment is scoped to `huifeideyu-1121/email-triage` at version `a1ad42be327c` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Installation creates a recurring background job that feeds recent email to an unrestricted Claude session.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because normal installation establishes an unattended and persistent execution channel from untrusted email to a fully empowered local agent.
