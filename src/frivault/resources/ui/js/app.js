"use strict";

const ROOT_ID = "00000000000000000000000000000000";
const versionElement = document.getElementById("app-version");
const connectionState = document.getElementById("connection-state");
const vaultState = document.getElementById("vault-state");
const navigation = document.getElementById("navigation");
const pageTitle = document.getElementById("page-title");
const pageContent = document.getElementById("page-content");
const quickSearch = document.querySelector("#quick-search-form input");
const appShell = document.querySelector(".app-shell");
const sidebarToggle = document.getElementById("sidebar-toggle");
const modal = document.getElementById("modal");
const modalForm = document.getElementById("modal-form");
const settingsDialog = document.getElementById("settings-dialog");
const settingsDialogContent = document.getElementById("settings-dialog-content");
const itemContextMenu = document.getElementById("item-context-menu");
const confirmDeleteDialog = document.getElementById("confirm-delete-dialog");
const confirmDeleteDescription = document.getElementById("confirm-delete-description");
const confirmDeleteItems = document.getElementById("confirm-delete-items");
const confirmDeleteCancel = document.getElementById("confirm-delete-cancel");
const confirmDeleteAccept = document.getElementById("confirm-delete-accept");
const toast = document.getElementById("toast");
let pageTransitionSequence = 0;
let pageTransitionAnimation = null;
let pageTransitionTarget = null;
let modalContentClearTimer = null;
let settingsContentClearTimer = null;
let confirmDeleteContentClearTimer = null;
modal.addEventListener("close", () => {
  clearTimeout(modalContentClearTimer);
  modalContentClearTimer = setTimeout(() => {
    if (!modal.open) modalForm.replaceChildren();
  }, 210);
});
settingsDialog.addEventListener("close", () => {
  settingsDialogContent.querySelectorAll('input[type="password"]').forEach((input) => { input.value = ""; });
  renderNavigation();
  clearTimeout(settingsContentClearTimer);
  settingsContentClearTimer = setTimeout(() => {
    if (!settingsDialog.open) settingsDialogContent.replaceChildren();
  }, 210);
});
confirmDeleteCancel.addEventListener("click", () => confirmDeleteDialog.close("cancel"));
confirmDeleteAccept.addEventListener("click", () => confirmDeleteDialog.close("confirm"));
const pages = [
  ["overview", "Home", "home"], ["files", "My Vault", "files"],
  ["search", "Search", "search"], ["recent", "Recent", "recent"],
  ["favorites", "Favorites", "favorites"], ["trash", "Trash", "trash"],
  ["settings", "Settings", "settings"],
];
const navigationGroups = [
  { label: "WORKSPACE", pages: ["overview", "files", "search", "recent", "favorites", "trash"] },
  { label: "PREFERENCES", pages: ["settings"], bottom: true },
];
const pageById = new Map(pages.map((page) => [page[0], page]));
let currentPage = "overview";
let currentFolder = ROOT_ID;
let folderStack = [];
let folderHistory = [];
let folderHistoryIndex = -1;
let selectedIds = new Set();
let selectionAnchorId = null;
let clipboardItemIds = [];
let importBatches = [];
let refreshingImportBatches = false;
let currentVault = null;
let preferences = {
  theme: "system", auto_lock_minutes: 15, default_sort_by: "name", density: "comfortable",
  confirm_permanent_delete: true, setup_complete: false, vault_configured: false,
};
let searchQuery = "";
let sortBy = "name";
let toastTimer = null;
let hasPaintedUi = false;

const iconAssets = {
  home: "icon-home.svg", files: "icon-my-vault.svg", search: "icon-search.svg",
  recent: "icon-clock.svg", favorites: "icon-star.svg", trash: "icon-trash.svg",
  vaults: "icon-vault.svg", privacy: "icon-shield.svg",
  lock: "icon-lock.svg", unlock: "icon-unlock.svg", settings: "icon-settings.svg",
  document: "icon-document.svg", open: "icon-open.svg", restore: "icon-restore.svg",
  delete: "icon-delete.svg", export: "icon-export.svg", rename: "icon-edit.svg",
  star: "icon-star.svg", info: "icon-info.svg", move: "icon-move.svg", copy: "icon-copy.svg",
  "folder-add": "icon-folder-add.svg", paste: "icon-paste.svg", "import-files": "icon-upload.svg",
  "import-folder": "icon-folder-import.svg", "select-all": "icon-select-all.svg",
  back: "icon-chevron-left.svg", forward: "icon-chevron-right.svg", up: "icon-arrow-up.svg",
  eye: "icon-eye.svg", "eye-off": "icon-eye-off.svg", warning: "icon-warning.svg",
  close: "icon-close.svg", appearance: "icon-appearance.svg", security: "icon-shield.svg",
  "file-preferences": "icon-list.svg", about: "icon-info.svg",
};

function uiIcon(name, className = "ui-icon") {
  const iconName = iconAssets[name] ? name : "document";
  return `<span class="ui-icon ui-icon--${iconName} ${className}" aria-hidden="true"></span>`;
}

function navigationIcon(name) {
  return uiIcon(name, "navigation__icon");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function setConnectionMessage(message, ready = false) {
  connectionState.lastElementChild.textContent = message;
  connectionState.classList.toggle("connection-state--ready", ready);
  connectionState.classList.toggle("connection-state--error", !ready && message !== "Starting desktop shell…");
}

function notify(message, error = false) {
  toast.textContent = message;
  toast.classList.toggle("toast--error", error);
  toast.classList.add("toast--visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("toast--visible"), 3200);
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
}

function applyDensity(density) {
  document.documentElement.dataset.density = density === "compact" ? "compact" : "comfortable";
}

function renderNavigation() {
  appShell.classList.remove("app-shell--setup", "app-shell--locked");
  const unlocked = currentVault?.state === "UNLOCKED";
  navigation.innerHTML = navigationGroups.map((group) => {
    const items = group.pages.map((id) => {
      const [, label, iconName] = pageById.get(id);
      const active = currentPage === id;
      const requiresVault = !["overview", "settings"].includes(id) && !unlocked;
      const hint = requiresVault ? "Open and unlock a vault to use this section" : label;
      return `<button class="navigation__item ${active ? "navigation__item--active" : ""}" data-page="${id}" title="${hint}" aria-label="${label}" ${requiresVault ? "disabled" : ""} ${active ? 'aria-current="page"' : ""}>
        ${navigationIcon(iconName)}<span class="navigation__label">${label}</span></button>`;
    }).join("");
    return `<div class="navigation__group ${group.bottom ? "navigation__group--bottom" : ""}"><div class="navigation__group-label">${group.label}</div>${items}</div>`;
  }).join("") + (unlocked ? `<button class="nav-lock" data-action="lock">${navigationIcon("lock")}<span>Lock vault</span></button>` :
    currentVault?.state === "LOCKED" ? `<button class="nav-lock" data-action="unlock">${navigationIcon("unlock")}<span>Unlock vault</span></button>` :
      `<button class="nav-lock" data-action="open-vault">${uiIcon("open")}<span>Open existing vault</span></button>`);
  vaultState.textContent = currentVault ? `${currentVault.state === "UNLOCKED" ? "Unlocked" : "Locked"} · ${currentVault.name || "Private vault"}` : "No vault open";
  pageTitle.textContent = pageById.get(currentPage)?.[1] || "Home";
  quickSearch.disabled = !unlocked;
  if (!unlocked) quickSearch.value = "";
}

function openModal(title, fields, submitLabel, onSubmit) {
  modalForm.innerHTML = `<h2>${escapeHtml(title)}</h2>${fields}<div class="modal__actions">
    <button type="button" class="button button--quiet" data-modal-cancel>Cancel</button>
    <button type="submit" class="button">${escapeHtml(submitLabel)}</button></div>`;
  modalForm.onsubmit = async (event) => {
    event.preventDefault();
    const submit = modalForm.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      await onSubmit(new FormData(modalForm));
      modal.close();
      modalForm.replaceChildren();
    } catch (error) {
      notify(error.message || "The action could not be completed", true);
    } finally {
      submit.disabled = false;
    }
  };
  modal.showModal();
  modalForm.querySelector("input")?.focus();
}

function field(label, name, type = "text", attributes = "") {
  return `<label class="field">${escapeHtml(label)}<input name="${name}" type="${type}" ${attributes} required></label>`;
}

function passwordField(label, name, id, autocomplete, describedBy = "") {
  const description = describedBy ? ` aria-describedby="${escapeHtml(describedBy)}"` : "";
  return `<div class="field"><label for="${escapeHtml(id)}">${escapeHtml(label)}</label><div class="password-control">
    <input id="${escapeHtml(id)}" name="${escapeHtml(name)}" type="password" autocomplete="${escapeHtml(autocomplete)}"${description} required>
    <button class="password-toggle" type="button" data-password-toggle aria-controls="${escapeHtml(id)}" aria-label="Show password" aria-pressed="false" title="Show password">
      ${uiIcon("eye", "password-toggle__glyph password-toggle__show")}
      ${uiIcon("eye-off", "password-toggle__glyph password-toggle__hide")}
    </button></div></div>`;
}

function formatBytes(value) {
  if (value == null) return "—";
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let amount = value / 1024;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) { amount /= 1024; index += 1; }
  return `${amount.toFixed(amount >= 10 ? 0 : 1)} ${units[index]}`;
}

function countLabel(count, singular) {
  return `${count} ${singular}${Number(count) === 1 ? "" : "s"}`;
}

function emptyState(title, detail) {
  return `<div class="empty-state">${uiIcon("files", "empty-state__mark")}<h2>${escapeHtml(title)}</h2><p>${escapeHtml(detail)}</p></div>`;
}

