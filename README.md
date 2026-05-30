# Literature Daily Digest

A Codex skill for generating local Markdown literature digests from configured
research keywords and journal names.

The skill discovers recent papers, deduplicates and ranks candidates, then writes
a bilingual-friendly Markdown draft with source metadata, DOI links, abstracts,
optional local full-text artifacts, ranking notes, scholarly review-style analysis scaffolds,
per-paper visual interpretation prompts, and source failure warnings. It works with public scholarly
metadata sources by default and can optionally use publisher APIs when local
environment variables are configured.

## What It Searches

Default no-key sources:

- PubMed
- arXiv
- Crossref
- OpenAlex

Optional API-key sources:

- Scopus Search through `ELSEVIER_API_KEY`
- Scopus Abstract Retrieval through `ELSEVIER_API_KEY` when the key is entitled for it
- Elsevier ScienceDirect Search through `ELSEVIER_API_KEY` when the key is entitled for it
- Elsevier Article Retrieval through `ELSEVIER_API_KEY`/`ELSEVIER_INSTTOKEN` for selected-paper full text when entitled
- Springer Nature Meta through `SPRINGER_NATURE_API_KEY`
- Springer Nature OpenAccess through `SPRINGER_OPENACCESS_API_KEY` or fallback `SPRINGER_NATURE_API_KEY`

## Quick Start

Run the public sample configuration:

```bash
python scripts/literature_digest.py --config scripts/sample_config.yaml
```

Generate a report without network calls:

```bash
python scripts/literature_digest.py --config scripts/sample_config.yaml --offline-sample
```

The script writes Markdown reports to `reports/` by default. Generated reports
are ignored by Git so local daily outputs do not get committed accidentally.

## Private Configuration

Copy the public sample before adding personal research topics, contact emails, or
publisher API settings:

```bash
cp scripts/sample_config.yaml scripts/config.local.yaml
```

On Windows PowerShell:

```powershell
Copy-Item scripts/sample_config.yaml scripts/config.local.yaml
```

Edit the local config:

- `keywords` for topic discovery.
- `journals` for hard journal filters.
- `priority_journals` for ranking boosts.
- `discover_priority_journals`, `nature_portfolio_journals`, and `openalex_publisher_ids` for Nature/Springer Nature journal and publisher watch discovery.
- `exclude_keywords` for filtering out unwanted themes.
- `sources` for enabling public or optional publisher sources.
- `output_dir` for report destination.
- `include_full_text` and `full_text_sources` for selected-paper full-text enrichment.
- `include_scholarly_scaffold` for reviewer-style per-paper analysis prompts.
- `include_per_paper_visuals` for figure-rich interpretation sections on each paper.
- `include_overview_visuals` for optional diagnostic SVG charts.

Keep local configs such as `scripts/config.local.yaml` out of Git.

## Optional API Keys

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then fill only the variables you need:

```text
LITERATURE_DIGEST_USER_AGENT="literature-daily-digest/1.0 (mailto:your-email@example.com)"
ELSEVIER_API_KEY=
ELSEVIER_INSTTOKEN=
SPRINGER_NATURE_API_KEY=
SPRINGER_OPENACCESS_API_KEY=
```

Do not commit `.env`. It is intentionally ignored.

Elsevier API keys are not all equivalent. A key that can run Scopus Search may
still receive HTTP 401 for Scopus `COMPLETE`, Scopus Abstract Retrieval, or
ScienceDirect Search. For Scopus-only keys, keep `sources` on `scopus` and
expect some records to be metadata-only. To retrieve Scopus abstracts, request
Scopus Abstract Retrieval access from Elsevier or add an institutional token in
`ELSEVIER_INSTTOKEN` when Elsevier has issued one.

Full-text enrichment is separate from search. When `include_full_text: true`, the
script attempts Elsevier Article Retrieval after ranking selected papers and
stores extracted text in local report artifacts. If the API key or institutional
token lacks article entitlement, the report records that status and the paper
remains abstract-only.

