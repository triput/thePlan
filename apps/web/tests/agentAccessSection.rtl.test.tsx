/**
 * Disposable UI interaction receipt for AgentAccessSection (Dex 1793145842.671319).
 * Renders + clicks + mocked fetchSettings/updateSettings — not source regex.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React, { type ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, type AgentCredential, type AgentCredentialCreated, type UserSettings } from "../src/api";
import { AgentAccessSection } from "../src/components/settings/AgentAccessSection";

const fetchSettings = vi.fn();
const updateSettings = vi.fn();
const listAgentCredentials = vi.fn();
const createAgentCredential = vi.fn();
const revokeAgentCredential = vi.fn();
const emitToast = vi.fn();

vi.mock("../src/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api")>();
  return {
    ...actual,
    fetchSettings: (...args: unknown[]) => fetchSettings(...args),
    updateSettings: (...args: unknown[]) => updateSettings(...args),
    listAgentCredentials: (...args: unknown[]) => listAgentCredentials(...args),
    createAgentCredential: (...args: unknown[]) => createAgentCredential(...args),
    revokeAgentCredential: (...args: unknown[]) => revokeAgentCredential(...args),
  };
});

vi.mock("../src/components/ToastHost", () => ({
  emitToast: (...args: unknown[]) => emitToast(...args),
}));

function baseSettings(overrides: Partial<UserSettings> = {}): UserSettings {
  return {
    timezone: "UTC",
    locale: "en-US",
    workday_minutes: 480,
    workday_start_local: "08:00",
    workweek_days: 5,
    inter_block_buffer_minutes: 5,
    upcoming_horizon_days: 7,
    default_estimated_duration_minutes: 30,
    default_min_block_duration_minutes: 15,
    default_schedule_style: "standalone",
    auto_defer_enabled: true,
    max_auto_schedule_minutes_per_project_per_day: null,
    scheduling_revision: 0,
    allow_agent_cli_access: false,
    allow_agent_cli_access_grandfathered: false,
    ...overrides,
  };
}

function sampleCredential(overrides: Partial<AgentCredential> = {}): AgentCredential {
  return {
    id: "cred-1",
    label: "laptop CLI",
    created_at: "2026-01-15T12:00:00.000Z",
    last_used_at: null,
    revoked_at: null,
    ...overrides,
  };
}

function renderSection(): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const ui: ReactElement = (
    <QueryClientProvider client={client}>
      <AgentAccessSection enabled />
    </QueryClientProvider>
  );
  render(ui);
}

describe("AgentAccessSection interaction", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    fetchSettings.mockReset();
    updateSettings.mockReset();
    listAgentCredentials.mockReset();
    createAgentCredential.mockReset();
    revokeAgentCredential.mockReset();
    emitToast.mockReset();
    listAgentCredentials.mockResolvedValue([]);
    vi.stubGlobal("confirm", vi.fn(() => true));
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("loads checkbox from settings (off) and still lists credentials", async () => {
    listAgentCredentials.mockResolvedValue([sampleCredential()]);
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: false }));
    renderSection();
    const box = await screen.findByRole("checkbox", { name: /allow agent and cli access/i });
    expect(box).not.toBeChecked();
    expect(fetchSettings).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("laptop CLI")).toBeInTheDocument();
    expect(listAgentCredentials).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /^revoke$/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/new credential label/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create credential/i })).not.toBeInTheDocument();
    expect(screen.getByText(/create is unavailable while agent and cli access is off/i)).toBeInTheDocument();
  });

  it("loads checkbox from settings (on) and lists credentials", async () => {
    listAgentCredentials.mockResolvedValue([sampleCredential()]);
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    renderSection();
    const box = await screen.findByRole("checkbox", { name: /allow agent and cli access/i });
    expect(box).toBeChecked();
    expect(await screen.findByText("laptop CLI")).toBeInTheDocument();
    expect(listAgentCredentials).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/theplan auth login --token/i)).toBeInTheDocument();
    expect(screen.queryByText(/\/api\/v1\/agent-credentials/)).not.toBeInTheDocument();
  });

  it("persists on then off with read-back from updateSettings result", async () => {
    const user = userEvent.setup();
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: false }));
    updateSettings
      .mockResolvedValueOnce(baseSettings({ allow_agent_cli_access: true }))
      .mockResolvedValueOnce(baseSettings({ allow_agent_cli_access: false }));

    renderSection();
    const box = await screen.findByRole("checkbox", { name: /allow agent and cli access/i });
    expect(box).not.toBeChecked();

    await user.click(box);
    await waitFor(() => expect(updateSettings).toHaveBeenCalledWith({ allow_agent_cli_access: true }));
    await waitFor(() => expect(box).toBeChecked());

    await user.click(box);
    await waitFor(() =>
      expect(updateSettings).toHaveBeenLastCalledWith({ allow_agent_cli_access: false }),
    );
    await waitFor(() => expect(box).not.toBeChecked());
    expect(updateSettings).toHaveBeenCalledTimes(2);
  });

  it("failed PATCH keeps prior checked state and shows visible error", async () => {
    const user = userEvent.setup();
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    updateSettings.mockRejectedValue(new Error("Agent access update blocked"));

    renderSection();
    const box = await screen.findByRole("checkbox", { name: /allow agent and cli access/i });
    expect(box).toBeChecked();

    await user.click(box);
    await waitFor(() => expect(updateSettings).toHaveBeenCalledWith({ allow_agent_cli_access: false }));
    await waitFor(() => {
      expect(screen.getByText("Agent access update blocked")).toBeInTheDocument();
    });
    expect(box).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /allow agent and cli access/i })).toBeChecked();
  });

  it("create shows secret once then dismiss clears it", async () => {
    const user = userEvent.setup();
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    const created: AgentCredentialCreated = {
      ...sampleCredential({ id: "cred-new", label: "ci bot" }),
      secret: "tp_agent_test_secret_once",
    };
    createAgentCredential.mockResolvedValue(created);

    renderSection();
    await screen.findByRole("checkbox", { name: /allow agent and cli access/i });

    await user.type(screen.getByLabelText(/new credential label/i), "ci bot");
    await user.click(screen.getByRole("button", { name: /create credential/i }));

    await waitFor(() => expect(createAgentCredential).toHaveBeenCalledWith({ label: "ci bot" }));
    expect(screen.getByText("tp_agent_test_secret_once")).toBeInTheDocument();
    expect(screen.getByText(/will not be shown again/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^done$/i }));
    expect(screen.queryByText("tp_agent_test_secret_once")).not.toBeInTheDocument();
  });

  it("blocks another create until Done dismisses the one-time secret", async () => {
    const user = userEvent.setup();
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    createAgentCredential
      .mockResolvedValueOnce({
        ...sampleCredential({ id: "cred-new", label: "ci bot" }),
        secret: "tp_agent_test_secret_once",
      } satisfies AgentCredentialCreated)
      .mockResolvedValueOnce({
        ...sampleCredential({ id: "cred-two", label: "second bot" }),
        secret: "tp_agent_second_secret",
      } satisfies AgentCredentialCreated);

    renderSection();
    await screen.findByRole("checkbox", { name: /allow agent and cli access/i });

    await user.type(screen.getByLabelText(/new credential label/i), "ci bot");
    await user.click(screen.getByRole("button", { name: /create credential/i }));
    await screen.findByText("tp_agent_test_secret_once");

    expect(screen.getByLabelText(/new credential label/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /create credential/i })).toBeDisabled();

    createAgentCredential.mockClear();
    await user.click(screen.getByRole("button", { name: /create credential/i }));
    expect(createAgentCredential).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /^done$/i }));
    expect(screen.getByLabelText(/new credential label/i)).not.toBeDisabled();

    await user.type(screen.getByLabelText(/new credential label/i), "second bot");
    await user.click(screen.getByRole("button", { name: /create credential/i }));
    await waitFor(() =>
      expect(createAgentCredential).toHaveBeenCalledWith({ label: "second bot" }),
    );
    expect(screen.getByText("tp_agent_second_secret")).toBeInTheDocument();
    expect(screen.queryByText("tp_agent_test_secret_once")).not.toBeInTheDocument();
  });

  it("list rows never render a secret even if the payload smuggles one", async () => {
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    listAgentCredentials.mockResolvedValue([
      {
        ...sampleCredential(),
        secret: "tp_agent_should_not_list",
      } as AgentCredential & { secret: string },
    ]);

    renderSection();
    expect(await screen.findByText("laptop CLI")).toBeInTheDocument();
    expect(screen.queryByText("tp_agent_should_not_list")).not.toBeInTheDocument();
  });

  it("revoke calls revokeAgentCredential after confirm", async () => {
    const user = userEvent.setup();
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    listAgentCredentials.mockResolvedValue([sampleCredential()]);
    revokeAgentCredential.mockResolvedValue(
      sampleCredential({ revoked_at: "2026-02-01T00:00:00.000Z" }),
    );

    renderSection();
    await screen.findByText("laptop CLI");
    await user.click(screen.getByRole("button", { name: /^revoke$/i }));

    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => expect(revokeAgentCredential).toHaveBeenCalledWith("cred-1"));
  });

  it("revoke confirm cancel does not call revokeAgentCredential", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("confirm", vi.fn(() => false));
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    listAgentCredentials.mockResolvedValue([sampleCredential()]);

    renderSection();
    await screen.findByText("laptop CLI");
    await user.click(screen.getByRole("button", { name: /^revoke$/i }));

    expect(window.confirm).toHaveBeenCalled();
    expect(revokeAgentCredential).not.toHaveBeenCalled();
  });

  it("create failure keeps form and shows visible error", async () => {
    const user = userEvent.setup();
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    createAgentCredential.mockRejectedValue(
      new ApiError(403, {
        detail: "Agent and CLI access is disabled",
        code: "AGENT_ACCESS_DISABLED",
      }),
    );

    renderSection();
    await screen.findByRole("checkbox", { name: /allow agent and cli access/i });
    await user.type(screen.getByLabelText(/new credential label/i), "blocked bot");
    await user.click(screen.getByRole("button", { name: /create credential/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/agent and cli access is disabled\. turn the setting on/i),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText(/will not be shown again/i)).not.toBeInTheDocument();
  });

  it("create maps AGENT_CREDENTIAL_CANNOT_ADMIN to browser-session copy", async () => {
    const user = userEvent.setup();
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    createAgentCredential.mockRejectedValue(
      new ApiError(403, {
        detail: "Agent credentials cannot administer agent access",
        code: "AGENT_CREDENTIAL_CANNOT_ADMIN",
      }),
    );

    renderSection();
    await screen.findByRole("checkbox", { name: /allow agent and cli access/i });
    await user.type(screen.getByLabelText(/new credential label/i), "mixed auth");
    await user.click(screen.getByRole("button", { name: /create credential/i }));

    await waitFor(() =>
      expect(screen.getByText(/requires a browser session \(no Bearer/i)).toBeInTheDocument(),
    );
  });

  it("revoke failure shows visible error and keeps active credential", async () => {
    const user = userEvent.setup();
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    listAgentCredentials.mockResolvedValue([sampleCredential()]);
    revokeAgentCredential.mockRejectedValue(
      new ApiError(404, {
        detail: "Agent credential not found",
        code: "AGENT_CREDENTIAL_NOT_FOUND",
      }),
    );

    renderSection();
    await screen.findByText("laptop CLI");
    await user.click(screen.getByRole("button", { name: /^revoke$/i }));

    await waitFor(() =>
      expect(screen.getByText(/that credential was not found/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /^revoke$/i })).toBeInTheDocument();
  });

  it("revoked credential shows status and hides revoke", async () => {
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    listAgentCredentials.mockResolvedValue([
      sampleCredential({
        revoked_at: "2026-02-01T00:00:00.000Z",
      }),
    ]);

    renderSection();
    expect(await screen.findByText("laptop CLI")).toBeInTheDocument();
    expect(document.querySelector(".agent-credential-status")?.textContent).toMatch(/Revoked/);
    expect(document.querySelector(".agent-credential-row.revoked")).not.toBeNull();
    expect(screen.queryByRole("button", { name: /^revoke$/i })).not.toBeInTheDocument();
  });

  it("list and revoke stay visible when allow is false", async () => {
    listAgentCredentials.mockResolvedValue([sampleCredential()]);
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: false }));
    renderSection();

    expect(await screen.findByText("laptop CLI")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^revoke$/i })).toBeInTheDocument();
    expect(screen.getByText(/existing credentials can still be listed and revoked/i)).toBeInTheDocument();
  });

  it("create UI is hidden when allow is false", async () => {
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: false }));
    listAgentCredentials.mockResolvedValue([]);
    renderSection();

    await screen.findByRole("checkbox", { name: /allow agent and cli access/i });
    expect(screen.queryByLabelText(/new credential label/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create credential/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/will not be shown again/i)).not.toBeInTheDocument();
    expect(createAgentCredential).not.toHaveBeenCalled();
  });

  it("revoke with allow=false does not call updateSettings or enable access", async () => {
    const user = userEvent.setup();
    listAgentCredentials.mockResolvedValue([sampleCredential()]);
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: false }));
    revokeAgentCredential.mockResolvedValue(
      sampleCredential({ revoked_at: "2026-02-01T00:00:00.000Z" }),
    );

    renderSection();
    await screen.findByText("laptop CLI");
    await user.click(screen.getByRole("button", { name: /^revoke$/i }));

    await waitFor(() => expect(revokeAgentCredential).toHaveBeenCalledWith("cred-1"));
    expect(updateSettings).not.toHaveBeenCalled();
    expect(createAgentCredential).not.toHaveBeenCalled();
    const box = screen.getByRole("checkbox", { name: /allow agent and cli access/i });
    expect(box).not.toBeChecked();
  });

  it("turning allow off clears a pending one-time secret and keeps list/revoke", async () => {
    const user = userEvent.setup();
    listAgentCredentials.mockResolvedValue([sampleCredential()]);
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    updateSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: false }));
    createAgentCredential.mockResolvedValue({
      ...sampleCredential({ id: "cred-new", label: "ci bot" }),
      secret: "tp_agent_test_secret_once",
    } satisfies AgentCredentialCreated);

    renderSection();
    await screen.findByRole("checkbox", { name: /allow agent and cli access/i });

    await user.type(screen.getByLabelText(/new credential label/i), "ci bot");
    await user.click(screen.getByRole("button", { name: /create credential/i }));
    expect(await screen.findByText("tp_agent_test_secret_once")).toBeInTheDocument();

    const box = screen.getByRole("checkbox", { name: /allow agent and cli access/i });
    const listCallsBeforeOff = listAgentCredentials.mock.calls.length;
    await user.click(box);
    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({ allow_agent_cli_access: false }),
    );
    await waitFor(() => expect(box).not.toBeChecked());

    expect(screen.queryByText("tp_agent_test_secret_once")).not.toBeInTheDocument();
    expect(screen.queryByText(/will not be shown again/i)).not.toBeInTheDocument();
    expect(
      screen.getByText(/one-time secret was cleared from this screen/i),
    ).toBeInTheDocument();
    expect(screen.getByText("laptop CLI")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^revoke$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create credential/i })).not.toBeInTheDocument();
    await waitFor(() =>
      expect(listAgentCredentials.mock.calls.length).toBeGreaterThan(listCallsBeforeOff),
    );
  });

  it("delayed create success after allow-off does not show secret and refreshes list", async () => {
    const user = userEvent.setup();
    let resolveCreate: (value: AgentCredentialCreated) => void = () => {};
    const pendingCreate = new Promise<AgentCredentialCreated>((resolve) => {
      resolveCreate = resolve;
    });
    listAgentCredentials.mockResolvedValue([sampleCredential()]);
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    updateSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: false }));
    createAgentCredential.mockReturnValue(pendingCreate);

    renderSection();
    await screen.findByRole("checkbox", { name: /allow agent and cli access/i });

    await user.type(screen.getByLabelText(/new credential label/i), "late bot");
    await user.click(screen.getByRole("button", { name: /create credential/i }));
    await waitFor(() => expect(createAgentCredential).toHaveBeenCalledWith({ label: "late bot" }));
    expect(screen.queryByText("tp_agent_late_secret")).not.toBeInTheDocument();

    const box = screen.getByRole("checkbox", { name: /allow agent and cli access/i });
    const listCallsBeforeOff = listAgentCredentials.mock.calls.length;
    await user.click(box);
    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({ allow_agent_cli_access: false }),
    );
    await waitFor(() => expect(box).not.toBeChecked());
    await waitFor(() =>
      expect(listAgentCredentials.mock.calls.length).toBeGreaterThan(listCallsBeforeOff),
    );

    const listCallsAfterOff = listAgentCredentials.mock.calls.length;
    listAgentCredentials.mockResolvedValue([
      sampleCredential(),
      sampleCredential({ id: "cred-late", label: "late bot" }),
    ]);
    resolveCreate({
      ...sampleCredential({ id: "cred-late", label: "late bot" }),
      secret: "tp_agent_late_secret",
    });

    await waitFor(() =>
      expect(listAgentCredentials.mock.calls.length).toBeGreaterThan(listCallsAfterOff),
    );
    expect(screen.queryByText("tp_agent_late_secret")).not.toBeInTheDocument();
    expect(screen.queryByText(/will not be shown again/i)).not.toBeInTheDocument();
    expect(await screen.findByText("late bot")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^revoke$/i }).length).toBeGreaterThanOrEqual(1);
    expect(box).not.toBeChecked();
  });

  it("allow off then on before delayed create success still suppresses in-flight secret", async () => {
    const user = userEvent.setup();
    let resolveCreate: (value: AgentCredentialCreated) => void = () => {};
    const pendingCreate = new Promise<AgentCredentialCreated>((resolve) => {
      resolveCreate = resolve;
    });
    listAgentCredentials.mockResolvedValue([sampleCredential()]);
    fetchSettings.mockResolvedValue(baseSettings({ allow_agent_cli_access: true }));
    updateSettings
      .mockResolvedValueOnce(baseSettings({ allow_agent_cli_access: false }))
      .mockResolvedValueOnce(baseSettings({ allow_agent_cli_access: true }));
    createAgentCredential.mockReturnValue(pendingCreate);

    renderSection();
    await screen.findByRole("checkbox", { name: /allow agent and cli access/i });

    await user.type(screen.getByLabelText(/new credential label/i), "race bot");
    await user.click(screen.getByRole("button", { name: /create credential/i }));
    await waitFor(() => expect(createAgentCredential).toHaveBeenCalledWith({ label: "race bot" }));

    const box = screen.getByRole("checkbox", { name: /allow agent and cli access/i });
    await user.click(box);
    await waitFor(() => expect(box).not.toBeChecked());

    await user.click(box);
    await waitFor(() => expect(box).toBeChecked());
    expect(screen.getByLabelText(/new credential label/i)).toBeInTheDocument();

    listAgentCredentials.mockResolvedValue([
      sampleCredential(),
      sampleCredential({ id: "cred-race", label: "race bot" }),
    ]);
    resolveCreate({
      ...sampleCredential({ id: "cred-race", label: "race bot" }),
      secret: "tp_agent_race_secret",
    });

    await waitFor(() => expect(screen.getByText("race bot")).toBeInTheDocument());
    expect(screen.queryByText("tp_agent_race_secret")).not.toBeInTheDocument();
    expect(screen.queryByText(/will not be shown again/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/one-time secret was cleared from this screen/i)).not.toBeInTheDocument();
  });
});
