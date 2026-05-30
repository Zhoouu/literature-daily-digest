const listFields = [
  "keywords",
  "journals",
  "priority_journals",
  "publisher_watch_terms",
  "openalex_publisher_ids",
  "nature_portfolio_journals",
  "exclude_keywords",
];

const boolFields = [
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
];

const intFields = [
  "journal_watch_per_term",
  "days_back",
  "max_papers",
  "max_candidates_per_source",
  "springer_page_size",
  "timeout_seconds",
  "full_text_max_chars",
  "full_text_min_chars",
  "full_text_max_papers",
];

const stringFields = [
  "output_dir",
  "full_text_dirname",
  "visuals_dirname",
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
];

const envKeys = [
  "LITERATURE_DIGEST_USER_AGENT",
  "ELSEVIER_API_KEY",
  "ELSEVIER_INSTTOKEN",
  "SPRINGER_NATURE_API_KEY",
  "SPRINGER_OPENACCESS_API_KEY",
];

let state = null;

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  bindTabs();
  bindButtons();
  loadState();
});

function bindTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      $(`${button.dataset.tab}Panel`).classList.add("active");
    });
  });
}

function bindButtons() {
  $("saveButton").addEventListener("click", saveConfig);
  $("loadSampleButton").addEventListener("click", loadSample);
  $("saveAndOfflineButton").addEventListener("click", saveAndRunOffline);
  $("runDigestButton").addEventListener("click", runDigest);
  $("copyRunButton").addEventListener("click", () => copyValue("runCommand"));
  $("copyOfflineButton").addEventListener("click", () => copyValue("offlineCommand"));
  document.querySelectorAll("[data-reveal]").forEach((button) => {
    button.addEventListener("click", () => toggleSecret(button.dataset.reveal, button));
  });
}

async function loadState() {
  try {
    const response = await fetch("/api/state");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    state = await response.json();
    renderState(state);
    showToast("Config loaded");
  } catch (error) {
    showToast(`Could not load config UI state: ${error.message}`);
  }
}

async function loadSample() {
  try {
    const response = await fetch("/api/state?sample=1");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const sampleState = await response.json();
    state = { ...state, ...sampleState, loadedFrom: "sample" };
    renderState(state);
    showToast("Sample loaded");
  } catch (error) {
    showToast(`Could not load sample: ${error.message}`);
  }
}

function renderState(nextState) {
  const config = nextState.config || {};
  listFields.forEach((field) => {
    $(field).value = (config[field] || []).join("\n");
  });
  boolFields.forEach((field) => {
    $(field).checked = Boolean(config[field]);
  });
  intFields.forEach((field) => {
    $(field).value = config[field] ?? "";
  });
  stringFields.forEach((field) => {
    $(field).value = config[field] ?? "";
  });
  envKeys.forEach((key) => {
    $(key).value = (nextState.env || {})[key] || "";
  });
  renderSources(nextState.sourceChoices || [], config.sources || []);
  renderFullTextSources(nextState.fullTextSourceChoices || [], config.full_text_sources || []);
  $("loadedFromBadge").textContent = nextState.loadedFrom === "local" ? "Local config" : "Sample config";
  $("configPathBadge").textContent = nextState.paths?.config || "";
  $("envPathBadge").textContent = nextState.paths?.env || "";
  $("runCommand").value = nextState.commands?.run || "";
  $("offlineCommand").value = nextState.commands?.offline || "";
  renderStatus(nextState.warnings || []);
  updateSourceCount();
}

function renderSources(choices, selected) {
  const selectedSet = new Set(selected);
  $("sourceGrid").innerHTML = "";
  choices.forEach((choice) => {
    const id = `source_${choice.id}`;
    const label = document.createElement("label");
    label.className = "checkbox-tile";
    label.innerHTML = `
      <input id="${id}" data-source="${choice.id}" type="checkbox" ${selectedSet.has(choice.id) ? "checked" : ""}>
      <span>
        <strong>${escapeHtml(choice.label)}</strong>
        ${choice.requiresKey ? '<span class="source-tag">API key</span>' : ""}
      </span>
    `;
    label.querySelector("input").addEventListener("change", updateSourceCount);
    $("sourceGrid").appendChild(label);
  });
}

