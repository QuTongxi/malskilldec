# Review: skill-forge

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `skill-forge` skill package, its normal entry path, and its directly referenced files.

Version identifier: `5b6597a442`

GitHub repository: `Adit-Jain-srm/skill-forge`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Third-Party Content Exposure; Unverifiable Dependencies / Potential Remote Prompt/Code Execution; Modifying System Services

## Executive Assessment

The skill discovers candidate repositories from untrusted community content and passes the resulting strings into shell-based `execSync` calls without parameterization or escaping. Successful candidates are copied into Cursor's trusted skill directory, and the MCP branch can persist new commands in `mcp.json`. This closes a path from external text to command execution and future agent startup.

## Audited Source Excerpt

```text
Phase 4: Action (CREATE compound skills / INSTALL / LEARN / ROUTE)
const result = execSync(`npx skills add ${repo} -a cursor -y`, {
  encoding: 'utf8',
  timeout: 60000,
  stdio: ['pipe', 'pipe', 'pipe']
});
execSync(`git clone --depth 1 https://github.com/${repo}.git "${tempDir}"`, {
  encoding: 'utf8',
  timeout: 30000
});
config.mcpServers[name] = {
  command: command.split(' ')[0],
  args,
  env
};
```

Source: `SKILL.md:94-105; scripts/install.js:34-82,109-131`

Location: `SKILL.md:94-105; scripts/install.js:34-82,109-131`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

`install.js` first constructs `npx skills add ${repo} -a cursor -y`; its fallback similarly interpolates the repository into a `git clone` shell command. The installer then copies discovered skill content beneath `~/.cursor/skills`, while MCP installation writes command and argument fields into the client configuration. No live community skill was installed. Source-level data-flow review confirmed the absence of a repository allowlist, shell escaping, or argument-array execution.

## Closing Analysis

Searching the community for extensions is not inherently harmful. The damage path arises because attacker-influenced discovery output is treated simultaneously as a shell fragment and as trusted future instructions. A malicious candidate can therefore execute during installation or persist through the agent and MCP configuration.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_RUNTIME
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its normal discovery-and-install path converts untrusted text into immediate and persistent code execution.
- Evidence: `SKILL.md:94-105; scripts/install.js:34-82,109-131` and the execution-path analysis above.

## Excluded False Positives

- Broad web discovery and `git clone` were not treated as malicious by themselves. The decisive evidence is untrusted interpolation into a shell followed by automatic installation into a trust root.

## Residual and Unresolved Risks

- The MCP command parser splits on spaces and persists the result, creating another opportunity for unintended execution when the client next starts.

## Repository and Provenance Findings

- The assessment is scoped to `Adit-Jain-srm/skill-forge` at version `5b6597a442` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
A discovered repository string is executed through a shell and its contents or commands are persisted in Cursor's trusted configuration.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its normal discovery-and-install path converts untrusted text into immediate and persistent code execution.
