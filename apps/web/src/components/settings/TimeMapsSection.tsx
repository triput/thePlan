/**
 * Settings — Time Maps (focus windows) CRUD.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createFocusWindow,
  deleteFocusWindow,
  fetchFocusWindows,
  updateFocusWindow,
  type FocusWindow,
  type TimeMapBand,
  type TimeMapBandTier,
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
import { emitToast } from "../ToastHost";
import { TimeMapOverridesSection } from "./TimeMapOverridesSection";

const EMPTY_TIME_MAP_FORM = {
  name: "",
  strictMode: false,
  bands: [defaultGreenBand()],
};

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

export function TimeMapsSection({ enabled }: { enabled: boolean }) {
  const queryClient = useQueryClient();
  const windowsQuery = useQuery({
    queryKey: ["focus-windows"],
    queryFn: fetchFocusWindows,
    enabled,
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState(EMPTY_TIME_MAP_FORM.name);
  const [formStrictMode, setFormStrictMode] = useState(EMPTY_TIME_MAP_FORM.strictMode);
  const [formBands, setFormBands] = useState<BandDraft[]>(() =>
    EMPTY_TIME_MAP_FORM.bands.map((band) => newBandDraft(band)),
  );
  const [showForm, setShowForm] = useState(false);
  const [overridesWindowId, setOverridesWindowId] = useState<string | null>(null);

  const resetForm = () => {
    setEditingId(null);
    setFormName(EMPTY_TIME_MAP_FORM.name);
    setFormStrictMode(EMPTY_TIME_MAP_FORM.strictMode);
    setFormBands(EMPTY_TIME_MAP_FORM.bands.map((band) => newBandDraft(band)));
  };

  const startEdit = (window: FocusWindow) => {
    setEditingId(window.id);
    setFormName(window.name);
    setFormStrictMode(window.strict_mode);
    const sorted = [...window.bands].sort((a, b) => a.sort_order - b.sort_order);
    setFormBands(
      sorted.length > 0
        ? sorted.map((band) => newBandDraft(band))
        : [newBandDraft(defaultGreenBand())],
    );
    setShowForm(true);
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const name = formName.trim();
      if (!name) throw new Error("Name is required");
      if (formBands.length === 0) throw new Error("Add at least one band");

      const bands = formBands.map((draft, index) => {
        const days_of_week = encodeDays(draft.days);
        if (days_of_week === 0) {
          throw new Error(`Band ${index + 1}: select at least one day`);
        }
        if (!isValidBandTimeRange(draft.start_time, draft.end_time)) {
          throw new Error(`Band ${index + 1}: end time must be after start time`);
        }
        return draftToBand(draft, index);
      });

      const body = {
        name,
        strict_mode: formStrictMode,
        bands,
      };
      if (editingId) {
        return updateFocusWindow(editingId, body);
      }
      return createFocusWindow(body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["focus-windows"] });
      emitToast(editingId ? "Time Map updated" : "Time Map created");
      resetForm();
      setShowForm(false);
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't save Time Map"),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteFocusWindow,
    onSuccess: (_void, windowId) => {
      queryClient.invalidateQueries({ queryKey: ["focus-windows"] });
      queryClient.invalidateQueries({ queryKey: ["time-map-overrides", windowId] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      emitToast("Time Map deleted");
      if (editingId) {
        resetForm();
        setShowForm(false);
      }
      setOverridesWindowId((prev) => (prev === windowId ? null : prev));
    },
    onError: () => emitToast("Couldn't delete Time Map"),
  });

  const windows = windowsQuery.data ?? [];

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
    setFormBands((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((band) => band.clientKey !== clientKey);
    });
  };

  return (
    <section className="settings-section">
      <div className="settings-section-header">
        <h3 className="settings-section-title">Time Maps</h3>
        {!showForm && (
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
          >
            Add Time Map
          </button>
        )}
      </div>
      <p className="settings-help muted small">
        Preferred scheduling windows for tasks. Quick-add tokens{" "}
        <code>@morning</code>, <code>@afternoon</code>, and <code>@evening</code> match the
        default seed names when present. Use <strong>Overrides</strong> on a map for temporary
        date ranges (travel, holidays).
      </p>
      {windowsQuery.isLoading && <p className="muted small">Loading Time Maps…</p>}
      {windows.length > 0 && (
        <ul className="time-map-list">
          {windows.map((window) => (
            <li key={window.id} className="time-map-list-item">
              <div className="time-map-row">
                <div className="time-map-info">
                  <div className="time-map-name">{window.name}</div>
                  <div className="muted small">{formatBandsSummary(window.bands ?? [])}</div>
                </div>
                {window.strict_mode && (
                  <span className="time-map-badge hard">Strict</span>
                )}
                <div className="time-map-actions">
                  <button
                    type="button"
                    className={`btn ghost small${overridesWindowId === window.id ? " active" : ""}`}
                    onClick={() =>
                      setOverridesWindowId((prev) => (prev === window.id ? null : window.id))
                    }
                  >
                    Overrides
                  </button>
                  <button
                    type="button"
                    className="btn ghost small"
                    onClick={() => startEdit(window)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="btn ghost small danger-text"
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(window.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
              {overridesWindowId === window.id && (
                <TimeMapOverridesSection windowId={window.id} enabled={enabled} />
              )}
            </li>
          ))}
        </ul>
      )}
      {!windowsQuery.isLoading && windows.length === 0 && !showForm && (
        <p className="muted small">No Time Maps yet.</p>
      )}
      {showForm && (
        <form
          className="time-map-form entity-form"
          onSubmit={(e) => {
            e.preventDefault();
            saveMutation.mutate();
          }}
        >
          <label className="field">
            <span>Name</span>
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="Morning Deep Work"
            />
          </label>
          <label className="time-map-hard-check">
            <input
              type="checkbox"
              checked={formStrictMode}
              onChange={(e) => setFormStrictMode(e.target.checked)}
            />
            Strict — no spill outside painted bands
          </label>
          <fieldset className="field time-map-bands-field">
            <legend>Bands</legend>
            <div className="time-map-band-list">
              {formBands.map((band, bandIndex) => (
                <div key={band.clientKey} className="time-map-band-row">
                  <div className="time-map-band-row-header">
                    <span className="time-map-band-row-label">Band {bandIndex + 1}</span>
                    <button
                      type="button"
                      className="btn ghost small danger-text"
                      disabled={formBands.length <= 1}
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
                  <div className="time-map-days" role="group" aria-label={`Band ${bandIndex + 1} days`}>
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
              disabled={saveMutation.isPending || !formName.trim()}
            >
              {saveMutation.isPending ? "Saving…" : editingId ? "Update" : "Create"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
