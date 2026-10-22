import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  describeApiError,
  fetchSettings,
  postRecoverHeld,
  postRecoverHeldReview,
  type HeldDispositionOut,
  type RecoverHeldReviewOut,
} from "../api";
import { HELD_MISSES_QUERY_KEY, invalidateAfterHeldMutation } from "../heldMissesQuery";
import {
  buildCatchUpWireFields,
  buildRecoverAuthorizeIntentFields,
  buildSuccessorWireFields,
  c2LimitationCopy,
  editorsFromReviewCatchUp,
  effectiveCatchUpFieldsAfterReview,
  isRecoverAuthorizeEnabled,
  recoverZoneLabels,
  shouldApplyReviewResponse,
  validateCatchUpEditors,
  type RecoverCatchUpBaseline,
  type RecoverCatchUpEditors,
  type RecoverCatchUpWireFields,
  type RecoverSuccessorMode,
  type RecoverSuccessorWireFields,
} from "../recoverHeldUi";
import { formatInstantInZone } from "../taskDetailDraft";
import { emitToast } from "./ToastHost";

interface HeldRecoverPaneProps {
  taskId: string;
  held: HeldDispositionOut;
  mutationPending: boolean;
  onClose: () => void;
  /** Lift success off the held row — parent keeps CTA after held unmounts. */
  onRecovered: (catchUpTaskId: string) => void;
}

function formatRuleInstant(iso: string | null | undefined, ruleZone: string): string {
  return formatInstantInZone(iso ?? null, ruleZone);
}

