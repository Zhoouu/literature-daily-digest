---
name: literature-daily-digest
description: Generate local Markdown daily literature digests from configured research keywords and journal names, with public-source paper discovery, optional Scopus/Elsevier/Springer API sources via environment variables, high-impact journal prioritization, bilingual English/Chinese report structure, DOI/link metadata, and clear source/failure notes. Use when Codex needs to create, configure, run, or refine a daily research-paper alert, literature daily report, paper digest, journal watch, PubMed/arXiv/Crossref/OpenAlex/Scopus/Elsevier/Springer search, or summarize newly published papers for a researcher.
---

# Literature Daily Digest

## Workflow

1. Inspect the user's config file. If none is provided, start from `scripts/sample_config.yaml`; use `scripts/config.local.yaml` only when the user wants their local private watch profile.
2. Read `references/config-schema.md` when editing config fields or explaining options.
3. Run the discovery script:

```bash
python scripts/literature_digest.py --config scripts/sample_config.yaml
```

Use `--date YYYY-MM-DD`, `--days-back N`, `--max-papers N`, or `--output-dir DIR` when the user asks for a specific run window or destination.
Use `--env-file PATH` only when local secrets live outside the auto-loaded `.env` near the config or current directory.

4. Open the generated Markdown report and refine the paper notes into a final bilingual digest.
5. Preserve source URLs, DOI links, source names, and failure warnings from the script output.

## Report Standard

Produce a local Markdown literature daily report with:

- English paper title exactly as reported by the source.
- Chinese title translation only when it is useful for scanning; do not replace the English title.
- Journal or venue, publication date, DOI, URL, source database, and first authors when available.
- A concise Chinese summary for each paper covering research question, method/data, main result, and relevance to the configured research direction.
- A short English note when the original abstract is especially technical or when a citation-ready phrasing is useful.
- Explicit caveats when only an abstract is available, when results are preprint-only, or when the source metadata is incomplete.

Do not invent findings that are not present in the title, abstract, or metadata. If the script only captured an abstract, mark claims as "based on abstract only" in the final report.

## Using the Script

The script discovers candidate papers from public sources, deduplicates them, ranks them, and writes a Markdown draft. It does not require API keys for the default sources.

Default no-key sources:

- PubMed for biomedical literature.
- arXiv for preprints.
- Crossref for DOI and journal metadata.
- OpenAlex for broad scholarly discovery.

Optional API-key sources:

- Scopus Search with `ELSEVIER_API_KEY`.
- Elsevier ScienceDirect with `ELSEVIER_API_KEY`.
- Springer Nature Meta with `SPRINGER_NATURE_API_KEY`.

Keep API keys, contact emails, and user-specific research profiles out of committed files. Use local `.env` for keys and `LITERATURE_DIGEST_USER_AGENT`, and use `scripts/config.local.yaml` or another ignored config for private topics.

If a source fails because of network, rate limit, or upstream API changes, keep the failure note in the report instead of silently dropping it.

For a network-free smoke test, run:

```bash
python scripts/literature_digest.py --config scripts/sample_config.yaml --offline-sample
```

## Ranking Guidance

Treat the script score as an explainable first pass, not as a scientific judgment. Prefer papers that:

- Match more configured keywords in the title or abstract.
- Appear in `priority_journals`.
- Were published inside the configured date window.
- Include a DOI, source URL, and usable abstract.
- Are directly connected to the user's stated research direction.

High-priority journals should raise ranking but should not exclude other clearly relevant work unless the config uses `journals` as a hard filter.

## Configuration

Use `references/config-schema.md` as the source of truth for config fields. Keep user-specific research interests in an ignored YAML config, not in `SKILL.md` or the public sample, so this skill remains reusable and GitHub-safe.

When creating a new user's config, copy `scripts/sample_config.yaml` to an ignored local filename such as `scripts/config.local.yaml`, then edit:

- `keywords` for topic discovery.
- `journals` for hard journal filters.
- `priority_journals` for ranking boosts.
- `exclude_keywords` for out-of-scope themes.
- `sources` for enabling public and optional publisher API sources.
- `output_dir` for the report destination.
- `.env` for `ELSEVIER_API_KEY`, `SPRINGER_NATURE_API_KEY`, and `LITERATURE_DIGEST_USER_AGENT`.

## Daily Automation

This skill creates the local digest workflow. For actual daily delivery, bind the script to a Codex automation or an operating-system scheduled task. Keep the automation prompt short: run the configured digest, open the generated report, polish the bilingual summaries, and report the output path.
