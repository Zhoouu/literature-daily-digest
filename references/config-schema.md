# Literature Daily Digest Config Schema

Use YAML for normal configuration. The script also accepts JSON with the same fields.

## Required Intent

At least one of `keywords` or `journals` must be non-empty.

## Fields

`keywords`
: List of research keywords or phrases. Use English terms for best coverage across APIs. The script treats them as OR terms and scores title matches higher than abstract matches.

`journals`
: List of journal names used as a hard filter after discovery. Leave empty to search by topic across all venues. Matching is case-insensitive and allows partial journal-name matches.

`priority_journals`
: List of preferred high-level journals or venues. These raise ranking but do not exclude other relevant papers.

`discover_priority_journals`
: Boolean. When `true`, journal names in `priority_journals` and `nature_portfolio_journals` are also used for journal-watch discovery in sources that support it. Default: `true`. This matters because ranking boosts do not help papers that were never fetched.

`journal_watch_per_term`
: Number of extra candidates to fetch for each watched journal/publisher query path. Default: `8`. Increase this when tracking broad publishers such as Springer Nature, or set to `0` to disable journal-watch expansion.

`publisher_watch_terms`
: Publisher display-name fragments used for ranking and reporting, such as `Springer Nature` or `Nature Portfolio`. These do not create API-specific publisher filters by themselves; use `openalex_publisher_ids` for no-key OpenAlex publisher watch.

`openalex_publisher_ids`
: OpenAlex publisher IDs or URLs used for publisher-watch discovery. For Springer Nature, use `https://openalex.org/P4310319965`. The script adds OpenAlex publisher-lineage queries after the normal keyword query.

`nature_portfolio_journals`
: Extra Nature Portfolio journal names used for discovery and ranking, useful for catching Article, Perspective, Review, Analysis, and related section types across the Nature family.

`exclude_keywords`
: List of terms that remove a paper when found in the title, abstract, or journal name.

`days_back`
: Integer date window ending at the run date. Default: `1`.

`max_papers`
: Maximum number of ranked papers to include in the report. Default: `10`.

`output_dir`
: Directory where Markdown reports are written. Relative paths are resolved from the current working directory where the script is run. Default: `reports`.

`sources`
: List of enabled discovery sources. Supported values: `pubmed`, `arxiv`, `crossref`, `openalex`, `scopus`, `elsevier`, `springer`, `springer-openaccess`. Default: the first four public/no-key sources. `scopus`, `elsevier`, `springer`, and `springer-openaccess` are optional API-key sources.

`content_type`
: Not a user-set config field; generated reports display each source's article/content type when available. Springer Nature Meta can provide values such as Article, Review Article, Perspective, Brief Communication, or Analysis. Crossref/OpenAlex provide broader type labels.

`elsevier_api_key_env`
: Environment variable that stores an Elsevier API key for Scopus Search, optional Scopus Abstract Retrieval, and optional ScienceDirect Search. Default: `ELSEVIER_API_KEY`. Used when `sources` includes `scopus`, `elsevier`, or `sciencedirect`.

`elsevier_insttoken_env`
: Optional environment variable that stores an Elsevier institutional token. Default: `ELSEVIER_INSTTOKEN`. Only set this when Elsevier has issued an insttoken for the key; it is sent as the `X-ELS-Insttoken` header.

`elsevier_no_proxy`
: Boolean. When `true`, requests to `api.elsevier.com` bypass the local/system HTTP(S) proxy so Elsevier sees the machine's direct network egress, while other sources keep the normal proxy behavior. Default: `true`.

`scopus_search_view`
: Scopus Search view. Default: `STANDARD`. Set to `COMPLETE` only when the key is entitled for that view; the script falls back to `STANDARD` on HTTP 401/403.

`scopus_enrich_abstracts`
: Boolean. When `true`, Scopus records without `dc:description` are enriched through the Scopus Abstract Retrieval API using `scopus_abstract_view`. Default: `true`.

`scopus_abstract_view`
: Scopus Abstract Retrieval view used for enrichment. Default: `META_ABS`, which is the lowest view that includes `dc:description` in Elsevier's current views table.

`elsevier_sciencedirect_view`
: ScienceDirect Search view. Default: `COMPLETE`, because `dc:description` is only available in the complete view. The script falls back to `STANDARD` on HTTP 401/403, but abstracts may then be unavailable.

