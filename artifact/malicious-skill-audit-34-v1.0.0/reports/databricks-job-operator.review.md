# Review: databricks-job-operator

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `databricks-job-operator` skill package, its normal entry path, and its directly referenced files.

Version identifier: `22d22bde30`

GitHub repository: `Repository no longer available`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Malicious Code; Modifying System Services

## Executive Assessment

The bundled migration orchestrator drops legacy tables and resets the sample data and checkpoints by default. It also rewrites or creates a Databricks job, starts a Docker stack, and may expose local Kafka through ngrok. The destructive operations are opt-out rather than opt-in, so an ordinary run can erase data in the catalog selected from the user's environment.

## Audited Source Excerpt

```text
Read [`Agents/databricks-job-operator.md`](../../Agents/databricks-job-operator.md) before doing substantive work.
if not args.skip_legacy_drop:
    output["legacy_drop"] = drop_legacy_tables(host, token, args.catalog)
if not args.skip_reset:
    output["reset_run"] = reset_dvdrental_tables(
        client, args.catalog, args.git_branch, args.poll_seconds, args.timeout_seconds
    )
if not args.skip_docker:
```

Source: `SKILL.md:10-20; scripts/migrate_and_run.py:510-547`

Location: `SKILL.md:10-20; scripts/migrate_and_run.py:510-547`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

`migrate_and_run.py` loads the Databricks host and token, calls `drop_legacy_tables` unless `--skip-legacy-drop` is supplied, and calls the reset notebook unless `--skip-reset` is supplied. It then prepares the local stack and triggers the cloud job. The audit did not connect to Databricks, Docker, or ngrok. Static control-flow inspection confirmed that both deletion stages precede the final run on the default path.

## Closing Analysis

A migration tool may legitimately offer a reset operation, but irreversible deletion should require an explicit target review and affirmative flag. This script instead assumes consent and relies on users to know which skip options prevent loss. The missing role-definition file is a provenance problem, but it does not erase the destructive behavior present in the distributed executable.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because ordinary execution performs destructive cloud-data operations without requiring explicit opt-in.
- Evidence: `SKILL.md:10-20; scripts/migrate_and_run.py:510-547` and the execution-path analysis above.

## Excluded False Positives

- Docker, ngrok, and the presence of demonstration tables were not sufficient for the verdict. The evidence is the default invocation of `DROP TABLE` and reset routines against environment-selected resources.

## Residual and Unresolved Risks

- Because the primary agent-definition file is missing, the sample may omit additional scope or safeguards; that uncertainty cannot make the existing default deletions safe.

## Repository and Provenance Findings

- The original repository is no longer available. This assessment is limited to the archived sample and the version identifier recorded above.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
A default migration run drops selected tables, clears state, changes a cloud job, starts local infrastructure, and triggers the new pipeline.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because ordinary execution performs destructive cloud-data operations without requiring explicit opt-in.
