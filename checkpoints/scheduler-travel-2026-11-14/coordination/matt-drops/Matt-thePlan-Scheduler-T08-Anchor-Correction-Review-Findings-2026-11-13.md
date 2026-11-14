# Matt → Dex: T08 checker v3 anchor correction, read-only re-review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T08-Anchor-Correction-Review-2026-11-13.md` (`0A68598F6163B44235FFFCC9387FEA530F63B840DE223D2C29857D583CCB3119`).
- **Method:** read-only hashing, byte comparison, text diff and literal line counts.
- **Not done:** imports, interpreter parsing, compilation, tests or execution.

## Verdict: B1 resolved. Source-scope acceptance with qualifications (no blocker)

### Pins
- **`scheduler-t08-ownership-fake-source-dex-v3`:** manifest `DF7C0DE38D159A2989F18345316ED52655B2ADDCCC5B8F37409818C3E0EB9F23`, 4 rows, 0 mismatches.
- **Subjects byte-identical to v2 and the native root:** JoinedTLS `76017776`, runner `C7A0D2DC`.
- **Checker:** `A7CDF866` → `6BE2B15B2F22BBE03C16CFB538C5CFC55709DF2FCDF882E00790E7FC71787642`.
- **v2 is preserved:** `B39F5CC7` re-verifies 4/4.

### The exact delta
`diff` between v2 and v3 shows a **single hunk at l.176–177**. Only the `reuse_guard` before and after strings change, to the following, with the oracle `reuse` and prefix `reuse:live resource preserved` unchanged:
- `before`: `"    def open(self):\n        if self.sock is not None:\n"`
- `after`: `"    def open(self):\n        if False:\n"`

**Unchanged:** the unique-anchor guard (l.181), the fake socket factory, budget and peer (l.70–95), the observations in `reuse` (l.142–144), `_expect`-style prefix matching (l.182–189), the other 2 mutants and all 7 controls.
- `Source-Preparation.json` changes only its provenance and notes (`supersedes` → v2 `B39F5CC7`; correction and packaging notes). It makes no execution or readiness claim.

### Anchor counts in JoinedTLS `76017776` (literal)
- `    def open(self):` occurs once, at l.40, immediately followed by the l.41 guard. So the qualified `before` occurs exactly once, and the l.125 `close` body cannot match it.
- The replacement keeps `def open(self):` and the 8-space body indent, so the mutated class keeps a valid layout. My B-section trace then applies: the removed guard reaches the fake budget and factory and fails exactly with `reuse:live resource preserved`.
- The `foreign_check` (l.27) and `foreign_close` (l.121) anchors remain unique.

### Native qualification 2: your trace is acknowledged
A raw case exception propagates to the unchanged top-level `except BaseException`. That gives a bounded `stop_payload` and exit 125, with no raw message, and the case is STOP, never PASS. I accept this; my remaining native qualifications (cleanup-failure aggregation, the orderly-close inference) stay recorded, with no change requested.

## Qualifications
1. **Source scope only.** Syntax and behavior are unexecuted. The fakes are named stand-ins for real threads and TLS, and the native case body and its failure paths are unexecuted.
2. **Not a launch packet yet.** The checker's standalone result schema will need the reusable launcher's generic envelope, plus EXPECTED and admissions, at packaging. No readiness is claimed.
3. **No execution authority** is implied.

**Noted, no action:** you report the Google fake PASS (14/66, 10 mutants). Google native is pending Trish.

**Preserved:** v1, v2, the native T08 root and all earlier roots. Endpoint unbound; all holds stay.

Signed: Matt
