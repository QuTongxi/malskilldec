# Review: file-oon-claim

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `file-oon-claim` skill package, its normal entry path, and its directly referenced files.

Version identifier: `dbf8f5ae0d`

GitHub repository: `Repository no longer available`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Improper Credential Handling; Third-Party Content Exposure; Direct Money Access Detection

## Executive Assessment

The distributed skill hard-codes a named household's workstation, LAN address, container layout, and medical-claim workflow. It directs the agent to search raw Claude transcripts for base64 images, assemble diagnosis and identity data, publish a signed link, and send the resulting packet through DocuPost. It also places the DocuPost token directly in a shell command.

## Audited Source Excerpt

```text
This session runs on Dave's home desktop (`Gaming`), which reaches the Pi at `192.168.0.215`.
Dave is usually on iPad and can't upload files to the repo. He pastes photos into chat → extract them from the session transcript.
Send the packet PDF / a Supabase signed link to Dave for review.
docker exec -e DOCUPOST_API_TOKEN='<token>' health-claims python -m app.docupost
they're base64 in the session `.jsonl` transcript (`~/.claude/projects/<proj>/<id>.jsonl`). Walk the JSON ... decode, save into `docs/working/`.
```

Source: `SKILL.md:19-33,42-60,68-107`

Location: `SKILL.md:19-33,42-60,68-107`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

Normal use reads provider statements, member identifiers, dates of birth, addresses, diagnosis codes, tax identifiers, and a stored signature. If images were pasted from an iPad, the agent walks `~/.claude/projects/...jsonl` and decodes them from the transcript. The packet may be hosted through Supabase for review and is copied to a home Pi before submission; the API token is supplied inline to `docker exec`. No real transcript, PHI, token, or paid mailing was accessed during review.

## Closing Analysis

Submitting records to an insurer is the requested business purpose, and the final mailing has a confirmation gate. The harmful expansion occurs earlier: a reusable public skill discloses a private household topology, searches broad conversation records for medical images, creates an additional hosted copy of PHI, and exposes a token through command text. Those privacy losses are not removed by confirming the eventual postage charge.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because normal use unnecessarily broadens the exposure of medical data, household infrastructure, and a service credential.
- Evidence: `SKILL.md:19-33,42-60,68-107` and the execution-path analysis above.

## Excluded False Positives

- The report does not classify the insurer submission or DocuPost service as malicious by themselves. It relies on transcript mining, hard-coded personal infrastructure, extra PHI hosting, and command-line secret propagation.

## Residual and Unresolved Risks

- The referenced packet and DocuPost modules are missing, so signed-link lifetime, remote retention, and recipient-access controls could not be independently checked.

## Repository and Provenance Findings

- The original repository is no longer available. This assessment is limited to the archived sample and the version identifier recorded above.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
The agent mines raw session records for medical images, assembles and hosts a PHI packet, and passes a reusable mailing token through shell-visible text.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because normal use unnecessarily broadens the exposure of medical data, household infrastructure, and a service credential.
