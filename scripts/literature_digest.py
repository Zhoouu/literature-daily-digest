#!/usr/bin/env python3
"""Discover recent papers and write a Markdown literature-digest draft.

The script intentionally uses the Python standard library for HTTP and parsing
so the skill can run in a fresh Codex environment without dependency setup.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import html
import json
import os
import re
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_SOURCES = ["pubmed", "arxiv", "crossref", "openalex"]


@dataclass
class Paper:
    title: str
    authors: List[str] = field(default_factory=list)
    journal: str = ""
    published: str = ""
    doi: str = ""
    url: str = ""
    abstract: str = ""
    source: str = ""
    source_id: str = ""
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)


@dataclass
class SourceStatus:
    source: str
    ok: bool
    message: str
    count: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Markdown daily literature digest.")
    parser.add_argument("--config", required=True, help="Path to YAML or JSON config.")
    parser.add_argument(
        "--env-file",
        help="Path to a local .env file with API keys. Defaults to auto-loading .env near the config or current directory.",
    )
    parser.add_argument("--date", help="Run date in YYYY-MM-DD format. Defaults to today.")
    parser.add_argument("--days-back", type=int, help="Override config days_back.")
    parser.add_argument("--max-papers", type=int, help="Override config max_papers.")
    parser.add_argument("--output-dir", help="Override config output_dir.")
    parser.add_argument(
        "--no-visuals",
        action="store_true",
        help="Do not write SVG visual overview assets, even when include_visuals is true in config.",
    )
    parser.add_argument(
        "--offline-sample",
        action="store_true",
        help="Generate a local sample report without calling network APIs.",
    )
    return parser.parse_args()


def load_env_files(config_path: Path, env_file: Optional[str]) -> None:
    if env_file:
        path = Path(env_file)
        if not path.exists():
            raise FileNotFoundError(f"Environment file not found: {path}")
        load_env_file(path)
        return

    candidates = [
        Path.cwd() / ".env",
        config_path.parent / ".env",
        config_path.parent.parent / ".env",
    ]
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        load_env_file(path)


def load_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        os.environ.setdefault(key, parse_env_value(value))


def parse_env_value(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
        return str(parsed)
    return value.split(" #", 1)[0].strip()


def load_config(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("Config root must be a mapping.")
        return data
    except ImportError:
        return parse_simple_yaml(text)


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Parse the limited top-level YAML shape used by sample_config.yaml."""

    data: Dict[str, Any] = {}
    current_key: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if re.match(r"^\s*-\s+", line):
            if current_key is None:
                raise ValueError(f"List item without a key: {raw_line}")
            data.setdefault(current_key, [])
            item = line.strip()[2:].strip()
            data[current_key].append(parse_scalar(item))
            continue
        if ":" not in line:
            raise ValueError(f"Unsupported YAML line: {raw_line}")
        key, value = line.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        if value == "":
            data[current_key] = []
        else:
            data[current_key] = parse_scalar(value)
            current_key = None
    return data


def parse_scalar(value: str) -> Any:
    if value in {"[]", "{}"}:
        return [] if value == "[]" else {}
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return ast.literal_eval(value)
    return value