export function HeldRecoverPane({
  taskId,
  held,
  mutationPending,
  onClose,
  onRecovered,
}: HeldRecoverPaneProps) {
  const queryClient = useQueryClient();

  /** Edit generation — bumps on relevant edits; late review responses must match. */
  const generationRef = useRef(0);
  const [generation, setGeneration] = useState(0);
  const [appliedGeneration, setAppliedGeneration] = useState(-1);
  const [stale, setStale] = useState(true);
  const [review, setReview] = useState<RecoverHeldReviewOut | null>(null);
  const [editors, setEditors] = useState<RecoverCatchUpEditors>({
    dueLocal: "",
    startNoEarlierLocal: "",
    startNoLaterLocal: "",
    deadlineLocal: "",
    remainingMinutes: "",
  });
  const [baseline, setBaseline] = useState<RecoverCatchUpBaseline | null>(null);
  const [remainingTouched, setRemainingTouched] = useState(false);
  const [successor, setSuccessor] = useState<RecoverSuccessorMode>("none");
  const [stepCount, setStepCount] = useState("1");
  /** Exact catch-up + successor wire from the last applied review (authorize + next refresh). */
  const [boundCatchUpFields, setBoundCatchUpFields] = useState<RecoverCatchUpWireFields>({});
  const [boundSuccessorFields, setBoundSuccessorFields] = useState<RecoverSuccessorWireFields>({});
  const [paneError, setPaneError] = useState<string | null>(null);
  const [reviewPending, setReviewPending] = useState(false);
  const [authorizePending, setAuthorizePending] = useState(false);
  const authorizeFlightRef = useRef(false);
  const formRef = useRef({
    successor,
    stepCount,
    editors,
    baseline,
    remainingTouched,
    priorCatchUpFields: boundCatchUpFields,
  });
  formRef.current = {
    successor,
    stepCount,
    editors,
    baseline,
    remainingTouched,
    priorCatchUpFields: boundCatchUpFields,
  };

  const bumpStale = useCallback(() => {
    generationRef.current += 1;
    setGeneration(generationRef.current);
    setStale(true);
  }, []);

  const runReview = useCallback(
    async (requestGeneration: number) => {
      setReviewPending(true);
      setPaneError(null);
      try {
        const settings = await queryClient.fetchQuery({
          queryKey: ["settings"],
          queryFn: fetchSettings,
        });
        const intent = formRef.current;
        if (intent.successor === "abort") {
          onClose();
          return;
        }
        const wire = buildCatchUpWireFields(intent);
        if (!wire.ok) {
          if (!shouldApplyReviewResponse(requestGeneration, generationRef.current)) return;
          setPaneError(wire.error);
          setStale(true);
          return;
        }
        const successorFields = buildSuccessorWireFields(intent);
        const result = await postRecoverHeldReview(taskId, {
          disposition_id: held.id,
          expected_revision: settings.scheduling_revision,
          ...successorFields,
          ...wire.fields,
        });
        if (!shouldApplyReviewResponse(requestGeneration, generationRef.current)) {
          return;
        }
        setReview(result);
        const mapped = editorsFromReviewCatchUp(result.catch_up);
        setEditors(mapped.editors);
        setBaseline(mapped.baseline);
        setRemainingTouched(false);
        // Effective reviewed intent (raw ISO) — next refresh re-sends; omit must not clear.
        const effective = effectiveCatchUpFieldsAfterReview(wire.fields, result.catch_up);
        setBoundCatchUpFields(effective);
        setBoundSuccessorFields(successorFields);
        setAppliedGeneration(requestGeneration);
        setStale(false);
        setPaneError(null);
      } catch (err) {
        if (!shouldApplyReviewResponse(requestGeneration, generationRef.current)) {
          return;
        }
        const message = describeApiError(err);
        setPaneError(message);
        setStale(true);
        emitToast(`Recover review failed — ${message}`);
        if (err instanceof ApiError && err.status === 409) {
          void queryClient.invalidateQueries({ queryKey: ["settings"] });
          void queryClient.invalidateQueries({ queryKey: HELD_MISSES_QUERY_KEY });
        }
      } finally {
        setReviewPending(false);
      }
    },
    [held.id, onClose, queryClient, taskId],
  );

  // Initial true-read-only review on open (server issues authorize_instant + binding).
  useEffect(() => {
    void runReview(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per mount / held id
  }, [held.id, taskId]);

  const onEditorChange = (patch: Partial<RecoverCatchUpEditors>) => {
    setEditors((prev) => ({ ...prev, ...patch }));
    bumpStale();
  };

  const onRemainingChange = (value: string) => {
    setEditors((prev) => ({ ...prev, remainingMinutes: value }));
    setRemainingTouched(true);
    bumpStale();
  };

  const onSuccessorChange = (mode: RecoverSuccessorMode) => {
    if (mode === "abort") {
      onClose();
      return;
    }
    setSuccessor(mode);
    bumpStale();
  };

  const refreshReview = () => {
    // Explicit refresh always requests a new server instant + binding.
    if (!stale) {
      bumpStale();
    }
    const requestGen = generationRef.current;
    void runReview(requestGen);
  };

  const authorizeEnabled = isRecoverAuthorizeEnabled({
    stale,
    reviewOkForAuthorize: review?.review_ok_for_authorize ?? false,
    reviewBinding: review?.review_binding,
    appliedGeneration,
    currentGeneration: generation,
    mutationPending: mutationPending || reviewPending || authorizePending,
  });

  const authorize = async () => {
    if (!authorizeEnabled || !review || authorizeFlightRef.current) return;
    authorizeFlightRef.current = true;
    setAuthorizePending(true);
    setPaneError(null);
    try {
      const settings = await queryClient.fetchQuery({
        queryKey: ["settings"],
        queryFn: fetchSettings,
      });
      const intent = formRef.current;
      const editorError = validateCatchUpEditors(intent.editors);
      if (editorError) {
        setPaneError(editorError);
        setStale(true);
        return;
      }
      // Recover authorize: echo bound review intent + binding — never rebuild omit-vs-null
      // from remapped editors (would drop catch_up_remaining_minutes after refresh).
      const intentFields = buildRecoverAuthorizeIntentFields({
        boundCatchUpFields,
        boundSuccessorFields,
      });
      const result = await postRecoverHeld(taskId, {
        disposition_id: held.id,
        expected_revision: settings.scheduling_revision,
        review_binding: review.review_binding,
        authorize_instant: review.authorize_instant,
        ...intentFields,
      });
      emitToast("Recovered held occurrence — catch-up task created");
      onRecovered(result.catch_up_task_id);
      invalidateAfterHeldMutation(queryClient);
      void queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      void queryClient.invalidateQueries({ queryKey: ["task", result.catch_up_task_id] });
    } catch (err) {
      const message = describeApiError(err);
      setPaneError(message);
      emitToast(`Recover failed — ${message}`);
      // 409: no auto-retry; retain catch-up edits; mark stale until re-review.
      setStale(true);
      if (err instanceof ApiError && err.status === 409) {
        void queryClient.invalidateQueries({ queryKey: ["settings"] });
        void queryClient.invalidateQueries({ queryKey: HELD_MISSES_QUERY_KEY });
      }
    } finally {
      authorizeFlightRef.current = false;
      setAuthorizePending(false);
    }
  };

  const zones = recoverZoneLabels(review?.cadence.timezone);
  const ruleZone = review?.cadence.timezone ?? "UTC";
  const oneOff = review?.eligibility.one_off_use_release === true;
  const showFixedPast =
    review?.next_normal.accept_past_required === true ||
    review?.successor_choice.status === "FIXED_PAST_REQUIRES_CHOICE";

  return (
    <div className="held-recover-pane" role="region" aria-label="Recover held miss">
      <p className="held-recover-title">
        <strong>Recover</strong>
        <span className="muted small"> — review before authorize</span>
      </p>

      {reviewPending && !review && (
        <p className="muted small" role="status">
          Loading recovery review…
        </p>
      )}

      {paneError && (
        <p className="form-error" role="alert">
          {paneError}
        </p>
      )}

      {oneOff && (
        <p className="form-error" role="alert">
          Recovery requires a recurring series. Use <strong>Release</strong> for this one-off held
          miss.
        </p>
      )}

      {review && !oneOff && (
        <>
          <div className="held-recover-block muted small">
            <p>
              <strong>Cadence</strong> — {review.cadence.is_fixed ? "fixed" : "completion-anchored"}
              ; <span className="held-recover-zone-rule">{zones.ruleZoneLabel}</span>
              {review.cadence.rrule_summary ? `; ${review.cadence.rrule_summary}` : ""}
            </p>
            <p>
              <strong>Review time</strong>: {formatRuleInstant(review.authorize_instant, ruleZone)}
            </p>
          </div>

          <div className="held-recover-block muted small">
            <p>
              <strong>Next regular occurrence</strong> ({zones.ruleZoneLabel}): due{" "}
              {formatRuleInstant(review.next_normal.due_at, ruleZone)}; earliest{" "}
              {formatRuleInstant(review.next_normal.start_no_earlier_at, ruleZone)}; latest{" "}
              {formatRuleInstant(review.next_normal.start_no_later_at, ruleZone)}; deadline{" "}
              {formatRuleInstant(review.next_normal.deadline_at, ruleZone)}
              {review.next_normal.landing_is_past ? " · landing is past" : ""}
            </p>
            <p>
              <strong>Next-occurrence effort</strong> — worked{" "}
              {review.next_normal_effort.worked_minutes}
              min; remaining {review.next_normal_effort.remaining_minutes}min (full restart)
            </p>
          </div>

          <div className="held-recover-block muted small">
            <p>
              <strong>Historical work</strong> (retained on series ledger; not copied to catch-up) —
              worked {review.historical_work.worked_minutes}min; remaining{" "}
              {review.historical_work.remaining_minutes ?? "—"}min; estimate{" "}
              {review.historical_work.estimated_duration_minutes}min;{" "}
              {review.historical_work.progress_entry_count} progress entries
            </p>
          </div>

          {review.c2.blocks_prevent_next_normal && (
            <p className="form-error" role="alert">
              {c2LimitationCopy(review.c2.code, review.c2.detail)}
            </p>
          )}

          {(review.successor_choice.status !== "ok" || showFixedPast) && (
            <div className="held-recover-block">
              <p className="muted small">
                <strong>Successor</strong> — {review.successor_choice.status}
                {showFixedPast
                  ? ". Choose accept past, step further, or abort before authorize."
                  : ""}
              </p>
              {showFixedPast && (
                <div className="held-recover-choice" role="group" aria-label="Successor choice">
                  <label className="held-recover-radio">
                    <input
                      type="radio"
                      name={`recover-successor-${held.id}`}
                      checked={successor === "accept_past"}
                      onChange={() => onSuccessorChange("accept_past")}
                      disabled={authorizePending}
                    />
                    Accept past (may need decision again if still past)
                  </label>
                  <label className="held-recover-radio">
                    <input
                      type="radio"
                      name={`recover-successor-${held.id}`}
                      checked={successor === "step"}
                      onChange={() => onSuccessorChange("step")}
                      disabled={authorizePending}
                    />
                    Step further
                    <input
                      type="number"
                      className="field-number held-recover-step"
                      min={1}
                      step={1}
                      value={stepCount}
                      disabled={successor !== "step" || authorizePending}
                      onChange={(e) => {
                        setStepCount(e.target.value);
                        bumpStale();
                      }}
                      aria-label="Step count"
                    />
                  </label>
                  <button
                    type="button"
                    className="btn link small"
                    disabled={authorizePending}
                    onClick={() => onSuccessorChange("abort")}
                  >
                    Abort recover
                  </button>
                </div>
              )}
            </div>
          )}

          <div className="held-recover-block">
            <p className="muted small">
              <strong>Catch-up</strong> — default remaining{" "}
              {review.catch_up.remaining_minutes_default}min
              {!review.catch_up.usable_dates_ok && review.catch_up.reject_code
                ? ` · ${review.catch_up.reject_code}`
                : ""}
            </p>
            <p className="field-hint muted small held-recover-edit-zone">
              {zones.editZoneLabel}
              {zones.zonesDiffer ? ` · targets above use ${zones.ruleZoneLabel}` : ""}
            </p>
            <label className="field">
              <span>Catch-up remaining (minutes)</span>
              <input
                type="number"
                className="field-number"
                min={0}
                step={1}
                value={editors.remainingMinutes}
                disabled={authorizePending}
                onChange={(e) => onRemainingChange(e.target.value)}
              />
            </label>
            <label className="field">
              <span>Catch-up due</span>
              <input
                type="datetime-local"
                className="field-datetime"
                value={editors.dueLocal}
                disabled={authorizePending}
                onChange={(e) => onEditorChange({ dueLocal: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Catch-up start no earlier</span>
              <input
                type="datetime-local"
                className="field-datetime"
                value={editors.startNoEarlierLocal}
                disabled={authorizePending}
                onChange={(e) => onEditorChange({ startNoEarlierLocal: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Catch-up start no later</span>
              <input
                type="datetime-local"
                className="field-datetime"
                value={editors.startNoLaterLocal}
                disabled={authorizePending}
                onChange={(e) => onEditorChange({ startNoLaterLocal: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Catch-up deadline</span>
              <input
                type="datetime-local"
                className="field-datetime"
                value={editors.deadlineLocal}
                disabled={authorizePending}
                onChange={(e) => onEditorChange({ deadlineLocal: e.target.value })}
              />
            </label>
          </div>

          {stale && (
            <p className="field-hint muted small" role="status">
              Review is stale after edits — refresh before Authorize.
            </p>
          )}
        </>
      )}

      <div className="form-actions held-miss-actions">
        <button
          type="button"
          className="btn secondary small"
          disabled={reviewPending || authorizePending || mutationPending}
          onClick={() => refreshReview()}
        >
          {reviewPending ? "Reviewing…" : "Refresh review"}
        </button>
        <button
          type="button"
          className="btn primary small"
          disabled={!authorizeEnabled || oneOff}
          onClick={() => void authorize()}
        >
          {authorizePending ? "Authorizing…" : "Authorize recover"}
        </button>
        <button
          type="button"
          className="btn secondary small"
          disabled={authorizePending}
          onClick={onClose}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
