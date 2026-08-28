/**
 * Settings — Plans (soft frames) CRUD.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createPlan,
  deletePlan,
  fetchPlans,
  updatePlan,
  type Plan,
} from "../../api";
import { formatDue } from "../../view";
import { emitToast } from "../ToastHost";

function planToDatetimeLocal(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function planFromDatetimeLocal(value: string): string | null {
  if (!value) return null;
  return new Date(value).toISOString();
}

const EMPTY_PLAN_FORM = { name: "", softTarget: "" };

export function PlansSection({ enabled }: { enabled: boolean }) {
  const queryClient = useQueryClient();
  const plansQuery = useQuery({
    queryKey: ["plans"],
    queryFn: fetchPlans,
    enabled,
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState(EMPTY_PLAN_FORM.name);
  const [formSoftTarget, setFormSoftTarget] = useState(EMPTY_PLAN_FORM.softTarget);
  const [showForm, setShowForm] = useState(false);

  const resetForm = () => {
    setEditingId(null);
    setFormName(EMPTY_PLAN_FORM.name);
    setFormSoftTarget(EMPTY_PLAN_FORM.softTarget);
  };

  const startEdit = (plan: Plan) => {
    setEditingId(plan.id);
    setFormName(plan.name);
    setFormSoftTarget(planToDatetimeLocal(plan.soft_target_at));
    setShowForm(true);
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const name = formName.trim();
      if (!name) throw new Error("Name is required");
      const body = {
        name,
        soft_target_at: planFromDatetimeLocal(formSoftTarget),
      };
      if (editingId) {
        return updatePlan(editingId, body);
      }
      return createPlan(body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      emitToast(editingId ? "Plan updated" : "Plan created");
      resetForm();
      setShowForm(false);
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't save Plan"),
  });

  const deleteMutation = useMutation({
    mutationFn: deletePlan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      emitToast("Plan deleted");
      if (editingId) {
        resetForm();
        setShowForm(false);
      }
    },
    onError: () => emitToast("Couldn't delete Plan"),
  });

  const plans = plansQuery.data ?? [];

  return (
    <section className="settings-section">
      <div className="settings-section-header">
        <h3 className="settings-section-title">Plans</h3>
        {!showForm && (
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
          >
            Add Plan
          </button>
        )}
      </div>
      <p className="settings-help muted small">
        Plans are flexible soft frames; the scheduler may slide tasks within them.
      </p>
      {plansQuery.isLoading && <p className="muted small">Loading Plans…</p>}
      {plans.length > 0 && (
        <ul className="time-map-list">
          {plans.map((plan) => (
            <li key={plan.id} className="time-map-row">
              <div className="time-map-info">
                <div className="time-map-name">{plan.name}</div>
                <div className="muted small">
                  {plan.soft_target_at
                    ? `Soft target ${formatDue(plan.soft_target_at)}`
                    : "No soft target"}
                </div>
              </div>
              <div className="time-map-actions">
                <button
                  type="button"
                  className="btn ghost small"
                  onClick={() => startEdit(plan)}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="btn ghost small danger-text"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(plan.id)}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {!plansQuery.isLoading && plans.length === 0 && !showForm && (
        <p className="muted small">No Plans yet.</p>
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
              placeholder="Q3 launch prep"
            />
          </label>
          <label className="field">
            <span>Soft target (optional)</span>
            <input
              type="datetime-local"
              className="field-datetime"
              value={formSoftTarget}
              onChange={(e) => setFormSoftTarget(e.target.value)}
            />
          </label>
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
