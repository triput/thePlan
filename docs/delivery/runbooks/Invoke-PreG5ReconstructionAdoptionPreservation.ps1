#Requires -Version 5.1
<#
.SYNOPSIS
  Pre-G5 reconstruction adoption: durable docker save + sidecars, then pin/decision-sheet updates.

.NOTES
  PLANNING until Trish -Execute after Dex ACCEPT of adoption/preservation package.
  Does NOT docker load, recreate household containers, run G1, or invoke household rollback.
  Refuses without -Execute.
#>
[CmdletBinding()]
param(
  [switch] $Execute,
  [string] $DestDir = "F:\DropFolder\backups\theplan-household-rollback-images",
  [string] $ExportStamp = "20261102T055454Z-b349fb02",
  [string] $ApiDigest = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b",
  [string] $WebDigest = "sha256:636901afe16e8ffda36601af75f029e2b076287a2c5ca868ecedd42029351969",
  [string] $AuditApprovalPath = "",
  [string] $ComposePinsPath = "",
  [string] $DecisionSheetPath = "",
  [switch] $ApplyOptionalAdoptedTags,
  [switch] $SkipHouseholdGuard,
  [int] $SaveTimeoutMs = 600000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "PreG5-ReconstructionAdoptionLib.ps1")

if (-not $Execute) {
  throw "PLANNING ONLY: Invoke-PreG5ReconstructionAdoptionPreservation.ps1 refuses without -Execute."
}
if ([string]::IsNullOrWhiteSpace($AuditApprovalPath)) {
  throw "PLANNING ONLY: -AuditApprovalPath is required with -Execute."
}

$result = Invoke-PreG5ReconstructionAdoptionPreservationCore `
  -DestDir $DestDir `
  -ExportStamp $ExportStamp `
  -ApiDigest $ApiDigest `
  -WebDigest $WebDigest `
  -AuditApprovalPath $AuditApprovalPath `
  -ComposePinsPath $ComposePinsPath `
  -DecisionSheetPath $DecisionSheetPath `
  -ApplyOptionalAdoptedTags:$ApplyOptionalAdoptedTags `
  -SkipHouseholdGuard:$SkipHouseholdGuard `
  -SaveTimeoutMs $SaveTimeoutMs

foreach ($n in @($result.Notes)) {
  if ($n) { Write-Host ("PREG5_RECON_NOTE " + $n) }
}
if ($result.FailureReceiptPath) {
  Write-Host ("PREG5_RECON_FAIL_RECEIPT path=" + $result.FailureReceiptPath)
}

exit $result.ExitCode
