/**
 * T2-REC-UI helpers — Option A zone honesty, edit-generation stale gates,
 * and omit-vs-null catch-up wire (no client RRULE).
 */

import {
  browserTimeZoneLabel,
  fromDatetimeLocal,
  toDatetimeLocal,
} from "./taskDetailDraft.ts";

export const RECOVER_REVIEW_CONTRACT_VERSION = "t2-rec-ui-v1";

export type RecoverSuccessorMode = "none" | "accept_past" | "step" | "abort";

/** Catch-up date fields that participate in omit-vs-null wire. */
export type CatchUpDateKey =
  | "catch_up_due_at"
  | "catch_up_start_no_earlier_at"
  | "catch_up_start_no_later_at"
  | "catch_up_deadline_at";

export interface RecoverCatchUpEditors {
  dueLocal: string;
  startNoEarlierLocal: string;
  startNoLaterLocal: string;
  deadlineLocal: string;
  remainingMinutes: string;
}

/** Baseline walls from the last applied review (ISO → datetime-local for compare). */
export interface RecoverCatchUpBaseline {
  dueLocal: string;
  startNoEarlierLocal: string;
  startNoLaterLocal: string;
  deadlineLocal: string;
  /** Server catch_up.remaining_minutes after overrides at review time. */
  remainingMinutes: number;
  remainingDefault: number;
}

export interface RecoverFormIntent {
  successor: RecoverSuccessorMode;
  stepCount: string;
  editors: RecoverCatchUpEditors;
  baseline: RecoverCatchUpBaseline | null;
  /** True once the operator changed remaining away from the reviewed value. */
  remainingTouched: boolean;
}

export interface RecoverZoneLabels {
  editZone: string;
  ruleZone: string;
  editZoneLabel: string;
  ruleZoneLabel: string;
  zonesDiffer: boolean;
}

/** Conspicuous Option A labels — edit = browser local; rule = review cadence.timezone. */
export function recoverZoneLabels(ruleTimezone: string | null | undefined): RecoverZoneLabels {
  const editZone = browserTimeZoneLabel();
  const ruleZone = (ruleTimezone ?? "").trim() || "—";
  return {
    editZone,
    ruleZone,
    editZoneLabel: `Editing in ${editZone} (browser local)`,
    ruleZoneLabel: `Rule zone ${ruleZone}`,
    zonesDiffer: Boolean(ruleTimezone) && ruleTimezone !== editZone,
  };
}

/**
 * Parse a datetime-local wall in browser local zone.
 * Rejects empty→null caller decision; rejects NaN; rejects gap snaps via round-trip
 * (input wall ≠ re-formatted local wall after Date parse).
 */
export function parseBrowserLocalWall(
  value: string,
): { ok: true; iso: string } | { ok: false; reason: string } {
  const trimmed = value.trim();
  if (!trimmed) {
    return { ok: false, reason: "empty" };
  }
  const d = new Date(trimmed);
  if (Number.isNaN(d.getTime())) {
    return { ok: false, reason: "invalid" };
  }
  // Gap / silent snap: browser Date moved the wall; refuse before wire.
  const roundTrip = toDatetimeLocal(d.toISOString());
  if (roundTrip !== trimmed) {
    return { ok: false, reason: "ambiguous_or_nonexistent" };
  }
  const iso = fromDatetimeLocal(trimmed);
  if (!iso) {
    return { ok: false, reason: "invalid" };
  }
  return { ok: true, iso };
}

export function validateCatchUpEditors(editors: RecoverCatchUpEditors): string | null {
  const fields: Array<[string, string]> = [
    [editors.dueLocal, "Catch-up due"],
    [editors.startNoEarlierLocal, "Catch-up start no earlier"],
    [editors.startNoLaterLocal, "Catch-up start no later"],
    [editors.deadlineLocal, "Catch-up deadline"],
  ];
  for (const [value, label] of fields) {
    if (!value.trim()) continue;
    const parsed = parseBrowserLocalWall(value);
    if (!parsed.ok) {
      if (parsed.reason === "ambiguous_or_nonexistent") {
        return `${label} is not a valid wall clock in browser local (gap/fold) — pick an unambiguous time`;
      }
      return `${label} is invalid`;
    }
  }
  if (editors.remainingMinutes.trim()) {
    const n = Number.parseInt(editors.remainingMinutes, 10);
    if (!Number.isFinite(n) || n < 0 || String(n) !== editors.remainingMinutes.trim()) {
      return "Catch-up remaining must be a whole number of minutes (0 allowed)";
    }
  }
  return null;
}

function editorLocalForKey(
  editors: RecoverCatchUpEditors,
  key: CatchUpDateKey,
): string {
  switch (key) {
    case "catch_up_due_at":
      return editors.dueLocal;
    case "catch_up_start_no_earlier_at":
      return editors.startNoEarlierLocal;
    case "catch_up_start_no_later_at":
      return editors.startNoLaterLocal;
    case "catch_up_deadline_at":
      return editors.deadlineLocal;
  }
}

function baselineLocalForKey(
  baseline: RecoverCatchUpBaseline,
  key: CatchUpDateKey,
): string {
  switch (key) {
    case "catch_up_due_at":
      return baseline.dueLocal;
    case "catch_up_start_no_earlier_at":
      return baseline.startNoEarlierLocal;
    case "catch_up_start_no_later_at":
      return baseline.startNoLaterLocal;
    case "catch_up_deadline_at":
      return baseline.deadlineLocal;
  }
}

/**
 * Build catch-up date/remaining fields for review or authorize.
 * Unchanged vs baseline → omit. Cleared → null. Edited → UTC ISO of browser wall.
 */
