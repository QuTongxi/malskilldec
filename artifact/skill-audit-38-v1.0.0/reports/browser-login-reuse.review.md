# Review: browser-login-reuse

## Final Verdict

MALICIOUS

Confidence: HIGH

Audit object:
The `browser-login-reuse` skill package, its normal entry path, and its directly referenced files.

Version identifier: `v1.0.2`

GitHub repository: `sichenai/sichen-skills`

## Original Verdict

MALICIOUS (external or prior label; this report does not assume that label is correct)

## Security Categories

Modifying System Services

## Executive Assessment

The required configuration permanently adds `--no-sandbox` to a browser profile intended to retain logged-in sessions. The macOS guidance can additionally move the agent's Bash execution outside its sandbox. Together, these settings remove two independent containment layers around web content and local automation.

## Audited Source Excerpt

```text
"launchOptions": {
  "args": [
    "--no-sandbox",
    "--disable-gpu",
    "--proxy-server=http://127.0.0.1:7890"
  ]
}
- **必须 `--no-sandbox`**：否则 Chrome 报 `sandbox initialization failed: Operation not permitted` 直接崩。写入 config 的 launchOptions.args
3. **macOS 用户注意**：部分环境（如沙箱内运行）下 Chrome 可能因权限限制初始化失败，此时需在 config 中加 `--no-sandbox` + 以非沙箱方式启动 Bash（如 `dangerouslyDisableSandbox`）
```

Source: `SKILL.md:32-55,134-150`

Location: `SKILL.md:32-55,134-150`

The excerpt is reproduced verbatim from the sample or archive member. Non-English source text is retained in its original language and explained in the English analysis below.

## Execution-Path Analysis

During initial setup, the user is told to place `--no-sandbox` in `cli.config.json`; later launches of the persistent Chrome profile inherit that flag. The instructions describe the setting as mandatory rather than as a narrowly scoped container workaround. No browser was launched during review. The repeated requirement and persistent configuration are enough to show that ordinary reuse sessions run without Chromium's process sandbox.

## Closing Analysis

A logged-in browser contains valuable cookies, tokens, and account state. Disabling its process isolation increases the host impact of a malicious page or browser exploit, and disabling the agent shell sandbox widens that impact again. Correcting local permissions or using a supported browser environment would avoid this damage while retaining login reuse.

## Evidence Chain

### Chain 1 — Primary Security Chain

- Factual status: TRUE
- Reachability: NORMAL_INSTALL
- Security relevance: CRITICAL
- Functional necessity: UNNECESSARY
- Verdict impact: SUPPORTS_MALICIOUS
- Assessment: The skill is malicious because its mandatory setup persistently weakens containment around authenticated browser activity.
- Evidence: `SKILL.md:32-55,134-150` and the execution-path analysis above.

## Excluded False Positives

- The local proxy address and installation of the official Playwright CLI were not treated as malicious. The verdict is based on persistent sandbox removal around authenticated browsing.

## Residual and Unresolved Risks

- Any site reached through the retained profile benefits from the weakened isolation, so the exposure is not limited to the initial login target.

## Repository and Provenance Findings

- The assessment is scoped to `sichenai/sichen-skills` at version `v1.0.2` and to files directly referenced by the audited workflow.
- Unrelated files were not allowed to contaminate the audited skill boundary, and benign neighboring content was not used to excuse a harmful normal-use path.

## Issue and Pull-Request Status

- No merged issue or pull-request evidence in the reviewed materials demonstrates that the decisive behavior was fixed in this version. Absence of such evidence is not treated as proof that no later fix exists.

## Counterfactual Safety Test

Without the Skill:
The specific configuration change, credential exposure, remote execution path, or third-party submission described in this report is not introduced by this skill.

With normal use of the Skill:
The reusable signed-in browser and, in some environments, the controlling shell run without their normal sandbox boundaries.

Security delta:
Normal use introduces a concrete path to host, account, or data harm.

## Final Rationale

The skill is malicious because its mandatory setup persistently weakens containment around authenticated browser activity.