`elsevier_article_retrieval_accept`
: Response format requested from Elsevier Article Retrieval for full-text enrichment. Default: `text/xml`, because it is easier to extract body text from XML than from PDF. Actual full-text availability depends on Elsevier API access and institutional entitlements.

`elsevier_article_retrieval_view`
: Elsevier Article Retrieval view requested for full-text enrichment. Default: `FULL`. If the key is not entitled for this view, the report records the authorization/access status and the paper remains abstract-only or metadata-only.

`springer_api_key_env`
: Environment variable that stores a Springer Nature API key for the Meta API. Default: `SPRINGER_NATURE_API_KEY`. Only used when `sources` includes `springer` or `springer-nature`.

`springer_openaccess_api_key_env`
: Environment variable that stores a Springer Nature OpenAccess API key. Default: `SPRINGER_OPENACCESS_API_KEY`, with runtime fallback to `SPRINGER_NATURE_API_KEY` or `SPRINGER_API_KEY` if the dedicated variable is empty. Only used when `sources` includes `springer-openaccess`, `springer-oa`, or `openaccess`.

`springer_no_proxy`
: Boolean. When `true`, requests to `api.springernature.com` bypass the local/system HTTP(S) proxy so Springer Nature sees the machine's direct network egress, while other sources keep normal proxy behavior. Default: `true`. This mirrors `elsevier_no_proxy` and is useful when API entitlement depends on a campus or official VPN IP.

`user_agent`
: Optional HTTP user agent string. Keep the public sample generic. Put personal contact information in a local `.env` file through `user_agent_env`.

`user_agent_env`
: Environment variable that can override `user_agent`. Default: `LITERATURE_DIGEST_USER_AGENT`.

`timeout_seconds`
: HTTP timeout per request. Default: `20`.

`max_candidates_per_source`
: Upper bound fetched from each source before filtering and deduplication. Default: `max(max_papers * 4, 20)`.

`include_abstracts`
: Boolean. Include abstracts in the Markdown draft when available. Default: `true`.

`include_full_text`
: Boolean. After candidate ranking, try to retrieve full text for selected papers and store it as local analysis artifacts. Default: `true`. The report links to local artifacts instead of printing long copyrighted text.

`full_text_sources`
: List of full-text retrievers to use after ranking. Currently implemented: `elsevier` / `sciencedirect` through Elsevier Article Retrieval. Default: `elsevier`.

`full_text_dirname`
: Directory suffix for local full-text artifacts under `output_dir`, combined with the run date as `literature-digest-YYYY-MM-DD-<full_text_dirname>`. Default: `full-text`.

`full_text_max_chars`
: Maximum characters stored per retrieved full text artifact. This limits very large XML/plain-text responses while preserving enough material for analysis. Default: `60000`.

`full_text_min_chars`
: Minimum extracted text length required before a retrieval is treated as full-text-level evidence rather than abstract/metadata. Default: `1200`.

`full_text_max_papers`
: Maximum number of selected papers to attempt full-text enrichment for. Default: `max_papers`.

`include_scholarly_scaffold`
: Boolean. Include the per-paper scholarly analysis scaffold that guides final Codex polishing through field positioning, method/evidence, contribution, Devil's Advocate, evidence caveat, and visual suggestions. Default: `true`.

`include_visuals`
: Boolean. Backward-compatible master switch for visual report material. By default this enables per-paper visual interpretation, not global overview charts. Default: `true`. Use `--no-visuals` for a text-only run.

`include_per_paper_visuals`
: Boolean. Add a `图文解读` section to each selected paper. The generated draft includes a grounded Mermaid research-logic diagram and instructions for replacing or supplementing it with a real paper figure during final polishing. Default: follows `include_visuals`, normally `true`.

`include_overview_visuals`
: Boolean. Write local SVG overview assets for ranking score and selected-paper source coverage. Default: `false`, because these overview charts are optional diagnostics and do not satisfy per-paper visual explanation.

`visuals_dirname`
: Directory suffix for generated SVG assets under `output_dir`, combined with the run date as `literature-digest-YYYY-MM-DD-<visuals_dirname>`. Default: `assets`.

## CLI Overrides

The command line can override config values:

```bash
python scripts/literature_digest.py --config scripts/sample_config.yaml --date 2026-05-25 --days-back 3 --max-papers 15
```

