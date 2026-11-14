# R1–R8 disposition matrix — jim-v2

Dex review 5306D7C646A26080F1AD4C3CA1687409E14F20312A41A1F5C6889345A0FB9059. Documents only; no execution authority.

| ID | Dex ask | v2 disposition |
| --- | --- | --- |
| R1 | Existing unchanged isolation as initial nonroot :443; bounded bind later; STOP if unsupported; namespace/sysctl/cap = contingency only; keep vendor origin/port, 127.0.0.1, verify-full; no root/translation/rewrite | **Addressed** in Implementation-Scope-Proposal §3.2 — default = unchanged isolation + bind probe + STOP; A/B contingencies only after observed need + Trish review |
| R2 | One exact case list + requirement map; fix T06 OTHER/PARTIAL orphans and MALFORMED/TRUNCATED -ACK spelling; no orphan/glob/missing variants; T08 multi-oracle OK | **Addressed** in Case-Registry.md — native **27** exact STOP units; OTHER/PARTIAL present; -ACK spelling frozen; T08 = NP-T08-OWNERSHIP multi-oracle; full 76-ID map |
| R3 | Exact control/source lineage not family labels; no fake userinfo/fragment/control-char REUSE; preserve CTRL-CONT-FOREIGN-BEFORE-SEND + REDIRECT-3XX; keep 76 IDs; T02 overrun not waived; update D1 framing PASS 73/73 with EXCESS-ITEM-BYTE / PRIMARY-BOTH-CLOSES host-fake lineage; not native proof | **Addressed** in Case-Registry §C + Proposal §0.2 — exact D2/route/framing hashes; CF-WITNESS for missing rows; framing RESULT 3905A070… / receipt 166BB080…; port still unexecuted |
| R4 | 3×210 ≠ min 720 elapsed; keep 240/request + 30 cleanup; account 600s plan validity; fresh planning or split batches; no reseed/retry expired attempt; state plan-clock capture/check; compute budgets from canonical list | **Addressed** in Proposal §4 — 630s work / 720s request-envelope clarification; ATTEMPT_VALIDITY_SECONDS=600 rules; batches from 27(+4) list |
| R5 | Host Docker vs in-runner; integrated_runner is registry/guard not Docker owner; never mount Docker socket to runner; list operator/Docker/immutable helpers + np_* with lineage; reuse DB/bootstrap | **Addressed** in Proposal §1.2 — host Invoke/supervisor/Docker vs np_integrated_runner guard-only; bootstrap reuse |
| R6 | Distinguish owned-resource retirement vs container failure disposal; later launch may request one bounded fault retirement; unconfirmed→STOP/UNKNOWN; container removal/SIGINT separately gated; no force/retry/foreign cleanup; UNKNOWN still proves disposition | **Addressed** in Proposal §5 |
| R7 | T04-DISCONNECT = ASGI/request-disconnect + joined retirement ≠ abrupt EOF; orderly requal = valid JSON + short CL + orderly TLS close; keep abrupt TLS vs malformed JSON/chunk/header distinct; share only on same observation; disclose parser coupling; no 57-case native repeat | **Addressed** in Case-Registry §A rows 22–24 + Proposal §6 |
| R8 | Prep wording: new roles outside lane; later Trish card for named fresh-copies; no code until approved; spell assembly file selection/deltas/authority; cite Final-Assembly JSON 85714151… data-only (229/5/13); launch hashes later gated | **Addressed** in Proposal §7 + Trish-source-preparation-card-wording.md |

One-line summary list (for handback):

1. **R1:** Unchanged-isolation :443 first; contingencies only after need; STOP on bind fail.
2. **R2:** Canonical 27 native (+4 CF); orphans/spelling fixed; 76-ID map exact.
3. **R3:** Exact lineage cites; framing PASS host-fake only; T02 overrun retained.
4. **R4:** 630/720 arithmetic corrected; 600s plan validity + fresh planning rules.
5. **R5:** Host Docker; runner = registry/guard; no socket mount.
6. **R6:** Owned retirement ≠ container disposal; fault retirement launch-gated.
7. **R7:** ASGI disconnect ≠ abrupt EOF; orderly short-CL+close_notify requal.
8. **R8:** No code until card; assembly JSON data-only; launch freeze later.
