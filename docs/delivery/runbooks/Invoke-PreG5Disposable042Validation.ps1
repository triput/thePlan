#Requires -Version 5.1
<#
.SYNOPSIS
  Disposable project: fresh-042 schema (alembic upgrade on empty DB) + reconstructed
  API/web startup validation. NOT backup-restore proof. NOT rollback_acceptance.

.NOTES
  PLANNING until Trish EXECUTE after Dex packet ACCEPT.
  Preflight refuse => NO compose down -v (may be unowned).
  Success receipt only after verified owned cleanup (see PreG5-DisposableValidationLib.ps1).
#>
[CmdletBinding()]
param(
  [switch] $Execute,
  [string] $ScratchRoot = "F:\DropFolder\scratch",
  [string] $ExportStamp = "20261102T055454Z-b349fb02",
  [string] $AttemptId = "disposable-042-val-4",
  [string] $ProjectName = "theplanpreg5snap20261102t055454zb349fb02val4",
  [string] $ComposeFile = "",
  [ValidateSet('SingleNet', 'DualNet')]
  [string] $OwnedNetworkProfile = "DualNet",
  [switch] $DualNet,
  [string] $SnapshotApiImage = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b",
  [string] $SnapshotWebImage = "sha256:636901afe16e8ffda36601af75f029e2b076287a2c5ca868ecedd42029351969",
  [string] $PostgresImage = "sha256:93d55776e04376e19adb2733e3ccebb4392ee7dd86d8ff238503b30fe719c84f",
  [string] $ExpectAlembic = "042_task_occurrence_dispositions",
  [int] $ComposeTimeoutMs = 180000,
  [int] $HttpTimeoutSec = 20,
  [string] $AuditApprovalPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "PreG5-SnapshotHelpers.ps1")
. (Join-Path $PSScriptRoot "PreG5-DisposableValidationLib.ps1")

if ([string]::IsNullOrWhiteSpace($ComposeFile)) {
  $ComposeFile = Get-PreG5DisposableDualNetComposeFile -RunbooksRoot $PSScriptRoot
}
if ($DualNet) { $OwnedNetworkProfile = 'DualNet' }

if (-not $Execute) {
  throw "PLANNING ONLY: Invoke-PreG5Disposable042Validation.ps1 refuses without -Execute."
}

$result = Invoke-PreG5Disposable042ValidationCore `
  -ScratchRoot $ScratchRoot `
  -ExportStamp $ExportStamp `
  -AttemptId $AttemptId `
  -ProjectName $ProjectName `
  -ComposeFile $ComposeFile `
  -SnapshotApiImage $SnapshotApiImage `
  -SnapshotWebImage $SnapshotWebImage `
  -PostgresImage $PostgresImage `
  -ExpectAlembic $ExpectAlembic `
  -AuditApprovalPath $AuditApprovalPath `
  -ComposeTimeoutMs $ComposeTimeoutMs `
  -HttpTimeoutSec $HttpTimeoutSec `
  -OwnedNetworkProfile $OwnedNetworkProfile `
  -DualNet:$DualNet

if ($result.ExitCode -eq 0) {
  Write-Host "DISPOSABLE_042_VALIDATION_OK rollback_acceptance=false not_backup_restore=true"
}
else {
  foreach ($n in @($result.Notes)) {
    if ($n) { Write-Host ("PREG5_DISP_NOTE " + $n) }
  }
}

exit $result.ExitCode