Nature/Springer Nature coverage has two paths. Without an API key, OpenAlex can
watch Springer Nature by publisher lineage through `openalex_publisher_ids`.
With `SPRINGER_NATURE_API_KEY`, the `springer` source uses Springer Nature Meta
and preserves publisher content types such as Article, Perspective, Review
Article, Analysis, or Brief Communication when available.
With `SPRINGER_OPENACCESS_API_KEY`, the `springer-openaccess` source can retrieve
open-access Springer Nature records and uses OA full text when the API response
contains it.

If a local proxy or VPN changes the public egress IP, keep
`elsevier_no_proxy: true` in the config. The script will bypass the system
HTTP(S) proxy only for `api.elsevier.com`; other discovery sources keep the
normal proxy behavior.

For Springer Nature keys tied to a campus or official VPN IP, keep
`springer_no_proxy: true`. The script will bypass the system HTTP(S) proxy for
`api.springernature.com`, covering both `springer` and `springer-openaccess`.

## CLI Options

```bash
python scripts/literature_digest.py \
  --config scripts/config.local.yaml \
  --date 2026-05-26 \
  --days-back 3 \
  --max-papers 15 \
  --output-dir reports
```

Useful flags:

- `--config PATH`: required YAML or JSON config path.
- `--env-file PATH`: load secrets from a specific local `.env` file.
- `--date YYYY-MM-DD`: run date, defaulting to today.
- `--days-back N`: override the config date window.
- `--max-papers N`: override the number of ranked papers in the report.
- `--output-dir DIR`: override the configured output directory.
- `--no-full-text`: skip full-text enrichment for one run.
- `--no-visuals`: suppress per-paper visual blocks and optional overview assets for one run.
- `--offline-sample`: generate a local sample report without network APIs.

See `references/config-schema.md` for the full configuration schema.

## Output

Each generated report includes:

- The configured date window and report path.
- Source status notes for each enabled discovery source.
- Ranked paper candidates with title, authors, venue, date, DOI, URL, source, and score.
- Publisher and content-type metadata when available, including Springer Nature section labels.
- Full-text evidence status and local artifact links when full text is retrieved.
- Per-paper `图文解读` sections with a grounded Mermaid logic diagram and instructions for replacing it with real paper figures when accessible.
- Optional diagnostic SVG overviews for ranking score and selected-paper source coverage when enabled.
- Relevance notes explaining why a paper was ranked.
- A scholarly reading scaffold for each paper: field positioning, method/evidence, contribution, Devil's Advocate question, and evidence caveat.
- Abstract text when available and enabled.
- A reminder to distinguish full-text-based claims from abstract-only claims.

The script preserves source failures in the report instead of hiding them, which
helps distinguish "no papers found" from "a source could not be queried."

## Using This As A Codex Skill

The skill entry point is `SKILL.md`. A typical Codex workflow is:

1. Inspect the user's config or start from `scripts/sample_config.yaml`.
2. Check `references/config-schema.md` before changing config fields.
3. Read `references/academic-review-lens.md` before final polishing.
4. Run `scripts/literature_digest.py` for the requested date window.
5. Open the generated Markdown report.
6. Read any local full-text artifacts linked from selected papers before writing final full-paper analysis.
7. Polish the draft into a final bilingual literature digest while preserving DOI links, source names, URLs, per-paper figure links/attribution notes, optional SVG links, full-text evidence status, and caveats.

## Repository Safety

Commit public, reusable files:

- `SKILL.md`
- `agents/openai.yaml`
- `references/config-schema.md`
- `references/academic-review-lens.md`
- `scripts/literature_digest.py`
- `scripts/sample_config.yaml`
- `.env.example`
- `.gitignore`
- `README.md`

Keep local and uncommitted:

- `.env`
- `scripts/config.local.yaml`
- private or personal config files
- generated `reports/` folders
- Python cache files
