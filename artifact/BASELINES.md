# Baselines

The nine detectors compared in Table 5. We do not redistribute their code. Each
was obtained from the source below at the state it had on the day we ran it, and
driven through its own documented workflow at its default or recommended
settings. Every baseline that needs an LLM was given the same backbone we use,
Qwen3-max (`qwen3-max-2026-01-23`).

Sentry skill-scanner, SkillSentry, and AI-Infra-Guard were run on **2026-08-10**;
the remaining six on **2026-07-20**. The commits below are the state of each
repository on its run date.

## Reducing a tool's output to a verdict

All nine ran over the same 200 skills and were scored at the skill level, so each
tool's output has to become one bit. We took that bit in the following order.
Where the tool has a paper, we used the paper's own criterion. Where it has none,
we used the verdict its README documents. Where it documents neither, we counted
a skill as detected when the tool's report reaches its top severity band, and
counted every lower band as benign.

The five research prototypes classify a skill as malicious or benign directly, so
their output was used as it stands. The four industry scanners report graded
findings rather than a verdict, so the top-band rule applies to them.

## Industry tools

| Tool | Source | State on run date | Verdict |
|---|---|---|---|
| AI-Infra-Guard | `Tencent/AI-Infra-Guard` | `cbe58e69`, 2026-08-10 | Top severity band of the skill scan report; lower bands benign. |
| Sentry skill-scanner | `getsentry/skills`, path `skills/skill-scanner` | repo `24fdb833`, 2026-08-08; the scanner directory itself last changed at `c8137358`, 2026-05-09 | Top severity band among the findings it returns; lower bands benign. |
| Cisco Skill Scanner | `cisco-ai-defense/skill-scanner` | `41fec4a9`, 2026-06-29 | Top severity band among the findings it returns; lower bands benign. |
| NVIDIA SkillSpector | `NVIDIA/skillspector` | `11567e8d`, 2026-07-20 | Top band of the `severity` label it reports alongside `risk_score`; lower bands benign. |

## Research prototypes

| Tool | Paper | Artifact | State on run date | Verdict |
|---|---|---|---|---|
| MASB | arXiv:2602.06547 | `protectskills/MaliciousAgentSkillsBench` | `eb9a745c`, 2026-07-20 | Binary, as the paper defines it. |
| SkillScan | arXiv:2601.10338 | `https://anonymous.4open.science/r/skillscan/` | Anonymized deposit, no revision history | Binary, as the paper defines it. |
| MalSkills | arXiv:2603.27204 | Zenodo, `10.5281/zenodo.19253764` | `MalSkills.zip`, v1, 2026-03-27 | Binary, as the paper defines it. |
| SkillSentry | arXiv:2608.03485 | `nizhangli062-jpg/SkillSentry-Adaptive-Honey-Worlds-for-Dynamic-Safety-Testing-of-Agent-Skills` | `9c0260bb`, 2026-08-04 | Binary prediction, returned by the tool itself. |
| Runtime Skill Audit | arXiv:2606.11671 | `tu-tuing/RuntimeSkill-Audit` | State of 2026-07-20; the repository has since been made private | Binary, as the paper defines it. |

## Notes

- **Runtime Skill Audit** completed only 93 of the 200 skills. It exits during
  task generation, before its agent runtime executes anything, with
  `Task generation failed ...; fallback tasks are disabled.` Those runs
  contribute no TP, FP, TN, or FN, so its row in Table 5 is computed over the
  93 completed skills alone.
- **Excluded from comparison.** Snyk AgentScan, VirusTotal Code Insight, and
  Socket rely on proprietary APIs and vendor-internal signature databases that
  cannot be deployed independently. SkillVetBench (arXiv:2606.16287) releases
  only its semantic vetting stage and omits the instrumented sandbox its paper
  describes.
