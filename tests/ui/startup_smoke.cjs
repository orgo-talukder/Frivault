"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sourcePath = path.resolve(__dirname, "../../src/frivault/resources/ui/js/app.js");
const source = fs.readFileSync(sourcePath, "utf8");

async function boot(status, apiOverrides = {}) {
  const elements = new Map();
  const windowListeners = new Map();
  const documentListeners = new Map();
  const element = (id) => {
    if (!elements.has(id)) {
      elements.set(id, {
        id,
        innerHTML: "",
        textContent: "",
        value: "",
        disabled: false,
        dataset: {},
        attributes: {},
        children: [],
        open: false,
        lastElementChild: { textContent: "" },
        classList: { toggle() {}, add() {}, remove() {} },
        addEventListener() {},
        showModal() { this.open = true; },
        close() { this.open = false; },
        replaceChildren() { this.children = []; },
        setAttribute(name, value) { this.attributes[name] = value; },
        querySelector() { return null; },
        querySelectorAll() { return []; },
      });
    }
    return elements.get(id);
  };

  const document = {
    documentElement: { dataset: {} },
    getElementById: element,
    querySelector: element,
    addEventListener(name, callback) { documentListeners.set(name, callback); },
  };
  const modalForm = element("modal-form");
  modalForm.submitControl = { disabled: false };
  modalForm.querySelector = (selector) =>
    selector === '[type="submit"]' ? modalForm.submitControl : null;
  const api = {
    async get_app_status() { return status; },
    async get_storage_summary() { return { file_count: 0, folder_count: 0, encrypted_bytes: 0 }; },
    async list_items() { return []; },
    ...apiOverrides,
  };
  const window = {
    pywebview: { api },
    addEventListener(name, callback) { windowListeners.set(name, callback); },
  };
  const context = {
    document,
    window,
    Date,
    TextEncoder,
    FormData: class {
      constructor(form) { this.form = form; }
      get(name) { return String(this.form.values[name] || ""); }
    },
    setTimeout() { return 1; },
    clearTimeout() {},
    setInterval() { return 1; },
    console,
  };

  vm.runInNewContext(source, context, { filename: "app.js" });
  await windowListeners.get("pywebviewready")();
  return { elements, document, documentListeners };
}

function setupForm(values) {
  const nameInput = { name: "vault_name", value: values.vault_name, type: "text", focus() {} };
  const controls = ["password", "confirm"].map((name) => {
    const input = { name, value: values[name], type: "password", focus() {} };
    const toggle = {
      attributes: { "aria-pressed": "false" },
      title: "Show password",
      setAttribute(key, value) { this.attributes[key] = value; },
    };
    return {
      input,
      querySelector(selector) { return selector === "input" ? input : toggle; },
    };
  });
  const submit = { disabled: false, textContent: "Create Frivault" };
  return {
    id: "setup-form",
    values,
    controls,
    submit,
    querySelector(selector) {
      if (selector === '[type="submit"]') return submit;
      if (selector === '[name="vault_name"]') return nameInput;
      if (selector === '[name="password"]') return controls[0].input;
      if (selector === '[name="confirm"]') return controls[1].input;
      return null;
    },
    querySelectorAll(selector) { return selector === ".password-control" ? controls : []; },
  };
}

