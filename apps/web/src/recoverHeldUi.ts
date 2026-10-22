/**
 * T2-REC-UI helpers — Option A zone honesty, edit-generation stale gates,
 * and omit-vs-null catch-up wire (no client RRULE).
 *
 * Review is STATELESS: omitted catch-up fields mean None/default, not "keep
 * prior review." Successive refreshes must re-send effective reviewed intent
 * (raw ISO precision); explicit clear remains null.
 */

import {
  browserTimeZoneLabel,
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

/**
 * Effective catch-up wire from the last applied review (raw ISO / remaining).
 * Re-sent on successive refreshes when editors are unchanged — omit must not clear.
 */
export type RecoverCatchUpWireFields = {
  catch_up_due_at?: string | null;
  catch_up_start_no_earlier_at?: string | null;
  catch_up_start_no_later_at?: string | null;
  catch_up_deadline_at?: string | null;
  catch_up_remaining_minutes?: number;
};

export interface RecoverFormIntent {
  successor: RecoverSuccessorMode;
  stepCount: string;
  editors: RecoverCatchUpEditors;
  baseline: RecoverCatchUpBaseline | null;
  /** True once the operator changed remaining away from the reviewed value. */
  remainingTouched: boolean;
  /**
   * Last reviewed catch-up wire. Carried across refreshes so unchanged fields
   * re-send raw ISO / remaining instead of omitting (stateless review).
   */
  priorCatchUpFields: RecoverCatchUpWireFields;
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

const WALL_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;

/** Offset of `timeZone` at `utcMs` (local-as-UTC − utcMs), same idea as timeMapOverrides. */
function getTimeZoneOffsetMs(utcMs: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date(utcMs));
  const map: Record<string, number> = {};
  for (const part of parts) {
    if (part.type !== "literal") map[part.type] = Number(part.value);
  }
  const asUtc = Date.UTC(
    map.year!,
    map.month! - 1,
    map.day!,
    map.hour!,
    map.minute!,
    map.second ?? 0,
  );
  return asUtc - utcMs;
}

/** Wall clock in IANA zone → one UTC candidate (converges; fold twin probed separately). */
function zonedWallToUtcMs(ymd: string, hour: number, minute: number, timeZone: string): number {
  const [y, mo, d] = ymd.split("-").map(Number);
  let ms = Date.UTC(y!, mo! - 1, d!, hour, minute);
  for (let i = 0; i < 4; i++) {
    ms = Date.UTC(y!, mo! - 1, d!, hour, minute) - getTimeZoneOffsetMs(ms, timeZone);
  }
  return ms;
}

/** Distinct zone offsets (ms) sampled across the local civil day — captures 30min DST steps. */
function offsetMsValuesAcrossLocalDay(ymd: string, timeZone: string): number[] {
  const [y, mo, d] = ymd.split("-").map(Number);
  const start = Date.UTC(y!, mo! - 1, d!, 0, 0) - 14 * 3_600_000;
  const end = Date.UTC(y!, mo! - 1, d!, 23, 59) + 14 * 3_600_000;
  const seen = new Set<number>();
  for (let t = start; t <= end; t += 900_000) {
    seen.add(getTimeZoneOffsetMs(t, timeZone));
  }
  return [...seen];
}

/** UTC instants to verify for a wall clock — one per offset side of transitions, plus converged primary. */
function utcCandidatesForWallInZone(
  ymd: string,
  hour: number,
  minute: number,
  timeZone: string,
): number[] {
  const [y, mo, d] = ymd.split("-").map(Number);
  const wallAsUtc = Date.UTC(y!, mo! - 1, d!, hour, minute);
  const candidates = new Set<number>();
  candidates.add(zonedWallToUtcMs(ymd, hour, minute, timeZone));
  for (const off of offsetMsValuesAcrossLocalDay(ymd, timeZone)) {
    candidates.add(wallAsUtc - off);
  }
  return [...candidates];
}

/** Format an instant as datetime-local wall (minute) in an IANA zone. */
export function formatWallInTimeZone(ms: number, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).formatToParts(new Date(ms));
  const map: Record<string, string> = {};
  for (const part of parts) {
    if (part.type !== "literal") map[part.type] = part.value;
  }
  return `${map.year}-${map.month}-${map.day}T${map.hour}:${map.minute}`;
}

/**
 * Resolve a datetime-local wall in an IANA zone.
 * Fail-closed on gap (no instant) and fold (two valid instants).
 */
export function parseWallInTimeZone(
  value: string,
  timeZone: string,
): { ok: true; iso: string } | { ok: false; reason: string } {
  const trimmed = value.trim();
  if (!trimmed) {
    return { ok: false, reason: "empty" };
  }
  const m = WALL_RE.exec(trimmed);
  if (!m) {
    return { ok: false, reason: "invalid" };
  }
  const h = Number(m[4]);
  const mi = Number(m[5]);
  const ymd = `${m[1]}-${m[2]}-${m[3]}`;
  const matches: number[] = [];
  for (const ms of utcCandidatesForWallInZone(ymd, h, mi, timeZone)) {
    if (Number.isNaN(ms)) continue;
    if (formatWallInTimeZone(ms, timeZone) === trimmed && !matches.includes(ms)) {
      matches.push(ms);
    }
  }
  if (matches.length === 0) {
    return { ok: false, reason: "ambiguous_or_nonexistent" };
  }
  if (matches.length > 1) {
    return { ok: false, reason: "ambiguous_or_nonexistent" };
  }
  return { ok: true, iso: new Date(matches[0]!).toISOString() };
}

