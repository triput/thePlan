#Requires -Version 5.1
<#
.SYNOPSIS
  Opt-in live Postgres proof for agent_credentials absent/present catalog probe SQL.

.NOTES
  PLANNING until -Execute (no live docker in default Validate-PreG5SnapshotFailurePaths suite).
  Requires real Docker; clears injected PreG5DockerRunner for the run.
  Uses pinned Postgres image digest, dedicated container name, isolated bridge network, verified cleanup.
  Alternate opt-in: env PREG5_LIVE_SQL_BOUNDARY=1 or Validate-PreG5DisposableOrchestration -LiveSqlBoundary (orchestration only).
#>
[CmdletBinding()]
param(
  [switch] $Execute,
  [string] $PostgresImage = "sha256:93d55776e04376e19adb2733e3ccebb4392ee7dd86d8ff238503b30fe719c84f",
  [int] $DockerTimeoutMs = 120000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "PreG5-SnapshotHelpers.ps1")
. (Join-Path $PSScriptRoot "PreG5-DisposableValidationLib.ps1")

if (-not $Execute) {
  throw "PLANNING ONLY: Invoke-PreG5DisposableAgentCredentialsSqlBoundaryLive.ps1 refuses without -Execute."
}

if ($null -ne $script:PreG5DockerRunner) {
  throw "PREG5_DISP_FAIL: live SQL boundary refuses while PreG5DockerRunner is injected; run from a fresh shell."
}

$proof = Invoke-PreG5DisposableAgentCredentialsAbsentSqlBoundaryProof `
  -PostgresImage $PostgresImage `
  -DockerTimeoutMs $DockerTimeoutMs `
  -AllowLivePostgres

if (-not $proof.live_postgres) {
  throw ("PREG5_DISP_FAIL: live SQL boundary did not complete live_postgres mode=" + [string]$proof.mode + " skip_reason=" + [string]$proof.skip_reason)
}

Write-Host ("PREG5_LIVE_SQL_BOUNDARY_OK mode=" + [string]$proof.mode)
exit 0