async function main() {
  const locked = await boot({
    ok: true,
    data: {
      version: "0.1.0",
      vault: null,
      settings: { theme: "system", auto_lock_minutes: 15, setup_complete: false },
    },
  });
  assert.match(locked.elements.get("page-title").textContent, /Set up Frivault/);
  const setupMarkup = locked.elements.get("page-content").innerHTML;
  assert.match(setupMarkup, /id="setup-form"/);
  assert.match(setupMarkup, /name="password"/);
  assert.match(setupMarkup, /name="confirm"/);
  assert.match(setupMarkup, /Create Frivault/);
  assert.equal((setupMarkup.match(/data-password-toggle/g) || []).length, 2);
  assert.doesNotMatch(locked.elements.get("navigation").innerHTML, /Create a vault/);

  const passwordInput = { type: "password" };
  const passwordToggle = {
    attributes: { "aria-controls": "setup-password", "aria-pressed": "false" },
    title: "Show password",
    getAttribute(name) { return this.attributes[name]; },
    setAttribute(name, value) { this.attributes[name] = value; },
  };
  locked.elements.get("page-content").querySelector = (selector) =>
    selector === "#setup-password" ? passwordInput : null;
  const toggleClick = locked.documentListeners.get("click");
  const toggleEvent = {
    target: { closest(selector) { return selector === "[data-password-toggle]" ? passwordToggle : null; } },
  };
  await toggleClick(toggleEvent);
  assert.equal(passwordInput.type, "text");
  assert.equal(passwordToggle.attributes["aria-pressed"], "true");
  assert.equal(passwordToggle.attributes["aria-label"], "Hide password");
  await toggleClick(toggleEvent);
  assert.equal(passwordInput.type, "password");
  assert.equal(passwordToggle.attributes["aria-pressed"], "false");
  assert.equal(passwordToggle.attributes["aria-label"], "Show password");

  let createdVaultArgs;
  const creating = await boot({
    ok: true,
    data: {
      version: "0.1.0",
      vault: null,
      settings: { theme: "system", auto_lock_minutes: 15, setup_complete: false },
    },
  }, {
    async create_vault(name, password) {
      createdVaultArgs = [name, password];
      return { state: "UNLOCKED", name };
    },
    async complete_first_run() {
      return { theme: "system", auto_lock_minutes: 15, setup_complete: true };
    },
  });
  const submittedForm = setupForm({
    vault_name: "My Frivault",
    password: "Correct horse battery staple 42",
    confirm: "Correct horse battery staple 42",
  });
  await creating.documentListeners.get("submit")({
    target: submittedForm,
    preventDefault() {},
  });
  assert.deepEqual(createdVaultArgs, ["My Frivault", "Correct horse battery staple 42"]);
  assert.match(creating.elements.get("page-content").innerHTML, /VAULT UNLOCKED/);
  assert.equal(submittedForm.controls[0].input.value, "");
  assert.equal(submittedForm.controls[0].input.type, "password");

  const unlocked = await boot({
    ok: true,
    data: {
      version: "0.1.0",
      vault: { vault_id: "test-vault", state: "UNLOCKED", name: "Preview vault" },
      settings: { theme: "system", auto_lock_minutes: 15, setup_complete: true },
    },
  }, {
    async get_storage_summary() { return { file_count: 1, folder_count: 0, encrypted_bytes: 11 }; },
    async list_items() {
      return [{ id: "test-item", name: "recent.txt", kind: "file", size_bytes: 11, modified_at_ns: 0 }];
    },
  });
  assert.match(unlocked.elements.get("page-title").textContent, /Home/);
  assert.match(unlocked.elements.get("page-content").innerHTML, /recent\.txt/);

  const rejectingUnlock = await boot({
    ok: true,
    data: {
      version: "0.1.0",
      vault: { vault_id: "saved-vault", state: "LOCKED", name: null },
      settings: {
        theme: "system", auto_lock_minutes: 15, setup_complete: true,
        vault_configured: true,
      },
    },
  }, {
    async unlock_vault() { throw new Error("Passphrase is incorrect"); },
  });
  const passwordInput = { value: "wrong password", focus() {} };
  const unlockForm = {
    id: "unlock-form",
    values: { password: "wrong password" },
    querySelector(selector) {
      if (selector === '[name="password"]') return passwordInput;
      if (selector === '[type="submit"]') return { disabled: false, textContent: "Unlock vault" };
      return null;
    },
  };
  await rejectingUnlock.documentListeners.get("submit")({
    target: unlockForm,
    preventDefault() {},
  });
  assert.equal(rejectingUnlock.elements.get("modal").open, false);
  assert.equal(passwordInput.value, "");
  assert.match(rejectingUnlock.elements.get("page-content").innerHTML, /id="unlock-form"/);
  assert.match(rejectingUnlock.elements.get("page-content").innerHTML, /That password could not unlock this vault/);
  assert.match(rejectingUnlock.elements.get("page-content").innerHTML, /VAULT LOCKED/);
  assert.doesNotMatch(rejectingUnlock.elements.get("page-content").innerHTML, /VAULT UNLOCKED/);

  const failed = await boot(null, {
    async get_app_status() { throw new Error("bridge unavailable"); },
  });
  assert.match(failed.elements.get("page-content").innerHTML, /could not load its desktop services/i);
  assert.match(failed.elements.get("page-content").innerHTML, /retry-status/);
  console.log("UI checks passed (setup toggle/create, locked, unlocked and bridge-failure states).");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
