#Requires -Version 5.1
<#
.SYNOPSIS
  Dump thePlan Postgres from Docker Compose into backups/.

.DESCRIPTION
  Wraps the Compose pg_dump one-liner. Intended for Windows Task Scheduler.

  Env overrides:
    COMPOSE_FILE       — default: <repo>/infra/compose/compose.yaml
    BACKUP_DIR         — default: <repo>/backups
    BACKUP_KEEP_DAYS   — default: 14
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ComposeFile = if ($env:COMPOSE_FILE) { $env:COMPOSE_FILE } else { Join-Path $RepoRoot "infra\compose\compose.yaml" }
$BackupDir = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { Join-Path $RepoRoot "backups" }
$KeepDays = 14
if ($env:BACKUP_KEEP_DAYS -match '^\d+$') {
  $KeepDays = [int]$env:BACKUP_KEEP_DAYS
}

if (-not (Test-Path $ComposeFile)) {
  Write-Error "Compose file not found: $ComposeFile"
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outFile = Join-Path $BackupDir "theplan-$stamp.sql"

Write-Host "Backing up to $outFile"
# Stream dump to file (cmd redirection keeps binary/text clean for SQL).
$composeArg = $ComposeFile.Replace('"', '""')
$outArg = $outFile.Replace('"', '""')
cmd /c "docker compose -f `"$composeArg`" exec -T postgres pg_dump -U theplan theplan > `"$outArg`""
if ($LASTEXITCODE -ne 0) {
  if (Test-Path $outFile) { Remove-Item $outFile -Force }
  Write-Error "pg_dump failed (is Compose postgres running?). Exit code $LASTEXITCODE"
}
if (-not (Test-Path $outFile) -or (Get-Item $outFile).Length -eq 0) {
  Write-Error "Backup file missing or empty: $outFile"
}

$cutoff = (Get-Date).AddDays(-$KeepDays)
Get-ChildItem -Path $BackupDir -Filter "theplan-*.sql" -File |
  Where-Object { $_.LastWriteTime -lt $cutoff } |
  ForEach-Object {
    Write-Host "Pruning $($_.Name)"
    Remove-Item $_.FullName -Force
  }

Write-Host "Done. Kept dumps newer than $KeepDays day(s)."
