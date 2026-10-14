# Dependabot-blind advisories in self-hosted AI apps

Many security advisories for the AI apps in this checklist exist in the GitHub Advisory Database only as **unreviewed** records. GitHub's own docs say: "Dependabot doesn't create Dependabot alerts for unreviewed advisories" ([About the GitHub Advisory Database](https://docs.github.com/en/code-security/security-advisories/working-with-global-security-advisories-from-the-github-advisory-database/about-the-github-advisory-database#unreviewed-vulnerability-advisories)). Most of these records name no package or version range, so `npm audit` and other tools that read reviewed data skip them too.

Counted by MV2 of Munim, Inc., with AI agents, on **14 October 2026** from GitHub's advisory search. Every number links to the search that produced it, so you can re-run it.

## The counts

| Project | Unreviewed | Reviewed | Unreviewed on page 1 by severity (C / H / M / L) |
|---|---|---|---|
| Langflow | [155](https://github.com/advisories?query=type%3Aunreviewed+langflow) | [49](https://github.com/advisories?query=type%3Areviewed+langflow) | 2 / 19 / 4 / 0 |
| n8n | [77](https://github.com/advisories?query=type%3Aunreviewed+n8n) | [201](https://github.com/advisories?query=type%3Areviewed+n8n) | 0 / 15 / 10 / 0 |
| Flowise | [55](https://github.com/advisories?query=type%3Aunreviewed+flowise) | [125](https://github.com/advisories?query=type%3Areviewed+flowise) | 8 / 13 / 3 / 1 |
| vLLM | [39](https://github.com/advisories?query=type%3Aunreviewed+vllm) | [88](https://github.com/advisories?query=type%3Areviewed+vllm) | 0 / 13 / 9 / 3 |
| Open WebUI | [34](https://github.com/advisories?query=type%3Aunreviewed+%22open+webui%22) | [177](https://github.com/advisories?query=type%3Areviewed+%22open+webui%22) | 1 / 15 / 8 / 1 |
| Dify | [33](https://github.com/advisories?query=type%3Aunreviewed+dify) | [0](https://github.com/advisories?query=type%3Areviewed+dify) | 6 / 6 / 10 / 3 |
| Ollama | [26](https://github.com/advisories?query=type%3Aunreviewed+ollama) | [46](https://github.com/advisories?query=type%3Areviewed+ollama) | 4 / 15 / 3 / 3 |
| LiteLLM | [10](https://github.com/advisories?query=type%3Aunreviewed+litellm) | [50](https://github.com/advisories?query=type%3Areviewed+litellm) | 1 / 3 / 1 / 5 |

"Page 1" is the 25 newest results (all 10 for LiteLLM). C / H / M / L = critical / high / moderate / low.

How to read it:
- **The search matches words, not products.** A few results belong to other projects. The LiteLLM search includes one wandb OpenUI record, and the Dify search includes one record for an unrelated repository. Treat every count as "about".
- **Unreviewed doesn't mean new.** Some are duplicates of a reviewed advisory that already alerts, filed again from another source under the CVE ID. 24 of Langflow's 25 newest unreviewed records were published on the same day (7 October 2026), so check that batch for duplicates before relying on it.
- **Dify has no reviewed advisories.** Dify ships as Docker images, not as a pip or npm package, so there is probably no package for an advisory to point at. Dependabot won't warn you about Dify, whatever the database holds. Watch [Dify's own security advisories](https://github.com/langgenius/dify/security/advisories) instead.
- **Flowise is the clearest gap.** All 25 of its newest unreviewed records name no package; eight are critical. Two of them are remote code execution through the Custom MCP node, fixed in 3.1.4 ([GHSA-q5vh-j6x8-9f53](https://github.com/advisories/GHSA-q5vh-j6x8-9f53), [GHSA-63x5-9mcr-7447](https://github.com/advisories/GHSA-63x5-9mcr-7447)). The Flowise maintainers' own advisories for them ([GHSA-vcwp-f9rq-3887](https://github.com/FlowiseAI/Flowise/security/advisories/GHSA-vcwp-f9rq-3887), [GHSA-x7x8-95gh-42xm](https://github.com/FlowiseAI/Flowise/security/advisories/GHSA-x7x8-95gh-42xm), 31 August 2026) list `flowise` and `flowise-components` `<= 3.1.3`, patched in 3.1.4, but were never imported into the global database. So a project pinned to Flowise 3.1.3 gets no Dependabot alert for either. Two other critical ones, the SSO takeovers in [Flowise](../README.md#flowise), have no fix at all.

## If you run one of these apps

1. **Don't treat "no Dependabot alert" as "no known issue".** Check the project's own security advisories page (for example `https://github.com/<owner>/<repo>/security/advisories`) against your version.
2. **Check a specific ID:** `python3 tools/ghsa_coverage_check.py GHSA-vcwp-f9rq-3887 CVE-2026-91931` tells you whether Dependabot can alert on it and, if not, why.
3. **Or scan your machine:** [local-ai-checkup](https://github.com/munimtechnologies/local-ai-checkup) compares installed versions against the projects' advisories, including the ones without CVE IDs.

## If you want to close a gap

Anyone with a GitHub account can fix one. Open the record, choose **Suggest improvements for this vulnerability**, add the package and version range from the project's own advisory, and submit. That opens a pull request that the GitHub Security Lab curators review ([community contributions](https://docs.github.com/en/code-security/security-advisories/working-with-global-security-advisories-from-the-github-advisory-database/about-the-github-advisory-database#community-contributions)). Two things trip people up:
- **The form needs a Title.** Records imported from a CVE alone often have no summary, and the page heading you see is just the start of the description. Use the upstream advisory's title.
- **The stored CVSS v4 vector may show an error.** Long vectors that spell out every optional metric as `X` fail the form's check. Accepted pull requests (for example [#9888](https://github.com/github/advisory-database/pull/9888)) replaced them with the base metrics only, which gives the same score.

To find gaps in bulk, [tools/advisory_gap_finder.py](../tools/advisory_gap_finder.py) reads a local clone of the database and lists every unreviewed record with no package. It sorts each into: the project's advisory exists but was never imported (fixable now), a duplicate of a reviewed advisory, or nothing upstream to copy from.

---

Counts change daily; re-run the linked searches for current numbers. General technical information, not professional advice. Text licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Written by MV2 of Munim, Inc., with AI agents. Corrections welcome as issues.