function renderSetup() {
  currentPage = "setup";
  appShell.classList.remove("app-shell--locked");
  appShell.classList.add("app-shell--setup");
  pageTitle.textContent = "Set up Frivault";
  quickSearch.disabled = true;
  pageContent.innerHTML = `<div class="setup-layout">
    <section class="setup-card" aria-labelledby="setup-heading">
      <div class="setup-brand"><img src="/assets/frivault_icon.ico" alt=""><span>FIRST-TIME SETUP</span></div>
      <h2 id="setup-heading">Create Frivault</h2>
      <p class="setup-intro">Name your vault and choose a strong password. Your files stay encrypted on this device.</p>
      <form id="setup-form" class="setup-form" novalidate>
        <label class="field" for="setup-vault-name">Vault name<input id="setup-vault-name" name="vault_name" type="text" maxlength="120" autocomplete="off" required></label>
        <div class="field">
          <label for="setup-password">Password</label>
          <div class="password-control">
            <input id="setup-password" name="password" type="password" autocomplete="new-password" aria-describedby="password-policy" required>
            <button class="password-toggle" type="button" data-password-toggle aria-controls="setup-password" aria-label="Show password" aria-pressed="false" title="Show password">
              ${uiIcon("eye", "password-toggle__glyph password-toggle__show")}
              ${uiIcon("eye-off", "password-toggle__glyph password-toggle__hide")}
            </button>
          </div>
        </div>
        <div class="field">
          <label for="setup-confirm-password">Confirm password</label>
          <div class="password-control">
            <input id="setup-confirm-password" name="confirm" type="password" autocomplete="new-password" aria-describedby="password-policy" required>
            <button class="password-toggle" type="button" data-password-toggle aria-controls="setup-confirm-password" aria-label="Show password" aria-pressed="false" title="Show password">
              ${uiIcon("eye", "password-toggle__glyph password-toggle__show")}
              ${uiIcon("eye-off", "password-toggle__glyph password-toggle__hide")}
            </button>
          </div>
        </div>
        <p class="field-hint" id="password-policy">Use at least 12 characters. Passwords are case-sensitive and cannot be recovered if forgotten.</p>
        <p class="setup-message" id="setup-message" role="status" aria-live="polite" hidden></p>
        <button class="button setup-submit" type="submit">Create Frivault</button>
      </form>
      <div class="setup-existing"><span>Already have a vault?</span><button class="text-button" data-action="open-vault">Open existing vault</button></div>
    </section>
    <aside class="setup-aside"><div class="setup-aside__icon">${navigationIcon("vaults")}</div><div class="eyebrow">LOCAL · PRIVATE · OFFLINE FIRST</div><h3>Your files stay on your device.</h3><p>No account or cloud connection is needed. Choose a parent folder and Frivault will create your named vault folder there.</p><div class="setup-aside__note"><strong>Keep a backup</strong><span>After setup, back up the complete vault folder to a separate location.</span></div></aside>
  </div>`;
  pageContent.querySelector('#setup-vault-name')?.focus();
}

function renderLocked() {
  if (currentVault?.state === "LOCKED") {
    renderUnlockScreen();
    return;
  }
  appShell.classList.remove("app-shell--locked");
  renderNavigation();
  if (currentPage === "settings") return renderSettings();
  const isConfigured = preferences.vault_configured;
  pageContent.innerHTML = `<section class="welcome-card"><div class="welcome-card__copy">
    <div class="welcome-card__label">${isConfigured ? "SAVED VAULT NOT FOUND" : "NO VAULT OPEN"}</div>
    <h2>${isConfigured ? "Locate your existing vault." : "Open a vault to continue."}</h2>
    <p>${isConfigured ? "Choose the folder of your existing vault. Frivault will remember its location; it will not create another vault." : "Choose an existing vault folder. Frivault works locally without an account."}</p>
    <div class="action-row"><button class="button" data-action="open-vault">${isConfigured ? "Locate existing vault" : "Open existing vault"}</button></div>
  </div><div class="welcome-card__mark"><img src="/assets/frivault_icon.ico" alt=""></div>
    <div class="welcome-card__foot"><span class="status-dot" aria-hidden="true"></span><strong>${isConfigured ? "Vault location needed" : "No vault is open"}</strong><span class="welcome-card__separator">·</span><span>Select an existing Frivault folder</span></div>
  </section>
  <div class="privacy-note">${uiIcon("privacy", "privacy-note__symbol")}<p><strong>Local and offline first.</strong> Vault details appear only while unlocked. Keep a separate backup of every vault folder; this preview has no recovery key.</p></div>`;
}

function renderUnlockScreen(message = "", isError = false) {
  appShell.classList.remove("app-shell--setup");
  appShell.classList.add("app-shell--locked");
  pageTitle.textContent = "Unlock Frivault";
  quickSearch.disabled = true;
  quickSearch.value = "";
  vaultState.textContent = "Vault locked";
  if (modal.open) {
    modal.close();
    modalForm.replaceChildren();
  }
  pageContent.innerHTML = `<div class="unlock-layout">
    <section class="unlock-card" aria-labelledby="unlock-heading">
      <div class="unlock-brand"><img src="/assets/frivault_icon.ico" alt=""><span>FRIVAULT · PRIVATE VAULT</span></div>
      <div class="unlock-mark" aria-hidden="true">${uiIcon("lock", "unlock-mark__icon")}</div>
      <div class="eyebrow">VAULT LOCKED</div>
      <h2 id="unlock-heading">Welcome back.</h2>
      <p class="unlock-intro">Enter your password to unlock your files on this device.</p>
      <form id="unlock-form" class="unlock-form" novalidate>
        ${passwordField("Password", "password", "unlock-password", "current-password", "unlock-password-hint")}
        <p class="field-hint" id="unlock-password-hint">Your password is never stored by Frivault.</p>
        <p class="setup-message ${isError ? "setup-message--error" : ""}" id="unlock-message" role="status" aria-live="polite" ${message ? "" : "hidden"}>${escapeHtml(message)}</p>
        <button class="button unlock-submit" type="submit">Unlock vault</button>
      </form>
      <div class="unlock-footnote"><span class="status-dot" aria-hidden="true"></span><span>Your vault remains encrypted while locked.</span></div>
    </section>
    <aside class="unlock-aside"><div class="unlock-aside__icon">${navigationIcon("vaults")}</div>
      <div class="eyebrow">LOCAL · PRIVATE · OFFLINE FIRST</div>
      <h3>Your private files stay on this device.</h3>
      <p>Unlocking is required each time Frivault starts. Your password protects the key that opens this vault.</p>
      <div class="unlock-aside__note"><strong>No recovery key</strong><span>If you forget your password, the vault contents cannot be recovered. Keep a separate backup of the complete vault folder.</span></div>
    </aside>
  </div>`;
  pageContent.querySelector("#unlock-password")?.focus();
}

async function refreshStatus() {
  const firstPaint = !hasPaintedUi;
  const result = await window.pywebview.api.get_app_status();
  const wasUnlocked = currentVault?.state === "UNLOCKED";
  const previousVault = JSON.stringify(currentVault);
  const previousPreferences = JSON.stringify(preferences);
  versionElement.textContent = `v${result.data.version}`;
  setConnectionMessage("Desktop shell connected", true);
  currentVault = result.data.vault;
  preferences = { ...preferences, ...result.data.settings };
  if (firstPaint) sortBy = preferences.default_sort_by || "name";
  applyTheme(preferences.theme);
  applyDensity(preferences.density);
  const changed = previousVault !== JSON.stringify(currentVault) || previousPreferences !== JSON.stringify(preferences);
  if (!preferences.vault_configured && !currentVault) {
    if (firstPaint || currentPage !== "setup") renderSetup();
    hasPaintedUi = true;
    return;
  }
  if (wasUnlocked && currentVault?.state !== "UNLOCKED") {
    currentPage = "overview";
    selectedIds.clear();
    folderStack = [];
    currentFolder = ROOT_ID;
    searchQuery = "";
    notify("Vault locked after inactivity");
  }
  if (currentVault?.state !== "UNLOCKED") {
    if (firstPaint || changed) renderLocked();
    hasPaintedUi = true;
    return;
  }
  if (!firstPaint && !changed) return;
  if (firstPaint || ["files", "search", "recent", "favorites", "trash"].includes(currentPage)) {
    await renderPage();
  } else {
    renderNavigation();
  }
  hasPaintedUi = true;
}

function renderStartupError() {
  setConnectionMessage("Desktop connection unavailable");
  renderNavigation();
  pageContent.innerHTML = `<section class="content-card startup-error" role="alert">
    <div class="eyebrow">CONNECTION ISSUE</div>
    <h2>Frivault could not load its desktop services</h2>
    <p>The window opened, but the local Python bridge did not return the vault status. Try reconnecting. If the issue continues, restart Frivault and check the local app log.</p>
    <button class="button" data-action="retry-status">Try again</button>
  </section>`;
  hasPaintedUi = true;
}

function fileIconCategory(name) {
  const dot = String(name).lastIndexOf(".");
  const extension = dot > 0 ? String(name).slice(dot + 1).toLowerCase() : "";
  const categories = {
    pdf: ["pdf"], word: ["doc", "docx", "docm", "dotx", "dotm", "odt", "rtf"], spreadsheet: ["xls", "xlsx", "xlsm", "xlsb", "xltx", "csv", "ods"],
    presentation: ["ppt", "pptx", "pptm", "potx", "odp"], image: ["png", "jpg", "jpeg", "gif", "bmp", "svg", "webp", "avif", "ico", "tif", "tiff", "psd", "ai", "xd", "sketch"],
    video: ["mp4", "mkv", "mov", "avi", "webm", "wmv", "m4v"], audio: ["mp3", "wav", "ogg", "flac", "m4a", "aac", "wma"],
    archive: ["zip", "7z", "rar", "tar", "gz", "bz2", "xz"], code: ["py", "js", "jsx", "ts", "tsx", "html", "css", "json", "xml", "yaml", "yml", "c", "h", "cpp", "java", "rs", "go", "sh", "bat", "sql", "toml"],
    application: ["exe", "msi", "appx", "msix"], text: ["txt", "md", "log", "ini", "cfg"],
  };
  return Object.entries(categories).find(([, extensions]) => extensions.includes(extension))?.[0] || "document";
}