export function buildCatchUpWireFields(
  intent: RecoverFormIntent,
): { ok: true; fields: Record<string, string | number | null> } | { ok: false; error: string } {
  const validation = validateCatchUpEditors(intent.editors);
  if (validation) return { ok: false, error: validation };

  const fields: Record<string, string | number | null> = {};
  const keys: CatchUpDateKey[] = [
    "catch_up_due_at",
    "catch_up_start_no_earlier_at",
    "catch_up_start_no_later_at",
    "catch_up_deadline_at",
  ];

  for (const key of keys) {
    const local = editorLocalForKey(intent.editors, key).trim();
    const baseLocal = intent.baseline ? baselineLocalForKey(intent.baseline, key) : "";
    if (local === baseLocal) {
      // Unchanged (incl. both empty) → omit so seconds/ms survive server-side.
      continue;
    }
    if (!local) {
      // Explicit clear.
      fields[key] = null;
      continue;
    }
    const parsed = parseBrowserLocalWall(local);
    if (!parsed.ok) {
      return { ok: false, error: `Invalid ${key}` };
    }
    fields[key] = parsed.iso;
  }

  if (intent.remainingTouched) {
    const raw = intent.editors.remainingMinutes.trim();
    if (raw === "") {
      // Cleared override → omit (server default). Distinct from sending 0.
      // If they touched then cleared, treat as omit.
    } else {
      fields.catch_up_remaining_minutes = Number.parseInt(raw, 10);
    }
  }

  return { ok: true, fields };
}

export function buildSuccessorWireFields(intent: RecoverFormIntent): {
  accept_past_ack?: boolean;
  step_count?: number;
  abort?: boolean;
} {
  if (intent.successor === "accept_past") return { accept_past_ack: true };
  if (intent.successor === "abort") return { abort: true };
  if (intent.successor === "step") {
    const n = Number.parseInt(intent.stepCount.trim(), 10);
    if (Number.isFinite(n) && n >= 1) return { step_count: n };
  }
  return {};
}

export type RecoverSuccessorWireFields = ReturnType<typeof buildSuccessorWireFields>;
export type RecoverCatchUpWireFields = Record<string, string | number | null>;

/**
 * Authorize must echo the same catch-up + successor intent that was HMAC-bound
 * on review. After a successful review, editors/baseline are remapped from the
 * response and remainingTouched is cleared — rebuild-from-editors would omit
 * overrides (e.g. catch_up_remaining_minutes: 45) and trip REVIEW_BINDING_MISMATCH.
 */
export function buildRecoverAuthorizeIntentFields(args: {
  boundCatchUpFields: RecoverCatchUpWireFields;
  boundSuccessorFields: RecoverSuccessorWireFields;
}): RecoverCatchUpWireFields & RecoverSuccessorWireFields {
  return {
    ...args.boundSuccessorFields,
    ...args.boundCatchUpFields,
  };
}

/** Soft affordance gate from TaskOut.recurrence only — not held-list / settings. */
export function canOfferRecoverAffordance(taskHasRecurrence: boolean): boolean {
  return taskHasRecurrence;
}

/**
 * Generation / stale gate for review↔authorize.
 * Authorize may enable only when fresh, binding present, review_ok, and generation matches.
 */
export function isRecoverAuthorizeEnabled(args: {
  stale: boolean;
  reviewOkForAuthorize: boolean;
  reviewBinding: string | null | undefined;
  appliedGeneration: number;
  currentGeneration: number;
  mutationPending: boolean;
}): boolean {
  if (args.mutationPending) return false;
  if (args.stale) return false;
  if (!args.reviewOkForAuthorize) return false;
  if (!args.reviewBinding) return false;
  if (args.appliedGeneration !== args.currentGeneration) return false;
  return true;
}

/** Discard late review responses whose request generation ≠ current. */
export function shouldApplyReviewResponse(
  requestGeneration: number,
  currentGeneration: number,
): boolean {
  return requestGeneration === currentGeneration;
}

export function editorsFromReviewCatchUp(catchUp: {
  due_at: string | null;
  start_no_earlier_at: string | null;
  start_no_later_at: string | null;
  deadline_at: string | null;
  remaining_minutes: number;
  remaining_minutes_default: number;
}): { editors: RecoverCatchUpEditors; baseline: RecoverCatchUpBaseline } {
  const editors: RecoverCatchUpEditors = {
    dueLocal: toDatetimeLocal(catchUp.due_at),
    startNoEarlierLocal: toDatetimeLocal(catchUp.start_no_earlier_at),
    startNoLaterLocal: toDatetimeLocal(catchUp.start_no_later_at),
    deadlineLocal: toDatetimeLocal(catchUp.deadline_at),
    remainingMinutes: String(catchUp.remaining_minutes),
  };
  const baseline: RecoverCatchUpBaseline = {
    dueLocal: editors.dueLocal,
    startNoEarlierLocal: editors.startNoEarlierLocal,
    startNoLaterLocal: editors.startNoLaterLocal,
    deadlineLocal: editors.deadlineLocal,
    remainingMinutes: catchUp.remaining_minutes,
    remainingDefault: catchUp.remaining_minutes_default,
  };
  return { editors, baseline };
}

/** C2 copy — code only; never delete/unpin/manual-clear remedy. */
export function c2LimitationCopy(code: string | null | undefined, detail: string | null | undefined): string {
  const bits = [
    code ? `Recovery blocked: ${code}` : "Recovery blocked while same-task blocks prevent next-normal.",
  ];
  if (detail) bits.push(detail);
  return bits.join(" — ");
}
