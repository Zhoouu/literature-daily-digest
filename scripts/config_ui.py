#!/usr/bin/env python3
"""Run a local web UI for editing literature-digest configuration.

The server is intentionally standard-library only so this skill remains easy to
use from a fresh clone. It writes public-safe research settings to an ignored
YAML file and secrets to a local .env file.
"""

from __future__ import annotations

import argparse
import ast
import json
import mimetypes
import os
import re
import subprocess
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = ROOT_DIR / "scripts"
UI_DIR = ROOT_DIR / "ui" / "configurator"
DEFAULT_CONFIG_PATH = SCRIPT_DIR / "config.local.yaml"
DEFAULT_SAMPLE_PATH = SCRIPT_DIR / "sample_config.yaml"
DEFAULT_ENV_PATH = ROOT_DIR / ".env"

SOURCE_CHOICES = [
    {"id": "pubmed", "label": "PubMed", "requiresKey": False},
    {"id": "arxiv", "label": "arXiv", "requiresKey": False},
    {"id": "crossref", "label": "Crossref", "requiresKey": False},
    {"id": "openalex", "label": "OpenAlex", "requiresKey": False},
    {"id": "scopus", "label": "Scopus", "requiresKey": True},
    {"id": "elsevier", "label": "Elsevier ScienceDirect", "requiresKey": True},
    {"id": "springer", "label": "Springer Nature Meta", "requiresKey": True},
    {"id": "springer-openaccess", "label": "Springer Nature OpenAccess", "requiresKey": True},
]

FULL_TEXT_SOURCE_CHOICES = ["elsevier", "sciencedirect", "springer-openaccess"]

LIST_FIELDS = {
    "keywords",
    "journals",
    "priority_journals",
    "publisher_watch_terms",
    "openalex_publisher_ids",
    "nature_portfolio_journals",
    "exclude_keywords",
    "sources",
    "full_text_sources",
}

BOOL_FIELDS = {
    "discover_priority_journals",
    "include_abstracts",
    "include_full_text",
    "include_scholarly_scaffold",
    "include_visuals",
    "include_per_paper_visuals",
    "include_overview_visuals",
    "elsevier_no_proxy",
    "scopus_enrich_abstracts",
    "springer_no_proxy",
}

INT_FIELDS = {
    "journal_watch_per_term": 0,
    "days_back": 1,
    "max_papers": 1,
    "max_candidates_per_source": 1,
    "springer_page_size": 1,
    "timeout_seconds": 5,
    "full_text_max_chars": 2000,
    "full_text_min_chars": 200,
    "full_text_max_papers": 0,
}

STRING_FIELDS = {
    "output_dir",
    "full_text_dirname",
    "visuals_dirname",
    "user_agent",
    "user_agent_env",
    "elsevier_api_key_env",
    "elsevier_insttoken_env",
    "scopus_search_view",
    "scopus_abstract_view",
    "elsevier_sciencedirect_view",
    "elsevier_article_retrieval_view",
    "elsevier_article_retrieval_accept",
    "springer_api_key_env",
    "springer_openaccess_api_key_env",
}

CONFIG_GROUPS = [
    (
        "Research profile",
        [
            "keywords",
            "journals",
            "priority_journals",
            "discover_priority_journals",
            "journal_watch_per_term",
            "publisher_watch_terms",
            "openalex_publisher_ids",
            "nature_portfolio_journals",
            "exclude_keywords",
        ],
    ),
    (
        "Discovery",
        [
            "days_back",
            "max_papers",
            "output_dir",
            "sources",
            "timeout_seconds",
            "max_candidates_per_source",
            "springer_page_size",
        ],
    ),
    (
        "Report",
        [
            "include_abstracts",
            "include_full_text",
            "full_text_sources",
            "full_text_dirname",
            "full_text_max_chars",
            "full_text_min_chars",
            "full_text_max_papers",
            "include_scholarly_scaffold",
            "include_visuals",
            "include_per_paper_visuals",
            "include_overview_visuals",
            "visuals_dirname",
        ],
    ),
    (
        "Environment binding",
        [
            "user_agent",
            "user_agent_env",
            "elsevier_api_key_env",
            "elsevier_insttoken_env",
            "elsevier_no_proxy",
            "scopus_search_view",
            "scopus_enrich_abstracts",
            "scopus_abstract_view",
            "elsevier_sciencedirect_view",
            "elsevier_article_retrieval_view",
            "elsevier_article_retrieval_accept",
            "springer_api_key_env",
            "springer_openaccess_api_key_env",
            "springer_no_proxy",
        ],
    ),
]

