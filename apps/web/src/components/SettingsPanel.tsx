/**
 * Settings modal shell — composes domain sections; owns user-settings query/mutation.
 * Cut #5 / DEF-011: section bodies live under ./settings/.
 */
import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSettings, updateSettings } from "../api";
import { useAuth } from "../auth";
import {
  isValidHex,
  loadOverrides,
  loadTheme,
  normalizeHex,
  resetOverrides,
  setOverride,
  setTheme,
  type ThemeId,
  type ThemeOverrideKey,
  type ThemeOverrides,
} from "../theme";
import { HouseholdPanel } from "./HouseholdPanel";
import { Modal } from "./Modal";
import { emitToast } from "./ToastHost";
import { AccountSection } from "./settings/AccountSection";
import { AssistStatusSection } from "./settings/AssistStatusSection";
import { CalendarAccountsSections } from "./settings/CalendarAccountsSections";
import { CalendarDisplaySection } from "./settings/CalendarDisplaySection";
import { PlansSection } from "./settings/PlansSection";
import { SchedulingDefaultsSection } from "./settings/SchedulingDefaultsSection";
import {
  buildSettingsPatch,
  isSettingsDirty,
  settingsToDraft,
  type SchedulingDraft,
} from "./settings/schedulingDraft";
import {
  buildDraftHex,
  CustomColorsSection,
  ThemePresetSection,
} from "./settings/ThemeSections";
import { TimeMapsSection } from "./settings/TimeMapsSection";

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [themeId, setThemeId] = useState<ThemeId>(() => loadTheme());
  const [overrides, setOverrides] = useState<ThemeOverrides>(() => loadOverrides());
  const [draftHex, setDraftHex] = useState<Record<ThemeOverrideKey, string>>(() =>
    buildDraftHex(loadOverrides()),
  );
  const [schedulingDraft, setSchedulingDraft] = useState<SchedulingDraft | null>(null);

  const settingsQuery = useQuery({
    queryKey: ["user-settings"],
    queryFn: fetchSettings,
    enabled: open,
  });

  useEffect(() => {
    if (settingsQuery.data) {
      setSchedulingDraft(settingsToDraft(settingsQuery.data));
    }
  }, [settingsQuery.data]);

  const saveSettingsMutation = useMutation({
    mutationFn: async () => {
      if (!settingsQuery.data || !schedulingDraft) return null;
      const patch = buildSettingsPatch(settingsQuery.data, schedulingDraft);
      if (!patch) return null;
      return updateSettings(patch);
    },
    onSuccess: (result) => {
      if (result) {
        queryClient.setQueryData(["user-settings"], result);
        setSchedulingDraft(settingsToDraft(result));
        emitToast("Scheduling defaults saved");
      }
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't save scheduling defaults"),
  });

  const handleDraftChange = useCallback((updater: (prev: SchedulingDraft) => SchedulingDraft) => {
    setSchedulingDraft((prev) => (prev ? updater(prev) : prev));
  }, []);

  const savedSettings = settingsQuery.data;
  const schedulingDirty =
    savedSettings && schedulingDraft
      ? isSettingsDirty(savedSettings, schedulingDraft)
      : false;

  useEffect(() => {
    if (!open) return;
    const currentTheme = loadTheme();
    const currentOverrides = loadOverrides();
    setThemeId(currentTheme);
    setOverrides(currentOverrides);
    setDraftHex(buildDraftHex(currentOverrides));
  }, [open]);

  const handleThemeChange = (id: ThemeId) => {
    setThemeId(id);
    setTheme(id);
    setDraftHex(buildDraftHex(overrides));
  };

  const handleOverrideInput = (key: ThemeOverrideKey, raw: string) => {
    setDraftHex((prev) => ({ ...prev, [key]: raw }));
    if (isValidHex(raw)) {
      const normalized = normalizeHex(raw);
      const next = setOverride(key, normalized);
      setOverrides(next);
    } else if (raw.trim() === "") {
      const next = setOverride(key, undefined);
      setOverrides(next);
      setDraftHex(buildDraftHex(next));
    }
  };

  const handleResetOverrides = () => {
    const next = resetOverrides();
    setOverrides(next);
    setDraftHex(buildDraftHex(next));
  };

  return (
    <Modal open={open} title="Settings" onClose={onClose} className="settings-modal">
      <AccountSection enabled={open} />

      <ThemePresetSection themeId={themeId} onThemeChange={handleThemeChange} />

      <SchedulingDefaultsSection
        draft={schedulingDraft}
        isLoading={settingsQuery.isLoading}
        isError={settingsQuery.isError}
        dirty={schedulingDirty}
        saving={saveSettingsMutation.isPending}
        onDraftChange={handleDraftChange}
        onSave={() => saveSettingsMutation.mutate()}
      />

      <CustomColorsSection
        themeId={themeId}
        overrides={overrides}
        draftHex={draftHex}
        onOverrideInput={handleOverrideInput}
        onResetOverrides={handleResetOverrides}
      />

      <CalendarDisplaySection open={open} />

      <TimeMapsSection enabled={open} />

      <PlansSection enabled={open} />

      <CalendarAccountsSections enabled={open} />

      <AssistStatusSection enabled={open} />

      {user.is_admin && <HouseholdPanel currentUserId={user.id} />}
    </Modal>
  );
}
