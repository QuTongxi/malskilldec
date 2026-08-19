# Baselines

The nine detectors compared in Table 5. We do not redistribute their code. Each
was obtained from the source below at the state it had on the date we ran it,
and driven through its own documented workflow at its default or recommended
settings. Every baseline that needs an LLM was given the same backbone we use,
Qwen3-max (`qwen3-max-2026-01-23`).

All nine ran over the same 200 skills and were scored at the skill level with
the same criterion as our own pipeline: a skill counts as detected when the tool
reports it malicious. Tools that emit a graded severity rather than a binary
verdict were mapped as recorded in the last column.

## Run dates

Sentry skill-scanner, SkillSentry, and AI-Infra-Guard were run on **2026-08-10**;
the remaining six on **2026-07-20**. The commits below are the state of each
repository on its run date.

## Industry tools

| Tool | Source | State on run date | Verdict mapping |
|---|---|---|---|
| AI-Infra-Guard | `Tencent/AI-Infra-Guard` | `cbe58e69`, 2026-08-10 | TODO |
| Sentry skill-scanner | `getsentry/skills`, path `skills/skill-scanner` | repo `24fdb833`, 2026-08-08; the scanner directory itself last changed at `c8137358`, 2026-05-09 | TODO |
| Cisco Skill Scanner | `cisco-ai-defense/skill-scanner` | `41fec4a9`, 2026-06-29 | TODO |
| NVIDIA SkillSpector | `NVIDIA/skillspector` | `11567e8d`, 2026-07-20 | TODO |

## Research prototypes

| Tool | Paper | Artifact | State on run date | Verdict mapping |
|---|---|---|---|---|
| SkillSentry | arXiv:2608.03485 | `nizhangli062-jpg/SkillSentry-Adaptive-Honey-Worlds-for-Dynamic-Safety-Testing-of-Agent-Skills` | `9c0260bb`, 2026-08-04 | TODO |
| MASB | arXiv:2602.06547 | TODO confirm | TODO | TODO |
| SkillScan | arXiv:2601.10338 | TODO confirm | TODO | TODO |
| MalSkills | arXiv:2603.27204 | TODO | TODO | TODO |
| Runtime Skill Audit | arXiv:2606.11671 | TODO | TODO | TODO |

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
