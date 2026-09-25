# Review: write-my-blog

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `write-my-blog` skill package, its normal entry path, and its directly referenced files.

Version identifier: `0.1.0 / 6e1c75f59b`

GitHub repository: `openclaw/skills`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Improper Credential Handling; Unverifiable Dependencies / Potential Remote Prompt/Code Execution

## Executive Assessment

The non-interactive setup accepts service-role, database, and cache credentials through command-line arguments or environment variables, writes them to `.env.local` without enforcing a restrictive mode, and prints the generated API key in its completion JSON. These choices create several additional plaintext copies of long-lived secrets. None is necessary to report that setup succeeded.

## Audited Source Excerpt

```text
--supabase-key <key>     Supabase service role key
SUPABASE_SERVICE_KEY=$SUPABASE_KEY
MONGODB_URI=$MONGODB_URI
SETUP_RESULT_JSON={"apiKey":"$API_KEY","dbProvider":"$DB_PROVIDER","cacheProvider":"$CACHE_PROVIDER","theme":"$THEME","blogName":"$BLOG_NAME","deployTarget":"$DEPLOY_TARGET"}
Allow network access (0.0.0.0/0 for serverless)
```

Source: `scripts/setup.sh:39-67,235-305,643-667`

Location: `scripts/setup.sh:39-67,235-305,643-667`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

During installation, the script assembles Supabase, MongoDB, and Redis values into a local environment file. Its final `SETUP_RESULT_JSON` includes the complete generated `apiKey`, which is emitted to stdout for the calling agent. No real cloud credential was supplied and no blog was deployed during review. Control-flow inspection with a fake value confirmed the full key would appear, and no `chmod 600` protects the environment file.

## Closing Analysis

A deployed application needs access to its configuration, but it does not need secrets echoed into an agent transcript or left with ambient filesystem permissions. Masked receipts, a secure store, and a restrictive file mode would preserve the workflow. The ordinary installer instead creates avoidable process-list, log, and local-file exposure.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its standard installer unnecessarily exposes reusable cloud and application secrets in several observable locations.
- Evidence: `scripts/setup.sh:39-67,235-305,643-667` and the execution-path analysis above.

## Excluded False Positives

- Creating an `.env` file and using the declared database providers are normal setup behavior. The finding concerns how the credentials are passed, stored, and returned.

## Residual and Unresolved Risks

- The guidance to allow MongoDB Atlas access from `0.0.0.0/0` and the use of mutable deployment tools further widen the eventual attack surface.

## Repository and Provenance Findings

- The package metadata identifies openclaw/skills commit 2a9723821305b73ef97f746bb4f1a78ea68ad14a as the source revision.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Setup spreads long-lived service credentials across command input, a broadly protected local file, and unmasked completion output.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its standard installer unnecessarily exposes reusable cloud and application secrets in several observable locations.
