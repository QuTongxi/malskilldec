# Review: aso-skill

## Final Verdict

MALICIOUS

Confidence: MEDIUM

Audit object:
The `aso-skill` skill package, its normal entry path, and its directly referenced files.

Version identifier: `d02716756fa2214a578b4d43ce2b2d50f53b3acf`

GitHub repository: `furkancingoz/aso-skill`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Improper Credential Handling

## Executive Assessment

The installation guide directs users to create an App Store Connect API key with the account-wide Admin role. The private key is stored with restrictive filesystem permissions and is used only with Apple's API, but the granted role is much broader than application-metadata optimization requires. A compromise therefore affects every application and additional administrative functions, not merely the app being optimized.

## Audited Source Excerpt

```text
1. Go to: https://appstoreconnect.apple.com/access/integrations/api
2. Click "Generate API Key"
3. Select "Admin" role
mv ~/Downloads/AuthKey_XXXXX.p8 ~/.aso/
chmod 600 ~/.aso/AuthKey_*.p8
chmod 600 ~/.aso/credentials.json
```

Source: `INSTALL.md:82-112; SKILL.md:212-216`

Location: `INSTALL.md:82-112; SKILL.md:212-216`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

The normal onboarding sequence opens Apple's integration settings, creates a key, and explicitly selects `Admin`. The key is moved to `~/.aso/`, protected with mode `0600`, and used locally to mint JWTs for official App Store Connect requests. No real Apple credential was created and no metadata was submitted during review. Source inspection confirmed that the storage and destination are appropriate; the excessive role is the harmful element.

## Closing Analysis

An App Manager or another command-specific role can cover most metadata and version operations without conferring account-wide administration. Asking to optimize one application's store presence does not require the blast radius created by an Admin key. Normal setup consequently weakens the user's Apple account in a way that a narrower design would avoid.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: HIGH
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious under the harm-based standard because normal setup unnecessarily expands a credential compromise to the user's entire App Store Connect account.
- Evidence: `INSTALL.md:82-112; SKILL.md:212-216` and the execution-path analysis above.

## Excluded False Positives

- Local JWT generation, mode `0600`, and requests to Apple's official API were treated as correct behavior. The verdict rests solely on the mandatory over-privileged role.

## Residual and Unresolved Risks

- The minimum sufficient role may vary by enabled command; the skill should publish and enforce a role matrix rather than defaulting every user to Admin.

## Repository and Provenance Findings

- The assessment is scoped to `furkancingoz/aso-skill` at version `d02716756fa2214a578b4d43ce2b2d50f53b3acf` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Onboarding creates a reusable App Store Connect key with account-wide Admin authority for a narrower ASO task.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious under the harm-based standard because normal setup unnecessarily expands a credential compromise to the user's entire App Store Connect account.
