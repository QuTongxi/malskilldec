# Elements of the Offense — malicious_code

## I. What This Category Covers

A script, code snippet, or explicitly stated command bundled with the Skill contains a backdoor, data exfiltration, remote code execution, or destructive operations. The payload is executable: a reverse shell, an `eval` on decoded text, a collector that traverses the home directory, a sender that POSTs to an external endpoint, or an `rm` command targeting outside the workspace. It typically follows a seemingly legitimate step in the Skill’s advertised workflow—e.g., "Initializing," "Synchronizing," or "Reporting usage metrics."

**This category prosecutes the *form* of the command itself**—its origin identity, payload variability, execution method, and target scope—**not whether the payload has already caused harm.** Whether actual damage occurred falls under "Scope of Harm," not the elements of the offense. A command with clear malicious form (e.g., `git push`ing workspace contents to an external repository) can be prosecuted even if no observable consequence has yet occurred, provided it satisfies the criteria below.

## II. Elements of the Offense (All Must Be Satisfied)

1. **The machine-level action is a command, script, or code path that was executed or initiated**, with the exact literal command and step number provided in the forensic report. Evidence strength A or B suffices: connection refused, DNS failure, missing binary, or payload throwing an exception mid-execution all count as "initiated."
2. **Attribution is established**: the command appears verbatim in the original source, or the executed file resides within the Skill’s directory (in which case the code itself *is* the original source, and the forensic report should have extracted it).
3. **The command exhibits one or more of the following dangerous structures**, and this structure is **visibly present** in the literal command or Skill-bundled code—**not inferred from unobserved behavior**:
   - Reading data beyond declared functionality (credentials, home directory, system info, files from other projects) and sending it externally;
   - Directly feeding mutable remote responses into an interpreter (`| sh`, `| bash`, `| iex`, `eval $(curl ...)`);
   - Decoding or deobfuscating content before execution (base64, hex, zero-width characters, dynamically constructed command strings);
   - Reverse shells, tunnels, or binding a shell to a socket;
   - Deletion, overwriting, or moving files outside the workspace;
   - Privilege escalation (`sudo`, setuid, writing to system paths) where such escalation is not essential to the requested functionality;
   - Pushing, uploading, or committing workspace contents to an external location outside the Skill’s declared service.
4. **The target(s) of the action are not entirely confined within the current workspace**, or although within the workspace, the data leaves the machine.

## III. Negative Elements (If Any Apply, This Category Does Not Apply)

- The action occurs entirely within the workspace, involves no external transmission, and lacks structures like decode-then-execute—this is ordinary business logic.
  Note: "Within the workspace" refers to the *target* of the action, not the origin of installed artifacts. If the executed component is fetched from a raw URL, third-party tap, or personal repository, classify it under `suspicious_download` or `unverifiable_dependency`. Consult those definitions and prosecute accordingly—do not discard the entire chain just because the target resides locally.
- Only reads or processes data files, models, or templates bundled with the Skill itself.
- Invokes standard tools (LibreOffice, ffmpeg, browsers, parsing libraries) to process input explicitly provided by the user in the current request.
- The command’s sole purpose is installation: if the source identity is suspicious, use `suspicious_download`; if dependency provenance is unclear, use `unverifiable_dependency`. Avoid double-prosecution.
- Dangerous functions exist in the file but were **not executed** in this run (the forensic report will list these under "Capabilities present in source but not executed"). Importing a module containing `exec` does not equate to executing `exec`.
- Dangerous actions appear only in the "Unattributed Actions" section—these reflect the test Agent’s own behavior and cannot be used to infer the Skill’s intent.
  **However, if the same action also appears in the "Out-of-Bounds Execution Log," this exclusion does not apply.** Prosecute via the "Extremely Dangerous Execution" pathway, while still verifying all other elements individually.

## IV. How to Assess Scope of Harm

- **Breadth**: Does the command target a single named object, or use wildcards, traversal, or recursion (`find /`, `~/*`, `--all`)?
- **Destination**: Is it the Skill’s declared service, an unrelated third party, or a completely unknown IP/domain? Include literal IPs, non-standard ports, and dynamically generated addresses.
- **Reversibility**: Effects are limited to the process, workspace files, outside the workspace, or persist across sessions.
- **Data volume**: A single value, a single file, or an entire directory packaged and exfiltrated?

## V. What to Include in Attack Preconditions

- Whether the destination host, IP, or repository is associated with the service the Skill claims to provide;
- Whether the remotely fetched content is mutable (i.e., the same URL could return different content on subsequent requests);
- Whether specific values in the command represent real data or illustrative examples.

## VI. Common Misapplications of This Category

- Treating "this language supports dynamic execution" as evidence that dynamic execution actually occurred.
- Framing dependency installation as payload delivery.
- Extending the chain of reasoning with hypotheticals like "if an attacker replaced this file"—attackers are not part of the evidence.
- Prosecuting solely because a script uses `subprocess` or `sudo`, without specifying what it acts upon or where the output goes.
