/**
 * Validation receipt: AgentAccessSection is wired into Settings and exports the control.
 * Credential mint/list/revoke UI lives in AgentCredentialsManager + api helpers.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

test("SettingsPanel mounts AgentAccessSection", () => {
  const panel = readFileSync(join(root, "src/components/SettingsPanel.tsx"), "utf8");
  assert.match(panel, /import \{ AgentAccessSection \}/);
  assert.match(panel, /<AgentAccessSection enabled=\{open\} \/>/);
});

test("AgentAccessSection toggles allow_agent_cli_access via updateSettings", () => {
  const section = readFileSync(
    join(root, "src/components/settings/AgentAccessSection.tsx"),
    "utf8",
  );
  assert.match(section, /Allow agent and CLI access/);
  assert.match(section, /allow_agent_cli_access/);
  assert.match(section, /updateSettings\(\{ allow_agent_cli_access: allow \}\)/);
  assert.match(section, /AgentCredentialsManager/);
});

test("AgentCredentialsManager wires list/create/revoke API helpers", () => {
  const manager = readFileSync(
    join(root, "src/components/settings/AgentCredentialsManager.tsx"),
    "utf8",
  );
  assert.match(manager, /listAgentCredentials/);
  assert.match(manager, /createAgentCredential/);
  assert.match(manager, /revokeAgentCredential/);
});

test("api.ts exports agent credential client helpers", () => {
  const api = readFileSync(join(root, "src/api.ts"), "utf8");
  assert.match(api, /export function listAgentCredentials/);
  assert.match(api, /export function createAgentCredential/);
  assert.match(api, /export function revokeAgentCredential/);
  assert.match(api, /export interface AgentCredential/);
  assert.match(api, /export interface AgentCredentialCreated/);
  const helpers = api.slice(api.indexOf("export function listAgentCredentials"));
  const helperBlock = helpers.slice(0, helpers.indexOf("export function fetchFocusWindows"));
  assert.doesNotMatch(helperBlock, /Authorization/i);
  assert.match(helperBlock, /apiFetch/);
  const listShape = api.slice(
    api.indexOf("export interface AgentCredential {"),
    api.indexOf("export interface AgentCredentialCreated"),
  );
  assert.doesNotMatch(listShape, /^\s*secret:/m);
});

test("AgentCredentialsManager blocks create while the one-time secret is shown", () => {
  const manager = readFileSync(
    join(root, "src/components/settings/AgentCredentialsManager.tsx"),
    "utf8",
  );
  assert.match(
    manager,
    /createBlocked = !canCreate \|\| createMutation\.isPending \|\| Boolean\(createdSecret\)/,
  );
  assert.match(manager, /canCreate/);
  assert.match(manager, /Copy this secret now/);
  assert.match(manager, /one-time secret was cleared/);
  assert.match(manager, /AGENT_ACCESS_DISABLED/);
  assert.match(manager, /AGENT_CREDENTIAL_CANNOT_ADMIN/);
});

test("AgentAccessSection keeps credentials manager mounted when allow is off", () => {
  const section = readFileSync(
    join(root, "src/components/settings/AgentAccessSection.tsx"),
    "utf8",
  );
  assert.match(section, /<AgentCredentialsManager enabled=\{enabled\} canCreate=\{allowed\} \/>/);
  assert.doesNotMatch(section, /\{allowed && <AgentCredentialsManager/);
});

test("UserSettings types include allow_agent_cli_access fields", () => {
  const api = readFileSync(join(root, "src/api.ts"), "utf8");
  assert.match(api, /allow_agent_cli_access: boolean/);
  assert.match(api, /allow_agent_cli_access_grandfathered: boolean/);
  assert.match(api, /\|\s*"allow_agent_cli_access"/);
});
