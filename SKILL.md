---
name: literature-daily-digest
description: Generate local Markdown daily literature digests from configured research keywords and journal names, with public-source paper discovery, Nature/Springer Nature publisher and journal watch support, optional Scopus/Elsevier/Springer API sources via environment variables, selected-paper full-text enrichment through entitled Elsevier Article Retrieval, high-impact journal prioritization, bilingual English/Chinese report structure, DOI/link metadata, scholarly reviewer-style analysis lenses, per-paper figure-rich interpretation guidance, optional diagnostic SVG overviews, and clear source/failure notes. Use when Codex needs to create, configure, run, or refine a daily research-paper alert, literature daily report, paper digest, journal watch, Nature Portfolio/Springer Nature monitoring, PubMed/arXiv/Crossref/OpenAlex/Scopus/Elsevier/Springer search, or summarize and academically interpret newly published papers from abstracts or full text for a researcher.
---

# Literature Daily Digest

## Workflow

1. Inspect the user's config file. If none is provided, start from `scripts/sample_config.yaml`; use `scripts/config.local.yaml` only when the user wants their local private watch profile.
2. Read `references/config-schema.md` when editing config fields or explaining options.
3. Read `references/academic-review-lens.md` before polishing selected papers into the final digest, especially when the user asks for more academic, peer-review-like interpretation.
4. If the user wants an easier setup surface, launch the local configuration UI:

```bash
python scripts/config_ui.py
```

Open `http://127.0.0.1:8765/`. The UI saves public-safe settings to the ignored
`scripts/config.local.yaml` and API/contact values to the ignored `.env`.

5. Run the discovery script:

```bash
python scripts/literature_digest.py --config scripts/sample_config.yaml
```

Use `--date YYYY-MM-DD`, `--days-back N`, `--max-papers N`, or `--output-dir DIR` when the user asks for a specific run window or destination.
Use `--env-file PATH` only when local secrets live outside the auto-loaded `.env` near the config or current directory.

6. Open the generated Markdown report and read any linked local full-text artifacts before writing full-paper analysis. Treat entries without a full-text artifact as abstract-only.
7. Refine the paper notes into a final bilingual digest using the scholarly analysis scaffold and the strongest available evidence level.
8. For each selected paper, turn the `图文解读` draft into a real per-paper visual explanation when evidence allows: prefer an accessible paper figure, graphical abstract, method diagram, or key result figure; otherwise keep or refine the grounded Mermaid logic diagram.
9. Preserve source URLs, DOI links, source names, full-text artifact paths/status, per-paper figure links/attribution notes, optional SVG asset links, and failure warnings from the script output.

## Report Standard

Produce a local Markdown literature daily report with:

- English paper title exactly as reported by the source.
- Chinese title translation only when it is useful for scanning; do not replace the English title.
- Journal or venue, publication date, DOI, URL, source database, and first authors when available.
- A concise Chinese summary for each paper covering research question, field positioning, method/data, main result, scholarly contribution, and relevance to the configured research direction.
- A peer-review-style reading note for selected papers: method/evidence strength, contribution delta, likely reviewer question, and a reading recommendation such as `必读`, `精读`, `略读`, or `观望`.
- A short English note when the original abstract is especially technical or when a citation-ready phrasing is useful.
- Explicit caveats when only an abstract is available, when full text could not be retrieved, when results are preprint-only, or when the source metadata is incomplete.
- Full-text evidence status for every selected paper. If a local artifact is linked, use it for final analysis but do not paste long copyrighted passages into the report.
- A per-paper visual explanation when `include_per_paper_visuals` is enabled: pair the textual interpretation with a real paper figure when accessible and reusable, or a grounded Mermaid research-logic diagram when only abstract/metadata evidence is available.

Do not invent findings that are not present in the title, abstract, metadata, or retrieved full text. If the script only captured an abstract, mark claims as "based on abstract only" in the final report.
Do not treat ranking/source overview charts as the report's visual substance; they are optional diagnostics only. The desired visual layer lives inside each paper's interpretation.
For final polishing, use `references/academic-review-lens.md` as the compact fusion of the daily-digest workflow with the academic reviewer-panel approach.

## Using the Script

The script discovers candidate papers from public sources, deduplicates them, ranks them, and writes a Markdown draft. It does not require API keys for the default sources.

Default no-key sources:

- PubMed for biomedical literature.
- arXiv for preprints.
- Crossref for DOI and journal metadata.
- OpenAlex for broad scholarly discovery.

Optional API-key sources:

- Scopus Search with `ELSEVIER_API_KEY`.
- Scopus Abstract Retrieval with `ELSEVIER_API_KEY` when the key is entitled.
- Elsevier ScienceDirect with `ELSEVIER_API_KEY` when the key is entitled.
- Elsevier Article Retrieval with `ELSEVIER_API_KEY` and optional `ELSEVIER_INSTTOKEN` for selected-paper full text when entitled.
- Springer Nature Meta with `SPRINGER_NATURE_API_KEY`.
- Springer Nature OpenAccess with `SPRINGER_OPENACCESS_API_KEY` or fallback `SPRINGER_NATURE_API_KEY`.

