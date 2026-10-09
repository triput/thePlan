/** Human-readable lines for scheduler reason_facts (mirrors API format_summary_text). */

function paramStr(params: Record<string, unknown>, key: string): string | null {
  const value = params[key];
  if (value == null) return null;
  return String(value);
}

export function formatScheduleReasonFact(code: string, params: Record<string, unknown>): string {
  const p = params;
  if (code === "excluded_manual_or_bundle") {
    const style = paramStr(p, "schedule_style") ?? "manual";
    const source = paramStr(p, "style_source");
    return source
      ? `Excluded from auto-scheduling (${style} via ${source}).`
      : `Excluded from auto-scheduling (${style}).`;
  }
  if (code === "excluded_duration_covered_by_pins") {
    const pinned = p.pinned_minutes;
    const requested = p.requested_minutes;
    if (pinned != null && requested != null) {
      return `Duration fully covered by pinned blocks (${pinned} of ${requested} minutes).`;
    }
    return "Duration fully covered by pinned blocks.";
  }
  if (code === "blocked_prerequisite") {
    const blockers = (p.blocking_task_ids as unknown[]) ?? [];
    if (blockers.length) {
      return `Waiting on unfinished prerequisite(s): ${blockers.map(String).join(", ")}.`;
    }
    return "Waiting on unfinished prerequisite(s).";
  }
  if (code === "placed") {
    const placed = p.placed_minutes;
    const tier = paramStr(p, "tier");
    const src = paramStr(p, "time_window_source");
    const parts: string[] = [];
    parts.push(placed != null ? `Placed ${placed} minute(s)` : "Placed");
    if (tier) parts.push(`in ${tier} tier`);
    if (src) parts.push(`(time map from ${src})`);
    return `${parts.join(" ")}.`;
  }
  if (code === "unplaced_horizon_exhausted") {
    const rem = p.remaining_minutes;
    return rem != null
      ? `Could not place ${rem} remaining minute(s) within the horizon.`
      : "Could not place remaining work within the horizon.";
  }
  if (code === "unplaced_no_slot") {
    const rem = p.remaining_minutes;
    return rem != null
      ? `No suitable slot found for ${rem} remaining minute(s).`
      : "No suitable slot found for remaining work.";
  }
  if (code === "unplaced_deadline_limit") {
    const rem = p.remaining_minutes;
    const deadline = paramStr(p, "deadline_at");
    if (rem != null && deadline) {
      return `Could not place ${rem} remaining minute(s) before the deadline (${deadline}).`;
    }
    if (rem != null) {
      return `Could not place ${rem} remaining minute(s) before the deadline.`;
    }
    return "Remaining work does not fit before the deadline.";
  }
  if (code === "blocked_dependency_cycle") {
    const members = (p.cycle_task_ids as unknown[]) ?? [];
    if (members.length) {
      return `Blocked by a dependency cycle involving: ${members.map(String).join(", ")}.`;
    }
    return "Blocked by a dependency cycle among prerequisites.";
  }
  if (code === "unplaced_project_daily_cap") {
    const cap = p.daily_cap_minutes;
    const day = paramStr(p, "local_date");
    if (cap != null && day) {
      return `Project daily auto-schedule cap (${cap} min) reached for ${day}.`;
    }
    if (cap != null) {
      return `Project daily auto-schedule cap (${cap} min) reached.`;
    }
    return "Project daily auto-schedule cap reached.";
  }
  if (code === "unplaced_insufficient_min_block") {
    const mbl = p.min_block_minutes;
    const rem = p.remaining_minutes;
    if (mbl != null && rem != null) {
      return `No contiguous window of at least ${mbl} minutes for ${rem} remaining minute(s).`;
    }
    if (mbl != null) {
      return `No contiguous window of at least ${mbl} minutes.`;
    }
    return "No contiguous window large enough for the minimum block size.";
  }
  if (code === "unplaced_no_time_map_interval") {
    return "No allowed Time Map interval in the horizon for this task.";
  }
  if (code === "unplaced_red_exclusion") {
    return "Time Map red bands exclude the remaining work in this horizon.";
  }
  if (code === "unplaced_busy_conflict") {
    return "External calendar busy time blocks placement in available windows.";
  }
  if (code === "unplaced_pinned_conflict") {
    return "Pinned blocks conflict with the remaining work in available windows.";
  }
  if (code === "excluded_lifecycle_completed") {
    return "Excluded from auto-scheduling (task completed).";
  }
  if (code === "excluded_lifecycle_trashed") {
    return "Excluded from auto-scheduling (task in trash).";
  }
  if (code === "excluded_lifecycle_archived") {
    const scope = paramStr(p, "archived_scope") ?? "container";
    return `Excluded from auto-scheduling (${scope} archived).`;
  }
  const extras = Object.keys(p).length ? ` (${JSON.stringify(p)})` : "";
  return `Scheduling note: ${code}${extras}.`;
}
