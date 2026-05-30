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

const sourcePresets = {
  public: ["pubmed", "arxiv", "crossref", "openalex"],
  biomed: ["pubmed", "crossref", "openalex"],
  nature: ["openalex", "springer", "springer-openaccess"],
  publisher: ["pubmed", "crossref", "openalex", "scopus", "elsevier", "springer", "springer-openaccess"],
};

const textFieldMeta = [
  ["keywords", "keywordsMeta", "terms"],
  ["journals", "journalsMeta", "filters"],
  ["priority_journals", "priorityJournalsMeta", "journals"],
  ["nature_portfolio_journals", "naturePortfolioMeta", "journals"],
  ["publisher_watch_terms", "publisherWatchMeta", "terms"],
  ["openalex_publisher_ids", "openalexPublisherMeta", "IDs"],
  ["exclude_keywords", "excludeKeywordsMeta", "exclusions"],
];

let state = null;
let backendWarnings = [];
let isDirty = false;

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  bindTabs();
  bindButtons();
  loadState();
});

function bindTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      selectTab(button.dataset.tab);
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
  document.querySelectorAll("[data-jump-tab]").forEach((button) => {
    button.addEventListener("click", () => selectTab(button.dataset.jumpTab));
  });
  document.querySelectorAll("[data-source-preset]").forEach((button) => {
    button.addEventListener("click", () => applySourcePreset(button.dataset.sourcePreset));
  });
}

function bindFormUpdates() {
  document.querySelectorAll("input, select, textarea").forEach((element) => {
    if (element.dataset.liveBound === "true") {
      return;
    }
    const handler = () => {
      setDirty(true);
      updateDerivedUI();
    };
    element.addEventListener("input", handler);
    element.addEventListener("change", handler);
    element.dataset.liveBound = "true";
  });
}

function selectTab(tabName) {
  document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
  const button = document.querySelector(`[data-tab="${tabName}"]`);
  const panel = $(`${tabName}Panel`);
  if (!button || !panel) {
    return;
  }
  button.classList.add("active");
  panel.classList.add("active");
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
  backendWarnings = nextState.warnings || [];
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
  bindFormUpdates();
  setDirty(false);
  updateDerivedUI();
}

function renderSources(choices, selected) {
  const selectedSet = new Set(selected);
  $("sourceGrid").innerHTML = "";
  choices.forEach((choice) => {
    const id = `source_${choice.id}`;
    const label = document.createElement("label");
    label.className = `checkbox-tile source-tile source-${choice.id}`;
    label.classList.toggle("selected", selectedSet.has(choice.id));
    label.innerHTML = `
      <input id="${id}" data-source="${choice.id}" type="checkbox" ${selectedSet.has(choice.id) ? "checked" : ""}>
      <span>
        <strong>${escapeHtml(choice.label)}</strong>
        ${choice.requiresKey ? '<span class="source-tag">API key</span>' : ""}
      </span>
    `;
    const input = label.querySelector("input");
    input.addEventListener("change", () => {
      label.classList.toggle("selected", input.checked);
      setDirty(true);
      updateDerivedUI();
    });
    $("sourceGrid").appendChild(label);
  });
}

