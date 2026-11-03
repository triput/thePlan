#Requires -Version 5.1
<#
  Shared pure receipt / finalization routines used by G1, G4 refuse checks, and Validate-*.
  Dot-source only. No docker, no household side effects.
#>

Set-StrictMode -Version Latest

function Get-G1Eligibility {
  param(
    [bool] $RestoreDrillPass,
    [bool] $CleanupOk,
    [bool] $WorkFailed
  )
  return [bool]($RestoreDrillPass -and $CleanupOk -and (-not $WorkFailed))
}

function New-G1ReceiptObject {
  param(
    [Parameter(Mandatory = $true)][string] $InvocationId,
    [Parameter(Mandatory = $true)][string] $DumpPath,
    [Parameter(Mandatory = $true)][string] $DumpSha256,
    [string] $SourceAlembic = $null,
    [string] $SourceDatabase = $null,
    [bool] $RestoreDrillPass = $false,
    [string] $RestoreDrillDb = $null,
    [bool] $RestoreDrillDbDropped = $false,
    [int] $SourceUsers = 0,
    [int] $SourceTasks = 0,
    [int] $SourceSettings = 0,
    [object] $WritersStopped = $null,
    [bool] $CleanupOk = $false,
    [object] $CleanupNotes = @(),
    [bool] $WorkFailed = $false,
    [string] $WorkError = $null
  )

  $eligible = Get-G1Eligibility -RestoreDrillPass $RestoreDrillPass -CleanupOk $CleanupOk -WorkFailed $WorkFailed
  $receipt = [ordered]@{
    schema_version           = 1
    g1_pass                  = $eligible
    g4_eligible              = $eligible
    invocation_id            = $InvocationId
    dump_path                = $DumpPath
    dump_sha256              = $DumpSha256
    source_alembic           = $SourceAlembic
    source_database          = $SourceDatabase
    restore_drill_pass       = [bool]$RestoreDrillPass
    restore_drill_db         = $RestoreDrillDb
    restore_drill_db_dropped = [bool]$RestoreDrillDbDropped
    source_users             = $SourceUsers
    source_tasks             = $SourceTasks
    source_settings          = $SourceSettings
    drill_matched_source     = [bool]$RestoreDrillPass
    writers_stopped          = $WritersStopped
    external_writers_attest  = "EXTERNAL_WRITERS_QUIESCED"
    cleanup_ok               = [bool]$CleanupOk
    cleanup_notes            = @($CleanupNotes)
    work_failed              = [bool]$WorkFailed
    work_error               = $WorkError
    unclean                  = (-not $CleanupOk)
    taken_utc                = (Get-Date).ToUniversalTime().ToString("o")
  }
  if ($WorkFailed) {
    $receipt.reason = "work_failed"
  } elseif (-not $CleanupOk) {
    $receipt.reason = "cleanup_failed"
  } elseif (-not $RestoreDrillPass) {
    $receipt.reason = "restore_drill_skipped_or_failed"
  }
  return $receipt
}

function Test-G1ReceiptAllowsG4 {
  <#
    Pure gate used by Invoke-G4HouseholdMigrate Assert-G1Receipt (field checks only).
    Dump existence/SHA verified separately where filesystem is available.
  #>
  param([Parameter(Mandatory = $true)]$Receipt)

  if ($Receipt.g1_pass -ne $true) { return @{ Ok = $false; Reason = "g1_pass != true" } }
  if ($Receipt.g4_eligible -ne $true) { return @{ Ok = $false; Reason = "g4_eligible != true" } }
  if ($Receipt.restore_drill_pass -ne $true) { return @{ Ok = $false; Reason = "restore_drill_pass != true" } }
  if ($Receipt.drill_matched_source -ne $true) { return @{ Ok = $false; Reason = "drill_matched_source != true" } }
  if ($Receipt.cleanup_ok -ne $true) { return @{ Ok = $false; Reason = "cleanup_ok != true" } }
  if ($Receipt.unclean -eq $true) { return @{ Ok = $false; Reason = "unclean=true" } }
  if ($Receipt.work_failed -eq $true) { return @{ Ok = $false; Reason = "work_failed=true" } }
  if ([string]::IsNullOrWhiteSpace([string]$Receipt.dump_path)) {
    return @{ Ok = $false; Reason = "dump_path missing" }
  }
  return @{ Ok = $true; Reason = "ok" }
}

function Get-RollbackBasicDisposition {
  <#
    This release package never disposes the renamed hold DB.
    Basic recovery reports state; hold disposal is a separate reviewed operation later.
  #>
  param(
    [bool] $BasicRecoveryOk,
    [bool] $CleanupOk,
    [string] $HoldDbName = $null
  )
  return [ordered]@{
    basic_recovery_ok     = [bool]$BasicRecoveryOk
    cleanup_ok            = [bool]$CleanupOk
    hold_retained         = $true
    hold_db_name          = $HoldDbName
    may_dispose_hold      = $false
    rollback_pass_allowed = $false
    package_scope         = "basic_recovery_only_hold_retained"
  }
}
