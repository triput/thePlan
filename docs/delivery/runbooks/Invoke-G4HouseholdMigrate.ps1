#Requires -Version 5.1
<#
.SYNOPSIS
  G4 household migrate: theplan 042 → 043 → 044 via committed g4-preflight.sh.

.NOTES
  PLANNING ARTIFACT until Trish EXECUTE. Requires G1 receipt (g4_eligible + cleanup_ok).
  PASS emitted only after cleanup succeeds; cleanup failure → nonzero exit (unclean).
#>
[CmdletBinding()]
param(
  [switch] $Execute,
  [Parameter(Mandatory = $true)][string] $G1ReceiptPath,
  [Parameter(Mandatory = $true)][string] $ExternalWritersQuiescedConfirm,
  [string] $ApiImage = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Household-ComposePins.ps1")
. (Join-Path $PSScriptRoot "Household-ReceiptDisposition.ps1")
. (Join-Path $PSScriptRoot "G3b-DockerProcess.ps1")

$script:HostTmpDirs = New-Object System.Collections.Generic.List[string]
$script:CleanupOk = $true
$script:CleanupNotes = New-Object System.Collections.Generic.List[string]
$script:ApiPinRels = @(
  "alembic.ini",
  "alembic/env.py",
  "alembic/versions/043_recovery_epoch.py",
  "alembic/versions/044_agent_cli_access.py",
  "app/config.py",
  "app/db.py",
  "app/models/__init__.py",
  "app/models/user.py",
  "app/models/task.py",
  "app/models/task_occurrence_disposition.py",
  "app/models/calendar.py",
  "app/models/free_busy_policy.py",
  "app/models/schedule.py",
  "app/models/scheduling_day_scoped.py",
  "app/models/availability.py",
  "app/models/enums.py",
  "app/models/scheduling_assignment.py",
  "app/models/hierarchy.py",
  "app/models/mixins.py",
  "app/models/handoff.py",
  "app/models/label.py",
  "app/models/time_map_override.py"
)

function Redact([string] $t) {
  if ([string]::IsNullOrEmpty($t)) { return $t }
  if ($env:THEPLAN_PGPASSWORD) {
    $t = $t -replace [regex]::Escape($env:THEPLAN_PGPASSWORD), "***"
  }
  if ($env:DATABASE_URL) {
    $t = $t -replace [regex]::Escape($env:DATABASE_URL), "DATABASE_URL=***"
  }
  return $t
}

function Fail([string] $msg) { throw ("G4_FAIL: " + (Redact $msg)) }

function Invoke-DockerCaptured {
  param([string[]] $DockerArgs, [string] $What)
  try {
    return Invoke-DockerCapturedCore -DockerArgs $DockerArgs -What $What -Redact { param($t) Redact $t }
  } catch {
    if ($_.Exception.Message -match '^G4_FAIL:') { throw $_.Exception.Message }
    Fail $_.Exception.Message
  }
}

function Register-HostTmpDir([string] $dir) { $script:HostTmpDirs.Add($dir) }

function Invoke-OwnedCleanup {
  foreach ($d in @($script:HostTmpDirs)) {
    try {
      if (Test-Path -LiteralPath $d) {
        Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction Stop
      }
      if (Test-Path -LiteralPath $d) {
        $script:CleanupOk = $false
        $script:CleanupNotes.Add("host_tmp_still_exists:$d")
      }
    } catch {
      $script:CleanupOk = $false
      $script:CleanupNotes.Add("host_tmp_rm_fail:" + (Redact $_.Exception.Message))
    }
  }
  $script:HostTmpDirs.Clear()

  $dbUrlCleared = $true
  if (Test-Path Env:DATABASE_URL) {
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    $dbUrlCleared = -not (Test-Path Env:DATABASE_URL)
  }
  if (-not $dbUrlCleared) {
    $script:CleanupOk = $false
    $script:CleanupNotes.Add("DATABASE_URL_still_set")
  }

  Write-Host ("g4_cleanup_ok=" + $script:CleanupOk.ToString().ToLowerInvariant() + " database_url_cleared=" + $dbUrlCleared.ToString().ToLowerInvariant())
  if ($script:CleanupNotes.Count -gt 0) {
    Write-Host ("g4_cleanup_notes=" + ($script:CleanupNotes -join "|"))
  }
  return $script:CleanupOk
}

function Parse-DbNameFromUrl([string] $url) {
  if ($url -notmatch '://') { Fail "DATABASE_URL missing scheme" }
  try {
    $normalized = $url.Replace("postgresql+psycopg://", "postgresql://").Replace("postgresql+psycopg2://", "postgresql://")
    $u = [Uri]$normalized
  } catch {
    Fail ("DATABASE_URL parse failed: " + (Redact $_.Exception.Message))
  }
  $db = $u.AbsolutePath.TrimStart("/")
  if ([string]::IsNullOrWhiteSpace($db)) { Fail "DATABASE_URL empty database" }
  if ($u.Query) { Fail "DATABASE_URL query-string forbidden" }
  $hostName = $u.Host.ToLowerInvariant()
  if ($hostName -notin @("127.0.0.1", "localhost", "postgres")) { Fail "DSN host not approved" }
  if (-not $u.IsDefaultPort -and $u.Port -ne 5432) { Fail "DSN port != 5432" }
  if ($db -notmatch '^[a-z][a-z0-9_]{0,62}$') { Fail "DATABASE_URL database unsafe" }
  return $db
}

function Get-Sha256File([string] $path) {
  return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Get-ApiSrcManifestSha([string] $root) {
  $sortedRels = [string[]]$script:ApiPinRels.Clone()
  [Array]::Sort($sortedRels, [StringComparer]::Ordinal)
  $lines = foreach ($r in $sortedRels) {
    $p = Join-Path $root ($r -replace '/', '\')
    if (-not (Test-Path -LiteralPath $p)) { Fail "ApiSrc missing pin file $r" }
    "{0}  {1}" -f (Get-Sha256File $p), $r
  }
  $blob = [Text.Encoding]::UTF8.GetBytes((($lines -join "`n") + "`n"))
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    return [BitConverter]::ToString($sha.ComputeHash($blob)).Replace("-", "").ToUpperInvariant()
  } finally { $sha.Dispose() }
}

function Invoke-Psql([string] $db, [string] $sql) {
  $r = Invoke-DockerCaptured -What "psql" -DockerArgs @(
    "exec", "-i", $script:PostgresContainer,
    "psql", "-v", "ON_ERROR_STOP=1", "-U", $script:PgUser, "-d", $db, "-tAc", $sql
  )
  return (($r.StdOut | Out-String).Trim())
}

function Assert-G1Receipt([string] $path) {
  if (-not (Test-Path -LiteralPath $path)) { Fail "G1 receipt missing: $path" }
  $r = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
  $gate = Test-G1ReceiptAllowsG4 -Receipt $r
  if (-not $gate.Ok) { Fail ("G1 receipt refused: " + $gate.Reason) }
  if (-not (Test-Path -LiteralPath ([string]$r.dump_path))) { Fail "G1 dump missing: $($r.dump_path)" }
  $shaFile = "$($r.dump_path).sha256"
  if (-not (Test-Path -LiteralPath $shaFile)) { Fail "G1 dump sha sidecar missing" }
  $expected = ((Get-Content -LiteralPath $shaFile -Raw).Trim() -split "\s+")[0].ToUpperInvariant()
  $actual = Get-Sha256File ([string]$r.dump_path)
  if ($expected -ne $actual) { Fail "G1 dump sha mismatch vs sidecar" }
  if ([string]$r.dump_sha256 -and ([string]$r.dump_sha256).ToUpperInvariant() -ne $actual) {
    Fail "G1 receipt dump_sha256 mismatch"
  }
  Write-Host ("g1_receipt_ok dump=" + $r.dump_path + " sha=" + $actual)
  return $r
}

if (-not $Execute) {
  throw "PLANNING ONLY: Invoke-G4HouseholdMigrate.ps1 refuses without -Execute (Trish G4 EXECUTE stamp required)."
}

$phase = "init"
$migrateOk = $false
$rev1 = $null
$workFailed = $false
$workError = $null

try {
  Assert-HouseholdRuntimePins
  Assert-ExternalWritersQuiesced -Evidence $ExternalWritersQuiescedConfirm -Phase "G4"
  Assert-WriterContainersStopped -Phase "G4"
  $null = Assert-G1Receipt $G1ReceiptPath

  Push-Location $script:ReleaseRoot
  try {
    $head = (git rev-parse HEAD).Trim()
    if ($head -ne $script:WantHead) { Fail "G4-R1 HEAD=$head want $($script:WantHead)" }
    $porcelain = git status --porcelain
    if ($porcelain) { Fail "G4-R1 worktree not clean" }
  } finally {
    Pop-Location
  }

  if ([string]::IsNullOrWhiteSpace($env:THEPLAN_PGPASSWORD)) {
    Fail "G4-R3 THEPLAN_PGPASSWORD not set"
  }

  $ver0 = Invoke-Psql $script:HouseholdDb "SELECT version_num FROM alembic_version"
  if ($ver0 -ne $script:ExpectAlembic042) {
    Fail "G4-R2 alembic=$ver0 want $($script:ExpectAlembic042)"
  }

  $ApiSrc = Join-Path $script:ReleaseRoot "apps\api"
  $manifest = Get-ApiSrcManifestSha $ApiSrc
  if ($manifest -ne $script:WantApiSrcManifest) {
    Fail "G4-R6 ApiSrc manifest=$manifest want $($script:WantApiSrcManifest)"
  }

  if ([string]::IsNullOrWhiteSpace($ApiImage)) {
    $ApiImage = $script:ApiImageBaseline
  }
  if ($ApiImage -notmatch '^sha256:[a-f0-9]{64}$') {
    Fail "G4-R8 ApiImage must be full sha256: digest"
  }
  Write-Host "g4_api_image=$ApiImage"

  $enc = [Uri]::EscapeDataString($env:THEPLAN_PGPASSWORD)
  $env:DATABASE_URL = "postgresql+psycopg://theplan:${enc}@127.0.0.1:5432/$($script:HouseholdDb)"
  $parsedDb = Parse-DbNameFromUrl $env:DATABASE_URL
  if ($parsedDb -ne $script:HouseholdDb) { Fail "G4-R4/R5 parsed db=$parsedDb" }
  if ($parsedDb -ne "theplan") { Fail "G4-R4 REFUSE: DSN not household theplan" }

  $userCount0 = [int](Invoke-Psql $script:HouseholdDb "SELECT COUNT(*)::text FROM users")
  $taskCount0 = [int](Invoke-Psql $script:HouseholdDb "SELECT COUNT(*)::text FROM tasks")
  $settingsCount0 = [int](Invoke-Psql $script:HouseholdDb "SELECT COUNT(*)::text FROM user_settings")
  if ($settingsCount0 -lt 1) { Fail "user_settings empty" }
  $userIds0 = Invoke-Psql $script:HouseholdDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM users"
  $taskIds0 = Invoke-Psql $script:HouseholdDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM tasks"
  Write-Host "pre_migrate users=$userCount0 tasks=$taskCount0 settings=$settingsCount0"

  $preflightHostDir = Join-Path ([System.IO.Path]::GetTempPath()) ("g4_preflight_" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Force -Path $preflightHostDir | Out-Null
  Register-HostTmpDir $preflightHostDir
  Copy-Item -LiteralPath $script:G4PreflightSh -Destination (Join-Path $preflightHostDir "preflight.sh") -Force

  $phase = "preflight_migrate"
  Invoke-DockerCaptured -What "g4 preflight+043+044" -DockerArgs @(
    "run", "--rm",
    "--network", "container:$($script:PostgresContainer)",
    "-v", "${ApiSrc}:/app:ro",
    "-v", "${preflightHostDir}:/g4:ro",
    "-w", "/app",
    "-e", "DATABASE_URL",
    "-e", "HOUSEHOLD_EXPECT_DB=theplan",
    "-e", "SEED_DEMO_USER=false",
    "-e", "ASSIST_ENABLED=false",
    "-e", "SCHEDULE_DISPATCH=external",
    "--entrypoint", "sh",
    $ApiImage,
    "/g4/preflight.sh"
  ) | Out-Null

  $phase = "postcheck"
  $rev1 = Invoke-Psql $script:HouseholdDb "SELECT version_num FROM alembic_version"
  if ($rev1 -ne $script:ExpectAlembic044) { Fail "post-migrate alembic=$rev1 want $($script:ExpectAlembic044)" }

  $gf = Invoke-Psql $script:HouseholdDb @"
SELECT COUNT(*)::text || '|' ||
       COUNT(*) FILTER (WHERE allow_agent_cli_access IS TRUE)::text || '|' ||
       COUNT(*) FILTER (WHERE allow_agent_cli_access_grandfathered IS TRUE)::text
FROM user_settings
"@
  $parts = $gf -split '\|'
  $sc = [int]$parts[0]; $allowN = [int]$parts[1]; $gfN = [int]$parts[2]
  if ($sc -ne $settingsCount0 -or $allowN -ne $sc -or $gfN -ne $sc) {
    Fail "grandfather incomplete settings=$sc allow=$allowN gf=$gfN"
  }

  $tbl = Invoke-Psql $script:HouseholdDb "SELECT CASE WHEN to_regclass('public.agent_credentials') IS NULL THEN 'f' ELSE 't' END"
  if ($tbl -ne "t") { Fail "agent_credentials missing" }

  $userCount1 = [int](Invoke-Psql $script:HouseholdDb "SELECT COUNT(*)::text FROM users")
  $taskCount1 = [int](Invoke-Psql $script:HouseholdDb "SELECT COUNT(*)::text FROM tasks")
  $userIds1 = Invoke-Psql $script:HouseholdDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM users"
  $taskIds1 = Invoke-Psql $script:HouseholdDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM tasks"
  if ($userCount1 -ne $userCount0 -or $userIds1 -ne $userIds0) { Fail "user inventory mismatch" }
  if ($taskCount1 -ne $taskCount0 -or $taskIds1 -ne $taskIds0) { Fail "task inventory mismatch" }

  Assert-WriterContainersStopped -Phase "G4-post"
  $migrateOk = $true
}
catch {
  $workFailed = $true
  $workError = Redact $_.Exception.Message
  Write-Host ("G4_FAIL phase=$phase err=" + $workError)
  Write-Host "STOP: do not G5; use Invoke-HouseholdRollbackTo042.ps1 after Trish authorize if DB advanced past 042"
}
finally {
  $null = Invoke-OwnedCleanup
}

if ($workFailed) {
  throw ("G4_FAIL: " + $workError)
}
if (-not $script:CleanupOk) {
  Write-Host "G4_UNCLEAN migrate_ok=$migrateOk — cleanup failure blocks PASS"
  exit 3
}
if (-not $migrateOk) {
  exit 1
}

Write-Host "G4_PASS alembic=$rev1 api_image=$ApiImage cleanup_ok=true"
exit 0