function renderFullTextSources(choices, selected) {
  const selectedSet = new Set(selected);
  $("fullTextSourceGrid").innerHTML = "";
  choices.forEach((choice) => {
    const id = `fulltext_${choice}`;
    const label = document.createElement("label");
    label.className = "checkbox-tile fulltext-tile";
    label.classList.toggle("selected", selectedSet.has(choice));
    label.innerHTML = `
      <input id="${id}" data-fulltext-source="${choice}" type="checkbox" ${selectedSet.has(choice) ? "checked" : ""}>
      <span><strong>${escapeHtml(choice)}</strong></span>
    `;
    const input = label.querySelector("input");
    input.addEventListener("change", () => {
      label.classList.toggle("selected", input.checked);
      setDirty(true);
      updateDerivedUI();
    });
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

function applySourcePreset(name) {
  const selected = new Set(sourcePresets[name] || []);
  document.querySelectorAll("[data-source]").forEach((input) => {
    input.checked = selected.has(input.dataset.source);
    input.closest(".checkbox-tile")?.classList.toggle("selected", input.checked);
  });
  setDirty(true);
  updateDerivedUI();
  showToast(`${presetLabel(name)} sources selected`);
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
  const normalized = warnings.map(normalizeWarning);
  if (!normalized.length) {
    const item = document.createElement("div");
    item.className = "status-item ok";
    item.textContent = "No warnings";
    statusList.appendChild(item);
    return;
  }
  normalized.forEach((warning) => {
    const item = document.createElement("div");
    item.className = `status-item ${warning.severity || "warning"}`;
    item.textContent = warning.message;
    statusList.appendChild(item);
  });
}

function updateSourceCount() {
  const count = document.querySelectorAll("[data-source]:checked").length;
  $("sourceCountBadge").textContent = `${count} enabled`;
}

function updateDerivedUI() {
  const snapshot = gatherPayload();
  const config = snapshot.config;
  const env = snapshot.env;
  updateFieldMeta(config);
  updateSourceCount();

  const localWarnings = buildLocalWarnings(config, env);
  const warnings = mergeWarnings([...backendWarnings.map((message) => ({ message, severity: "warning" })), ...localWarnings]);
  renderStatus(warnings);

  const blockingCount = warnings.filter((warning) => warning.severity === "error").length;
  const topicCount = config.keywords.length + config.journals.length;
  const apiChecks = requiredApiChecks(config, env);
  const activeApiChecks = apiChecks.filter((check) => check.required && check.metric !== false);
  const readyApiChecks = activeApiChecks.filter((check) => check.ready);

  $("profileMetric").textContent = String(topicCount);
  $("profileInsight").textContent = topicCount ? `${config.keywords.length} keyword / ${config.journals.length} journal` : "Needs topic";
  $("sourceMetric").textContent = String(config.sources.length);
  $("sourceInsight").textContent = sourceInsight(config.sources);
  $("apiMetric").textContent = activeApiChecks.length ? `${readyApiChecks.length}/${activeApiChecks.length}` : "0";
  $("apiInsight").textContent = activeApiChecks.length ? "Active checks" : "No API source";
  $("runMetric").textContent = String(blockingCount);
  $("runInsight").textContent = blockingCount ? "Blocked" : isDirty ? "Unsaved changes" : "Ready";

  renderApiReadiness(apiChecks);
  renderRunPlan("runPlan", config, env);
  renderRunPlan("reportPlan", config, env);
  updateTabStates(config, warnings, apiChecks);
  updateRunControls(blockingCount);
}

function updateFieldMeta(config) {
  textFieldMeta.forEach(([field, metaId, label]) => {
    const element = $(metaId);
    if (!element) {
      return;
    }
    const count = (config[field] || []).length;
    element.textContent = `${count} ${label}`;
  });
}

function buildLocalWarnings(config, env) {
  const warnings = [];
  const sources = new Set(config.sources);
  const fullTextSources = new Set(config.full_text_sources);
  const hasElsevierKey = Boolean(env.ELSEVIER_API_KEY);
  const hasSpringerMetaKey = Boolean(env.SPRINGER_NATURE_API_KEY);
  const hasSpringerOpenAccessKey = Boolean(env.SPRINGER_OPENACCESS_API_KEY || env.SPRINGER_NATURE_API_KEY);

  if (!config.keywords.length && !config.journals.length) {
    warnings.push({ severity: "error", scope: "profile", message: "Add at least one keyword or hard journal filter." });
  }
  if (!config.sources.length) {
    warnings.push({ severity: "error", scope: "sources", message: "Enable at least one discovery source." });
  }
  if (!config.output_dir) {
    warnings.push({ severity: "error", scope: "report", message: "Set an output directory." });
  }
  if ((sources.has("scopus") || sources.has("elsevier")) && !hasElsevierKey) {
    warnings.push({ severity: "warning", scope: "api", message: "Elsevier-backed sources are enabled without ELSEVIER_API_KEY." });
  }
  if (sources.has("springer") && !hasSpringerMetaKey) {
    warnings.push({ severity: "warning", scope: "api", message: "Springer Nature Meta is enabled without SPRINGER_NATURE_API_KEY." });
  }
  if (sources.has("springer-openaccess") && !hasSpringerOpenAccessKey) {
    warnings.push({ severity: "warning", scope: "api", message: "Springer OpenAccess is enabled without a Springer key." });
  }
  if (config.include_full_text && (fullTextSources.has("elsevier") || fullTextSources.has("sciencedirect")) && !hasElsevierKey) {
    warnings.push({ severity: "warning", scope: "api", message: "Elsevier full-text enrichment is enabled without ELSEVIER_API_KEY." });
  }
  if (safeInt(config.max_candidates_per_source, 0) < safeInt(config.max_papers, 1)) {
    warnings.push({ severity: "warning", scope: "sources", message: "Max candidates per source is lower than max papers." });
  }
  if (safeInt(config.springer_page_size, 20) > 20) {
    warnings.push({ severity: "warning", scope: "sources", message: "Springer page size should stay at 20 or lower." });
  }
  if (!config.include_visuals && config.include_per_paper_visuals) {
    warnings.push({ severity: "warning", scope: "report", message: "Per-paper visuals are on while the visual master switch is off." });
  }
  return warnings;
}

function requiredApiChecks(config, env) {
  const sources = new Set(config.sources);
  const fullTextSources = new Set(config.full_text_sources);
  const needsElsevier = sources.has("scopus") || sources.has("elsevier") || (config.include_full_text && (fullTextSources.has("elsevier") || fullTextSources.has("sciencedirect")));
  return [
    {
      name: "Elsevier",
      required: needsElsevier,
      ready: Boolean(env.ELSEVIER_API_KEY),
      note: needsElsevier ? "Search/full text" : "Idle",
    },
    {
      name: "Springer Meta",
      required: sources.has("springer"),
      ready: Boolean(env.SPRINGER_NATURE_API_KEY),
      note: sources.has("springer") ? "Meta source" : "Idle",
    },
    {
      name: "Springer OA",
      required: sources.has("springer-openaccess"),
      ready: Boolean(env.SPRINGER_OPENACCESS_API_KEY || env.SPRINGER_NATURE_API_KEY),
      note: sources.has("springer-openaccess") ? "OpenAccess source" : "Idle",
    },
    {
      name: "User Agent",
      required: false,
      metric: false,
      ready: Boolean(env.LITERATURE_DIGEST_USER_AGENT),
      note: env.LITERATURE_DIGEST_USER_AGENT ? "Set" : "YAML fallback",
    },
  ];
}

function renderApiReadiness(checks) {
  $("apiReadiness").innerHTML = checks
    .map((check) => {
      const stateName = check.required ? (check.ready ? "ready" : "missing") : check.ready ? "ready" : "idle";
      const value = check.required ? (check.ready ? "Ready" : "Missing") : check.ready ? "Ready" : "Idle";
      return `
        <div class="api-card ${stateName}">
          <strong>${escapeHtml(check.name)}</strong>
          <span>${escapeHtml(value)}</span>
          <small>${escapeHtml(check.note)}</small>
        </div>
      `;
    })
    .join("");
}

function renderRunPlan(containerId, config) {
  const container = $(containerId);
  if (!container) {
    return;
  }
  const chips = [
    ["Window", `${safeInt(config.days_back, 1)}d`],
    ["Max", `${safeInt(config.max_papers, 1)} papers`],
    ["Sources", String(config.sources.length)],
    ["Full Text", config.include_full_text ? "On" : "Off"],
    ["Visuals", config.include_per_paper_visuals ? "Per-paper" : config.include_visuals ? "Basic" : "Off"],
    ["Output", config.output_dir || "None"],
  ];
  container.innerHTML = chips
    .map(([label, value]) => `<span class="plan-chip"><strong>${escapeHtml(label)}</strong>${escapeHtml(value)}</span>`)
    .join("");
}

function updateTabStates(config, warnings, apiChecks) {
  const hasScope = (scope, severity) => warnings.some((warning) => warning.scope === scope && (!severity || warning.severity === severity));
  setTabState("profile", config.keywords.length || config.journals.length ? "ready" : "error");
  setTabState("sources", hasScope("sources", "error") ? "error" : hasScope("sources") ? "attention" : "ready");
  setTabState("report", hasScope("report", "error") ? "error" : hasScope("report") ? "attention" : "ready");
  const apiMissing = apiChecks.some((check) => check.required && check.metric !== false && !check.ready);
  setTabState("api", apiMissing ? "attention" : "ready");
  setTabState("run", warnings.some((warning) => warning.severity === "error") ? "error" : warnings.length ? "attention" : "ready");
}

function setTabState(tabName, status) {
  const button = document.querySelector(`[data-tab="${tabName}"]`);
  if (!button) {
    return;
  }
  button.dataset.state = status;
}

function updateRunControls(blockingCount) {
  const blocked = blockingCount > 0;
  $("runDigestButton").disabled = blocked;
  $("saveAndOfflineButton").disabled = blocked;
  $("runStatusBadge").textContent = blocked ? "Blocked" : isDirty ? "Unsaved" : "Ready";
}

function setDirty(value) {
  isDirty = value;
  const badge = $("dirtyBadge");
  badge.textContent = value ? "Unsaved" : "Saved";
  badge.classList.toggle("dirty", value);
  badge.classList.toggle("saved", !value);
}

function sourceInsight(sources) {
  const apiSources = sources.filter((source) => ["scopus", "elsevier", "springer", "springer-openaccess"].includes(source));
  if (!sources.length) {
    return "No source";
  }
  if (!apiSources.length) {
    return "Public only";
  }
  return `${apiSources.length} API-backed`;
}

function mergeWarnings(warnings) {
  const seen = new Set();
  const result = [];
  warnings.map(normalizeWarning).forEach((warning) => {
    if (!warning.message || seen.has(warning.message)) {
      return;
    }
    seen.add(warning.message);
    result.push(warning);
  });
  return result;
}

function normalizeWarning(warning) {
  if (typeof warning === "string") {
    return { severity: "warning", scope: "general", message: warning };
  }
  return {
    severity: warning.severity || "warning",
    scope: warning.scope || "general",
    message: warning.message || "",
  };
}

function safeInt(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function presetLabel(name) {
  return {
    public: "Public",
    biomed: "Biomed",
    nature: "Nature",
    publisher: "Publisher API",
  }[name] || "Preset";
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