/**
 * Parse a datetime-local wall in browser local zone.
 * Rejects empty; rejects invalid shape; fail-closed on DST gap and fold.
 */
export function parseBrowserLocalWall(
  value: string,
): { ok: true; iso: string } | { ok: false; reason: string } {
  return parseWallInTimeZone(value, browserTimeZoneLabel());
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

function catchUpIsoFromReview(
  catchUp: {
    due_at: string | null;
    start_no_earlier_at: string | null;
    start_no_later_at: string | null;
    deadline_at: string | null;
  },
  key: CatchUpDateKey,
): string | null {
  switch (key) {
    case "catch_up_due_at":
      return catchUp.due_at;
    case "catch_up_start_no_earlier_at":
      return catchUp.start_no_earlier_at;
    case "catch_up_start_no_later_at":
      return catchUp.start_no_later_at;
    case "catch_up_deadline_at":
      return catchUp.deadline_at;
  }
}

/**
 * Build catch-up date/remaining fields for review or authorize.
 *
 * - Edited → UTC ISO of browser wall.
 * - Explicit clear → null.
 * - Unchanged vs baseline → re-send prior raw ISO / remaining when present
 *   (stateless review: omit would clear). First review with no prior → omit.
 */
export function buildCatchUpWireFields(
  intent: RecoverFormIntent,
): { ok: true; fields: RecoverCatchUpWireFields } | { ok: false; error: string } {
  const validation = validateCatchUpEditors(intent.editors);
  if (validation) return { ok: false, error: validation };

  const fields: RecoverCatchUpWireFields = { ...intent.priorCatchUpFields };
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
      // Unchanged: keep prior raw ISO (or prior null). Do not delete — omit clears on review.
      continue;
    }
    if (!local) {
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
      // Cleared override → drop prior so omit reaches server default.
      delete fields.catch_up_remaining_minutes;
    } else {
      fields.catch_up_remaining_minutes = Number.parseInt(raw, 10);
    }
  }
  // remainingTouched false: keep prior remaining (if any) across refresh.

  return { ok: true, fields };
}

/**
 * After a successful review, merge sent wire + response into effective intent
 * so the next refresh re-sends raw ISO precision (not minute-truncated editors).
 */
export function effectiveCatchUpFieldsAfterReview(
  sent: RecoverCatchUpWireFields,
  catchUp: {
    due_at: string | null;
    start_no_earlier_at: string | null;
    start_no_later_at: string | null;
    deadline_at: string | null;
    remaining_minutes: number;
    remaining_minutes_default: number;
  },
): RecoverCatchUpWireFields {
  const keys: CatchUpDateKey[] = [
    "catch_up_due_at",
    "catch_up_start_no_earlier_at",
    "catch_up_start_no_later_at",
    "catch_up_deadline_at",
  ];
  const out: RecoverCatchUpWireFields = {};
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(sent, key)) {
      const sentVal = sent[key];
      if (sentVal === null) {
        out[key] = null;
      } else if (typeof sentVal === "string") {
        // Prefer server-normalized ISO when present; else keep sent.
        out[key] = catchUpIsoFromReview(catchUp, key) ?? sentVal;
      }
    } else {
      const fromServer = catchUpIsoFromReview(catchUp, key);
      if (fromServer) {
        out[key] = fromServer;
      }
    }
  }
  if (Object.prototype.hasOwnProperty.call(sent, "catch_up_remaining_minutes")) {
    out.catch_up_remaining_minutes = sent.catch_up_remaining_minutes;
  } else if (catchUp.remaining_minutes !== catchUp.remaining_minutes_default) {
    // Server absorbed a prior override into catch_up; carry it for next refresh.
    out.catch_up_remaining_minutes = catchUp.remaining_minutes;
  }
  return out;
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

/** Authorize body fields: catch-up wire + successor flags (booleans allowed). */
export type RecoverAuthorizeIntentFields = RecoverCatchUpWireFields & RecoverSuccessorWireFields;

/**
 * Authorize must echo the same catch-up + successor intent that was HMAC-bound
 * on review. After a successful review, editors/baseline are remapped from the
 * response and remainingTouched is cleared — rebuild-from-editors alone would
 * omit overrides; carry bound fields instead.
 */
export function buildRecoverAuthorizeIntentFields(args: {
  boundCatchUpFields: RecoverCatchUpWireFields;
  boundSuccessorFields: RecoverSuccessorWireFields;
}): RecoverAuthorizeIntentFields {
  return {
    ...args.boundCatchUpFields,
    ...args.boundSuccessorFields,
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
