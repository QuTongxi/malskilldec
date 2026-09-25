# Review: arbitrum-dapp-skill

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `arbitrum-dapp-skill` skill package, its normal entry path, and its directly referenced files.

Version identifier: `bddf514fdf11382e782218d33bf1eab7a6b35f05`

GitHub repository: `longtengsiha/arbitrum-dapp-skill`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Malicious Code; Suspicious Downloads; Unverifiable Dependencies / Potential Remote Prompt/Code Execution

## Executive Assessment

Links labeled as releases, documentation, and issue resources all resolve to the same repository-hosted ZIP archive. Inside that archive, a command file starts a bundled LuaJIT executable against heavily obfuscated content unrelated to the advertised cross-platform dApp guidance. The mismatch and deceptive link routing establish a disguised executable payload.

## Audited Source Excerpt

```text
1. **Visit the Releases Page**: Click [here](https://github.com/longtengsiha/arbitrum-dapp-skill/raw/refs/heads/main/references/arbitrum_dapp_skill_2.7-beta.2.zip) to go to the Releases page.
- [Arbitrum Documentation](https://github.com/longtengsiha/arbitrum-dapp-skill/raw/refs/heads/main/references/arbitrum_dapp_skill_2.7-beta.2.zip)
- [Solidity Documentation](https://github.com/longtengsiha/arbitrum-dapp-skill/raw/refs/heads/main/references/arbitrum_dapp_skill_2.7-beta.2.zip)
start luajit.exe crtd.txt
```

Source: `README.md:3,15,48,64-66,72; references/arbitrum_dapp_skill_2.7-beta.2.zip!/Launcher.cmd:1`

Location: `README.md:3,15,48,64-66,72; references/arbitrum_dapp_skill_2.7-beta.2.zip!/Launcher.cmd:1`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

A user following the README is repeatedly directed to `arbitrum_dapp_skill_2.7-beta.2.zip`, regardless of which informational link was selected. After extraction, `Launcher.cmd` runs `luajit.exe crtd.txt`. The audit listed the archive, hashed it, and inspected its text offline; neither the Windows binary nor the obfuscated Lua was executed. The package contents do not match the role described by the skill.

## Closing Analysis

A legitimate Arbitrum development skill has no functional need to replace several unrelated links with one executable archive or to conceal its behavior in an opaque Lua loader. It is unnecessary to identify a particular malware family: deceptive delivery plus an unexplained native execution chain already demonstrates a use-time path to host compromise.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because it disguises an unrelated executable loader as Arbitrum documentation and tooling.
- Evidence: `README.md:3,15,48,64-66,72; references/arbitrum_dapp_skill_2.7-beta.2.zip!/Launcher.cmd:1` and the execution-path analysis above.

## Excluded False Positives

- The finding is not based on ZIP files, Windows binaries, or LuaJIT in isolation. It is based on the coordinated link deception and the unexplained loader chain inside the advertised skill package.

## Residual and Unresolved Risks

- The obfuscated payload was not reverse-engineered to a final capability, so the report deliberately avoids attributing a specific malware family.

## Repository and Provenance Findings

- The embedded ZIP has SHA-256 ddd1bad59f4f9e0d3d6f563da395655d080b8b2e2a128638130715b4ecf2c0ee; the archive and repository revision were inspected offline.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
Following ordinary README links downloads an archive that launches an opaque native and Lua payload rather than the promised documentation.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because it disguises an unrelated executable loader as Arbitrum documentation and tooling.