ENV_KEYS = [
    "LITERATURE_DIGEST_USER_AGENT",
    "ELSEVIER_API_KEY",
    "ELSEVIER_INSTTOKEN",
    "SPRINGER_NATURE_API_KEY",
    "SPRINGER_OPENACCESS_API_KEY",
]

ENV_COMMENTS = {
    "LITERATURE_DIGEST_USER_AGENT": "Optional: identify your local script politely to scholarly APIs.",
    "ELSEVIER_API_KEY": "Optional publisher APIs. Leave blank unless you enabled these sources.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the Literature Daily Digest local config UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="Port. Default: 8765")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Local YAML config path.")
    parser.add_argument("--sample", default=str(DEFAULT_SAMPLE_PATH), help="Public sample YAML path.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Local .env path.")
    parser.add_argument("--open", action="store_true", help="Open the UI in the default browser.")
    return parser.parse_args()


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Config root must be an object.")
        return data
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("Config root must be a mapping.")
        return data
    except ImportError:
        return parse_simple_yaml(text)


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Parse the top-level scalar/list YAML shape used by this project."""

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


def parse_env_file(path: Path) -> Dict[str, str]:
    values = {key: "" for key in ENV_KEYS}
    if not path.exists() or not path.is_file():
        return values
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
        if key in values:
            values[key] = parse_env_value(value)
    return values


def parse_env_value(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        try:
            return str(ast.literal_eval(value))
        except (SyntaxError, ValueError):
            return value[1:-1]
    return value.split(" #", 1)[0].strip()


def merge_config(sample: Dict[str, Any], local: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(sample)
    merged.update(local)
    return normalize_config(merged)


def normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(config)

    defaults: Dict[str, Any] = {
        "keywords": [],
        "journals": [],
        "priority_journals": [],
        "discover_priority_journals": True,
        "journal_watch_per_term": 8,
        "publisher_watch_terms": [],
        "openalex_publisher_ids": [],
        "nature_portfolio_journals": [],
        "exclude_keywords": [],
        "days_back": 1,
        "max_papers": 10,
        "output_dir": "reports",
        "sources": ["pubmed", "arxiv", "crossref", "openalex"],
        "timeout_seconds": 20,
        "max_candidates_per_source": 40,
        "springer_page_size": 20,
        "include_abstracts": True,
        "include_full_text": True,
        "full_text_sources": ["elsevier"],
        "full_text_dirname": "full-text",
        "full_text_max_chars": 60000,
        "full_text_min_chars": 1200,
        "full_text_max_papers": 10,
        "include_scholarly_scaffold": True,
        "include_visuals": True,
        "include_per_paper_visuals": True,
        "include_overview_visuals": False,
        "visuals_dirname": "assets",
        "user_agent": "literature-daily-digest/1.0",
        "user_agent_env": "LITERATURE_DIGEST_USER_AGENT",
        "elsevier_api_key_env": "ELSEVIER_API_KEY",
        "elsevier_insttoken_env": "ELSEVIER_INSTTOKEN",
        "elsevier_no_proxy": True,
        "scopus_search_view": "STANDARD",
        "scopus_enrich_abstracts": True,
        "scopus_abstract_view": "META_ABS",
        "elsevier_sciencedirect_view": "COMPLETE",
        "elsevier_article_retrieval_view": "FULL",
        "elsevier_article_retrieval_accept": "text/xml",
        "springer_api_key_env": "SPRINGER_NATURE_API_KEY",
        "springer_openaccess_api_key_env": "SPRINGER_OPENACCESS_API_KEY",
        "springer_no_proxy": True,
    }

    for key, value in defaults.items():
        normalized.setdefault(key, value)
    for key in LIST_FIELDS:
        normalized[key] = coerce_list(normalized.get(key, []))
    for key in BOOL_FIELDS:
        normalized[key] = coerce_bool(normalized.get(key), bool(defaults.get(key, False)))
    for key, minimum in INT_FIELDS.items():
        normalized[key] = coerce_int(normalized.get(key, defaults.get(key, minimum)), minimum)
    for key in STRING_FIELDS:
        normalized[key] = str(normalized.get(key, "") or "").strip()
    normalized["springer_page_size"] = min(20, normalized["springer_page_size"])

    source_ids = {choice["id"] for choice in SOURCE_CHOICES}
    normalized["sources"] = [source for source in normalized["sources"] if source in source_ids]
    if not normalized["sources"]:
        normalized["sources"] = ["pubmed", "arxiv", "crossref", "openalex"]
    normalized["full_text_sources"] = [
        source for source in normalized["full_text_sources"] if source in FULL_TEXT_SOURCE_CHOICES
    ]
    if not normalized["full_text_sources"]:
        normalized["full_text_sources"] = ["elsevier"]
    return normalized


def normalize_payload_config(raw_config: Dict[str, Any], current_config: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_config({**current_config, **raw_config})
    if not normalized["keywords"] and not normalized["journals"]:
        raise ValueError("Add at least one keyword or journal.")
    return normalized


def coerce_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[\r\n]+", value)
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        parts = [value]
    result: List[str] = []
    seen: set[str] = set()
    for part in parts:
        item = str(part or "").strip()
        if not item:
            continue
        marker = item.lower()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def coerce_int(value: Any, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, parsed)


def normalize_env_values(raw_env: Dict[str, Any]) -> Dict[str, str]:
    return {key: str(raw_env.get(key, "") or "").strip() for key in ENV_KEYS}


def build_warnings(config: Dict[str, Any], env_values: Dict[str, str]) -> List[str]:
    warnings: List[str] = []
    sources = set(config.get("sources", []))
    available_env = dict(env_values)
    for key in ENV_KEYS:
        available_env[key] = available_env.get(key) or os.environ.get(key, "")

    if {"scopus", "elsevier"} & sources and not available_env.get("ELSEVIER_API_KEY"):
        warnings.append("Elsevier-backed sources are enabled but ELSEVIER_API_KEY is empty.")
    if "springer" in sources and not available_env.get("SPRINGER_NATURE_API_KEY"):
        warnings.append("Springer Nature Meta is enabled but SPRINGER_NATURE_API_KEY is empty.")
    if "springer-openaccess" in sources and not (
        available_env.get("SPRINGER_OPENACCESS_API_KEY") or available_env.get("SPRINGER_NATURE_API_KEY")
    ):
        warnings.append("Springer OpenAccess is enabled but no Springer key is configured.")
    if config.get("include_full_text") and "elsevier" in config.get("full_text_sources", []):
        if not available_env.get("ELSEVIER_API_KEY"):
            warnings.append("Elsevier full-text enrichment needs ELSEVIER_API_KEY entitlement.")
    if config.get("include_full_text") and "springer-openaccess" in config.get("full_text_sources", []):
        if not (available_env.get("SPRINGER_OPENACCESS_API_KEY") or available_env.get("SPRINGER_NATURE_API_KEY")):
            warnings.append("Springer OpenAccess JATS full-text enrichment needs a Springer OpenAccess or Nature API key.")
    if not available_env.get("LITERATURE_DIGEST_USER_AGENT"):
        warnings.append("LITERATURE_DIGEST_USER_AGENT is empty; public sources will use the YAML user_agent.")
    return warnings


def write_yaml_config(path: Path, config: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Local configuration generated by scripts/config_ui.py.",
        "# This file is ignored by Git. Public defaults live in scripts/sample_config.yaml.",
        "",
    ]
    written: set[str] = set()
    for group_name, keys in CONFIG_GROUPS:
        lines.append(f"# {group_name}")
        for key in keys:
            if key not in config:
                continue
            lines.extend(format_yaml_field(key, config[key]))
            written.add(key)
        lines.append("")
    extra_keys = sorted(key for key in config if key not in written)
    if extra_keys:
        lines.append("# Other")
        for key in extra_keys:
            lines.extend(format_yaml_field(key, config[key]))
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def format_yaml_field(key: str, value: Any) -> List[str]:
    if isinstance(value, (list, tuple)):
        items = coerce_list(value)
        if not items:
            return [f"{key}: []"]
        lines = [f"{key}:"]
        lines.extend(f"  - {yaml_scalar(item, key)}" for item in items)
        return lines
    return [f"{key}: {yaml_scalar(value, key)}"]


def yaml_scalar(value: Any, key: str = "") -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if key in {"springer_api_key_env", "springer_openaccess_api_key_env"}:
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def write_env_file(path: Path, values: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    output: List[str] = []

    if existing_lines:
        for line in existing_lines:
            key = env_key_from_line(line)
            if key in values:
                output.append(f"{key}={format_env_value(values[key], key)}")
                seen.add(key)
            else:
                output.append(line)
        missing = [key for key in ENV_KEYS if key not in seen]
        if missing:
            if output and output[-1].strip():
                output.append("")
            for key in missing:
                comment = ENV_COMMENTS.get(key)
                if comment:
                    output.append(f"# {comment}")
                output.append(f"{key}={format_env_value(values[key], key)}")
    else:
        output = [
            "# Local environment for Literature Daily Digest. Do not commit this file.",
            "",
            "# Optional: identify your local script politely to scholarly APIs.",
            f"LITERATURE_DIGEST_USER_AGENT={format_env_value(values['LITERATURE_DIGEST_USER_AGENT'], 'LITERATURE_DIGEST_USER_AGENT')}",
            "",
            "# Optional publisher APIs. Leave blank unless you enabled these sources.",
            f"ELSEVIER_API_KEY={format_env_value(values['ELSEVIER_API_KEY'], 'ELSEVIER_API_KEY')}",
            f"ELSEVIER_INSTTOKEN={format_env_value(values['ELSEVIER_INSTTOKEN'], 'ELSEVIER_INSTTOKEN')}",
            f"SPRINGER_NATURE_API_KEY={format_env_value(values['SPRINGER_NATURE_API_KEY'], 'SPRINGER_NATURE_API_KEY')}",
            f"SPRINGER_OPENACCESS_API_KEY={format_env_value(values['SPRINGER_OPENACCESS_API_KEY'], 'SPRINGER_OPENACCESS_API_KEY')}",
        ]
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def env_key_from_line(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return ""
    key = stripped.split("=", 1)[0].strip()
    return key if key in ENV_KEYS else ""


def format_env_value(value: str, key: str = "") -> str:
    value = value or ""
    if not value:
        return ""
    if key in {"SPRINGER_NATURE_API_KEY", "SPRINGER_OPENACCESS_API_KEY"}:
        return value
    if re.fullmatch(r"[A-Za-z0-9_./:@+-]+", value):
        return value
    return json.dumps(value, ensure_ascii=False)


def make_command(config_path: Path, env_path: Path, offline: bool = False) -> str:
    parts = [
        "python",
        relative_path(SCRIPT_DIR / "literature_digest.py"),
        "--config",
        relative_path(config_path),
    ]
    if env_path.exists():
        parts.extend(["--env-file", relative_path(env_path)])
    if offline:
        parts.append("--offline-sample")
    return " ".join(quote_command_part(part) for part in parts)


def quote_command_part(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:\\-]+", value):
        return value
    return json.dumps(value)


def relative_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT_DIR.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def response_state(config_path: Path, sample_path: Path, env_path: Path, use_sample: bool = False) -> Dict[str, Any]:
    sample = normalize_config(load_config(sample_path))
    local_exists = config_path.exists()
    local = {} if use_sample or not local_exists else load_config(config_path)
    config = merge_config(sample, local)
    env_values = parse_env_file(env_path)
    loaded_from = "sample" if use_sample or not local_exists else "local"
    return {
        "config": config,
        "sampleConfig": sample,
        "env": env_values,
        "paths": {
            "config": relative_path(config_path),
            "configAbsolute": str(config_path.resolve()),
            "sample": relative_path(sample_path),
            "env": relative_path(env_path),
            "envAbsolute": str(env_path.resolve()),
        },
        "loadedFrom": loaded_from,
        "sourceChoices": SOURCE_CHOICES,
        "fullTextSourceChoices": FULL_TEXT_SOURCE_CHOICES,
        "envKeys": ENV_KEYS,
        "warnings": build_warnings(config, env_values),
        "commands": {
            "run": make_command(config_path, env_path),
            "offline": make_command(config_path, env_path, offline=True),
        },
    }


def run_digest(config_path: Path, env_path: Path, offline: bool) -> Dict[str, Any]:
    if not config_path.exists():
        raise ValueError("Save a local config before running the digest.")
    command = [
        sys.executable,
        str(SCRIPT_DIR / "literature_digest.py"),
        "--config",
        str(config_path),
    ]
    if env_path.exists():
        command.extend(["--env-file", str(env_path)])
    if offline:
        command.append("--offline-sample")
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    return {
        "ok": completed.returncode == 0,
        "returnCode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "command": " ".join(quote_command_part(part) for part in command),
    }


def make_handler(config_path: Path, sample_path: Path, env_path: Path) -> type[BaseHTTPRequestHandler]:
    class ConfigUIHandler(BaseHTTPRequestHandler):
        server_version = "LiteratureDigestConfigUI/1.0"

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/state":
                params = urllib.parse.parse_qs(parsed.query)
                use_sample = params.get("sample", ["0"])[0] == "1"
                self.send_json(response_state(config_path, sample_path, env_path, use_sample=use_sample))
                return
            self.serve_static(parsed.path)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            try:
                if parsed.path == "/api/save":
                    payload = self.read_json()
                    current = response_state(config_path, sample_path, env_path)["config"]
                    config = normalize_payload_config(payload.get("config", {}), current)
                    env_values = normalize_env_values(payload.get("env", {}))
                    write_yaml_config(config_path, config)
                    write_env_file(env_path, env_values)
                    self.send_json(response_state(config_path, sample_path, env_path) | {"saved": True})
                    return
                if parsed.path == "/api/run-offline":
                    result = run_digest(config_path, env_path, offline=True)
                    status = response_state(config_path, sample_path, env_path)
                    self.send_json(status | {"run": result})
                    return
                if parsed.path == "/api/run":
                    result = run_digest(config_path, env_path, offline=False)
                    status = response_state(config_path, sample_path, env_path)
                    self.send_json(status | {"run": result})
                    return
                self.send_error(404, "Not found")
            except subprocess.TimeoutExpired:
                self.send_json({"error": "Digest run timed out after 300 seconds."}, status=504)
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, status=400)

        def read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 2_000_000:
                raise ValueError("Request body is too large.")
            raw = self.rfile.read(length).decode("utf-8")
            data = json.loads(raw or "{}")
            if not isinstance(data, dict):
                raise ValueError("Request body must be a JSON object.")
            return data

        def send_json(self, data: Dict[str, Any], status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def serve_static(self, path: str) -> None:
            if path in {"", "/"}:
                file_path = UI_DIR / "index.html"
            else:
                relative = urllib.parse.unquote(path.lstrip("/"))
                file_path = UI_DIR / relative
            try:
                resolved = file_path.resolve()
                resolved.relative_to(UI_DIR.resolve())
            except ValueError:
                self.send_error(403, "Forbidden")
                return
            if not resolved.exists() or not resolved.is_file():
                self.send_error(404, "Not found")
                return
            content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            body = resolved.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    return ConfigUIHandler


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    sample_path = Path(args.sample).resolve()
    env_path = Path(args.env_file).resolve()
    if not UI_DIR.exists():
        print(f"UI assets not found: {UI_DIR}", file=sys.stderr)
        return 2
    if not sample_path.exists():
        print(f"Sample config not found: {sample_path}", file=sys.stderr)
        return 2

    handler = make_handler(config_path, sample_path, env_path)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Literature Daily Digest config UI: {url}")
    print(f"Config: {relative_path(config_path)}")
    print(f"Env: {relative_path(env_path)}")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping config UI.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
