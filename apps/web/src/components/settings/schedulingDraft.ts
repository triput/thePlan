/**
 * User-settings draft helpers for Scheduling defaults.
 * Owns PATCH shape for updateSettings — keep in sync with UserSettingsUpdate.
 */
import type { ScheduleStyle, UserSettings, UserSettingsUpdate } from "../../api";

export type SchedulingDraft = {
  timezone: string;
  locale: string;
  inter_block_buffer_minutes: string;
  upcoming_horizon_days: string;
  default_estimated_duration_minutes: string;
  default_min_block_duration_minutes: string;
  default_schedule_style: ScheduleStyle;
  auto_defer_enabled: boolean;
  max_auto_schedule_minutes_per_project_per_day: string;
};

export function settingsToDraft(settings: UserSettings): SchedulingDraft {
  return {
    timezone: settings.timezone,
    locale: settings.locale,
    inter_block_buffer_minutes: String(settings.inter_block_buffer_minutes),
    upcoming_horizon_days: String(settings.upcoming_horizon_days),
    default_estimated_duration_minutes: String(settings.default_estimated_duration_minutes),
    default_min_block_duration_minutes: String(settings.default_min_block_duration_minutes),
    default_schedule_style: settings.default_schedule_style,
    auto_defer_enabled: settings.auto_defer_enabled,
    max_auto_schedule_minutes_per_project_per_day:
      settings.max_auto_schedule_minutes_per_project_per_day == null
        ? ""
        : String(settings.max_auto_schedule_minutes_per_project_per_day),
  };
}

function parsePositiveInt(raw: string): number | null {
  const value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

function parseNonNegativeInt(raw: string): number | null {
  const value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value) || value < 0) return null;
  return value;
}

/** Diff saved settings vs draft into a partial PATCH body (or null if clean). */
export function buildSettingsPatch(
  saved: UserSettings,
  draft: SchedulingDraft,
): UserSettingsUpdate | null {
  const patch: UserSettingsUpdate = {};
  const timezone = draft.timezone.trim();
  const locale = draft.locale.trim();
  if (!timezone) throw new Error("Timezone is required");
  if (!locale) throw new Error("Locale is required");
  if (timezone !== saved.timezone) patch.timezone = timezone;
  if (locale !== saved.locale) patch.locale = locale;

  const bufferMinutes = parseNonNegativeInt(draft.inter_block_buffer_minutes);
  if (bufferMinutes === null) {
    throw new Error("Buffer minutes must be zero or greater");
  }
  if (bufferMinutes !== saved.inter_block_buffer_minutes) {
    patch.inter_block_buffer_minutes = bufferMinutes;
  }

  const horizonDays = parsePositiveInt(draft.upcoming_horizon_days);
  if (horizonDays === null) throw new Error("Upcoming horizon days must be a positive number");
  if (horizonDays !== saved.upcoming_horizon_days) patch.upcoming_horizon_days = horizonDays;

  const defaultDuration = parsePositiveInt(draft.default_estimated_duration_minutes);
  if (defaultDuration === null) {
    throw new Error("Default task duration must be a positive number");
  }
  if (defaultDuration !== saved.default_estimated_duration_minutes) {
    patch.default_estimated_duration_minutes = defaultDuration;
  }

  const minBlockDuration = parsePositiveInt(draft.default_min_block_duration_minutes);
  if (minBlockDuration === null) {
    throw new Error("Default min block length must be a positive number");
  }
  if (minBlockDuration !== saved.default_min_block_duration_minutes) {
    patch.default_min_block_duration_minutes = minBlockDuration;
  }

  if (draft.default_schedule_style !== saved.default_schedule_style) {
    patch.default_schedule_style = draft.default_schedule_style;
  }
  if (draft.auto_defer_enabled !== saved.auto_defer_enabled) {
    patch.auto_defer_enabled = draft.auto_defer_enabled;
  }

  const capRaw = draft.max_auto_schedule_minutes_per_project_per_day.trim();
  if (capRaw === "") {
    if (saved.max_auto_schedule_minutes_per_project_per_day != null) {
      patch.max_auto_schedule_minutes_per_project_per_day = null;
    }
  } else {
    const projectDailyCap = parsePositiveInt(capRaw);
    if (projectDailyCap === null) {
      throw new Error("Max minutes per project per day must be a positive number or empty");
    }
    if (projectDailyCap !== saved.max_auto_schedule_minutes_per_project_per_day) {
      patch.max_auto_schedule_minutes_per_project_per_day = projectDailyCap;
    }
  }

  return Object.keys(patch).length > 0 ? patch : null;
}

export function isSettingsDirty(saved: UserSettings, draft: SchedulingDraft): boolean {
  try {
    return buildSettingsPatch(saved, draft) !== null;
  } catch {
    return true;
  }
}