function fileIconMarkup(item, className = "item-card__file-art") {
  return `<img class="${className}" src="/assets/file-${fileIconCategory(item.name)}.svg" alt="">`;
}

function itemCard(item, trashed = false) {
  const isFolder = item.kind === "folder";
  const icon = isFolder
    ? '<img class="item-card__art" src="/assets/folder.svg" alt="">'
    : fileIconMarkup(item);
  const openAction = isFolder && !trashed ? "enter-folder" : "properties";
  return `<article class="item-card ${isFolder ? "item-card--folder" : "item-card--file"}" data-item="${escapeHtml(item.id)}" data-favorite="${Boolean(item.favorite)}">
    <button class="item-card__open" type="button" data-action="${openAction}" data-id="${escapeHtml(item.id)}" aria-label="${isFolder && !trashed ? "Open folder" : "View properties"}: ${escapeHtml(item.name)}">
      <span class="item-card__visual">${icon}</span><span class="item-card__name">${escapeHtml(item.name)}</span>
    </button>
  </article>`;
}

function toolbar(view) {
  const selectionActions = view === "trash"
    ? `<div class="toolbar__selection-actions" role="group" aria-label="Trash actions">
      <button class="button button--quiet toolbar__icon-button" data-action="restore" data-requires-selection="many" aria-label="Restore" title="Restore" disabled>${uiIcon("restore", "button__icon")}</button>
      <button class="button button--danger toolbar__icon-button" data-action="permanent-delete" data-requires-selection="many" aria-label="Delete permanently" title="Delete permanently" disabled>${uiIcon("delete", "button__icon")}</button>
    </div>`
    : `<div class="toolbar__selection-actions" role="group" aria-label="Selected item actions">
      <button class="button button--quiet toolbar__icon-button" data-action="copy" data-requires-selection="many" aria-label="Copy" title="Copy" disabled>${uiIcon("copy", "button__icon")}</button>
      <button class="button button--quiet toolbar__icon-button" data-action="paste" aria-label="Paste" title="Paste" disabled>${uiIcon("paste", "button__icon")}</button>
      <button class="button button--quiet toolbar__icon-button" data-action="rename" data-requires-selection="one" aria-label="Rename" title="Rename" disabled>${uiIcon("rename", "button__icon")}</button>
      <button class="button button--quiet toolbar__icon-button" data-action="move" data-requires-selection="many" aria-label="Move" title="Move" disabled>${uiIcon("move", "button__icon")}</button>
      <button class="button button--quiet toolbar__icon-button" data-action="toggle-favorite" data-requires-selection="one" aria-label="Favorite" title="Favorite" disabled>${uiIcon("star", "button__icon")}</button>
      <button class="button button--quiet toolbar__icon-button" data-action="export" data-requires-selection="one" aria-label="Export" title="Export" disabled>${uiIcon("export", "button__icon")}</button>
      <button class="button button--danger toolbar__icon-button" data-action="trash" data-requires-selection="many" aria-label="Move to Trash" title="Move to Trash" disabled>${uiIcon("delete", "button__icon")}</button>
    </div>`;
  const primary = view === "files" ? `<div class="toolbar__primary-actions">
    <button class="button" data-action="new-folder">${uiIcon("folder-add", "button__icon")}<span>New folder</span></button>
    <button class="button button--quiet" data-action="import-files">${uiIcon("import-files", "button__icon")}<span>Import files</span></button>
    <button class="button button--quiet" data-action="import-folder">${uiIcon("import-folder", "button__icon")}<span>Import folder</span></button>
    <label class="toolbar__sort">Sort<select id="sort-select" aria-label="Sort items"><option value="name" ${sortBy === "name" ? "selected" : ""}>Name</option><option value="type" ${sortBy === "type" ? "selected" : ""}>Type</option><option value="size" ${sortBy === "size" ? "selected" : ""}>Size</option><option value="created" ${sortBy === "created" ? "selected" : ""}>Date created</option><option value="modified" ${sortBy === "modified" ? "selected" : ""}>Date modified</option></select></label>
  </div>` : "";
  return `<div class="toolbar"><div class="toolbar__primary">${selectionActions}${primary}<span class="visually-hidden" id="selection-count" aria-live="polite"></span></div></div>`;
}

async function renderItems(view, items) {
  hideItemContextMenu();
  const summary = await window.pywebview.api.get_storage_summary();
  const title = pages.find(([id]) => id === currentPage)?.[1] || "My Vault";
  const crumbs = folderStack.map((folder, index) => {
    const separator = '<span class="breadcrumb__separator" aria-hidden="true">›</span>';
    const label = escapeHtml(folder.name);
    const isCurrent = index === folderStack.length - 1;
    const item = isCurrent
      ? `<span class="breadcrumb__current" aria-current="page">${label}</span>`
      : `<button class="breadcrumb__item" data-action="breadcrumb" data-id="${folder.id}">${label}</button>`;
    return `${separator}${item}`;
  }).join("");
  const rootCrumb = folderStack.length
    ? '<button class="breadcrumb__item" data-action="root">My Vault</button>'
    : '<span class="breadcrumb__current" aria-current="page">My Vault</span>';
  pageContent.innerHTML = `<div class="summary-strip"><span>${countLabel(summary.file_count, "file")}</span><span>${countLabel(summary.folder_count, "folder")}</span><span>${formatBytes(summary.plaintext_bytes)} stored</span></div>
    ${currentPage === "files" ? `<div class="location-bar"><div class="folder-nav" role="group" aria-label="Folder navigation">
      <button class="folder-nav__button" data-action="back-folder" aria-label="Back" title="Back" ${folderHistoryIndex <= 0 ? "disabled" : ""}>${uiIcon("back", "folder-nav__icon")}</button>
      <button class="folder-nav__button" data-action="forward-folder" aria-label="Forward" title="Forward" ${folderHistoryIndex < 0 || folderHistoryIndex >= folderHistory.length - 1 ? "disabled" : ""}>${uiIcon("forward", "folder-nav__icon")}</button>
      <button class="folder-nav__button" data-action="up-folder" aria-label="Up" title="Go to parent folder" ${folderStack.length === 0 ? "disabled" : ""}>${uiIcon("up", "folder-nav__icon")}</button>
    </div><nav class="breadcrumb" aria-label="Current folder">${rootCrumb}${crumbs}</nav></div>` : ""}
    ${currentPage === "search" ? `<form id="search-form" class="search-form"><input name="query" type="search" value="${escapeHtml(searchQuery)}" placeholder="Search names in this vault" aria-label="Search vault"><button class="button">Search</button></form><p class="search-hint">Searches encrypted file and folder names while the vault is unlocked. Type, date, and size filters are not available in this preview.</p>` : ""}
    ${toolbar(view)}
    ${importStatusMarkup(currentFolder)}
    ${items.length ? `<div class="item-grid" aria-label="${escapeHtml(title)} items">${items.map((item) => itemCard(item, view === "trash")).join("")}</div>` : emptyState(title === "Search" ? "No matching items" : "Nothing here yet", title === "Trash" ? "Deleted items appear here until permanently removed." : "Import a file or create a folder to get started.")}`;
  updateSelectionLabel();
}

async function renderPage() {
  renderNavigation();
  hideItemContextMenu();
  selectedIds.clear();
  selectionAnchorId = null;
  if (currentPage === "settings") return renderSettings();
  if (currentVault?.state !== "UNLOCKED") return renderLocked();
  if (currentPage === "overview") {
    const summary = await window.pywebview.api.get_storage_summary();
    const recent = await window.pywebview.api.list_items("recent");
    const recentRows = recent.slice(0, 5).map((item) => `<div class="recent-row"><span class="recent-row__icon">${item.kind === "folder" ? '<img src="/assets/folder.svg" alt="">' : fileIconMarkup(item, "")}</span><span class="recent-row__name">${escapeHtml(item.name)}</span><span class="recent-row__type">${item.kind === "folder" ? "Folder" : formatBytes(item.size_bytes)}</span><time>${new Date(item.modified_at_ns / 1e6).toLocaleDateString()}</time></div>`).join("");
    pageContent.innerHTML = `<section class="welcome-card"><div class="welcome-card__copy"><div class="welcome-card__label">VAULT UNLOCKED · LOCAL SESSION</div><h2>${escapeHtml(currentVault.name || "Your private space")}</h2><p>Your encrypted files are available locally. Lock the vault whenever you step away.</p><div class="action-row"><button class="button" data-page="files">${uiIcon("files", "button__icon")}<span>Browse files</span></button><button class="button button--quiet" data-action="import-files">${uiIcon("import-files", "button__icon")}<span>Import files</span></button><button class="button button--quiet" data-action="new-folder">${uiIcon("folder-add", "button__icon")}<span>New folder</span></button><button class="button button--quiet" data-action="lock">${uiIcon("lock", "button__icon")}<span>Lock vault</span></button></div></div><div class="welcome-card__mark"><img src="/assets/frivault_icon.ico" alt=""></div></section>
      <div class="stat-grid"><article><span>Files</span><strong>${summary.file_count}</strong></article><article><span>Folders</span><strong>${summary.folder_count}</strong></article><article><span>Encrypted storage used</span><strong>${formatBytes(summary.encrypted_bytes)}</strong><small>Current vault data on disk</small></article></div>
      <section class="recent-panel"><div class="section__heading"><div><div class="eyebrow">PRIVATE ACTIVITY</div><h2>Recently changed</h2></div><button class="text-button" data-page="recent">View all</button></div>${recentRows || '<div class="recent-empty">No file activity yet. Import files to start building your vault.</div>'}</section>
      <div class="privacy-note">${uiIcon("privacy", "privacy-note__symbol")}<p><strong>Private by design.</strong> Names and contents stay encrypted in this local vault. Keep an independent backup of the vault folder.</p></div>`;
    return;
  }
  let view = currentPage;
  let items = [];
  if (currentPage === "files") items = await window.pywebview.api.list_items("files", currentFolder, sortBy, false);
  else if (currentPage === "search") items = await window.pywebview.api.search_items(searchQuery);
  else items = await window.pywebview.api.list_items(view);
  await renderItems(view, items);
}

