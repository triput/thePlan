/**
 * Settings — temporary Time Map overrides (dated band replacements).
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTimeMapOverride,
  deleteTimeMapOverride,
  fetchSettings,
  fetchTimeMapOverrides,
  updateTimeMapOverride,
  type TimeMapBand,
  type TimeMapBandTier,
  type TimeMapOverride,
} from "../../api";
import {
  DAY_BITS,
  decodeDays,
  defaultGreenBand,
  encodeDays,
  formatBandsSummary,
  isValidBandTimeRange,
  TIME_MAP_TIER_LABELS,
} from "../../focusWindows";
import {
  bandCrossesMidnight,
  describeOverrideStatus,
  formatTimeMapOverrideError,
  isOverrideExpired,
} from "../../timeMapOverrides";
import { TimezonePicker } from "../TimezonePicker";
import { emitToast } from "../ToastHost";

type BandDraft = {
  clientKey: string;
  id?: string;
  tier: TimeMapBandTier;
  start_time: string;
  end_time: string;
  days: boolean[];
  sort_order: number;
};

function newBandDraft(band: TimeMapBand = defaultGreenBand()): BandDraft {
  return {
    clientKey: band.id ?? crypto.randomUUID(),
    id: band.id,
    tier: band.tier,
    start_time: band.start_time,
    end_time: band.end_time,
    days: decodeDays(band.days_of_week),
    sort_order: band.sort_order,
  };
}

function draftToBand(draft: BandDraft, sortOrder: number): TimeMapBand {
  const band: TimeMapBand = {
    tier: draft.tier,
    start_time: draft.start_time,
    end_time: draft.end_time,
    days_of_week: encodeDays(draft.days),
    sort_order: sortOrder,
  };
  if (draft.id) band.id = draft.id;
  return band;
}

const EMPTY_OVERRIDE_FORM = {
  localStart: "",
  localEnd: "",
  timezone: "",
  strictMode: false,
  bands: [defaultGreenBand()],
};

export function TimeMapOverridesSection({
  windowId,
  enabled,
}: {
  windowId: string;
  enabled: boolean;
}) {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    enabled,
  });
  const overridesQuery = useQuery({
    queryKey: ["time-map-overrides", windowId],
    queryFn: () => fetchTimeMapOverrides(windowId),
    enabled: enabled && Boolean(windowId),
  });

  const defaultTimezone = settingsQuery.data?.timezone ?? "UTC";

  const [editingId, setEditingId] = useState<string | null>(null);
  const [formStart, setFormStart] = useState(EMPTY_OVERRIDE_FORM.localStart);
  const [formEnd, setFormEnd] = useState(EMPTY_OVERRIDE_FORM.localEnd);
  const [formTimezone, setFormTimezone] = useState("");
  const [formStrictMode, setFormStrictMode] = useState(EMPTY_OVERRIDE_FORM.strictMode);
  const [formBands, setFormBands] = useState<BandDraft[]>(() =>
    EMPTY_OVERRIDE_FORM.bands.map((band) => newBandDraft(band)),
  );
  const [showForm, setShowForm] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const resetForm = () => {
    setEditingId(null);
    setFormStart(EMPTY_OVERRIDE_FORM.localStart);
    setFormEnd(EMPTY_OVERRIDE_FORM.localEnd);
    setFormTimezone(defaultTimezone);
    setFormStrictMode(EMPTY_OVERRIDE_FORM.strictMode);
    setFormBands(EMPTY_OVERRIDE_FORM.bands.map((band) => newBandDraft(band)));
    setFormError(null);
  };

  const startCreate = () => {
    resetForm();
    setFormTimezone(defaultTimezone);
    setShowForm(true);
  };

  const startEdit = (override: TimeMapOverride) => {
    setEditingId(override.id);
    setFormStart(override.local_start_date);
    setFormEnd(override.local_end_date);
    setFormTimezone(override.timezone);
    setFormStrictMode(override.strict_mode);
    const sorted = [...override.bands].sort((a, b) => a.sort_order - b.sort_order);
    setFormBands(sorted.map((band) => newBandDraft(band)));
    setFormError(null);
    setShowForm(true);
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      setFormError(null);
      if (!formStart || !formEnd) throw new Error("Start and end dates are required");
      if (formEnd < formStart) throw new Error("End date must be on or after start date");
      const tz = formTimezone.trim();
      if (!tz) throw new Error("Timezone is required");

      const bands =
        formBands.length === 0
          ? []
          : formBands.map((draft, index) => {
              const days_of_week = encodeDays(draft.days);
              if (days_of_week === 0) {
                throw new Error(`Band ${index + 1}: select at least one day`);
              }
              if (bandCrossesMidnight(draft.start_time, draft.end_time)) {
                throw new Error(
                  `Band ${index + 1} crosses midnight. Split it into two bands that each stay within one local day.`,
                );
              }
              if (!isValidBandTimeRange(draft.start_time, draft.end_time)) {
                throw new Error(`Band ${index + 1}: end time must be after start time`);
              }
              return draftToBand(draft, index);
            });

      const body = {
        local_start_date: formStart,
        local_end_date: formEnd,
        timezone: tz,
        strict_mode: formStrictMode,
        bands,
      };
      if (editingId) {
        return updateTimeMapOverride(windowId, editingId, body);
      }
      return createTimeMapOverride(windowId, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["time-map-overrides", windowId] });
      emitToast(editingId ? "Override updated" : "Override created");
      resetForm();
      setShowForm(false);
    },
    onError: (err: Error) => {
      const message = formatTimeMapOverrideError(err);
      setFormError(message);
      emitToast(message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (overrideId: string) => deleteTimeMapOverride(windowId, overrideId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["time-map-overrides", windowId] });
      emitToast("Override deleted");
      if (editingId) {
        resetForm();
        setShowForm(false);
      }
    },
    onError: (err: Error) => emitToast(formatTimeMapOverrideError(err)),
  });

  const overrides = overridesQuery.data ?? [];

  const updateBand = (clientKey: string, patch: Partial<BandDraft>) => {
    setFormBands((prev) =>
      prev.map((band) => (band.clientKey === clientKey ? { ...band, ...patch } : band)),
    );
  };

  const toggleBandDay = (clientKey: string, index: number, checked: boolean) => {
    setFormBands((prev) =>
      prev.map((band) => {
        if (band.clientKey !== clientKey) return band;
        const days = [...band.days];
        days[index] = checked;
        return { ...band, days };
      }),
    );
  };

  const addBand = () => {
    setFormBands((prev) => [...prev, newBandDraft(defaultGreenBand(prev.length))]);
  };

  const removeBand = (clientKey: string) => {
    setFormBands((prev) => prev.filter((band) => band.clientKey !== clientKey));
  };

  return (
    <div className="time-map-overrides-panel">
      <div className="time-map-overrides-header">
        <span className="time-map-overrides-title">Temporary overrides</span>
        {!showForm && (
          <button type="button" className="link-btn" onClick={startCreate}>
            Add override
          </button>
        )}
      </div>
      <p className="settings-help muted small">
        Replace this map&apos;s bands for specific local dates (travel, holidays). Your weekly
        map stays unchanged. Saving an override does not replan — run{" "}
        <strong>Update schedule</strong> on the calendar when you are ready.
      </p>
      {overridesQuery.isLoading && <p className="muted small">Loading overrides…</p>}
      {overrides.length > 0 && (
        <ul className="time-map-override-list">
          {overrides.map((override) => {
            const expired = isOverrideExpired(override);
            return (
              <li key={override.id} className="time-map-override-row">
                <div className="time-map-override-info">
                  <div className="time-map-override-dates">{describeOverrideStatus(override)}</div>
                  <div className="muted small">{formatBandsSummary(override.bands ?? [])}</div>
                </div>
                {override.strict_mode && (
                  <span className="time-map-badge hard">Strict</span>
                )}
                {expired && <span className="time-map-badge expired">Expired</span>}
                <div className="time-map-actions">
                  <button
                    type="button"
                    className="btn ghost small"
                    onClick={() => startEdit(override)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="btn ghost small danger-text"
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(override.id)}
                  >
                    Delete
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {!overridesQuery.isLoading && overrides.length === 0 && !showForm && (
        <p className="muted small">No temporary overrides for this map.</p>
      )}
      {showForm && (
        <form
          className="time-map-form entity-form time-map-override-form"
          onSubmit={(e) => {
            e.preventDefault();
            saveMutation.mutate();
          }}
        >
          {formError && (
            <p className="form-error" role="alert">
              {formError}
            </p>
          )}
          <div className="time-map-override-date-row">
            <label className="field">
              <span>Start date</span>
              <input
                type="date"
                value={formStart}
                onChange={(e) => setFormStart(e.target.value)}
                required
              />
            </label>
            <label className="field">
              <span>End date</span>
              <input
                type="date"
                value={formEnd}
                onChange={(e) => setFormEnd(e.target.value)}
                required
              />
            </label>
          </div>
          <label className="field">
            <span>Timezone for these dates</span>
            <TimezonePicker
              value={formTimezone || defaultTimezone}
              onChange={setFormTimezone}
            />
          </label>
          <label className="time-map-hard-check">
            <input
              type="checkbox"
              checked={formStrictMode}
              onChange={(e) => setFormStrictMode(e.target.checked)}
            />
            Strict — no spill outside painted bands (empty bands + strict = unavailable all day)
          </label>
          <fieldset className="field time-map-bands-field">
            <legend>Replacement bands</legend>
            <div className="time-map-band-list">
              {formBands.length === 0 && (
                <p className="muted small">No bands — with Strict, the map is unavailable all day.</p>
              )}
              {formBands.map((band, bandIndex) => (
                <div key={band.clientKey} className="time-map-band-row">
                  <div className="time-map-band-row-header">
                    <span className="time-map-band-row-label">Band {bandIndex + 1}</span>
                    <button
                      type="button"
                      className="btn ghost small danger-text"
                      onClick={() => removeBand(band.clientKey)}
                    >
                      Remove
                    </button>
                  </div>
                  <div className="time-map-band-row-fields">
                    <label className="field">
                      <span>Tier</span>
                      <select
                        className="field-select"
                        value={band.tier}
                        onChange={(e) =>
                          updateBand(band.clientKey, {
                            tier: e.target.value as TimeMapBandTier,
                          })
                        }
                      >
                        {(Object.keys(TIME_MAP_TIER_LABELS) as TimeMapBandTier[]).map((tier) => (
                          <option key={tier} value={tier}>
                            {TIME_MAP_TIER_LABELS[tier]}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>Start</span>
                      <input
                        type="time"
                        value={band.start_time}
                        onChange={(e) =>
                          updateBand(band.clientKey, { start_time: e.target.value })
                        }
                      />
                    </label>
                    <label className="field">
                      <span>End</span>
                      <input
                        type="time"
                        value={band.end_time}
                        onChange={(e) => updateBand(band.clientKey, { end_time: e.target.value })}
                      />
                    </label>
                  </div>
                  <div
                    className="time-map-days"
                    role="group"
                    aria-label={`Band ${bandIndex + 1} days`}
                  >
                    {DAY_BITS.map(({ label }, index) => (
                      <label key={label} className="time-map-day-check">
                        <input
                          type="checkbox"
                          checked={band.days[index]}
                          onChange={(e) => toggleBandDay(band.clientKey, index, e.target.checked)}
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <button type="button" className="link-btn time-map-add-band" onClick={addBand}>
              Add band
            </button>
          </fieldset>
          <div className="form-actions">
            <button
              type="button"
              className="btn secondary small"
              onClick={() => {
                resetForm();
                setShowForm(false);
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn primary small"
              disabled={saveMutation.isPending || !formStart || !formEnd}
            >
              {saveMutation.isPending ? "Saving…" : editingId ? "Update override" : "Create override"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
