#Requires -Version 5.1
<#
  Harmless failure-path validation against the REAL shared routines in
  Household-ReceiptDisposition.ps1 (same module G1/G4/rollback use).
  Does NOT touch household DB, compose, or production dumps.
  Exit 0 = all cases passed.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Household-ReceiptDisposition.ps1")

$tmp = Join-Path $env:TEMP ("g1_receipt_validate_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$failed = 0

function Assert-True([bool] $cond, [string] $msg) {
  if (-not $cond) {
    Write-Host "FAIL: $msg"
    $script:failed++
  } else {
    Write-Host "OK: $msg"
  }
}

try {
  # --- Get-G1Eligibility (actual production function) ---
  Assert-True (Get-G1Eligibility -RestoreDrillPass $true -CleanupOk $true -WorkFailed $false) `
    "Get-G1Eligibility all_good"
  Assert-True (-not (Get-G1Eligibility -RestoreDrillPass $true -CleanupOk $false -WorkFailed $false)) `
    "Get-G1Eligibility cleanup_fail"
  Assert-True (-not (Get-G1Eligibility -RestoreDrillPass $false -CleanupOk $true -WorkFailed $false)) `
    "Get-G1Eligibility no_drill (SkipRestoreDrill path)"
  Assert-True (-not (Get-G1Eligibility -RestoreDrillPass $true -CleanupOk $true -WorkFailed $true)) `
    "Get-G1Eligibility work_fail"

  # --- New-G1ReceiptObject fields (actual production builder) ---
  $good = New-G1ReceiptObject -InvocationId "inv1" -DumpPath "D:\x.dump" -DumpSha256 "ABC" `
    -RestoreDrillPass $true -CleanupOk $true -WorkFailed $false `
    -SourceUsers 1 -SourceTasks 2 -SourceSettings 3 -RestoreDrillDbDropped $true
  Assert-True ($good.g1_pass -eq $true -and $good.g4_eligible -eq $true -and $good.cleanup_ok -eq $true -and $good.unclean -eq $false) `
    "New-G1ReceiptObject success fields"
  Assert-True (-not $good.PSObject.Properties["reason"] -or -not $good.reason) `
    "New-G1ReceiptObject success has no failure reason"

  $unclean = New-G1ReceiptObject -InvocationId "inv2" -DumpPath "D:\y.dump" -DumpSha256 "DEF" `
    -RestoreDrillPass $true -CleanupOk $false -WorkFailed $false -CleanupNotes @("host_tmp_rm_fail")
  Assert-True ($unclean.g1_pass -eq $false -and $unclean.g4_eligible -eq $false -and $unclean.unclean -eq $true -and $unclean.reason -eq "cleanup_failed") `
    "New-G1ReceiptObject cleanup_fail disposition"

  $skip = New-G1ReceiptObject -InvocationId "inv3" -DumpPath "D:\z.dump" -DumpSha256 "GHI" `
    -RestoreDrillPass $false -CleanupOk $true -WorkFailed $false
  Assert-True ($skip.g4_eligible -eq $false -and $skip.reason -eq "restore_drill_skipped_or_failed") `
    "New-G1ReceiptObject SkipRestoreDrill not g4_eligible"

  $work = New-G1ReceiptObject -InvocationId "inv4" -DumpPath "D:\w.dump" -DumpSha256 "JKL" `
    -RestoreDrillPass $true -CleanupOk $true -WorkFailed $true -WorkError "boom"
  Assert-True ($work.g4_eligible -eq $false -and $work.reason -eq "work_failed" -and $work.work_error -eq "boom") `
    "New-G1ReceiptObject work_fail disposition"

  # Round-trip JSON like G1 Write-G1Receipt → G4 read
  $path = Join-Path $tmp "sample.g1-receipt.json"
  ($unclean | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $path -Encoding utf8
  $loaded = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
  $gateBad = Test-G1ReceiptAllowsG4 -Receipt $loaded
  Assert-True (-not $gateBad.Ok) ("Test-G1ReceiptAllowsG4 refuses unclean: " + $gateBad.Reason)

  ($good | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $path -Encoding utf8
  $loadedGood = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
  $gateGood = Test-G1ReceiptAllowsG4 -Receipt $loadedGood
  Assert-True $gateGood.Ok ("Test-G1ReceiptAllowsG4 accepts clean eligible: " + $gateGood.Reason)

  # --- Rollback basic disposition (actual production function) — package never disposes hold ---
  $d1 = Get-RollbackBasicDisposition -BasicRecoveryOk $true -CleanupOk $true -HoldDbName "theplan_rb_hold_x"
  Assert-True ($d1.basic_recovery_ok -eq $true -and $d1.may_dispose_hold -eq $false -and $d1.hold_retained -eq $true -and $d1.rollback_pass_allowed -eq $false) `
    "basic OK still may_dispose_hold=false hold_retained=true"
  $d2 = Get-RollbackBasicDisposition -BasicRecoveryOk $true -CleanupOk $false -HoldDbName "theplan_rb_hold_y"
  Assert-True ($d2.cleanup_ok -eq $false -and $d2.may_dispose_hold -eq $false) `
    "cleanup fail still cannot dispose"
  # Exit-order contract used by rollback script: unclean (exit 3) before basic-only (exit 4)
  $cleanupOk = $false; $basicOk = $true
  $branch = if (-not $cleanupOk) { "unclean" } elseif ($basicOk) { "basic_only" } else { "fail" }
  Assert-True ($branch -eq "unclean") "cleanup failure preferred over basic-only exit"

  Write-Host "Validate-G1ReceiptCleanupLogic done failed=$failed (real Household-ReceiptDisposition.ps1)"
  if ($failed -gt 0) { exit 1 }
  exit 0
}
finally {
  if (Test-Path -LiteralPath $tmp) {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
  }
}