async function transitionToPage(nextPage, { prepare = () => {}, force = false, surface = pageContent } = {}) {
  if (nextPage === currentPage && !force) {
    if (pageTransitionTarget !== null) {
      pageTransitionSequence += 1;
      pageTransitionAnimation?.cancel();
      pageTransitionAnimation = null;
      pageTransitionTarget = null;
      pageContent.removeAttribute("aria-busy");
    }
    prepare();
    return renderPage();
  }

  const previousPage = currentPage;
  const sequence = ++pageTransitionSequence;
  pageTransitionTarget = nextPage;
  pageTransitionAnimation?.cancel();
  pageTransitionAnimation = null;
  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (reduceMotion || !surface.firstElementChild) {
    prepare();
    currentPage = nextPage;
    pageTransitionTarget = null;
    pageContent.removeAttribute("aria-busy");
    navigation.inert = false;
    pageContent.parentElement.inert = false;
    return renderPage();
  }

  pageContent.setAttribute("aria-busy", "true");
  navigation.inert = true;
  pageContent.parentElement.inert = true;
  const fadeOut = surface.animate(
    [
      { opacity: 1, transform: "translateY(0)" },
      { opacity: 0, transform: "translateY(-5px)" },
    ],
    { duration: 130, easing: "cubic-bezier(.4, 0, 1, 1)", fill: "forwards" },
  );
  pageTransitionAnimation = fadeOut;
  try {
    await fadeOut.finished;
    if (sequence !== pageTransitionSequence) return;

    prepare();
    currentPage = nextPage;
    await renderPage();
    if (sequence !== pageTransitionSequence) return;

    fadeOut.cancel();
    const fadeIn = surface.animate(
      [
        { opacity: 0, transform: "translateY(5px)" },
        { opacity: 1, transform: "translateY(0)" },
      ],
      { duration: 180, easing: "cubic-bezier(0, 0, .2, 1)" },
    );
    pageTransitionAnimation = fadeIn;
    await fadeIn.finished;
  } catch (error) {
    if (error?.name !== "AbortError") {
      if (sequence === pageTransitionSequence) {
        currentPage = previousPage;
        renderNavigation();
      }
      throw error;
    }
  } finally {
    if (sequence === pageTransitionSequence) {
      pageTransitionAnimation?.cancel();
      pageTransitionAnimation = null;
      pageTransitionTarget = null;
      pageContent.removeAttribute("aria-busy");
      navigation.inert = false;
      pageContent.parentElement.inert = false;
    }
  }
}

function getImportBatchState(batch) {
  const taskById = new Map((batch.operations || []).map((task) => [task.task_id, task]));
  const tasks = batch.taskIds.map((taskId) => taskById.get(taskId)).filter(Boolean);
  const missingCount = batch.taskIds.length - tasks.length;
  const activeTasks = tasks.filter((task) => ["PENDING", "RUNNING"].includes(task.state));
  const activeCount = activeTasks.length + missingCount;
  const succeededCount = tasks.filter((task) => task.state === "SUCCEEDED").length;
  const failedTasks = tasks.filter((task) => task.state === "FAILED");
  const cancelledCount = tasks.filter((task) => task.state === "CANCELLED").length;
  const complete = missingCount === 0 && activeCount === 0;
  const totalBytes = tasks.reduce((sum, task) => sum + task.total_bytes, 0);
  const completedBytes = tasks.reduce((sum, task) => sum + task.completed_bytes, 0);
  const progressDeterminate = activeCount > 0 && missingCount === 0
    && activeTasks.every((task) => task.total_bytes > 0);
  const progress = totalBytes > 0
    ? Math.min(100, Math.round(completedBytes * 100 / totalBytes))
    : 0;
  let summary;
  const kind = batch.kind || "import";
  const noun = kind === "copy" ? "Copy" : kind === "export" ? "Export" : "Import";
  const verb = kind === "copy" ? "copied" : "imported";
  if (activeCount) {
    summary = batch.cancelRequested
      ? `Stopping the active ${noun.toLowerCase()}…`
      : kind === "export"
        ? "Exporting file…"
        : `${noun}ing ${batch.taskIds.length} item${batch.taskIds.length === 1 ? "" : "s"} into ${batch.destinationName}…`;
  } else if (failedTasks.length || cancelledCount) {
    summary = `${noun} finished: ${succeededCount} completed, ${failedTasks.length} failed, ${cancelledCount} cancelled.`;
  } else {
    summary = kind === "export" ? "Export complete." : `${noun} complete: ${succeededCount} item${succeededCount === 1 ? "" : "s"} ${verb} to ${batch.destinationName}.`;
  }
  const errorMessages = [...new Set(failedTasks.map((task) => task.error).filter(Boolean))];
  const details = errorMessages.slice(0, 2).join(" · ");
  return {
    activeCount, complete, succeededCount, failedCount: failedTasks.length, cancelledCount,
    summary, details, progressDeterminate, progress,
    byteProgress: totalBytes > 0 ? `${formatBytes(completedBytes)} of ${formatBytes(totalBytes)}` : "",
  };
}

function importBatchMarkup(batch) {
  const state = getImportBatchState(batch);
  const label = batch.kind === "copy" ? "Copy" : batch.kind === "export" ? "Export" : "Import";
  return `<section class="import-status" data-import-batch="${escapeHtml(batch.batchId)}">
    <div class="import-status__heading"><div><strong>${label} status</strong><p class="import-status__summary" role="status" aria-live="polite">${escapeHtml(state.summary)}</p></div>
      <button class="import-status__dismiss" type="button" data-action="dismiss-operation-status" data-id="${escapeHtml(batch.batchId)}" aria-label="Dismiss ${label.toLowerCase()} status" title="Dismiss ${label.toLowerCase()} status" ${state.activeCount ? "hidden" : ""}>${uiIcon("close", "import-status__dismiss-icon")}</button></div>
    <progress class="import-status__progress" max="100" aria-label="${label} progress" ${state.progressDeterminate ? `value="${state.progress}"` : ""} ${state.activeCount ? "" : "hidden"}></progress>
    <div class="import-status__footer"><span class="import-status__details">${escapeHtml(state.details || (state.activeCount ? state.byteProgress : ""))}</span>
      <button class="button button--quiet import-status__cancel" type="button" data-action="cancel-operation-batch" data-id="${escapeHtml(batch.batchId)}" ${state.activeCount ? "" : "hidden"} ${batch.cancelRequested ? "disabled" : ""}>${batch.cancelRequested ? "Cancelling…" : `Cancel ${label.toLowerCase()}`}</button></div>
  </section>`;
}

function updateImportBatchPanel(batch) {
  const panel = [...pageContent.querySelectorAll("[data-import-batch]")]
    .find((element) => element.dataset.importBatch === batch.batchId);
  if (!panel) return;
  const state = getImportBatchState(batch);
  panel.querySelector(".import-status__summary").textContent = state.summary;
  const progress = panel.querySelector(".import-status__progress");
  progress.hidden = state.activeCount === 0;
  if (state.progressDeterminate) progress.value = state.progress;
  else progress.removeAttribute("value");
  const details = panel.querySelector(".import-status__details");
  details.textContent = state.details || (state.activeCount ? state.byteProgress : "");
  const cancel = panel.querySelector(".import-status__cancel");
  cancel.hidden = state.activeCount === 0;
  cancel.disabled = Boolean(batch.cancelRequested);
  const label = batch.kind === "copy" ? "copy" : batch.kind === "export" ? "export" : "import";
  cancel.textContent = batch.cancelRequested ? "Cancelling…" : `Cancel ${label}`;
  panel.querySelector(".import-status__dismiss").hidden = state.activeCount > 0;
}

function importStatusMarkup(folderId) {
  return importBatches
    .filter((batch) => batch.destinationFolderId === folderId)
    .map(importBatchMarkup)
    .join("");
}

function trackOperationBatch(taskIds, destinationFolderId, destinationName, kind = "import") {
  if (!taskIds.length) return null;
  const batch = {
    batchId: taskIds[0], taskIds: [...taskIds], destinationFolderId, destinationName,
    kind, operations: [], cancelRequested: false, completed: false,
  };
  importBatches.push(batch);
  return batch;
}

async function refreshImportBatches() {
  if (!importBatches.length || refreshingImportBatches || !window.pywebview?.api) return;
  refreshingImportBatches = true;
  try {
    const operations = await window.pywebview.api.get_operations();
    let refreshDestination = false;
    for (const batch of importBatches) {
      batch.operations = operations.filter((task) => batch.taskIds.includes(task.task_id));
      const state = getImportBatchState(batch);
      if (state.complete && !batch.completed) {
        batch.completed = true;
        if (currentPage === "files" && currentFolder === batch.destinationFolderId) {
          refreshDestination = true;
        }
        const label = batch.kind === "copy" ? "Copy" : batch.kind === "export" ? "Export" : "Import";
        if (state.failedCount) notify(`${label} finished with ${state.failedCount} failure(s)`, true);
        else if (state.cancelledCount) notify(`${label} cancelled`);
        else notify(`${label} complete`);
      }
      updateImportBatchPanel(batch);
    }
    if (refreshDestination) await renderPage();
  } finally {
    refreshingImportBatches = false;
  }
}

