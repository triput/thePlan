# Full review reconciliation for draft 0.3

Julie (1792434985.791419 and .837849) and Jim (1792435676.832389) both report reading full draft 0.2 with matching SHA256 71710E9B35C06462ABF2E8119E7AE1EB7BC4C96CBD7A37070927C98450FA0155. Neither reports a blocker to writing 0.3. This is not implementation approval or final design sign-off.

Integrate Julie's intake corrections in Full-Spec-Review-Julie-2026-10-19.md. Additional engineering requirements from Jim: sync coverage of the requested horizon with an explicit freshness policy; canonical provider calendar identity for duplicate aliases; Microsoft busy/free and safe-export contracts as completion gates; existing time_worked_minutes/remaining estimate assessed for progress semantics, with a new signal identified if necessary; new bounds included in fingerprint/stale detection; isolated startup/restart tests proving no prohibited sync/calculation/export is triggered. Unknown baselines remain unresolved rather than invented. Do not change gitignore on this suggestion alone.

Product choices for Trish:
1. Proposed soft early-afternoon preference within hard day-of bounds.
2. Proposed missed default: held/visible unless the routine is explicitly designated skippable; no automatic stacking. Keep disposition history.
3. Proposed scope: recurrence engine/CLI support outside this repair; authorized operator may set per-one-off bounds once supported, without authorizing live edits now.
4. Date-only owning zone: Jim recommends owner settings zone; Dex requires explicit examples of source-calendar differences before presenting this as a harmless default. Source-local day versus owner-local day is a real semantic choice. Recommend preserve source-calendar day where supplied, with explicit fallback, rather than silently reinterpret. Bring tradeoff to Trish.

Hold remains across implementation, deployment and all real-data proposal/replan/Apply operations. Engineering details may be designed, not executed.
