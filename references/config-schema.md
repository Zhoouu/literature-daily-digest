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

`exclude_keywords`
: List of terms that remove a paper when found in the title, abstract, or journal name.

`days_back`
: Integer date window ending at the run date. Default: `1`.

`max_papers`
: Maximum number of ranked papers to include in the report. Default: `10`.

`output_dir`
: Directory where Markdown reports are written. Relative paths are resolved from the current working directory where the script is run. Default: `reports`.

`sources`
: List of enabled discovery sources. Supported values: `pubmed`, `arxiv`, `crossref`, `openalex`, `scopus`, `elsevier`, `springer`. Default: the first four public/no-key sources. `scopus`, `elsevier`, and `springer` are optional API-key sources.

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

`springer_api_key_env`
: Environment variable that stores a Springer Nature API key for the Meta API. Default: `SPRINGER_NATURE_API_KEY`. Only used when `sources` includes `springer` or `springer-nature`.

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

`include_scholarly_scaffold`
: Boolean. Include the per-paper scholarly analysis scaffold that guides final Codex polishing through field positioning, method/evidence, contribution, Devil's Advocate, evidence caveat, and visual suggestions. Default: `true`.

`include_visuals`
: Boolean. Write local SVG visual overview assets and embed them in the Markdown report. Current visuals include ranking-score overview and selected-paper source coverage. Default: `true`. Use `--no-visuals` for a text-only run.

`visuals_dirname`
: Directory suffix for generated SVG assets under `output_dir`, combined with the run date as `literature-digest-YYYY-MM-DD-<visuals_dirname>`. Default: `assets`.

## CLI Overrides

The command line can override config values:

```bash
python scripts/literature_digest.py --config scripts/sample_config.yaml --date 2026-05-25 --days-back 3 --max-papers 15
```

Use `--offline-sample` to generate a local sample report without network calls.

Use `--no-visuals` to suppress SVG asset generation for a single run.

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

When a local proxy or VPN exposes a non-institutional egress IP, keep `elsevier_no_proxy: true` so only Elsevier API calls bypass the proxy. This is useful when the institution recognizes direct campus or official VPN IPs. It does not change PubMed, arXiv, Crossref, OpenAlex, or Springer requests.

Scopus Search date filtering is less precise than PubMed/Crossref/OpenAlex in this script: the API request is limited by publication year and sorted by original load date, then the report keeps the returned candidates. Scopus `coverDate` can point to a future issue date.

Do not put API keys in YAML. To enable publisher APIs, create a local `.env` file or set shell variables:

```powershell
$env:LITERATURE_DIGEST_USER_AGENT = "literature-daily-digest/1.0 (mailto:your-email@example.com)"
$env:ELSEVIER_API_KEY = "your-elsevier-key"
$env:ELSEVIER_INSTTOKEN = "your-elsevier-insttoken-if-issued"
$env:SPRINGER_NATURE_API_KEY = "your-springer-key"
```

Then add `scopus`, `elsevier`, and/or `springer` under `sources`.

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