async function renderSettings(container = pageContent) {
  const passwordSettings = currentVault?.state === "UNLOCKED" ? `<section class="settings-panel" data-settings-panel="security">
    <div class="settings-panel__heading"><div><span class="settings-kicker">VAULT PASSWORD</span><h3>Change vault password</h3>
      <p>Confirm your current password, then choose a new one. Your encrypted files are not re-encrypted.</p></div></div>
    <form id="password-change-form" class="password-settings" novalidate>
      ${passwordField("Current password", "current_password", "current-vault-password", "current-password")}
      ${passwordField("New password", "new_password", "new-vault-password", "new-password", "new-password-policy")}
      ${passwordField("Confirm new password", "confirm_password", "confirm-vault-password", "new-password", "new-password-policy")}
      <p class="field-hint" id="new-password-policy">Use at least 12 characters. Passwords are case-sensitive. There is no recovery key.</p>
      <p class="setup-message" id="password-change-message" role="status" aria-live="polite" hidden></p>
      <button class="button" type="submit">Change password</button>
    </form>
  </section>` : `<section class="settings-panel" data-settings-panel="security">
    <div class="settings-panel__heading"><div><span class="settings-kicker">VAULT PASSWORD</span><h3>Change vault password</h3>
      <p>Unlock your vault before changing its password.</p></div><span class="settings-status settings-status--locked">Locked</span></div>
  </section>`;
  container.innerHTML = `<div class="settings-page">
    <form id="settings-form" class="settings-form">
      <section class="settings-panel settings-category-panel" data-settings-panel="appearance" aria-labelledby="settings-appearance-title">
        <div class="settings-panel__heading"><div><span class="settings-kicker">DISPLAY</span><h2 id="settings-appearance-title">Appearance</h2><p>Choose a theme and comfortable spacing for this device.</p></div></div>
        <fieldset class="settings-choice-group"><legend>Color theme</legend><div class="settings-choice-grid settings-choice-grid--three">
          <label class="settings-choice"><input type="radio" name="theme" value="system" ${preferences.theme === "system" ? "checked" : ""}><span class="settings-choice__preview settings-choice__preview--system" aria-hidden="true"><i></i><i></i><i></i></span><strong>System</strong><small>Match Windows</small></label>
          <label class="settings-choice"><input type="radio" name="theme" value="light" ${preferences.theme === "light" ? "checked" : ""}><span class="settings-choice__preview settings-choice__preview--light" aria-hidden="true"><i></i><i></i><i></i></span><strong>Light</strong><small>Bright surfaces</small></label>
          <label class="settings-choice"><input type="radio" name="theme" value="dark" ${preferences.theme === "dark" ? "checked" : ""}><span class="settings-choice__preview settings-choice__preview--dark" aria-hidden="true"><i></i><i></i><i></i></span><strong>Dark</strong><small>Low-light surfaces</small></label>
        </div></fieldset>
        <fieldset class="settings-choice-group"><legend>Interface spacing</legend><div class="settings-choice-grid settings-choice-grid--two">
          <label class="settings-choice settings-choice--density"><input type="radio" name="density" value="comfortable" ${(preferences.density || "comfortable") === "comfortable" ? "checked" : ""}><span class="settings-choice__density-mark settings-choice__density-mark--comfortable" aria-hidden="true"></span><strong>Comfortable</strong><small>More room between items</small></label>
          <label class="settings-choice settings-choice--density"><input type="radio" name="density" value="compact" ${preferences.density === "compact" ? "checked" : ""}><span class="settings-choice__density-mark settings-choice__density-mark--compact" aria-hidden="true"></span><strong>Compact</strong><small>Fit more items on screen</small></label>
        </div></fieldset>
      </section>
      <section class="settings-panel settings-category-panel" data-settings-panel="security" aria-labelledby="settings-security-title">
        <div class="settings-panel__heading"><div><span class="settings-kicker">SECURITY</span><h2 id="settings-security-title">Lock behavior</h2><p>Control how long Frivault stays unlocked while you are away.</p></div></div>
        <label class="field">Auto-lock after inactivity<select name="timeout"><option value="1">1 minute</option><option value="5">5 minutes</option><option value="10">10 minutes</option><option value="15">15 minutes</option><option value="30">30 minutes</option><option value="60">60 minutes</option></select></label>
        <div class="settings-callout"><strong>Password required at every launch</strong><span>Frivault opens locked each time. This protection cannot be disabled.</span></div>
      </section>
      <section class="settings-panel settings-category-panel" data-settings-panel="files" aria-labelledby="settings-files-title">
        <div class="settings-panel__heading"><div><span class="settings-kicker">FILE BROWSER</span><h2 id="settings-files-title">File preferences</h2><p>Choose how items are sorted and how permanent deletion is handled.</p></div></div>
        <label class="field">Default sorting<select name="default_sort_by"><option value="name">Name</option><option value="type">Type</option><option value="size">Size</option><option value="created">Date created</option><option value="modified">Recently modified</option></select></label>
        <label class="settings-checkbox"><input name="confirm_permanent_delete" type="checkbox" value="true" ${preferences.confirm_permanent_delete ? "checked" : ""}><span><strong>Confirm permanent deletion</strong><small>Ask before permanently removing items from Trash.</small></span></label>
      </section>
    </form>
    ${passwordSettings}
    <section class="settings-panel" data-settings-panel="privacy" aria-labelledby="settings-privacy-title">
      <div class="settings-panel__heading"><div><span class="settings-kicker">PRIVACY &amp; BACKUP</span><h2 id="settings-privacy-title">Local storage</h2><p>Your vault is stored on this computer.</p></div></div>
      <div class="settings-callout"><strong>Offline by design</strong><span>No account, cloud sync, analytics, or remote file transfer is used.</span></div>
      <p class="settings-note">Back up the complete vault folder to a separate location. Frivault does not upload or keep a second copy of it.</p>
    </section>
    <section class="settings-panel settings-about" data-settings-panel="about" aria-labelledby="settings-about-title">
      <div><span class="settings-kicker">ABOUT FRIVAULT</span><h2 id="settings-about-title">Private files. Stored locally.</h2>
        <dl class="settings-about__details"><div><dt>App version</dt><dd>${escapeHtml(versionElement.textContent.replace(/^v/, ""))}</dd></div><div><dt>Vault format</dt><dd>Version 1</dd></div></dl></div>
    </section>
  </div>`;
  container.querySelector('[name="timeout"]').value = String(preferences.auto_lock_minutes);
  container.querySelector('[name="default_sort_by"]').value = preferences.default_sort_by || "name";
  const footer = document.getElementById("settings-dialog-footer");
  if (footer && container === settingsDialogContent) footer.hidden = false;
  setSettingsCategory("appearance");
}

