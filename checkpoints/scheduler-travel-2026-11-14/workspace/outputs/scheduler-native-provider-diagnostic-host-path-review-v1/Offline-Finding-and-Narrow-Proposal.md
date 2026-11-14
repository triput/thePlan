# Diagnostic successor: inherited operator path review

Dex, November 12, 2026. Offline source/metadata inspection only. This is a design proposal, not an implemented correction or launch authorization.

## Verified finding

The stopped native-provider v3 and Matt preparation successor have byte-identical Invoke-Native-Provider.ps1 files: SHA256 090A0FA89549D33A381A9DDFF64DFC6AEE59E22F6832AD36018F7ACF8D3AF612.

Line 42 hardcodes the stopped packet's sibling evidence directory, scheduler-native-provider-first-native-launch-candidate-dex-v3.evidence. That directory exists and holds preserved failure/cleanup evidence. Lines 93-94 refuse an existing evidence directory. Independently, the preparation successor's host launch_ready is false and lines 52-53 refuse before child creation. No operator was invoked to establish these facts.

Changing only the optional ReceiptPath argument cannot repair the path: the old evidence-directory check happens before default receipt selection, and public-ca is also created beneath the hardcoded old evidence directory. The successor Docker config instead expects its own sibling evidence/public-ca path, including the runner read-only CA bind. Redirecting just the receipt would leave CA staging inconsistent even if the old evidence were absent.

## Narrowest proposed later correction

In a separately approved fresh launch successor, replace only the old evidence-directory label at line 42 with that final packet's unique sibling evidence-directory label. Keep the existing directory-exists refusal, receipt-exists refusal, public-CA path derivation, pins, admission order and all supervision unchanged. Prefer this exact literal label replacement for the next one-shot packet; a reusable dynamic operator refactor is unnecessary to resolve this instance.

Regenerate only the resulting operator hash and appropriate command/input/admission metadata after the final packet name is selected. Verify that operator evidence root, default receipt parent, host receipt declarations, Docker public_ca_directory and runner CA bind all resolve to that same unique sibling root. Require the new root absent while the stopped evidence remains present and unchanged. Keep every path outside the payload source directory.

No final candidate bytes/hash are asserted here because the final launch packet name has not been selected or authorized. This proposal does not grant source-change or execution authority. Matt's current diagnostic assignment properly preserves the operator unchanged and records objection O1.

## Later acceptance evidence

- Fresh-copy diff contains only the approved evidence label plus truthful refreeze metadata.
- Stopped packet and evidence hashes remain unchanged.
- Exact runner diagnostic candidate and immutable host validator/API pins remain reconciled.
- Static path comparison closes the receipt/CA/bind consistency issue; no directory is created for a probe.
- Separate explicit launch approval admits exact final command, hashes, limits and cleanup scope. No automatic retry or rerun follows from this document.

The diagnostic fake verification packet can be reviewed separately; this native operator issue does not justify changing its checker or widening its scope. Full transport/native proof remains incomplete, endpoint unbound and all other holds stay.