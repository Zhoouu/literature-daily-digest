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
: List of enabled discovery sources. Supported values: `pubmed`, `arxiv`, `crossref`, `openalex`, `elsevier`, `springer`. Default: the first four public/no-key sources. `elsevier` and `springer` are optional API-key sources.

`elsevier_api_key_env`
: Environment variable that stores an Elsevier API key for the ScienceDirect Search API. Default: `ELSEVIER_API_KEY`. Only used when `sources` includes `elsevier` or `sciencedirect`.

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

## CLI Overrides

The command line can override config values:

```bash
python scripts/literature_digest.py --config scripts/sample_config.yaml --date 2026-05-25 --days-back 3 --max-papers 15
```

Use `--offline-sample` to generate a local sample report without network calls.

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

Elsevier and Springer Nature should be treated as optional enhanced sources rather than mandatory daily dependencies. Keep `crossref` and `openalex` enabled because they already index metadata from many Elsevier, Springer, Nature, Wiley, ACS, and society journals without user API keys.

Do not put API keys in YAML. To enable publisher APIs, create a local `.env` file or set shell variables:

```powershell
$env:LITERATURE_DIGEST_USER_AGENT = "literature-daily-digest/1.0 (mailto:your-email@example.com)"
$env:ELSEVIER_API_KEY = "your-elsevier-key"
$env:SPRINGER_NATURE_API_KEY = "your-springer-key"
```

Then add `elsevier` and/or `springer` under `sources`.

## GitHub-Safe Layout

Commit these files:

- `SKILL.md`
- `agents/openai.yaml`
- `references/config-schema.md`
- `scripts/literature_digest.py`
- `scripts/sample_config.yaml`
- `.env.example`
- `.gitignore`

Keep these local and uncommitted:

- `.env`
- `scripts/config.local.yaml`
- any `scripts/*private*.yaml` or `scripts/*personal*.yaml`
- generated `reports/` folders