function setSettingsCategory(category) {
  settingsDialog.querySelectorAll("[data-settings-category]").forEach((button) => {
    const active = button.dataset.settingsCategory === category;
    button.classList.toggle("settings-nav__item--active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  settingsDialogContent.querySelectorAll("[data-settings-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.settingsPanel !== category;
  });
  const footer = document.getElementById("settings-dialog-footer");
  if (footer) footer.hidden = category === "about" || category === "privacy";
  settingsDialogContent.scrollTop = 0;
}

async function openSettingsDialog() {
  if (!settingsDialog.open) {
    clearTimeout(settingsContentClearTimer);
    await renderSettings(settingsDialogContent);
    settingsDialog.showModal();
  }
}

function updateSelectionLabel() {
  const label = document.getElementById("selection-count");
  if (label) label.textContent = selectedIds.size ? `${selectedIds.size} selected` : "No items selected";
  const cards = [...pageContent.querySelectorAll(".item-card")];
  cards.forEach((card) => {
    const selected = selectedIds.has(card.dataset.item);
    card.classList.toggle("item-card--selected", selected);
  });
  const selectAll = pageContent.querySelector('[data-action="select-all"]');
  if (selectAll) {
    const allSelected = cards.length > 0 && cards.every((card) => selectedIds.has(card.dataset.item));
    selectAll.textContent = allSelected ? "Deselect all" : "Select all";
    selectAll.disabled = cards.length === 0;
  }
  pageContent.querySelectorAll("[data-requires-selection]").forEach((button) => {
    const mode = button.dataset.requiresSelection;
    button.disabled = mode === "one" ? selectedIds.size !== 1 : selectedIds.size === 0;
  });
  const pasteButton = pageContent.querySelector('[data-action="paste"]');
  if (pasteButton) pasteButton.disabled = clipboardItemIds.length === 0;
}

function hideItemContextMenu() {
  itemContextMenu.hidden = true;
  itemContextMenu.replaceChildren();
}

function menuCommand(action, label, iconName, item = null) {
  const id = item?.dataset.item || "";
  const name = item?.querySelector(".item-card__name")?.textContent || "";
  return `<button type="button" role="menuitem" class="item-context-menu__command" data-action="${action}" data-id="${escapeHtml(id)}" data-name="${escapeHtml(name)}">${uiIcon(iconName, "item-context-menu__icon")}<span>${label}</span></button>`;
}

function showItemContextMenu(event, card = null) {
  if (card) {
    const id = card.dataset.item;
    if (!selectedIds.has(id)) {
      selectedIds.clear();
      selectedIds.add(id);
    }
    selectionAnchorId = id;
    updateSelectionLabel();
  } else {
    selectedIds.clear();
    selectionAnchorId = null;
    updateSelectionLabel();
  }
  const selectedCount = selectedIds.size;
  const isTrash = currentPage === "trash";
  const isFolder = card?.classList.contains("item-card--folder");
  const isFavorite = card?.dataset.favorite === "true";
  let commands = "";
  if (card && isTrash) {
    commands += menuCommand("restore", "Restore", "restore", card);
    commands += menuCommand("permanent-delete", "Delete permanently", "delete", card);
  } else if (card) {
    if (selectedCount === 1) {
      if (isFolder) commands += menuCommand("enter-folder", "Open", "open", card);
      else commands += menuCommand("export", "Export…", "export", card);
      commands += menuCommand("rename", "Rename", "rename", card);
      commands += menuCommand("toggle-favorite", isFavorite ? "Remove from Favorites" : "Add to Favorites", "star", card);
      commands += '<div class="item-context-menu__separator" role="separator"></div>';
      commands += menuCommand("properties", "Properties", "info", card);
    }
    commands += menuCommand("move", "Move to…", "move", card);
      commands += menuCommand("copy", "Copy", "copy", card);
    commands += menuCommand("trash", "Move to Trash", "delete", card);
  } else {
    commands = menuCommand("new-folder", "New folder", "folder-add");
    commands += menuCommand("import-files", "Import files…", "import-files");
    commands += menuCommand("import-folder", "Import folder…", "import-folder");
    commands += '<div class="item-context-menu__separator" role="separator"></div>';
    commands += menuCommand("select-all", "Select all", "select-all");
  }
  itemContextMenu.innerHTML = `${selectedCount > 1 && card ? `<div class="item-context-menu__heading">${selectedCount} items selected</div>` : ""}${commands}`;
  itemContextMenu.hidden = false;
  const bounds = itemContextMenu.getBoundingClientRect();
  const fallbackX = card ? card.getBoundingClientRect().left : 12;
  const fallbackY = card ? card.getBoundingClientRect().bottom : 12;
  const x = event.clientX || fallbackX;
  const y = event.clientY || fallbackY;
  itemContextMenu.style.left = `${Math.max(8, Math.min(x, window.innerWidth - bounds.width - 8))}px`;
  itemContextMenu.style.top = `${Math.max(8, Math.min(y, window.innerHeight - bounds.height - 8))}px`;
  itemContextMenu.querySelector('[role="menuitem"]')?.focus();
}

function selectItemFromCard(card, event) {
  const id = card.dataset.item;
  const cards = [...pageContent.querySelectorAll(".item-card")];
  const toggle = event.ctrlKey || event.metaKey;
  if (event.shiftKey && selectionAnchorId) {
    const start = cards.findIndex((entry) => entry.dataset.item === selectionAnchorId);
    const end = cards.indexOf(card);
    if (start >= 0 && end >= 0) {
      selectedIds.clear();
      cards.slice(Math.min(start, end), Math.max(start, end) + 1).forEach((entry) => selectedIds.add(entry.dataset.item));
    } else {
      selectedIds.clear();
      selectedIds.add(id);
      selectionAnchorId = id;
    }
  } else if (toggle) {
    if (selectedIds.has(id)) selectedIds.delete(id);
    else selectedIds.add(id);
    selectionAnchorId = id;
  } else {
    selectedIds.clear();
    selectedIds.add(id);
    selectionAnchorId = id;
  }
  updateSelectionLabel();
}

function resetFolderHistory() {
  currentFolder = ROOT_ID;
  folderStack = [];
  folderHistory = [{ folderId: ROOT_ID, stack: [] }];
  folderHistoryIndex = 0;
}

function navigateFolder(folderId, name) {
  if (folderHistoryIndex < 0) {
    folderHistory = [{ folderId: currentFolder, stack: [...folderStack] }];
    folderHistoryIndex = 0;
  }
  folderHistory = folderHistory.slice(0, folderHistoryIndex + 1);
  folderStack = [...folderStack, { id: folderId, name }];
  currentFolder = folderId;
  folderHistory.push({ folderId, stack: [...folderStack] });
  folderHistoryIndex = folderHistory.length - 1;
  return renderPage();
}

function goToFolderHistory(direction) {
  const nextIndex = folderHistoryIndex + direction;
  if (nextIndex < 0 || nextIndex >= folderHistory.length) return;
  folderHistoryIndex = nextIndex;
  currentFolder = folderHistory[nextIndex].folderId;
  folderStack = [...folderHistory[nextIndex].stack];
  return renderPage();
}

function goToParentFolder() {
  if (!folderStack.length) return;
  const nextStack = folderStack.slice(0, -1);
  const parent = nextStack.at(-1);
  const parentId = parent?.id || ROOT_ID;
  const parentStack = nextStack;
  if (folderHistoryIndex < 0) {
    folderHistory = [{ folderId: currentFolder, stack: [...folderStack] }];
    folderHistoryIndex = 0;
  }
  folderHistory = folderHistory.slice(0, folderHistoryIndex + 1);
  currentFolder = parentId;
  folderStack = parentStack;
  folderHistory.push({ folderId: parentId, stack: [...parentStack] });
  folderHistoryIndex = folderHistory.length - 1;
  return renderPage();
}

function confirmPermanentDeletion(itemIds) {
  const cards = itemIds.map((id) => [...pageContent.querySelectorAll(".item-card")]
    .find((card) => card.dataset.item === id)).filter(Boolean);
  const folders = cards.filter((card) => card.classList.contains("item-card--folder")).length;
  const count = itemIds.length;
  confirmDeleteDescription.textContent = `${count} ${count === 1 ? "item" : "items"} will be permanently deleted from this vault.${folders ? " All files and subfolders inside the selected folders will be deleted too." : ""}`;
  confirmDeleteItems.innerHTML = cards.slice(0, 4).map((card) => {
    const name = card.querySelector(".item-card__name")?.textContent || "Unnamed item";
    const kind = card.classList.contains("item-card--folder") ? "Folder" : "File";
    return `<li>${uiIcon(kind === "Folder" ? "files" : "document", "confirm-delete__item-icon")}<span class="confirm-delete__item-name">${escapeHtml(name)}</span><span class="confirm-delete__item-kind">${kind}</span></li>`;
  }).join("");
  if (count > cards.length) {
    confirmDeleteItems.insertAdjacentHTML("beforeend", `<li class="confirm-delete__more">And ${count - cards.length} more ${count - cards.length === 1 ? "item" : "items"}</li>`);
  }
  confirmDeleteDialog.returnValue = "cancel";
  return new Promise((resolve) => {
    confirmDeleteDialog.addEventListener("close", () => {
      resolve(confirmDeleteDialog.returnValue === "confirm");
      clearTimeout(confirmDeleteContentClearTimer);
      confirmDeleteContentClearTimer = setTimeout(() => {
        if (!confirmDeleteDialog.open) confirmDeleteItems.replaceChildren();
      }, 210);
    }, { once: true });
    clearTimeout(confirmDeleteContentClearTimer);
    confirmDeleteDialog.showModal();
    requestAnimationFrame(() => confirmDeleteCancel.focus());
  });
}

function requireOne() {
  if (selectedIds.size !== 1) throw new Error("Select exactly one item first");
  return [...selectedIds][0];
}

async function finishFirstRun() {
  try {
    preferences = await window.pywebview.api.complete_first_run();
  } catch {
    preferences = { ...preferences, setup_complete: true, vault_configured: true };
    notify("Vault created, but setup status could not be saved. Restart Frivault if setup appears again.", true);
  }
}

function setSetupFeedback(message, error = false) {
  const feedback = document.getElementById("setup-message");
  if (!feedback) return;
  feedback.textContent = message;
  feedback.hidden = !message;
  feedback.classList.toggle("setup-message--error", error);
}

function setUnlockFeedback(message, error = false) {
  const feedback = document.getElementById("unlock-message");
  if (!feedback) return;
  feedback.textContent = message;
  feedback.hidden = !message;
  feedback.classList.toggle("setup-message--error", error);
}

function resetPasswordFields(form, clearValues = false) {
  form.querySelectorAll(".password-control").forEach((control) => {
    const input = control.querySelector("input");
    const toggle = control.querySelector("[data-password-toggle]");
    if (clearValues) input.value = "";
    input.type = "password";
    toggle.setAttribute("aria-pressed", "false");
    toggle.setAttribute("aria-label", "Show password");
    toggle.title = "Show password";
  });
}

function setPasswordChangeFeedback(message, error = false) {
  const feedback = document.getElementById("password-change-message");
  if (!feedback) return;
  feedback.textContent = message;
  feedback.hidden = !message;
  feedback.classList.toggle("setup-message--error", error);
}

async function openVaultFlow() {
  const result = await window.pywebview.api.open_vault_dialog();
  if (!result) return;
  currentVault = result;
  if (result.state === "UNLOCKED") {
    await finishFirstRun();
    currentPage = "overview";
    await renderPage();
    return;
  }
  currentPage = "overview";
  renderLocked();
}

async function lockFlow() {
  await window.pywebview.api.lock_vault();
  const status = await window.pywebview.api.get_app_status();
  currentVault = status.data.vault;
  currentPage = "overview";
  selectedIds.clear();
  clipboardItemIds = [];
  folderStack = [];
  currentFolder = ROOT_ID;
  searchQuery = "";
  renderLocked();
  notify("Vault locked");
}

async function act(action, button) {
  const api = window.pywebview.api;
  if (action === "close-settings") {
    settingsDialog.close();
    return;
  }
  if (action === "retry-status") {
    try { await refreshStatus(); }
    catch { renderStartupError(); }
    return;
  }
  if (action === "select-all") {
    const cards = [...pageContent.querySelectorAll(".item-card")];
    const select = cards.some((card) => !selectedIds.has(card.dataset.item));
    cards.forEach((card) => select ? selectedIds.add(card.dataset.item) : selectedIds.delete(card.dataset.item));
    selectionAnchorId = select ? cards[0]?.dataset.item || null : null;
    updateSelectionLabel();
    return;
  }
  if (action === "open-vault") return openVaultFlow();
  if (action === "lock") return lockFlow();
  if (action === "unlock") {
    return renderUnlockScreen();
  }
  if (action === "import-files" || action === "import-folder") {
    const destinationFolderId = currentFolder;
    const destinationName = folderStack.length ? folderStack[folderStack.length - 1].name : "My Vault";
    const result = action === "import-files"
      ? await api.import_files_dialog(destinationFolderId)
      : await api.import_folder_dialog(destinationFolderId);
    if (!result.task_ids.length) return;
    trackOperationBatch(result.task_ids, destinationFolderId, destinationName, "import");
    if (currentPage === "files" && currentFolder === destinationFolderId) await renderPage();
    refreshImportBatches().catch(() => {});
    notify(`Started ${result.task_ids.length} import operation(s)`);
    return;
  }
  if (action === "new-folder") return openModal("Create a folder", field("Folder name", "name"), "Create folder", async (data) => {
    await api.create_folder(currentFolder, data.get("name"));
    await renderPage();
    notify("Folder created");
  });
  if (action === "enter-folder") {
    const row = button.closest("[data-item]") || [...pageContent.querySelectorAll("[data-item]")].find((item) => item.dataset.item === button.dataset.id);
    const name = button.dataset.name || row?.querySelector(".item-card__name, .item-name__text")?.textContent || "Folder";
    return navigateFolder(button.dataset.id, name);
  }
  if (action === "back-folder") return goToFolderHistory(-1);
  if (action === "forward-folder") return goToFolderHistory(1);
  if (action === "up-folder") return goToParentFolder();
  if (action === "root") { resetFolderHistory(); return renderPage(); }
  if (action === "breadcrumb") {
    const index = folderStack.findIndex((entry) => entry.id === button.dataset.id);
    if (index < 0) return;
    const nextStack = folderStack.slice(0, index + 1);
    const location = { folderId: button.dataset.id, stack: nextStack };
    if (folderHistoryIndex < 0) {
      folderHistory = [{ folderId: currentFolder, stack: [...folderStack] }];
      folderHistoryIndex = 0;
    }
    folderHistory = folderHistory.slice(0, folderHistoryIndex + 1);
    currentFolder = location.folderId;
    folderStack = location.stack;
    folderHistory.push(location);
    folderHistoryIndex = folderHistory.length - 1;
    return renderPage();
  }
  if (action === "trash") {
    if (!selectedIds.size) throw new Error("Select at least one item");
    await api.trash_items([...selectedIds]);
    selectedIds.clear(); await renderPage(); notify("Moved to Trash"); return;
  }
  if (action === "restore") {
    if (!selectedIds.size) throw new Error("Select items to restore");
    await api.restore_items([...selectedIds]); selectedIds.clear(); await renderPage(); notify("Items restored"); return;
  }
  if (action === "permanent-delete") {
    if (!selectedIds.size) throw new Error("Select items to delete");
    const itemIds = [...selectedIds];
    if (preferences.confirm_permanent_delete && !await confirmPermanentDeletion(itemIds)) return;
    await api.permanently_delete_items(itemIds); selectedIds.clear(); await renderPage(); notify("Items permanently removed from the vault"); return;
  }
  if (action === "toggle-favorite") {
    const id = requireOne();
    const items = await api.search_items("");
    const item = items.find((entry) => entry.id === id);
    await api.set_favorites([id], !item?.favorite); await renderPage(); return;
  }
  if (action === "rename") {
    const id = requireOne();
    const item = await api.get_item_properties(id);
    return openModal("Rename item", `${field("New name", "name", "text", `value="${escapeHtml(item.name)}"`)}`, "Save name", async (data) => {
      await api.rename_item(id, data.get("name")); await renderPage(); notify("Name updated");
    });
  }
  if (action === "export") {
    const id = requireOne();
    const operation = await api.export_file_dialog(id);
    if (!operation) return;
    const destinationName = folderStack.length ? folderStack[folderStack.length - 1].name : "My Vault";
    trackOperationBatch([operation.task_id], currentFolder, destinationName, "export");
    await renderPage();
    refreshImportBatches().catch(() => {});
    notify("Export started"); return;
  }
  if (action === "cancel-operation-batch") {
    const batch = importBatches.find((entry) => entry.batchId === button.dataset.id);
    if (!batch || batch.cancelRequested) return;
    const operations = await api.get_operations();
    batch.operations = operations.filter((task) => batch.taskIds.includes(task.task_id));
    const activeIds = batch.operations
      .filter((task) => ["PENDING", "RUNNING"].includes(task.state))
      .map((task) => task.task_id);
    if (!activeIds.length) {
      await refreshImportBatches();
      return;
    }
    batch.cancelRequested = true;
    updateImportBatchPanel(batch);
    const results = await Promise.allSettled(activeIds.map((taskId) => api.cancel_operation(taskId)));
    const failure = results.find((result) => result.status === "rejected");
    if (failure) {
      batch.cancelRequested = false;
      updateImportBatchPanel(batch);
      throw failure.reason;
    }
    notify("Cancellation requested");
    return;
  }
  if (action === "dismiss-operation-status") {
    importBatches = importBatches.filter((batch) => batch.batchId !== button.dataset.id);
    button.closest("[data-import-batch]")?.remove();
    return;
  }
  if (action === "copy") {
    if (!selectedIds.size) throw new Error("Select items first");
    clipboardItemIds = [...selectedIds];
    updateSelectionLabel();
    notify(`${clipboardItemIds.length} item${clipboardItemIds.length === 1 ? "" : "s"} ready to paste`);
    return;
  }
  if (action === "paste") {
    if (!clipboardItemIds.length) throw new Error("Copy an item before pasting");
    const destinationFolderId = currentFolder;
    const destinationName = folderStack.length ? folderStack[folderStack.length - 1].name : "My Vault";
    const operation = await api.copy_items([...clipboardItemIds], destinationFolderId);
    trackOperationBatch([operation.task_id], destinationFolderId, destinationName, "copy");
    selectedIds.clear();
    selectionAnchorId = null;
    await renderPage();
    refreshImportBatches().catch(() => {});
    notify("Paste started");
    return;
  }
  if (action === "move") {
    if (!selectedIds.size) throw new Error("Select items first");
    const folders = await api.list_folders();
    const choices = folders.map((folder) => `<option value="${escapeHtml(folder.id)}">${escapeHtml(folder.path)}</option>`).join("");
    return openModal("Move items", `<label class="field">Destination folder<select name="destination"><option value="${ROOT_ID}">My Vault (root)</option>${choices}</select></label>`, "Move", async (data) => {
      await api.move_items([...selectedIds], data.get("destination"));
      selectedIds.clear(); await renderPage(); notify("Items moved");
    });
  }
  if (action === "properties") {
    const item = await api.get_item_properties(button.dataset.id);
    return openModal("Item properties", `<p><strong>${escapeHtml(item.name)}</strong></p><p>Type: ${escapeHtml(item.kind)}</p><p>Size: ${formatBytes(item.size_bytes)}</p>`, "Close", async () => {});
  }
}

document.addEventListener("click", async (event) => {
  const contextCommand = event.target.closest("#item-context-menu [data-action]");
  if (contextCommand) {
    event.preventDefault();
    hideItemContextMenu();
    try { await act(contextCommand.dataset.action, contextCommand); }
    catch (error) { notify(error.message || "The action could not be completed", true); }
    return;
  }
  if (!event.target.closest("#item-context-menu")) hideItemContextMenu();

  const passwordToggle = event.target.closest("[data-password-toggle]");
  if (passwordToggle) {
    const input = document.getElementById(passwordToggle.getAttribute("aria-controls"));
    if (!input) return;
    const visible = input.type === "password";
    input.type = visible ? "text" : "password";
    const label = visible ? "Hide password" : "Show password";
    passwordToggle.setAttribute("aria-pressed", String(visible));
    passwordToggle.setAttribute("aria-label", label);
    passwordToggle.title = label;
    return;
  }
  const itemOpen = event.target.closest(".item-card__open");
  if (itemOpen) {
    event.preventDefault();
    const card = itemOpen.closest(".item-card");
    if (event.detail >= 2 || event.detail === 0) {
      if (!selectedIds.has(card.dataset.item)) {
        selectedIds.clear();
        selectedIds.add(card.dataset.item);
      }
      selectionAnchorId = card.dataset.item;
      updateSelectionLabel();
      try { await act(itemOpen.dataset.action, itemOpen); }
      catch (error) { notify(error.message || "Could not open this item", true); }
    } else {
      selectItemFromCard(card, event);
    }
    return;
  }
  const pageButton = event.target.closest("[data-page]");
  if (pageButton && !pageButton.disabled) {
    if (pageButton.dataset.page === "settings") {
      try { await openSettingsDialog(); }
      catch (error) { notify(error.message || "Settings could not be opened", true); }
      return;
    }
    const nextPage = pageButton.dataset.page;
    try {
      await transitionToPage(nextPage, {
        prepare: () => { if (nextPage === "files") resetFolderHistory(); },
      });
    } catch (error) { notify(error.message || "Could not load this view", true); }
    return;
  }
  const settingsCategory = event.target.closest("[data-settings-category]");
  if (settingsCategory) {
    setSettingsCategory(settingsCategory.dataset.settingsCategory);
    return;
  }
  const contentArea = event.target.closest(".main-content");
  const selectionControl = event.target.closest(
    ".topbar, .toolbar, .location-bar, .summary-strip, .item-card, .item-context-menu, button, input, select, textarea, a, [role='button']",
  );
  if (contentArea && !selectionControl
      && ["files", "search", "recent", "favorites", "trash"].includes(currentPage)) {
    if (selectedIds.size) {
      selectedIds.clear();
      selectionAnchorId = null;
      updateSelectionLabel();
    }
    return;
  }
  const actionButton = event.target.closest("[data-action]");
  if (!actionButton) return;
  if (actionButton.hasAttribute("data-modal-cancel")) { modal.close(); return; }
  try { await act(actionButton.dataset.action, actionButton); }
  catch (error) { notify(error.message || "The action could not be completed", true); }
});

document.addEventListener("change", (event) => {
  if (event.target.id === "sort-select") {
    sortBy = event.target.value;
    renderPage().catch((error) => notify(error.message, true));
    return;
  }
});

document.addEventListener("contextmenu", (event) => {
  if (!pageContent.contains(event.target) || currentVault?.state !== "UNLOCKED"
      || !["files", "search", "recent", "favorites", "trash"].includes(currentPage)) return;
  const card = event.target.closest(".item-card");
  if (!card && !event.target.closest(".item-grid, .empty-state")) return;
  event.preventDefault();
  showItemContextMenu(event, card);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !itemContextMenu.hidden) {
    hideItemContextMenu();
    return;
  }
  if (currentPage === "files" && event.altKey && ["ArrowLeft", "ArrowRight", "ArrowUp"].includes(event.key)) {
    event.preventDefault();
    if (event.key === "ArrowLeft") goToFolderHistory(-1);
    else if (event.key === "ArrowRight") goToFolderHistory(1);
    else goToParentFolder();
    return;
  }
  if (itemContextMenu.hidden) return;
  const commands = [...itemContextMenu.querySelectorAll('[role="menuitem"]')];
  const index = commands.indexOf(document.activeElement);
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const direction = event.key === "ArrowDown" ? 1 : -1;
    commands[(index + direction + commands.length) % commands.length]?.focus();
  }
});

