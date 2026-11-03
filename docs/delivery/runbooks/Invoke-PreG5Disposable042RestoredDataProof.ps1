#Requires -Version 5.1
<#
.SYNOPSIS
  Disposable project: pg_restore G3b/G1-bound dump onto fresh postgres @ 042 + DualNet startup validation.
  Restored-data rollback proof on disposable only — NOT rollback_acceptance, NOT household.

.NOTES
  PLANNING until Trish -Execute after Dex packet ACCEPT.
  Preflight refuse => NO compose down -v (may be unowned).
  Proposal MD: docs/delivery/0.7-AGENT-CLI-ACCESS-Phase1-PREG5-DISPOSABLE-042-RESTORED-DATA-PROOF-PROPOSAL-2026-11-02.md (Page).
#>
[CmdletBinding()]
param(
  [switch] $Execute,
  [string] $ScratchRoot = "F:\DropFolder\scratch",
  [string] $ExportStamp = "20261102T055454Z-b349fb02",
  [string] $AttemptId = "disposable-042-restore-1",
  [string] $ProjectName = "theplanpreg5snap20261102t055454zb349fb02restore1",
  [string] $ComposeFile = "",
  [ValidateSet('SingleNet', 'DualNet')]
  [string] $OwnedNetworkProfile = "DualNet",
  [switch] $DualNet,
  [string] $SnapshotApiImage = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b",
  [string] $SnapshotWebImage = "sha256:636901afe16e8ffda36601af75f029e2b076287a2c5ca868ecedd42029351969",
  [string] $PostgresImage = "sha256:93d55776e04376e19adb2733e3ccebb4392ee7dd86d8ff238503b30fe719c84f",
  [string] $ExpectAlembic = "042_task_occurrence_dispositions",
  [Alias("RestoreDumpPath")]
  [string] $DumpPath = "F:\DropFolder\backups\theplan-g3b-rehearsal\household042-readonly-20261102t043243-684b118f56.dump",
  [string] $InventoryManifestPath = "",
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
if ([string]::IsNullOrWhiteSpace($InventoryManifestPath)) {
  $InventoryManifestPath = Get-PreG5DefaultDisposable042RestoredDataInventoryManifestPath -RunbooksRoot $PSScriptRoot
}

if (-not $Execute) {
  throw "PLANNING ONLY: Invoke-PreG5Disposable042RestoredDataProof.ps1 refuses without -Execute."
}

$result = Invoke-PreG5Disposable042RestoredDataProofCore `
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
  -DumpPath $DumpPath `
  -InventoryManifestPath $InventoryManifestPath `
  -ComposeTimeoutMs $ComposeTimeoutMs `
  -HttpTimeoutSec $HttpTimeoutSec `
  -OwnedNetworkProfile $OwnedNetworkProfile `
  -DualNet:$DualNet

if ($result.ExitCode -eq 0) {
  Write-Host "DISPOSABLE_042_RESTORED_DATA_PROOF_OK restored_data_rollback_proof=true rollback_acceptance=false"
}
else {
  foreach ($n in @($result.Notes)) {
    if ($n) { Write-Host ("PREG5_DISP_NOTE " + $n) }
  }
}

exit $result.ExitCode