def normalize_config(config: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    normalized = dict(config)
    normalized.setdefault("keywords", [])
    normalized.setdefault("journals", [])
    normalized.setdefault("priority_journals", [])
    normalized.setdefault("exclude_keywords", [])
    normalized.setdefault("days_back", 1)
    normalized.setdefault("max_papers", 10)
    normalized.setdefault("output_dir", "reports")
    normalized.setdefault("sources", DEFAULT_SOURCES)
    normalized.setdefault("include_abstracts", True)
    normalized.setdefault("include_scholarly_scaffold", True)
    normalized.setdefault("include_visuals", True)
    normalized.setdefault("visuals_dirname", "assets")
    normalized.setdefault("timeout_seconds", 20)
    normalized.setdefault("user_agent", "literature-daily-digest/1.0")
    normalized.setdefault("user_agent_env", "LITERATURE_DIGEST_USER_AGENT")
    normalized.setdefault("elsevier_api_key_env", "ELSEVIER_API_KEY")
    normalized.setdefault("elsevier_insttoken_env", "ELSEVIER_INSTTOKEN")
    normalized.setdefault("elsevier_no_proxy", True)
    normalized.setdefault("scopus_search_view", "STANDARD")
    normalized.setdefault("scopus_enrich_abstracts", True)
    normalized.setdefault("scopus_abstract_view", "META_ABS")
    normalized.setdefault("elsevier_sciencedirect_view", "COMPLETE")
    normalized.setdefault("springer_api_key_env", "SPRINGER_NATURE_API_KEY")

    if args.days_back is not None:
        normalized["days_back"] = args.days_back
    if args.max_papers is not None:
        normalized["max_papers"] = args.max_papers
    if args.output_dir:
        normalized["output_dir"] = args.output_dir
    if args.no_visuals:
        normalized["include_visuals"] = False

    for key in ["keywords", "journals", "priority_journals", "exclude_keywords", "sources"]:
        normalized[key] = as_string_list(normalized.get(key, []))

    for key in [
        "user_agent_env",
        "elsevier_api_key_env",
        "elsevier_insttoken_env",
        "scopus_search_view",
        "scopus_abstract_view",
        "elsevier_sciencedirect_view",
        "springer_api_key_env",
        "visuals_dirname",
    ]:
        normalized[key] = str(normalized.get(key, "") or "").strip()

    user_agent_env = normalized["user_agent_env"]
    if user_agent_env:
        env_user_agent = os.environ.get(user_agent_env, "").strip()
        if env_user_agent:
            normalized["user_agent"] = env_user_agent

    normalized["days_back"] = max(1, int(normalized.get("days_back", 1)))
    normalized["max_papers"] = max(1, int(normalized.get("max_papers", 10)))
    normalized["timeout_seconds"] = max(5, int(normalized.get("timeout_seconds", 20)))
    default_candidates = max(normalized["max_papers"] * 4, 20)
    normalized["max_candidates_per_source"] = max(
        1,
        int(normalized.get("max_candidates_per_source") or default_candidates),
    )

    if not normalized["keywords"] and not normalized["journals"]:
        raise ValueError("Config must include at least one keyword or journal.")
    return normalized


def as_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        items: List[str] = []
        for item in value:
            if isinstance(item, (list, tuple)):
                items.extend(as_string_list(item))
            elif item is not None and str(item).strip():
                items.append(str(item).strip())
        return items
    return [str(value).strip()]


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def parse_run_date(value: Optional[str]) -> dt.date:
    if value:
        return dt.date.fromisoformat(value)
    return dt.date.today()


def date_window(run_date: dt.date, days_back: int) -> Tuple[dt.date, dt.date]:
    return run_date - dt.timedelta(days=days_back - 1), run_date


def request_text(url: str, config: Dict[str, Any], extra_headers: Optional[Dict[str, str]] = None) -> str:
    headers = {
        "User-Agent": str(config.get("user_agent", "literature-daily-digest/1.0")),
        "Accept": "application/json, application/xml, text/xml, */*",
    }
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(
        url,
        headers=headers,
    )
    timeout = int(config.get("timeout_seconds", 20))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if should_bypass_proxy(url, config) else None
    open_url = opener.open if opener else urllib.request.urlopen
    with open_url(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def should_bypass_proxy(url: str, config: Dict[str, Any]) -> bool:
    if not as_bool(config.get("elsevier_no_proxy"), True):
        return False
    host = urllib.parse.urlparse(url).hostname or ""
    return host.lower() == "api.elsevier.com"


def strip_markup(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def compact_text(value: str, max_chars: int = 1800) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def normalize_doi(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    return value.lower()


def build_query(config: Dict[str, Any]) -> str:
    terms = config["keywords"] or config["journals"]
    return " OR ".join(terms)


def quoted_or_query(terms: List[str]) -> str:
    cleaned = [term.replace('"', "").strip() for term in terms if term.strip()]
    if not cleaned:
        return ""
    return " OR ".join(f'"{term}"' if " " in term else term for term in cleaned)


def scopus_query(config: Dict[str, Any]) -> str:
    terms = config["keywords"] or config["journals"]
    query = quoted_or_query(terms)
    if not query:
        return ""
    if config["keywords"]:
        return f"TITLE-ABS-KEY({query})"
    return f"SRCTITLE({query})"


def env_api_key(config: Dict[str, Any], config_field: str, fallback_names: List[str]) -> Tuple[str, str]:
    configured = str(config.get(config_field, "") or "").strip()
    names = [configured] if configured else []
    names.extend(name for name in fallback_names if name not in names)
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value, name
    return "", configured or fallback_names[0]


def elsevier_headers(config: Dict[str, Any], api_key: str) -> Dict[str, str]:
    headers = {"X-ELS-APIKey": api_key}
    insttoken, _ = env_api_key(config, "elsevier_insttoken_env", ["ELSEVIER_INSTTOKEN"])
    if insttoken:
        headers["X-ELS-Insttoken"] = insttoken
    return headers


def http_status(exc: BaseException) -> Optional[int]:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code
    return None


def fetch_pubmed(config: Dict[str, Any], start: dt.date, end: dt.date) -> Tuple[List[Paper], SourceStatus]:
    terms: List[str] = []
    for keyword in config["keywords"]:
        terms.append(f'"{keyword}"[Title/Abstract]')
    for journal in config["journals"]:
        terms.append(f'"{journal}"[Journal]')
    query = " OR ".join(terms)
    params = {
        "db": "pubmed",
        "term": query,
        "mindate": start.strftime("%Y/%m/%d"),
        "maxdate": end.strftime("%Y/%m/%d"),
        "datetype": "pdat",
        "retmax": str(config["max_candidates_per_source"]),
        "retmode": "json",
        "sort": "pub date",
    }
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)
    try:
        search_data = json.loads(request_text(esearch_url, config))
        ids = search_data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return [], SourceStatus("pubmed", True, "No PubMed records found in date window.", 0)
        efetch_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
        }
        efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(efetch_params)
        root = ET.fromstring(request_text(efetch_url, config))
        papers = [parse_pubmed_article(article) for article in root.findall(".//PubmedArticle")]
        papers = [paper for paper in papers if paper.title]
        return papers, SourceStatus("pubmed", True, "Fetched PubMed records.", len(papers))
    except Exception as exc:  # noqa: BLE001
        return [], SourceStatus("pubmed", False, f"PubMed failed: {exc}", 0)


def parse_pubmed_article(article: ET.Element) -> Paper:
    title = text_from(article, ".//ArticleTitle")
    journal = text_from(article, ".//Journal/Title") or text_from(article, ".//ISOAbbreviation")
    abstract_parts = [strip_markup("".join(part.itertext())) for part in article.findall(".//Abstract/AbstractText")]
    abstract = " ".join(part for part in abstract_parts if part)
    authors = []
    for author in article.findall(".//Author")[:8]:
        last = text_from(author, "LastName")
        initials = text_from(author, "Initials")
        collective = text_from(author, "CollectiveName")
        name = collective or " ".join(part for part in [last, initials] if part)
        if name:
            authors.append(name)
    doi = ""
    for article_id in article.findall(".//ArticleId"):
        if article_id.attrib.get("IdType", "").lower() == "doi":
            doi = article_id.text or ""
            break
    pmid = text_from(article, ".//PMID")
    published = pubmed_date(article)
    return Paper(
        title=strip_markup(title),
        authors=authors,
        journal=strip_markup(journal),
        published=published,
        doi=normalize_doi(doi),
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        abstract=strip_markup(abstract),
        source="PubMed",
        source_id=pmid,
    )


def text_from(node: ET.Element, path: str) -> str:
    found = node.find(path)
    if found is None:
        return ""
    return strip_markup("".join(found.itertext()))


def pubmed_date(article: ET.Element) -> str:
    date_node = article.find(".//Article/Journal/JournalIssue/PubDate")
    if date_node is None:
        return ""
    year = text_from(date_node, "Year")
    month = text_from(date_node, "Month")
    day = text_from(date_node, "Day")
    if month and not month.isdigit():
        month = month_name_to_number(month)
    if year and month and day:
        return f"{year}-{int(month):02d}-{int(day):02d}"
    if year and month:
        return f"{year}-{int(month):02d}"
    return year


def month_name_to_number(value: str) -> str:
    months = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    return str(months.get(value[:3].lower(), 1))


def fetch_arxiv(config: Dict[str, Any], start: dt.date, end: dt.date) -> Tuple[List[Paper], SourceStatus]:
    query_terms = [f'all:"{term}"' for term in (config["keywords"] or config["journals"])]
    query = " OR ".join(query_terms)
    params = {
        "search_query": query,
        "start": "0",
        "max_results": str(config["max_candidates_per_source"]),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    try:
        root = ET.fromstring(request_text(url, config))
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        papers = []
        for entry in root.findall("atom:entry", ns):
            paper = parse_arxiv_entry(entry, ns)
            if date_in_window(paper.published, start, end):
                papers.append(paper)
        return papers, SourceStatus("arxiv", True, "Fetched arXiv records.", len(papers))
    except Exception as exc:  # noqa: BLE001
        return [], SourceStatus("arxiv", False, f"arXiv failed: {exc}", 0)


def parse_arxiv_entry(entry: ET.Element, ns: Dict[str, str]) -> Paper:
    title = find_text_ns(entry, "atom:title", ns)
    abstract = find_text_ns(entry, "atom:summary", ns)
    url = find_text_ns(entry, "atom:id", ns)
    published = find_text_ns(entry, "atom:published", ns)[:10]
    authors = [find_text_ns(author, "atom:name", ns) for author in entry.findall("atom:author", ns)]
    doi = find_text_ns(entry, "arxiv:doi", ns)
    journal = find_text_ns(entry, "arxiv:journal_ref", ns) or "arXiv"
    return Paper(
        title=strip_markup(title),
        authors=[author for author in authors if author][:8],
        journal=strip_markup(journal),
        published=published,
        doi=normalize_doi(doi),
        url=url,
        abstract=strip_markup(abstract),
        source="arXiv",
        source_id=url.rsplit("/", 1)[-1] if url else "",
    )


def find_text_ns(node: ET.Element, path: str, ns: Dict[str, str]) -> str:
    found = node.find(path, ns)
    if found is None:
        return ""
    return strip_markup("".join(found.itertext()))


def fetch_crossref(config: Dict[str, Any], start: dt.date, end: dt.date) -> Tuple[List[Paper], SourceStatus]:
    params = {
        "query.bibliographic": build_query(config),
        "filter": f"from-pub-date:{start.isoformat()},until-pub-date:{end.isoformat()},type:journal-article",
        "sort": "published",
        "order": "desc",
        "rows": str(config["max_candidates_per_source"]),
    }
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    try:
        data = json.loads(request_text(url, config))
        items = data.get("message", {}).get("items", [])
        papers = [parse_crossref_item(item) for item in items]
        papers = [paper for paper in papers if paper.title]
        return papers, SourceStatus("crossref", True, "Fetched Crossref records.", len(papers))
    except Exception as exc:  # noqa: BLE001
        return [], SourceStatus("crossref", False, f"Crossref failed: {exc}", 0)


def parse_crossref_item(item: Dict[str, Any]) -> Paper:
    title = first_string(item.get("title"))
    journal = first_string(item.get("container-title"))
    authors = []
    for author in item.get("author", [])[:8]:
        name = " ".join(part for part in [author.get("given", ""), author.get("family", "")] if part)
        if name:
            authors.append(name)
    doi = normalize_doi(item.get("DOI", ""))
    url = item.get("URL", "") or (f"https://doi.org/{doi}" if doi else "")
    abstract = strip_markup(item.get("abstract", ""))
    published = date_parts_to_iso(item.get("published-print") or item.get("published-online") or item.get("published"))
    return Paper(
        title=strip_markup(title),
        authors=authors,
        journal=strip_markup(journal),
        published=published,
        doi=doi,
        url=url,
        abstract=abstract,
        source="Crossref",
        source_id=doi,
    )


def fetch_openalex(config: Dict[str, Any], start: dt.date, end: dt.date) -> Tuple[List[Paper], SourceStatus]:
    filters = f"from_publication_date:{start.isoformat()},to_publication_date:{end.isoformat()},type:article"
    params = {
        "search": build_query(config),
        "filter": filters,
        "sort": "publication_date:desc",
        "per-page": str(min(config["max_candidates_per_source"], 200)),
    }
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    try:
        data = json.loads(request_text(url, config))
        items = data.get("results", [])
        papers = [parse_openalex_item(item) for item in items]
        papers = [paper for paper in papers if paper.title]
        return papers, SourceStatus("openalex", True, "Fetched OpenAlex records.", len(papers))
    except Exception as exc:  # noqa: BLE001
        return [], SourceStatus("openalex", False, f"OpenAlex failed: {exc}", 0)


def parse_openalex_item(item: Dict[str, Any]) -> Paper:
    title = item.get("title") or item.get("display_name") or ""
    authors = []
    for authorship in item.get("authorships", [])[:8]:
        author = authorship.get("author", {}).get("display_name", "")
        if author:
            authors.append(author)
    primary_location = item.get("primary_location") or {}
    source_info = primary_location.get("source") or {}
    journal = source_info.get("display_name", "") or item.get("host_venue", {}).get("display_name", "")
    doi = normalize_doi(item.get("doi") or "")
    url = item.get("doi") or item.get("id", "")
    abstract = inverted_index_to_text(item.get("abstract_inverted_index") or {})
    return Paper(
        title=strip_markup(title),
        authors=authors,
        journal=strip_markup(journal),
        published=item.get("publication_date", ""),
        doi=doi,
        url=url,
        abstract=strip_markup(abstract),
        source="OpenAlex",
        source_id=item.get("id", ""),
    )


def fetch_elsevier(config: Dict[str, Any], start: dt.date, end: dt.date) -> Tuple[List[Paper], SourceStatus]:
    api_key, env_name = env_api_key(config, "elsevier_api_key_env", ["ELSEVIER_API_KEY"])
    if not api_key:
        return [], SourceStatus(
            "elsevier",
            False,
            f"Elsevier ScienceDirect skipped: set environment variable {env_name} and enable source 'elsevier'.",
            0,
        )
    query = quoted_or_query(config["keywords"] or config["journals"])
    requested_view = (str(config.get("elsevier_sciencedirect_view") or "COMPLETE").strip() or "COMPLETE").upper()
    params = {
        "query": query,
        "count": str(min(config["max_candidates_per_source"], 100)),
        "httpAccept": "application/json",
        "view": requested_view,
    }
    headers = elsevier_headers(config, api_key)
    url = "https://api.elsevier.com/content/search/sciencedirect?" + urllib.parse.urlencode(params)
    try:
        data = json.loads(request_text(url, config, headers))
        entries = data.get("search-results", {}).get("entry", [])
        papers = [parse_elsevier_entry(entry) for entry in entries]
        papers = [paper for paper in papers if paper.title and date_in_window(paper.published, start, end)]
        return papers, SourceStatus("elsevier", True, "Fetched Elsevier ScienceDirect records.", len(papers))
    except Exception as exc:  # noqa: BLE001
        status = http_status(exc)
        if requested_view != "STANDARD" and status in {401, 403}:
            params["view"] = "STANDARD"
            retry_url = "https://api.elsevier.com/content/search/sciencedirect?" + urllib.parse.urlencode(params)
            try:
                data = json.loads(request_text(retry_url, config, headers))
                entries = data.get("search-results", {}).get("entry", [])
                papers = [parse_elsevier_entry(entry) for entry in entries]
                papers = [paper for paper in papers if paper.title and date_in_window(paper.published, start, end)]
                message = (
                    f"Fetched Elsevier ScienceDirect STANDARD records after {requested_view} was not authorized; "
                    "ScienceDirect abstracts may be unavailable."
                )
                return papers, SourceStatus("elsevier", True, message, len(papers))
            except Exception as retry_exc:  # noqa: BLE001
                return [], SourceStatus("elsevier", False, f"Elsevier ScienceDirect failed: {retry_exc}", 0)
        return [], SourceStatus("elsevier", False, f"Elsevier ScienceDirect failed: {exc}", 0)


def parse_elsevier_entry(entry: Dict[str, Any]) -> Paper:
    title = entry.get("dc:title") or entry.get("title") or ""
    journal = entry.get("prism:publicationName") or entry.get("publicationName") or ""
    doi = normalize_doi(entry.get("prism:doi") or entry.get("doi") or "")
    url = entry.get("prism:url") or link_value(entry.get("link")) or (f"https://doi.org/{doi}" if doi else "")
    abstract = entry.get("dc:description") or entry.get("description") or ""
    published = entry.get("prism:coverDate") or entry.get("coverDate") or entry.get("prism:coverDisplayDate") or ""
    authors = parse_authorish(entry.get("authors") or entry.get("author") or entry.get("dc:creator"))
    return Paper(
        title=strip_markup(str(title)),
        authors=authors[:8],
        journal=strip_markup(str(journal)),
        published=str(published),
        doi=doi,
        url=str(url),
        abstract=strip_markup(str(abstract)),
        source="Elsevier ScienceDirect",
        source_id=doi,
    )


def fetch_scopus(config: Dict[str, Any], start: dt.date, end: dt.date) -> Tuple[List[Paper], SourceStatus]:
    api_key, env_name = env_api_key(config, "elsevier_api_key_env", ["ELSEVIER_API_KEY"])
    if not api_key:
        return [], SourceStatus(
            "scopus",
            False,
            f"Scopus skipped: set environment variable {env_name} and enable source 'scopus'.",
            0,
        )
    requested_view = (str(config.get("scopus_search_view") or "STANDARD").strip() or "STANDARD").upper()
    params = {
        "query": scopus_query(config),
        "count": str(min(config["max_candidates_per_source"], 25)),
        "sort": "-orig-load-date",
        "httpAccept": "application/json",
        "view": requested_view,
    }
    if start.year == end.year:
        params["date"] = str(end.year)
    else:
        params["date"] = f"{start.year}-{end.year}"
    headers = elsevier_headers(config, api_key)
    url = "https://api.elsevier.com/content/search/scopus?" + urllib.parse.urlencode(params)
    try:
        data = json.loads(request_text(url, config, headers))
    except Exception as exc:  # noqa: BLE001
        status = http_status(exc)
        if requested_view != "STANDARD" and status in {401, 403}:
            params["view"] = "STANDARD"
            fallback_url = "https://api.elsevier.com/content/search/scopus?" + urllib.parse.urlencode(params)
            try:
                data = json.loads(request_text(fallback_url, config, headers))
                requested_view = "STANDARD"
            except Exception as retry_exc:  # noqa: BLE001
                return [], SourceStatus("scopus", False, f"Scopus failed: {retry_exc}", 0)
        else:
            return [], SourceStatus("scopus", False, f"Scopus failed: {exc}", 0)

    entries = data.get("search-results", {}).get("entry", [])
    papers = [parse_scopus_entry(entry) for entry in entries]
    papers = [paper for paper in papers if paper.title]
    abstract_note = ""
    added = 0
    if as_bool(config.get("scopus_enrich_abstracts"), True) and as_bool(config.get("include_abstracts"), True):
        added, abstract_note = enrich_scopus_abstracts(papers, config, api_key)
    message = f"Fetched Scopus {requested_view} records using year-level date filtering."
    if added:
        message += f" Added {added} abstracts through Scopus Abstract Retrieval."
    if abstract_note:
        message += f" {abstract_note}"
    return papers, SourceStatus("scopus", True, message, len(papers))


def enrich_scopus_abstracts(papers: List[Paper], config: Dict[str, Any], api_key: str) -> Tuple[int, str]:
    headers = elsevier_headers(config, api_key)
    view = (str(config.get("scopus_abstract_view") or "META_ABS").strip() or "META_ABS").upper()
    added = 0
    missing_ids = 0
    transient_failures = 0
    for paper in papers:
        if paper.abstract:
            continue
        identifier_path = scopus_retrieval_identifier_path(paper)
        if not identifier_path:
            missing_ids += 1
            continue
        params = {
            "view": view,
            "httpAccept": "application/json",
        }
        url = "https://api.elsevier.com/content/abstract/" + identifier_path + "?" + urllib.parse.urlencode(params)
        try:
            data = json.loads(request_text(url, config, headers))
        except Exception as exc:  # noqa: BLE001
            status = http_status(exc)
            if status in {401, 403}:
                return added, (
                    f"Scopus Abstract Retrieval {view} is not authorized for this Elsevier key; "
                    "Scopus-only entries may lack abstracts."
                )
            if status == 404:
                continue
            transient_failures += 1
            continue
        abstract = abstract_from_scopus_retrieval(data)
        if abstract:
            paper.abstract = strip_markup(abstract)
            added += 1
        time.sleep(0.1)
    notes = []
    if missing_ids:
        notes.append(f"{missing_ids} Scopus records had no retrievable Scopus ID/EID.")
    if transient_failures:
        notes.append(f"{transient_failures} Scopus abstract lookups failed transiently.")
    return added, " ".join(notes)


def scopus_retrieval_identifier_path(paper: Paper) -> str:
    for value in [paper.source_id, paper.url]:
        match = re.search(r"(?:SCOPUS_ID:|scopus_id/)(\d+)", value or "", flags=re.I)
        if match:
            return "scopus_id/" + urllib.parse.quote(match.group(1))
    for value in [paper.source_id, paper.url]:
        match = re.search(r"\b2-s2\.0-\d+\b", value or "", flags=re.I)
        if match:
            return "eid/" + urllib.parse.quote(match.group(0))
    return ""


def abstract_from_scopus_retrieval(data: Dict[str, Any]) -> str:
    response = data.get("abstracts-retrieval-response") or {}
    candidates = [
        response.get("coredata", {}),
        response,
        response.get("item", {}),
    ]
    for candidate in candidates:
        value = first_text_for_keys(candidate, {"dc:description", "description", "abstract"})
        if value:
            return value
    return ""


def first_text_for_keys(value: Any, keys: set[str]) -> str:
    if isinstance(value, dict):
        for key in keys:
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item
        for item in value.values():
            found = first_text_for_keys(item, keys)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = first_text_for_keys(item, keys)
            if found:
                return found
    return ""


def parse_scopus_entry(entry: Dict[str, Any]) -> Paper:
    title = entry.get("dc:title") or entry.get("title") or ""
    journal = entry.get("prism:publicationName") or entry.get("publicationName") or ""
    doi = normalize_doi(entry.get("prism:doi") or entry.get("doi") or "")
    url = entry.get("prism:url") or link_value(entry.get("link")) or (f"https://doi.org/{doi}" if doi else "")
    abstract = entry.get("dc:description") or entry.get("description") or ""
    published = entry.get("prism:coverDate") or entry.get("coverDate") or ""
    source_id = str(entry.get("dc:identifier") or entry.get("eid") or doi)
    authors = parse_authorish(entry.get("author") or entry.get("dc:creator"))
    return Paper(
        title=strip_markup(str(title)),
        authors=authors[:8],
        journal=strip_markup(str(journal)),
        published=str(published),
        doi=doi,
        url=str(url),
        abstract=strip_markup(str(abstract)),
        source="Scopus",
        source_id=source_id,
    )


def fetch_springer(config: Dict[str, Any], start: dt.date, end: dt.date) -> Tuple[List[Paper], SourceStatus]:
    api_key, env_name = env_api_key(config, "springer_api_key_env", ["SPRINGER_NATURE_API_KEY", "SPRINGER_API_KEY"])
    if not api_key:
        return [], SourceStatus(
            "springer",
            False,
            f"Springer Nature skipped: set environment variable {env_name} and enable source 'springer'.",
            0,
        )
    query = quoted_or_query(config["keywords"] or config["journals"])
    params = {
        "api_key": api_key,
        "q": query,
        "s": "1",
        "p": str(min(config["max_candidates_per_source"], 100)),
    }
    url = "https://api.springernature.com/meta/v2/json?" + urllib.parse.urlencode(params)
    try:
        data = json.loads(request_text(url, config))
        records = data.get("records", [])
        papers = [parse_springer_record(record) for record in records]
        papers = [paper for paper in papers if paper.title and date_in_window(paper.published, start, end)]
        return papers, SourceStatus("springer", True, "Fetched Springer Nature Meta records.", len(papers))
    except Exception as exc:  # noqa: BLE001
        return [], SourceStatus("springer", False, f"Springer Nature failed: {exc}", 0)


def parse_springer_record(record: Dict[str, Any]) -> Paper:
    title = record.get("title") or ""
    journal = record.get("journalTitle") or record.get("publicationName") or record.get("container-title") or ""
    doi = normalize_doi(record.get("doi") or "")
    url = link_value(record.get("url")) or (f"https://doi.org/{doi}" if doi else "")
    abstract = record.get("abstract") or ""
    published = record.get("publicationDate") or record.get("onlineDate") or record.get("printDate") or ""
    authors = parse_authorish(record.get("creators") or record.get("authors"))
    return Paper(
        title=strip_markup(str(title)),
        authors=authors[:8],
        journal=strip_markup(str(journal)),
        published=str(published),
        doi=doi,
        url=str(url),
        abstract=strip_markup(str(abstract)),
        source="Springer Nature Meta",
        source_id=doi,
    )


def parse_authorish(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        if "author" in value:
            return parse_authorish(value["author"])
        if "creator" in value:
            return parse_authorish(value["creator"])
        for key in ["name", "display_name", "$", "surname"]:
            if value.get(key):
                name = str(value[key])
                if key == "surname" and value.get("givenName"):
                    name = f"{value.get('givenName')} {name}"
                return [name]
        return []
    if isinstance(value, list):
        authors: List[str] = []
        for item in value:
            authors.extend(parse_authorish(item))
        return [author for author in authors if author]
    return [str(value)]


def link_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("@href") or value.get("href") or value.get("value") or value.get("$") or "")
    if isinstance(value, list):
        for item in value:
            found = link_value(item)
            if found:
                return found
    return ""


def first_string(value: Any) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    if value is None:
        return ""
    return str(value)


def date_parts_to_iso(value: Any) -> str:
    parts = (value or {}).get("date-parts", [[]])
    if not parts or not parts[0]:
        return ""
    year = int(parts[0][0])
    month = int(parts[0][1]) if len(parts[0]) > 1 else 1
    day = int(parts[0][2]) if len(parts[0]) > 2 else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def inverted_index_to_text(index: Dict[str, List[int]]) -> str:
    if not index:
        return ""
    positions: List[Tuple[int, str]] = []
    for word, indexes in index.items():
        for position in indexes:
            positions.append((int(position), word))
    return " ".join(word for _, word in sorted(positions))


def date_in_window(value: str, start: dt.date, end: dt.date) -> bool:
    parsed = parse_partial_date(value)
    if parsed is None:
        return True
    return start <= parsed <= end


def parse_partial_date(value: str) -> Optional[dt.date]:
    if not value:
        return None
    match = re.match(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", value)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2) or 1)
    day = int(match.group(3) or 1)
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def offline_sample_papers(run_date: dt.date) -> Tuple[List[Paper], List[SourceStatus]]:
    papers = [
        Paper(
            title="Deep learning reconstruction for portable ultrasound imaging",
            authors=["Sample A", "Sample B"],
            journal="IEEE Transactions on Medical Imaging",
            published=run_date.isoformat(),
            doi="10.0000/sample-ultrasound-1",
            url="https://doi.org/10.0000/sample-ultrasound-1",
            abstract=(
                "This sample record describes a neural reconstruction method for portable ultrasound. "
                "It reports improved image quality on a multi-center retrospective dataset."
            ),
            source="OfflineSample",
            source_id="sample-1",
        ),
        Paper(
            title="Foundation models for robust medical image analysis",
            authors=["Sample C"],
            journal="Medical Image Analysis",
            published=run_date.isoformat(),
            doi="10.0000/sample-medimg-2",
            url="https://doi.org/10.0000/sample-medimg-2",
            abstract=(
                "This sample record evaluates foundation models across segmentation and classification tasks "
                "and highlights domain shift as a major limitation."
            ),
            source="OfflineSample",
            source_id="sample-2",
        ),
    ]
    return papers, [SourceStatus("offline-sample", True, "Generated offline sample records.", len(papers))]


def fetch_all(config: Dict[str, Any], start: dt.date, end: dt.date) -> Tuple[List[Paper], List[SourceStatus]]:
    fetchers = {
        "pubmed": fetch_pubmed,
        "arxiv": fetch_arxiv,
        "crossref": fetch_crossref,
        "openalex": fetch_openalex,
        "scopus": fetch_scopus,
        "elsevier": fetch_elsevier,
        "sciencedirect": fetch_elsevier,
        "springer": fetch_springer,
        "springer-nature": fetch_springer,
    }
    all_papers: List[Paper] = []
    statuses: List[SourceStatus] = []
    for source in config["sources"]:
        source_key = source.lower()
        fetcher = fetchers.get(source_key)
        if fetcher is None:
            statuses.append(SourceStatus(source, False, f"Unsupported source: {source}", 0))
            continue
        papers, status = fetcher(config, start, end)
        all_papers.extend(papers)
        statuses.append(status)
        time.sleep(0.2)
    return all_papers, statuses


def filter_and_rank(papers: List[Paper], config: Dict[str, Any], run_date: dt.date) -> List[Paper]:
    filtered = [paper for paper in papers if not excluded(paper, config)]
    if config["journals"]:
        filtered = [paper for paper in filtered if journal_matches(paper.journal, config["journals"])]
    deduped = deduplicate(filtered)
    for paper in deduped:
        paper.score, paper.reasons = score_paper(paper, config, run_date)
    deduped.sort(key=lambda item: (item.score, item.published), reverse=True)
    return deduped[: config["max_papers"]]


def excluded(paper: Paper, config: Dict[str, Any]) -> bool:
    haystack = " ".join([paper.title, paper.abstract, paper.journal]).lower()
    return any(term.lower() in haystack for term in config["exclude_keywords"])


def journal_matches(journal: str, journals: Iterable[str]) -> bool:
    normalized = journal.lower()
    return any(term.lower() in normalized for term in journals)


def deduplicate(papers: List[Paper]) -> List[Paper]:
    merged: Dict[str, Paper] = {}
    for paper in papers:
        key = normalize_doi(paper.doi) or normalize_title(paper.title)
        if not key:
            continue
        existing = merged.get(key)
        if existing is None:
            merged[key] = paper
            continue
        if paper.source not in existing.source.split(", "):
            existing.source = f"{existing.source}, {paper.source}"
        if not existing.abstract or len(paper.abstract) > len(existing.abstract):
            existing.abstract = paper.abstract
        if not existing.doi and paper.doi:
            existing.doi = paper.doi
        if not existing.url and paper.url:
            existing.url = paper.url
        if not existing.journal and paper.journal:
            existing.journal = paper.journal
        if not existing.published and paper.published:
            existing.published = paper.published
        if len(paper.authors) > len(existing.authors):
            existing.authors = paper.authors
    return list(merged.values())


def score_paper(paper: Paper, config: Dict[str, Any], run_date: dt.date) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []
    title_lower = paper.title.lower()
    abstract_lower = paper.abstract.lower()

    title_matches = [term for term in config["keywords"] if term.lower() in title_lower]
    abstract_matches = [
        term for term in config["keywords"] if term.lower() in abstract_lower and term not in title_matches
    ]
    if title_matches:
        score += 3.0 * len(title_matches)
        reasons.append("title keyword match: " + ", ".join(title_matches))
    if abstract_matches:
        score += 1.0 * len(abstract_matches)
        reasons.append("abstract keyword match: " + ", ".join(abstract_matches))

    priority_hits = [journal for journal in config["priority_journals"] if journal.lower() in paper.journal.lower()]
    if priority_hits:
        score += 8.0
        reasons.append("priority journal: " + ", ".join(priority_hits))

    if config["journals"] and journal_matches(paper.journal, config["journals"]):
        score += 4.0
        reasons.append("configured journal filter matched")

    published_date = parse_partial_date(paper.published)
    if published_date:
        age = max(0, (run_date - published_date).days)
        recency = max(0.0, 3.0 - min(age, 30) / 10.0)
        score += recency
        reasons.append(f"recent publication: {paper.published}")

    if paper.doi:
        score += 0.5
    if paper.abstract:
        score += 0.5
    if "," in paper.source:
        score += 0.5
        reasons.append("found in multiple sources")
    if not reasons:
        reasons.append("metadata match from configured search")
    return score, reasons


def paper_type_label(paper: Paper) -> str:
    haystack = f"{paper.title} {paper.abstract}".lower()
    patterns = [
        ("Systematic review / meta-analysis", ["systematic review", "scoping review", "meta-analysis", "meta analysis"]),
        ("Computational / machine-learning study", ["machine learning", "deep learning", "foundation model", "segmentation", "classification", "prediction model"]),
        ("Clinical trial / intervention", ["randomized", "randomised", "clinical trial", "intervention"]),
        ("Observational clinical study", ["cohort", "case-control", "cross-sectional", "retrospective", "prospective"]),
        ("Experimental / laboratory study", ["experiment", "in vitro", "in vivo", "animal model", "phantom study"]),
        ("Qualitative / interview study", ["qualitative", "interview", "focus group", "thematic analysis"]),
        ("Case study / case series", ["case study", "case series", "case report"]),
        ("Theoretical / conceptual paper", ["framework", "conceptual", "theory", "perspective"]),
    ]
    for label, keywords in patterns:
        if any(keyword in haystack for keyword in keywords):
            return label
    return "Unclassified from metadata"


def method_signals(paper: Paper) -> List[str]:
    haystack = f"{paper.title} {paper.abstract}".lower()
    signals = [
        ("systematic review", "systematic review"),
        ("meta-analysis", "meta-analysis"),
        ("randomized", "randomized design"),
        ("retrospective", "retrospective data"),
        ("prospective", "prospective data"),
        ("cohort", "cohort design"),
        ("cross-sectional", "cross-sectional design"),
        ("deep learning", "deep learning"),
        ("machine learning", "machine learning"),
        ("foundation model", "foundation model"),
        ("segmentation", "segmentation task"),
        ("classification", "classification task"),
        ("simulation", "simulation"),
        ("phantom", "phantom experiment"),
        ("interview", "interviews"),
        ("qualitative", "qualitative analysis"),
    ]
    found = [label for keyword, label in signals if keyword in haystack]
    return found[:5]


def evidence_readiness(paper: Paper) -> str:
    if not paper.abstract:
        return "metadata only"
    markers = ["abstract"]
    if paper.doi:
        markers.append("DOI")
    if "," in paper.source:
        markers.append("multi-source match")
    return " + ".join(markers)


def evidence_caveat(paper: Paper) -> str:
    if not paper.abstract:
        return "Only metadata was retrieved; do not summarize methods, results, or conclusions beyond title-level signals."
    return "Based on retrieved abstract and metadata; verify numerical results, figures, and limitations against the full text before final claims."


def markdown_cell(value: str, max_chars: int = 88) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if len(value) > max_chars:
        value = value[: max_chars - 3].rstrip() + "..."
    return value.replace("|", "\\|")


def format_overview_table(papers: List[Paper]) -> List[str]:
    lines = [
        "| # | Paper | Venue | Type signal | Evidence | Score |",
        "|---|-------|-------|-------------|----------|-------|",
    ]
    for index, paper in enumerate(papers, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    markdown_cell(paper.title, 58),
                    markdown_cell(paper.journal or "not available", 34),
                    markdown_cell(paper_type_label(paper), 32),
                    markdown_cell(evidence_readiness(paper), 28),
                    f"{paper.score:.2f}",
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def safe_path_segment(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return value.strip(".-") or "assets"


def source_counts_from_papers(papers: List[Paper]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for paper in papers:
        for source in [part.strip() for part in paper.source.split(",") if part.strip()]:
            counts[source] = counts.get(source, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].lower())))


def write_visual_assets(
    papers: List[Paper],
    config: Dict[str, Any],
    run_date: dt.date,
    output_dir: Path,
) -> List[Tuple[str, str]]:
    if not papers or not as_bool(config.get("include_visuals"), True):
        return []

    asset_dirname = f"literature-digest-{run_date.isoformat()}-{safe_path_segment(str(config.get('visuals_dirname') or 'assets'))}"
    asset_dir = output_dir / asset_dirname
    asset_dir.mkdir(parents=True, exist_ok=True)

    score_path = asset_dir / "ranking-score-overview.svg"
    score_path.write_text(render_score_svg(papers), encoding="utf-8")

    source_path = asset_dir / "selected-source-coverage.svg"
    source_path.write_text(render_source_svg(source_counts_from_papers(papers)), encoding="utf-8")

    return [
        ("Ranking score overview", score_path.relative_to(output_dir).as_posix()),
        ("Selected paper source coverage", source_path.relative_to(output_dir).as_posix()),
    ]


def render_score_svg(papers: List[Paper]) -> str:
    width = 940
    row_height = 54
    chart_left = 350
    chart_width = 420
    height = 96 + row_height * len(papers)
    max_score = max((paper.score for paper in papers), default=1.0) or 1.0
    colors = ["#2563eb", "#059669", "#d97706", "#7c3aed", "#dc2626", "#0f766e"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Ranking score overview">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="28" y="38" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#111827">Daily Literature Picks</text>',
        '<text x="28" y="64" font-family="Arial, sans-serif" font-size="13" fill="#4b5563">Ranking scores are discovery signals, not quality judgments.</text>',
    ]
    for index, paper in enumerate(papers, start=1):
        y = 88 + (index - 1) * row_height
        bar_width = max(8, int((paper.score / max_score) * chart_width))
        color = colors[(index - 1) % len(colors)]
        title = html.escape(markdown_cell(f"{index}. {paper.title}", 54), quote=True)
        score = f"{paper.score:.2f}"
        parts.extend(
            [
                f'<text x="28" y="{y + 22}" font-family="Arial, sans-serif" font-size="13" fill="#111827">{title}</text>',
                f'<rect x="{chart_left}" y="{y + 6}" width="{chart_width}" height="18" rx="4" fill="#e5e7eb"/>',
                f'<rect x="{chart_left}" y="{y + 6}" width="{bar_width}" height="18" rx="4" fill="{color}"/>',
                f'<text x="{chart_left + chart_width + 16}" y="{y + 21}" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#111827">{score}</text>',
                f'<text x="{chart_left}" y="{y + 42}" font-family="Arial, sans-serif" font-size="12" fill="#6b7280">{html.escape(paper_type_label(paper), quote=True)}</text>',
            ]
        )
    parts.append("</svg>")
    return "\n".join(parts)


def render_source_svg(counts: Dict[str, int]) -> str:
    width = 760
    row_height = 48
    height = 86 + row_height * max(1, len(counts))
    max_count = max(counts.values(), default=1)
    chart_left = 220
    chart_width = 360
    colors = ["#059669", "#2563eb", "#d97706", "#7c3aed", "#dc2626", "#0891b2"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Selected paper source coverage">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="28" y="38" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#111827">Source Coverage</text>',
        '<text x="28" y="62" font-family="Arial, sans-serif" font-size="13" fill="#4b5563">How many selected papers were supported by each source.</text>',
    ]
    if not counts:
        parts.append('<text x="28" y="104" font-family="Arial, sans-serif" font-size="14" fill="#6b7280">No selected papers.</text>')
    for index, (source, count) in enumerate(counts.items(), start=1):
        y = 82 + (index - 1) * row_height
        bar_width = max(10, int((count / max_count) * chart_width))
        color = colors[(index - 1) % len(colors)]
        parts.extend(
            [
                f'<text x="28" y="{y + 21}" font-family="Arial, sans-serif" font-size="14" fill="#111827">{html.escape(source, quote=True)}</text>',
                f'<rect x="{chart_left}" y="{y + 6}" width="{chart_width}" height="18" rx="4" fill="#e5e7eb"/>',
                f'<rect x="{chart_left}" y="{y + 6}" width="{bar_width}" height="18" rx="4" fill="{color}"/>',
                f'<text x="{chart_left + chart_width + 16}" y="{y + 21}" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#111827">{count}</text>',
            ]
        )
    parts.append("</svg>")
    return "\n".join(parts)


def write_markdown(
    papers: List[Paper],
    statuses: List[SourceStatus],
    config: Dict[str, Any],
    run_date: dt.date,
    start: dt.date,
    end: dt.date,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"literature-digest-{run_date.isoformat()}.md"
    visual_assets = write_visual_assets(papers, config, run_date, output_dir)
    lines: List[str] = []
    lines.append(f"# Literature Daily Digest - {run_date.isoformat()}")
    lines.append("")
    lines.append("## Search Summary")
    lines.append("")
    lines.append(f"- Date window: {start.isoformat()} to {end.isoformat()}")
    lines.append(f"- Keywords: {format_list(config['keywords'])}")
    lines.append(f"- Journal filter: {format_list(config['journals'])}")
    lines.append(f"- Priority journals: {format_list(config['priority_journals'])}")
    lines.append(f"- Sources: {format_list(config['sources'])}")
    lines.append(f"- Max papers: {config['max_papers']}")
    lines.append(f"- Scholarly analysis scaffold: {'enabled' if as_bool(config.get('include_scholarly_scaffold'), True) else 'disabled'}")
    lines.append(f"- Visual overview: {'enabled' if visual_assets else 'disabled'}")
    lines.append("")
    lines.append("## Source Status")
    lines.append("")
    for status in statuses:
        marker = "OK" if status.ok else "FAILED"
        lines.append(f"- {marker} {status.source}: {status.message} ({status.count} records)")
    lines.append("")

    if not papers:
        lines.append("## Today's Picks")
        lines.append("")
        lines.append("No papers passed the configured filters. Check the source-status notes above, broaden keywords, or increase `days_back`.")
        lines.append("")
    else:
        if visual_assets:
            lines.append("## Visual Overview")
            lines.append("")
            for alt_text, relative_path in visual_assets:
                lines.append(f"![{alt_text}]({relative_path})")
                lines.append("")

        lines.append("## At A Glance")
        lines.append("")
        lines.extend(format_overview_table(papers))

        lines.append("## Today's Picks")
        lines.append("")
        for index, paper in enumerate(papers, start=1):
            lines.extend(
                format_paper(
                    index,
                    paper,
                    as_bool(config.get("include_abstracts"), True),
                    as_bool(config.get("include_scholarly_scaffold"), True),
                )
            )

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def format_list(values: List[str]) -> str:
    return ", ".join(values) if values else "none"


def format_paper(index: int, paper: Paper, include_abstract: bool, include_scholarly_scaffold: bool) -> List[str]:
    authors = ", ".join(paper.authors[:5])
    if len(paper.authors) > 5:
        authors += ", et al."
    doi_link = f"https://doi.org/{paper.doi}" if paper.doi else ""
    signals = method_signals(paper)
    lines = [
        f"### {index}. {paper.title}",
        "",
        f"- Authors: {authors or 'not available'}",
        f"- Journal/Venue: {paper.journal or 'not available'}",
        f"- Published: {paper.published or 'not available'}",
        f"- DOI: {paper.doi or 'not available'}",
        f"- URL: {paper.url or doi_link or 'not available'}",
        f"- Sources: {paper.source}",
        f"- Ranking score: {paper.score:.2f}",
        f"- Match reasons: {'; '.join(paper.reasons)}",
        f"- Type signal: {paper_type_label(paper)}",
        f"- Evidence status: {evidence_readiness(paper)}",
        "",
    ]
    if include_scholarly_scaffold:
        lines.extend(
            [
                "**学术精读框架（待 Codex 基于摘要/全文精炼）**",
                "",
                "- 领域定位：确认本文属于哪个问题域、研究范式和目标读者；避免只按关键词做表层归类。",
                f"- 方法/数据镜头：自动线索为 {', '.join(signals) if signals else '摘要/元数据未显式给出'}；终稿需说明研究设计、数据来源、样本/任务和可重复性边界。",
                "- 核心发现：只在摘要或全文明确给出时写结论；没有结果细节时标注“摘要未提供充分结果细节”。",
                "- 贡献判断：用“相比已有研究新增了什么”来概括，不把高分期刊或热点词等同于学术贡献。",
                "- Devil's Advocate：指出最可能被审稿人追问的一点，例如因果链、泛化范围、对照基线、样本偏倚或替代解释。",
                f"- 证据边界：{evidence_caveat(paper)}",
                "- 图文建议：若全文含关键机制图、流程图、模型结构图或核心结果图，终稿优先插入；若只有摘要，不生成伪图。",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "**中文总结初稿（待 Codex 精炼）**",
                "",
                "- 研究问题：基于题名和摘要初筛，本文可能与配置的研究方向相关。",
                "- 方法/数据：请在最终日报中根据摘要补充具体方法、数据集、实验设计或理论贡献。",
                "- 主要结果：仅在摘要明确给出时总结结果；否则标注“摘要未提供充分结果细节”。",
                "- 相关性：结合上方匹配原因判断其对当前研究关键词或期刊追踪的价值。",
                "",
            ]
        )
    if include_abstract and paper.abstract:
        lines.extend(["**English Abstract**", "", compact_text(paper.abstract), ""])
    elif include_abstract:
        lines.extend(["**English Abstract**", "", "Not available from the queried source.", ""])
    return lines


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    try:
        load_env_files(config_path, args.env_file)
        config = normalize_config(load_config(config_path), args)
        run_date = parse_run_date(args.date)
    except Exception as exc:  # noqa: BLE001
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    start, end = date_window(run_date, config["days_back"])
    if args.offline_sample:
        raw_papers, statuses = offline_sample_papers(run_date)
    else:
        raw_papers, statuses = fetch_all(config, start, end)
    ranked = filter_and_rank(raw_papers, config, run_date)
    output_path = write_markdown(ranked, statuses, config, run_date, start, end, Path(config["output_dir"]))
    print(f"Wrote {output_path} with {len(ranked)} papers.")
    failed = [status for status in statuses if not status.ok]
    if failed:
        print("Some sources failed; see report Source Status for details.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