document.addEventListener("submit", async (event) => {
  if (event.target.id === "unlock-form") {
    event.preventDefault();
    const form = event.target;
    const passwordInput = form.querySelector('[name="password"]');
    const password = String(new FormData(form).get("password") || "");
    const submit = form.querySelector('[type="submit"]');
    setUnlockFeedback("");
    if (!password) {
      setUnlockFeedback("Enter your vault password to continue.", true);
      passwordInput.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "Unlocking…";
    try {
      currentVault = await window.pywebview.api.unlock_vault(password);
    } catch {
      passwordInput.value = "";
      setUnlockFeedback("That password could not unlock this vault. Check it and try again.", true);
      passwordInput.focus();
      submit.disabled = false;
      submit.textContent = "Unlock vault";
      return;
    }
    passwordInput.value = "";
    currentPage = "overview";
    const setupCompletion = finishFirstRun();
    try {
      await transitionToPage("overview", { force: true, surface: pageContent.parentElement });
      await setupCompletion;
      hasPaintedUi = true;
      notify("Vault unlocked");
    } catch (error) {
      appShell.classList.remove("app-shell--locked", "app-shell--setup");
      renderNavigation();
      pageContent.innerHTML = `<section class="content-card startup-error" role="alert">
        <div class="eyebrow">VAULT UNLOCKED</div><h2>Your vault is open, but the dashboard could not load.</h2>
        <p>${escapeHtml(error.message || "Try loading the vault again.")}</p>
        <button class="button" data-action="retry-status">Retry</button>
      </section>`;
      notify("Vault unlocked, but the dashboard could not load", true);
    } finally {
      submit.disabled = false;
      submit.textContent = "Unlock vault";
    }
    return;
  }
  if (event.target.id === "setup-form") {
    event.preventDefault();
    const form = event.target;
    const data = new FormData(form);
    const vaultName = String(data.get("vault_name") || "").trim();
    const password = String(data.get("password") || "");
    const confirmation = String(data.get("confirm") || "");
    resetPasswordFields(form);
    const submit = form.querySelector('[type="submit"]');
    const nameInput = form.querySelector('[name="vault_name"]');
    const passwordInput = form.querySelector('[name="password"]');
    const confirmInput = form.querySelector('[name="confirm"]');
    setSetupFeedback("");
    if (!vaultName) {
      setSetupFeedback("Enter a name for your vault.", true);
      nameInput.focus();
      return;
    }
    if (password !== confirmation) {
      setSetupFeedback("The passwords do not match. Check both fields and try again.", true);
      confirmInput.focus();
      return;
    }
    if (Array.from(password.trim()).length < 12) {
      setSetupFeedback("Use a password with at least 12 non-space characters.", true);
      passwordInput.focus();
      return;
    }
    if (new TextEncoder().encode(password).length > 1024) {
      setSetupFeedback("This password is too long. Use no more than 1,024 UTF-8 bytes.", true);
      passwordInput.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "Choose vault location…";
    setSetupFeedback("Select a parent folder in the Windows dialog. Your named vault folder will be created there.");
    try {
      currentVault = await window.pywebview.api.create_vault(vaultName, password);
      if (!currentVault) {
        resetPasswordFields(form, true);
        setSetupFeedback("No folder was selected. Your password was cleared; enter it again when you are ready to continue.");
        return;
      }
      resetPasswordFields(form, true);
      await finishFirstRun();
      currentPage = "overview";
      await renderPage();
      hasPaintedUi = true;
      resetPasswordFields(form, true);
      notify("Frivault is ready. Your vault is open.");
    } catch (error) {
      resetPasswordFields(form);
      setSetupFeedback(error.message || "Frivault could not be created. Try another location.", true);
    } finally {
      submit.disabled = false;
      submit.textContent = "Create Frivault";
    }
    return;
  }
  if (event.target.id === "quick-search-form") {
    event.preventDefault();
    searchQuery = new FormData(event.target).get("query").trim();
    currentPage = "search";
    try { await renderPage(); }
    catch (error) { notify(error.message || "Search could not be completed", true); }
    return;
  }
  if (event.target.id === "search-form") {
    event.preventDefault(); searchQuery = new FormData(event.target).get("query");
    try { await renderPage(); } catch (error) { notify(error.message, true); }
  }
  if (event.target.id === "settings-form") {
    event.preventDefault();
    const data = new FormData(event.target);
    const activeCategory = settingsDialog.querySelector(".settings-nav__item--active")?.dataset.settingsCategory || "appearance";
    try {
      preferences = await window.pywebview.api.save_settings(
        data.get("theme"),
        Number(data.get("timeout")),
        data.get("default_sort_by"),
        data.get("confirm_permanent_delete") === "true",
        data.get("density"),
      );
      sortBy = preferences.default_sort_by || "name";
      applyTheme(preferences.theme);
      applyDensity(preferences.density);
      await renderSettings(settingsDialogContent);
      setSettingsCategory(activeCategory);
      notify("Preferences saved");
    } catch (error) { notify(error.message || "Settings could not be saved", true); }
    return;
  }
  if (event.target.id === "password-change-form") {
    event.preventDefault();
    const form = event.target;
    const data = new FormData(form);
    const currentPassword = String(data.get("current_password") || "");
    const newPassword = String(data.get("new_password") || "");
    const confirmation = String(data.get("confirm_password") || "");
    const submit = form.querySelector('[type="submit"]');
    resetPasswordFields(form);
    setPasswordChangeFeedback("");
    if (!currentPassword) {
      setPasswordChangeFeedback("Enter your current password.", true);
      form.querySelector('[name="current_password"]').focus();
      return;
    }
    if (newPassword !== confirmation) {
      setPasswordChangeFeedback("The new passwords do not match.", true);
      form.querySelector('[name="confirm_password"]').focus();
      return;
    }
    if (Array.from(newPassword.trim()).length < 12) {
      setPasswordChangeFeedback("Use a new password with at least 12 non-space characters.", true);
      form.querySelector('[name="new_password"]').focus();
      return;
    }
    if (new TextEncoder().encode(newPassword).length > 1024) {
      setPasswordChangeFeedback("The new password exceeds 1,024 UTF-8 bytes.", true);
      form.querySelector('[name="new_password"]').focus();
      return;
    }
    if (currentPassword === newPassword) {
      setPasswordChangeFeedback("Choose a new password different from the current one.", true);
      form.querySelector('[name="new_password"]').focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "Updating password…";
    try {
      await window.pywebview.api.change_vault_passphrase(currentPassword, newPassword);
      resetPasswordFields(form, true);
      setPasswordChangeFeedback("Password changed. Use the new password the next time you open Frivault.");
      notify("Vault password changed");
    } catch (error) {
      resetPasswordFields(form);
      setPasswordChangeFeedback(error.message || "The password could not be changed.", true);
    } finally {
      submit.disabled = false;
      submit.textContent = "Change password";
    }
    return;
  }
});

document.addEventListener("input", (event) => {
  if (event.target.closest?.("#setup-form")) setSetupFeedback("");
  if (event.target.closest?.("#unlock-form")) setUnlockFeedback("");
  if (event.target.closest?.("#password-change-form")) setPasswordChangeFeedback("");
});

let lastPing = 0;
function pingOnActivity() {
  if (Date.now() - lastPing > 15000 && window.pywebview?.api) {
    lastPing = Date.now(); window.pywebview.api.ping();
  }
}
document.addEventListener("pointerdown", pingOnActivity);
document.addEventListener("keydown", pingOnActivity);

sidebarToggle.addEventListener("click", () => {
  const collapsed = appShell.classList.toggle("app-shell--sidebar-collapsed");
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  sidebarToggle.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
  sidebarToggle.title = collapsed ? "Expand sidebar" : "Collapse sidebar";
});

window.addEventListener("pywebviewready", async () => {
  try { await refreshStatus(); }
  catch { renderStartupError(); }
});
setTimeout(() => {
  if (!hasPaintedUi) renderStartupError();
}, 8000);
setInterval(() => {
  if (window.pywebview?.api) {
    refreshStatus().catch(() => {
      if (!hasPaintedUi) renderStartupError();
      else setConnectionMessage("Desktop status unavailable");
    });
  }
}, 5000);
setInterval(() => {
  if (importBatches.some((batch) => !batch.completed)) {
    refreshImportBatches().catch(() => {});
  }
}, 1000);
