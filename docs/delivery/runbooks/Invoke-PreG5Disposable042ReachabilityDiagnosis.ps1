#Requires -Version 5.1
<#
.SYNOPSIS
  Disposable project reachability diagnosis (layered probe matrix). NOT startup validation.

.NOTES
  PLANNING until Trish EXECUTE after Dex packet ACCEPT.
  Preflight refuse => NO compose down -v (may be unowned).
  Requires -Execute and -AuditApprovalPath. Default AttemptId: disposable-042-reach-1.
#>
[CmdletBinding()]
param(
  [switch] $Execute,
  [string] $ScratchRoot = "F:\DropFolder\scratch",
  [string] $ExportStamp = "20261102T055454Z-b349fb02",
  [string] $AttemptId = "disposable-042-reach-1",
  [string] $ProjectName = "theplanpreg5snap20261102t055454zb349fb02",
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

if ([string]::IsNullOrWhiteSpace($ComposeFile)) {
  $ComposeFile = Join-Path $PSScriptRoot "compose.pre-g5-snapshot-disposable.yaml"
}

if (-not $Execute) {
  throw "PLANNING ONLY: Invoke-PreG5Disposable042ReachabilityDiagnosis.ps1 refuses without -Execute."
}
if ([string]::IsNullOrWhiteSpace($AuditApprovalPath)) {
  throw "PLANNING ONLY: -AuditApprovalPath is required with -Execute."
}

$result = Invoke-PreG5Disposable042ReachabilityDiagnosisCore `
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
  -HostHttpTimeoutSec $HostHttpTimeoutSec `
  -ProbeMatrixDeadlineMs $ProbeMatrixDeadlineMs `
  -ComposeExecProbeTimeoutMs $ComposeExecProbeTimeoutMs

if ($result.ExitCode -eq 0) {
  Write-Host "DISPOSABLE_042_REACHABILITY_DIAGNOSIS_OK startup_validation_ok=false"
}
else {
  foreach ($n in @($result.Notes)) {
    if ($n) { Write-Host ("PREG5_REACH_NOTE " + $n) }
  }
}

exit $result.ExitCode