Nature/Springer Nature coverage depends on discovery, not only ranking:

- `priority_journals` raises scores, but `discover_priority_journals: true` also uses those journal names as watch terms.
- `nature_portfolio_journals` adds explicit Nature Portfolio journal watch terms.
- `openalex_publisher_ids` enables no-key OpenAlex publisher-lineage discovery; use `https://openalex.org/P4310319965` for Springer Nature.
- Springer Nature Meta, when enabled with `SPRINGER_NATURE_API_KEY`, can expose publisher `contentType` labels such as Article, Perspective, Review Article, Analysis, or Brief Communication.
- Springer Nature OpenAccess, when enabled as `springer-openaccess`, can provide open-access records; add `springer-openaccess` to `full_text_sources` to retrieve selected-paper OA JATS full text by DOI when available.

Elsevier entitlements are source-specific. If Scopus Search works but abstracts
are missing, check Source Status: the skill should treat HTTP 401/403 from
Scopus `COMPLETE`, Scopus Abstract Retrieval, or ScienceDirect as an access
problem, not as evidence that the paper has no abstract. Use
`ELSEVIER_INSTTOKEN` only when Elsevier has issued an institutional token.
Keep `elsevier_no_proxy: true` when a local proxy or VPN changes the public
egress IP; this bypasses the system HTTP(S) proxy only for `api.elsevier.com`
and leaves the other sources unchanged.
Keep `springer_no_proxy: true` for the same reason when using Springer Nature
Meta or OpenAccess; it bypasses the system HTTP(S) proxy for
`api.springernature.com`.
Keep `springer_page_size` at `20` or lower; Springer Meta/OpenAccess can return
HTTP 403 for larger `p` page sizes even when the key and no-proxy path are valid.
The script should paginate internally when more candidates are requested.

Keep API keys, contact emails, and user-specific research profiles out of committed files. Use local `.env` for keys and `LITERATURE_DIGEST_USER_AGENT`, and use `scripts/config.local.yaml` or another ignored config for private topics.

If a source fails because of network, rate limit, or upstream API changes, keep the failure note in the report instead of silently dropping it.
Full-text enrichment runs after ranking, so it only attempts the selected papers. Elsevier Article Retrieval may return only abstract/metadata or HTTP 401/403 when the key is not entitled; Springer OpenAccess JATS may return no XML body for non-OA or unavailable records. Preserve that status in the report.

For a network-free smoke test, run:

```bash
python scripts/literature_digest.py --config scripts/sample_config.yaml --offline-sample
```

Add `--no-visuals` when a text-only draft is preferred.
Add `--no-full-text` when a metadata/abstract-only draft is preferred.

## Ranking Guidance

Treat the script score as an explainable first pass, not as a scientific judgment. Prefer papers that:

- Match more configured keywords in the title or abstract.
- Appear in `priority_journals`.
- Match `nature_portfolio_journals` or `publisher_watch_terms` such as Springer Nature.
- Were published inside the configured date window.
- Include a DOI, source URL, and usable abstract.
- Are directly connected to the user's stated research direction.

High-priority journals should raise ranking but should not exclude other clearly relevant work unless the config uses `journals` as a hard filter.
The final reading recommendation should come from the scholarly lenses, not from score alone.

## Configuration

Use `references/config-schema.md` as the source of truth for config fields. Keep user-specific research interests in an ignored YAML config, not in `SKILL.md` or the public sample, so this skill remains reusable and GitHub-safe.

When creating a new user's config, copy `scripts/sample_config.yaml` to an ignored local filename such as `scripts/config.local.yaml`, then edit:

- `keywords` for topic discovery.
- `journals` for hard journal filters.
- `priority_journals` for ranking boosts.
- `discover_priority_journals`, `nature_portfolio_journals`, and `openalex_publisher_ids` for Nature/Springer Nature coverage.
- `exclude_keywords` for out-of-scope themes.
- `sources` for enabling public and optional publisher API sources.
- `output_dir` for the report destination.
- `.env` for `ELSEVIER_API_KEY`, optional `ELSEVIER_INSTTOKEN`, `SPRINGER_NATURE_API_KEY`, `SPRINGER_OPENACCESS_API_KEY`, and `LITERATURE_DIGEST_USER_AGENT`.

For users who prefer a form-based setup, run `python scripts/config_ui.py`; it
edits the same ignored YAML and `.env` files and can run an offline sample check
from the browser.

## Daily Automation

This skill creates the local digest workflow. For actual daily delivery, bind the script to a Codex automation or an operating-system scheduled task. Keep the automation prompt short: run the configured digest, open the generated report, polish the bilingual summaries, and report the output path.
