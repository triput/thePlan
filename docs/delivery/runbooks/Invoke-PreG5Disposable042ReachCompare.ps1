#Requires -Version 5.1
<#
.SYNOPSIS
  Dual-network reach-compare (post reach-1). NOT startup validation.

.NOTES
  PLANNING until Trish EXECUTE after Dex packet ACCEPT (post-compare-1 host HTTP fix).
  Preflight refuse => NO compose down -v (may be unowned).
  Requires -Execute and -AuditApprovalPath.
  Default AttemptId: disposable-042-reach-compare-2 (compare-1 sealed; do not reuse).
#>
[CmdletBinding()]
param(
  [switch] $Execute,
  [string] $ScratchRoot = "F:\DropFolder\scratch",
  [string] $ExportStamp = "20261102T055454Z-b349fb02",
  [string] $AttemptId = "disposable-042-reach-compare-2",
  [string] $ProjectName = "theplanpreg5snap20261102t055454zb349fb02cmp2",
  [string] $ComposeFile = "",
  [string] $SnapshotApiImage = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b",
  [string] $SnapshotWebImage = "sha256:636901afe16e8ffda36601af75f029e2b076287a2c5ca868ecedd42029351969",
  [string] $PostgresImage = "sha256:93d55776e04376e19adb2733e3ccebb4392ee7dd86d8ff238503b30fe719c84f",
  [string] $ExpectAlembic = "042_task_occurrence_dispositions",
  [int] $ComposeTimeoutMs = 180000,
  [int] $HostHttpTimeoutSec = 20,
  [int] $ProbeMatrixDeadlineMs = 180000,
  [int] $ComposeExecProbeTimeoutMs = 25000,
  [string] $AuditApprovalPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "PreG5-SnapshotHelpers.ps1")
. (Join-Path $PSScriptRoot "PreG5-DisposableValidationLib.ps1")
. (Join-Path $PSScriptRoot "PreG5-ReachabilityDiagnosisLib.ps1")
. (Join-Path $PSScriptRoot "PreG5-ReachabilityCompareLib.ps1")

if (-not $Execute) {
  throw "PLANNING ONLY: Invoke-PreG5Disposable042ReachCompare.ps1 refuses without -Execute."
}
if ([string]::IsNullOrWhiteSpace($AuditApprovalPath)) {
  throw "PLANNING ONLY: -AuditApprovalPath is required with -Execute."
}

$result = Invoke-PreG5Disposable042ReachCompareCore `
  -ScratchRoot $ScratchRoot `
  -ExportStamp $ExportStamp `
  -AttemptId $AttemptId `
  -ProjectName $ProjectName `
  -ComposeFile $(if ($ComposeFile) { $ComposeFile } else { "" }) `
  -SnapshotApiImage $SnapshotApiImage `
  -SnapshotWebImage $SnapshotWebImage `
  -PostgresImage $PostgresImage `
  -ExpectAlembic $ExpectAlembic `
  -AuditApprovalPath $AuditApprovalPath `
  -ComposeTimeoutMs $ComposeTimeoutMs `
  -HostHttpTimeoutSec $HostHttpTimeoutSec `
  -ProbeMatrixDeadlineMs $ProbeMatrixDeadlineMs `
  -ComposeExecProbeTimeoutMs $ComposeExecProbeTimeoutMs

if ($result.ExitCode -eq 0) {
  Write-Host "DISPOSABLE_042_REACH_COMPARE_OK startup_validation_ok=false dual_net=true"
}
else {
  foreach ($n in @($result.Notes)) {
    if ($n) { Write-Host ("PREG5_REACH_COMPARE_NOTE " + $n) }
  }
}

exit $result.ExitCode
