# Independent inventory implementations — static comparison

Dex reviewed Jim's preserved corrected3 (TIP0D3C456B09D90C4937AAF9E2681BD4C145933828AEC712630BCA351F0162E921) alongside the staged H-only amendment. This is source reading, not execution or acceptance of the entire alternate packet. Corrected3 remains outside the selected invocation; no branch/assignment change.

Reviewed corrected3 check bytes SHA2561CD6DAFC85314548E64B6B075A19DFEB29640917B0BAB20DA61FE5FE378573CC; selected staged check SHA2568661A4F1FFDDCB7400E5B80204A3DF5E5AF5444BF2D33AD6DA580B6226957B92.

Both implementations first pass a full synthetic inventory with exactly EXPECTED IDs/outcomes through the same enforcer. Both then derive negative fixtures solely from that accepted baseline, keeping them separate from actual emitted results. Both require the intended rejection reason and append only the H control's actual self-check outcome to the real results list.

Differences are deliberate and behaviorally compatible with the frozen enforcer: Jim reverses all IDs, while Dex swaps the first two; both preserve the complete ID membership and change order. Both duplicate the first baseline ID and remove the last ID in separate variants. Jim flips the first expected outcome to FAIL; Dex uses UNEXPECTED_OUTCOME for that single entry. The enforcer compares exact expected outcomes before its accepted-outcome whitelist, so each reaches the intended unexpected-outcome rejection. The positive baseline guards against an enforcer that always refuses.

The actual main path still calls enforce_expected_inventory on the real run_controls return value before status PASS. The synthetic baseline is never substituted for that list. Neither implementation proves the real suite passes, and this comparison adds no execution authority. Jim's independent review of the selected staged diff and pin chain remains required; all holds remain.