Use `--offline-sample` to generate a local sample report without network calls.

Use `--no-full-text` to suppress full-text enrichment for a single run.

Use `--no-visuals` to suppress per-paper visual blocks and optional overview SVG assets for a single run.

Use `--env-file` when secrets live somewhere other than the auto-loaded `.env` near the config or current directory:

```bash
python scripts/literature_digest.py --config scripts/config.local.yaml --env-file .env
```

## Suggested Priority Journal Pattern

Keep `priority_journals` broad enough for discovery but specific enough to reflect taste:

```yaml
priority_journals:
  - Nature
  - Science
  - Cell
  - Nature Materials
  - Nature Nanotechnology
  - Nature Electronics
  - Nature Biomedical Engineering
  - Nature Machine Intelligence
  - Nature Computational Science
  - Science Advances
  - Journal of the Mechanics and Physics of Solids
  - International Journal of Solids and Structures
  - Computer Methods in Applied Mechanics and Engineering
  - Extreme Mechanics Letters
  - Advanced Materials
  - npj Flexible Electronics
```

This list is a ranking preference, not an endorsement or impact-factor calculation.

## Publisher API Notes

Elsevier and Springer Nature should be treated as optional enhanced sources rather than mandatory daily dependencies. Keep `crossref` and `openalex` enabled because they already index metadata from many Elsevier, Springer, Nature, Wiley, ACS, and society journals without user API keys. Use `scopus` when your Elsevier key has Scopus Search access but not ScienceDirect Search v2 access.

Scopus Search access does not guarantee abstract payload access. With a basic Scopus Search key, `STANDARD` search records may omit `dc:description`; `COMPLETE` Scopus Search, Scopus Abstract Retrieval `META_ABS`, and ScienceDirect Search can return HTTP 401/403 unless Elsevier has enabled the relevant entitlement or the request includes a valid institutional token. The script keeps Scopus Search usable, then attempts Abstract Retrieval enrichment only when configured and records authorization failures in Source Status.

Full-text enrichment is separate from search. After the script ranks selected papers, it can call Elsevier Article Retrieval by DOI, PII, EID, Scopus ID, or PubMed ID and store extracted body text under the report output directory. Elsevier may return only abstract/metadata or HTTP 401/403 when the key or institutional token lacks article entitlements; the report keeps those notes so final summaries can distinguish full-text evidence from abstract-only evidence.

When a local proxy or VPN exposes a non-institutional egress IP, keep `elsevier_no_proxy: true` so only Elsevier API calls bypass the proxy. This is useful when the institution recognizes direct campus or official VPN IPs. It does not change PubMed, arXiv, Crossref, OpenAlex, or Springer requests.

For Springer Nature Meta/OpenAccess, keep `springer_no_proxy: true` when entitlement depends on direct campus or official VPN egress. Both `springer` and `springer-openaccess` use `api.springernature.com`, so this bypass applies to both.

Scopus Search date filtering is less precise than PubMed/Crossref/OpenAlex in this script: the API request is limited by publication year and sorted by original load date, then the report keeps the returned candidates. Scopus `coverDate` can point to a future issue date.

Do not put API keys in YAML. To enable publisher APIs, create a local `.env` file or set shell variables:

```powershell
$env:LITERATURE_DIGEST_USER_AGENT = "literature-daily-digest/1.0 (mailto:your-email@example.com)"
$env:ELSEVIER_API_KEY = "your-elsevier-key"
$env:ELSEVIER_INSTTOKEN = "your-elsevier-insttoken-if-issued"
$env:SPRINGER_NATURE_API_KEY = "your-springer-meta-key"
$env:SPRINGER_OPENACCESS_API_KEY = "your-springer-openaccess-key"
```

Then add `scopus`, `elsevier`, `springer`, and/or `springer-openaccess` under `sources`.

## GitHub-Safe Layout

Commit these files:

- `SKILL.md`
- `agents/openai.yaml`
- `references/config-schema.md`
- `references/academic-review-lens.md`
- `scripts/literature_digest.py`
- `scripts/sample_config.yaml`
- `.env.example`
- `.gitignore`

Keep these local and uncommitted:

- `.env`
- `scripts/config.local.yaml`
- any `scripts/*private*.yaml` or `scripts/*personal*.yaml`
- generated `reports/` folders