function renderFullTextSources(choices, selected) {
  const selectedSet = new Set(selected);
  $("fullTextSourceGrid").innerHTML = "";
  choices.forEach((choice) => {
    const id = `fulltext_${choice}`;
    const label = document.createElement("label");
    label.className = "checkbox-tile";
    label.innerHTML = `
      <input id="${id}" data-fulltext-source="${choice}" type="checkbox" ${selectedSet.has(choice) ? "checked" : ""}>
      <span><strong>${escapeHtml(choice)}</strong></span>
    `;
    $("fullTextSourceGrid").appendChild(label);
  });
}

function gatherPayload() {
  const config = {};
  listFields.forEach((field) => {
    config[field] = splitLines($(field).value);
  });
  config.sources = Array.from(document.querySelectorAll("[data-source]:checked")).map((input) => input.dataset.source);
  config.full_text_sources = Array.from(document.querySelectorAll("[data-fulltext-source]:checked")).map(
    (input) => input.dataset.fulltextSource,
  );
  boolFields.forEach((field) => {
    config[field] = $(field).checked;
  });
  intFields.forEach((field) => {
    config[field] = Number.parseInt($(field).value, 10);
  });
  stringFields.forEach((field) => {
    config[field] = $(field).value.trim();
  });
  const env = {};
  envKeys.forEach((key) => {
    env[key] = $(key).value.trim();
  });
  return { config, env };
}

async function saveConfig() {
  const response = await postJson("/api/save", gatherPayload());
  state = response;
  renderState(state);
  showToast("Saved");
  return response;
}

async function saveAndRunOffline() {
  try {
    await saveConfig();
    await runEndpoint("/api/run-offline", "Offline sample");
  } catch (error) {
    showToast(error.message);
  }
}

async function runDigest() {
  try {
    await saveConfig();
    await runEndpoint("/api/run", "Digest");
  } catch (error) {
    showToast(error.message);
  }
}

async function runEndpoint(path, label) {
  $("runStatusBadge").textContent = "Running";
  $("runOutput").textContent = `${label} started...\n`;
  const response = await postJson(path, {});
  state = response;
  renderState(state);
  const run = response.run || {};
  const output = [
    run.command || "",
    "",
    run.stdout ? `STDOUT\n${run.stdout}` : "",
    run.stderr ? `STDERR\n${run.stderr}` : "",
    `Exit code: ${run.returnCode ?? "unknown"}`,
  ]
    .filter(Boolean)
    .join("\n");
  $("runOutput").textContent = output;
  $("runStatusBadge").textContent = run.ok ? "Complete" : "Failed";
  showToast(run.ok ? `${label} complete` : `${label} failed`);
}

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || data.error) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function renderStatus(warnings) {
  const statusList = $("statusList");
  statusList.innerHTML = "";
  if (!warnings.length) {
    const item = document.createElement("div");
    item.className = "status-item ok";
    item.textContent = "No warnings";
    statusList.appendChild(item);
    return;
  }
  warnings.forEach((warning) => {
    const item = document.createElement("div");
    item.className = "status-item warning";
    item.textContent = warning;
    statusList.appendChild(item);
  });
}

function updateSourceCount() {
  const count = document.querySelectorAll("[data-source]:checked").length;
  $("sourceCountBadge").textContent = `${count} enabled`;
}

function splitLines(value) {
  const seen = new Set();
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter((item) => {
      if (!item || seen.has(item.toLowerCase())) {
        return false;
      }
      seen.add(item.toLowerCase());
      return true;
    });
}

async function copyValue(id) {
  const value = $(id).value;
  try {
    await navigator.clipboard.writeText(value);
    showToast("Copied");
  } catch {
    $(id).select();
    document.execCommand("copy");
    showToast("Copied");
  }
}

function toggleSecret(id, button) {
  const input = $(id);
  const isPassword = input.type === "password";
  input.type = isPassword ? "text" : "password";
  button.textContent = isPassword ? "Hide" : "Show";
}

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove("show"), 2400);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
