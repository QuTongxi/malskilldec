# Review: userscript-saas

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `userscript-saas` skill package, its normal entry path, and its directly referenced files.

Version identifier: `dd5471c802`

GitHub repository: `Repository no longer available`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Improper Credential Handling; Malicious Code; Modifying System Services

## Executive Assessment

The preferred deployment pattern generates a public account and payment service but never requires password hashing, salted verification, or secure reset-code storage. At the same time it mandates wildcard CORS, uses password-based SSH automation, creates a system service, and permanently opens a firewall port. The skill therefore publishes a security-sensitive application from a specification that omits its basic credential protections.

## Audited Source Excerpt

```text
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT UNIQUE
);
POST /api/register         - {email, password}          → auto_login, auto username from prefix
POST /api/login            - {email, password}          → username, balance
**CORS**: Always add CORSMiddleware with `allow_origins=["*"]`
```

Source: `SKILL.md:39-67,84-103,145-163`

Location: `SKILL.md:39-67,84-103,145-163`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The v4 pattern defines registration, login, password reset, balances, and recharge endpoints over a `password TEXT` field. The document gives detailed deployment instructions but contains no Argon2, bcrypt, salt, or verify requirement; it does require `allow_origins=["*"]` and describes `sshpass` plus permanent firewall changes. No real service or user database was created. The missing safeguards and broad exposure are part of the primary deployment guidance rather than a detached example.

## Closing Analysis

A column named `password` does not by itself prove that one implementation stores plaintext. The stronger evidence is the complete preferred specification: it handles real credentials and paid balances, yet omits a hashing contract while mandating permissive exposure. Following that specification creates a foreseeably vulnerable public service and expands the host attack surface.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its normal output is a persistently deployed authentication service with predictable, consequential security omissions.
- Evidence: `SKILL.md:39-67,84-103,145-163` and the execution-path analysis above.

## Excluded False Positives

- The verdict does not infer plaintext storage solely from the SQLite column name. It is based on the full authentication specification's missing password controls and its compulsory public deployment settings.

## Residual and Unresolved Risks

- Reset codes also lack a hashing and retry-limit requirement, and multi-server control through password-based SSH can spread a compromise beyond one host.

## Repository and Provenance Findings

- The original repository is no longer available. This assessment is limited to the archived sample and the version identifier recorded above.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
The generated SaaS exposes account, reset, and payment functions publicly without a required password-hashing design and with wildcard CORS.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its normal output is a persistently deployed authentication service with predictable, consequential security omissions.
