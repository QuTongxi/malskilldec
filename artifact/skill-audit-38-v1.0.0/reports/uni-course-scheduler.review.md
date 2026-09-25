# Review: uni-course-scheduler

## Final Verdict

BENIGN

Confidence: HIGH

Audit object:
The `uni-course-scheduler` skill package, its normal entry path, and its directly referenced files.

Version identifier: `8c688269c016f90e9c281439eadaf8538ec5f749`

GitHub repository: `ez-hq/uni-course-scheduler`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Third-Party Content Exposure; Direct Money Access Detection

## Executive Assessment

The skill can submit course data to a paid cloud service, but it places two explicit approval gates before that submission. The user first reviews the collected data and later reviews the current fee; without both confirmations, the cloud run is not started. A local, no-cost path also remains available.

## Audited Source Excerpt

```text
BEFORE running `loomloom market quote`, present the collection summary to the user and obtain explicit confirmation of the DATA.
Before submitting any cloud run: show the platform's current fee estimate and obtain the user's explicit confirmation in the current conversation. No confirmation, no submission.
```

Source: `SKILL.md:233-269`

Location: `SKILL.md:233-269`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The workflow gathers course-catalog information and performs local quality checks. Before requesting a market quote it presents the data summary, and before the paid run it presents the fee estimate and asks again in the current conversation. No course records were uploaded and no payment was made during review. The control-flow text places both gates before the external submission.

## Closing Analysis

Third-party content, cloud processing, and payment are capabilities that deserve scrutiny, but they are not damage by themselves. Here the destination, data, and cost are disclosed, and the user can decline either stage. The evidence does not show silent billing, an unrelated recipient, or a bypass of the stated controls.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: USER_EXPLICIT_OPTION
- Security relevance: MEDIUM
- Functional necessity: NECESSARY
- Verdict impact: SUPPORTS_BENIGN
- Assessment: The skill is benign because its normal workflow does not complete a harmful data or payment action without informed, current user approval.
- Evidence: `SKILL.md:233-269` and the execution-path analysis above.

## Excluded False Positives

- The original alert appears to have treated third-party data handling and payment capability as sufficient. This review requires an actual harmful path, which the two confirmation gates prevent.

## Residual and Unresolved Risks

- Indirect prompt injection in collected course pages and ordinary cloud-privacy concerns remain, but neither is shown to bypass the documented approvals.

## Repository and Provenance Findings

- The assessment is scoped to `ez-hq/uni-course-scheduler` at version `8c688269c016f90e9c281439eadaf8538ec5f749` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
The user may choose a paid cloud scheduling run only after separately approving the collected data and the quoted fee.

Security delta:
Normal use does not establish a concrete path to host, account, or data harm.

## Final Rationale

The skill is benign because its normal workflow does not complete a harmful data or payment action without informed, current user approval.
