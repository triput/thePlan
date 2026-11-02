#Requires -Version 5.1
<#
.SYNOPSIS
  G3b disposable migrate/restore rehearsal — PLANNING (Dex 1793592674, argv 1793592864, manifest/drain 1793593359).

.DESCRIPTION
  Do not run without Trish G3b EXECUTE + -AllowExecute.

  Secrets: THEPLAN_PGPASSWORD in process env only (never a parameter).
  docker run uses -e DATABASE_URL (name inherit). Exceptions/docker output redacted.
  Docker argv: G3b-DockerProcess.ps1 (MS command-line quoting). Preflight via mounted sh script.
  Harmless argv probe: Probe-G3bDockerArgv.ps1 (same wrapper).

.EXAMPLE

  # $env:THEPLAN_PGPASSWORD = <secret store>   # out-of-band
  powershell -NoProfile -File `
    "F:\Code Repo\ThePlan\docs\delivery\runbooks\Invoke-G3bMigrateRehearsal.ps1" `
    -AcquireReadOnlyDump `
    -ApiSrc "F:\Code Repo\ThePlan\apps\api" `
    -ApiImage "sha256:9aac7395a068d0761ad81c2339d60b69f5bd90e0cb7ef498f26d2634b0edfa36" `
    -ExpectedApiSrcManifestSha256 "B572CCC10429CA3BE9BF57E55276AAB0CF4C6934E15F41E1C5C0497077676635" `
    -AllowExecute
  Remove-Item Env:THEPLAN_PGPASSWORD,Env:DATABASE_URL -ErrorAction SilentlyContinue
#>
[CmdletBinding()]
param(
  [string] $PgHost = "127.0.0.1",
  [int] $PgPort = 5432,
  [string] $PgUser = "theplan",
  [string] $HouseholdDb = "theplan",
  [string] $DumpPath = "",
  [switch] $AcquireReadOnlyDump,
  [string] $DumpOutDir = "F:\DropFolder\backups\theplan-g3b-rehearsal",
  [string] $RehearsalDbPrefix = "theplan_g3b_r",
  [Parameter(Mandatory = $true)]
  [string] $ApiImage,
  [Parameter(Mandatory = $true)]
  [string] $ApiSrc,
  [Parameter(Mandatory = $true)]
  [string] $ExpectedApiSrcManifestSha256,
  [string] $PostgresContainer = "compose-postgres-1",
  [switch] $SkipCleanup,
  [switch] $AllowExecute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:RehearsalOk = $false
$script:RestoreOk = $false
$script:TmpCleanupOk = $true
$script:DbCleanupOk = $true
$script:CleanupOk = $false
$script:CreatedByThisRun = $false
$script:RehearsalDb = $null
$script:KeptDb = $false
$script:ContainerTmps = [System.Collections.Generic.List[string]]::new()
$script:HostTmpDirs = [System.Collections.Generic.List[string]]::new()
$script:OverallOk = $false

# Pin set: alembic env + settings engine + models imported by env.py (app.models *)
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

function Redact([string] $text) {
  if ([string]::IsNullOrEmpty($text)) { return $text }
  $t = $text
  $pw = $env:THEPLAN_PGPASSWORD
  if ($pw) { $t = $t.Replace($pw, "***") }
  if ($env:DATABASE_URL) {
    $t = $t.Replace($env:DATABASE_URL, "DATABASE_URL=***")
  }
  $t = [regex]::Replace($t, '(?i)(postgresql(?:\+psycopg2?)?://[^:\s]+):([^@\s]+)@', '$1:***@')
  $t = [regex]::Replace($t, '(?i)(PASSWORD|PWD|SECRET|TOKEN)=([^\s;]+)', '$1=***')
  return $t
}

function Fail([string] $msg) {
  # Throw so caller's try/finally always runs (do not exit here).
  throw ("G3b_FAIL: " + (Redact $msg))
}

. (Join-Path $PSScriptRoot "G3b-DockerProcess.ps1")

function Invoke-DockerCaptured {
  param([string[]] $DockerArgs, [string] $What)
  try {
    return Invoke-DockerCapturedCore -DockerArgs $DockerArgs -What $What -Redact { param($t) Redact $t }
  } catch {
    if ($_.Exception.Message -match '^G3b_FAIL:') { throw $_.Exception.Message }
    Fail $_.Exception.Message
  }
}

function Write-Utf8NoBom([string] $path, [string] $content) {
  $enc = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($path, $content, $enc)
}

function Register-HostTmpDir([string] $dir) { $script:HostTmpDirs.Add($dir) }

function Remove-HostTmpDirs {
  $ok = $true
  foreach ($d in @($script:HostTmpDirs)) {
    try {
      if (Test-Path -LiteralPath $d) {
        Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction Stop
      }
    } catch {
      Write-Host ("host_tmp_rm_error=" + (Redact $_.Exception.Message))
      $ok = $false
    }
  }
  $script:HostTmpDirs.Clear()
  return $ok
}

function Assert-SafeIdent([string] $name, [string] $label) {
  if ([string]::IsNullOrWhiteSpace($name)) { Fail "$label empty" }
  if ($name -notmatch '^[a-z][a-z0-9_]{0,62}$') {
    Fail "$label fails safe identifier grammar"
  }
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
  Assert-SafeIdent $db "DATABASE_URL database"
  return $db
}

function Get-Sha256File([string] $path) {
  return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Get-ApiSrcManifestSha([string] $root) {
  # Pin grammar: sort relative paths with ordinal (culture-invariant) order, then hash the joined lines.
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
  Assert-SafeIdent $db "psql database"
  $r = Invoke-DockerCaptured -What "psql" -DockerArgs @(
    "exec", "-i", $PostgresContainer,
    "psql", "-v", "ON_ERROR_STOP=1", "-U", $PgUser, "-d", $db, "-tAc", $sql
  )
  return (($r.StdOut | Out-String).Trim())
}

function Test-DbExists([string] $name) {
  Assert-SafeIdent $name "exists-check database"
  $n = Invoke-Psql "postgres" ("SELECT 1 FROM pg_database WHERE datname = '{0}'" -f $name)
  return ($n -eq "1")
}

function Write-DumpSidecar([string] $dumpFile, [hashtable] $meta) {
  $sha = Get-Sha256File $dumpFile
  Set-Content -LiteralPath "$dumpFile.sha256" -Value "$sha  $(Split-Path $dumpFile -Leaf)" -Encoding ascii
  ($meta + @{ dump_sha256 = $sha }) | ConvertTo-Json | Set-Content -LiteralPath "$dumpFile.meta.json" -Encoding utf8
}

function Assert-DumpSidecar([string] $dumpFile) {
  if (-not (Test-Path -LiteralPath $dumpFile)) { Fail "dump missing" }
  if (-not (Test-Path -LiteralPath "$dumpFile.sha256")) { Fail "dump .sha256 missing" }
  if (-not (Test-Path -LiteralPath "$dumpFile.meta.json")) { Fail "dump .meta.json missing" }
  $expected = ((Get-Content -LiteralPath "$dumpFile.sha256" -Raw).Trim() -split "\s+")[0].ToUpperInvariant()
  $actual = Get-Sha256File $dumpFile
  if ($expected -ne $actual) { Fail "dump sha mismatch" }
  $meta = Get-Content -LiteralPath "$dumpFile.meta.json" -Raw | ConvertFrom-Json
  if ($meta.source_alembic -ne "042_task_occurrence_dispositions") { Fail "dump meta alembic != 042" }
  if ($meta.source_database -ne $HouseholdDb) { Fail "dump meta source_database mismatch" }
  Write-Host "dump_ok sha=$actual taken_utc=$($meta.taken_utc)"
}

function Register-ContainerTmp([string] $path) { $script:ContainerTmps.Add($path) }

function Remove-ContainerTmps {
  $ok = $true
  foreach ($p in @($script:ContainerTmps)) {
    try {
      Invoke-DockerCaptured -What "rm container tmp" -DockerArgs @("exec", $PostgresContainer, "rm", "-f", $p) | Out-Null
    } catch {
      Write-Host ("tmp_rm_error=" + (Redact $_.Exception.Message))
      $ok = $false
    }
  }
  $script:ContainerTmps.Clear()
  if (-not (Remove-HostTmpDirs)) { $ok = $false }
  $script:TmpCleanupOk = $ok
}

function Remove-RehearsalDb {
  if ($SkipCleanup) {
    $script:KeptDb = $true
    $script:DbCleanupOk = $false
    Write-Host "cleanup_mode=SkipCleanup rehearsal_db=$($script:RehearsalDb) kept=True"
    Write-Host "db_cleanup_ok=False"
    return
  }
  if (-not $script:CreatedByThisRun -or [string]::IsNullOrWhiteSpace($script:RehearsalDb)) {
    Write-Host "db_cleanup_skipped=not_created_by_this_run"
    $script:DbCleanupOk = $true
    Write-Host "db_cleanup_ok=True"
    return
  }
  Assert-SafeIdent $script:RehearsalDb "cleanup database"
  Invoke-Psql "postgres" ("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{0}' AND pid <> pg_backend_pid()" -f $script:RehearsalDb) | Out-Null
  Invoke-Psql "postgres" ("DROP DATABASE `"{0}`"" -f $script:RehearsalDb) | Out-Null
  $script:CreatedByThisRun = $false
  $script:DbCleanupOk = $true
  Write-Host "dropped_db=$($script:RehearsalDb)"
  Write-Host "db_cleanup_ok=True"
}

# --- gates ---
if (-not $AllowExecute) {
  Fail "Refusing to run: pass -AllowExecute only after Trish G3b EXECUTE stamp"
}

$PgPassword = $env:THEPLAN_PGPASSWORD
if ([string]::IsNullOrWhiteSpace($PgPassword)) {
  Fail "THEPLAN_PGPASSWORD empty — set in process env (no password parameter)"
}

Assert-SafeIdent $PgUser "PgUser"
Assert-SafeIdent $HouseholdDb "HouseholdDb"
Assert-SafeIdent $RehearsalDbPrefix "RehearsalDbPrefix"
if ($PostgresContainer -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$') { Fail "PostgresContainer unsafe" }
if ($ApiImage -notmatch '^sha256:[a-fA-F0-9]{64}$') {
  Fail "ApiImage must be explicit digest sha256:<64 hex> (no running-container fallback)"
}
$ExpectedApiSrcManifestSha256 = $ExpectedApiSrcManifestSha256.ToUpperInvariant()
if ($ExpectedApiSrcManifestSha256 -notmatch '^[A-F0-9]{64}$') { Fail "ExpectedApiSrcManifestSha256 must be 64 hex" }

$ApiSrc = (Resolve-Path -LiteralPath $ApiSrc).Path
$actualManifest = Get-ApiSrcManifestSha $ApiSrc
Write-Host "api_src_manifest_sha256=$actualManifest"
if ($actualManifest -ne $ExpectedApiSrcManifestSha256) {
  Fail "ApiSrc manifest drift: actual!=expected (refusing before dump/create)"
}
Write-Host "api_src_manifest_ok=True"
Write-Host "alembic_image=$ApiImage"

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmss").ToLowerInvariant()
$inv = ([guid]::NewGuid().ToString("N").Substring(0, 10))
$script:RehearsalDb = ("{0}_{1}_{2}" -f $RehearsalDbPrefix, $stamp, $inv).ToLowerInvariant()
Assert-SafeIdent $script:RehearsalDb "RehearsalDb"
if ($script:RehearsalDb -ceq "theplan") { Fail "REFUSE: rehearsal DB is household name" }

Write-Host "g3b_rehearsal_db=$($script:RehearsalDb)"
Write-Host "note=no_household_service_stop"

try {
  New-Item -ItemType Directory -Force -Path $DumpOutDir | Out-Null

  if ($AcquireReadOnlyDump) {
    $hhRev = Invoke-Psql $HouseholdDb "SELECT version_num FROM alembic_version"
    if ($hhRev -ne "042_task_occurrence_dispositions") { Fail "household alembic != 042" }
    $DumpPath = Join-Path $DumpOutDir ("household042-readonly-{0}-{1}.dump" -f $stamp, $inv)
    Write-Host "acquiring_read_only_dump=$DumpPath"
    $tmpIn = "/tmp/g3b_acq_$inv.dump"
    Register-ContainerTmp $tmpIn
    Invoke-DockerCaptured -What "pg_dump" -DockerArgs @(
      "exec", $PostgresContainer, "pg_dump", "-U", $PgUser, "-d", $HouseholdDb, "-Fc", "--no-owner", "-f", $tmpIn
    ) | Out-Null
    Invoke-DockerCaptured -What "docker cp dump" -DockerArgs @("cp", "${PostgresContainer}:${tmpIn}", $DumpPath) | Out-Null
    Invoke-DockerCaptured -What "rm acq tmp" -DockerArgs @("exec", $PostgresContainer, "rm", "-f", $tmpIn) | Out-Null
    [void]$script:ContainerTmps.Remove($tmpIn)
    if (-not (Test-Path -LiteralPath $DumpPath) -or ((Get-Item $DumpPath).Length -lt 1)) { Fail "acquired dump empty" }
    Write-DumpSidecar $DumpPath @{
      taken_utc       = (Get-Date).ToUniversalTime().ToString("o")
      source_database = $HouseholdDb
      source_alembic  = $hhRev
      mode            = "read_only_no_quiesce"
      rehearsal_db    = $script:RehearsalDb
      note            = "Not G1 authoritative quiesced backup"
    }
  }

  if ([string]::IsNullOrWhiteSpace($DumpPath)) { Fail "DumpPath required (or -AcquireReadOnlyDump)" }
  Assert-DumpSidecar $DumpPath

  if (Test-DbExists $script:RehearsalDb) {
    Fail "REFUSE: rehearsal DB already exists"
  }

  Invoke-Psql "postgres" ("CREATE DATABASE `"{0}`" OWNER `"{1}`"" -f $script:RehearsalDb, $PgUser) | Out-Null
  $script:CreatedByThisRun = $true
  Write-Host "created_db=$($script:RehearsalDb)"

  $tmpRestore = "/tmp/g3b_restore_$inv.dump"
  Register-ContainerTmp $tmpRestore
  Invoke-DockerCaptured -What "docker cp restore" -DockerArgs @("cp", $DumpPath, "${PostgresContainer}:${tmpRestore}") | Out-Null
  Invoke-DockerCaptured -What "pg_restore" -DockerArgs @(
    "exec", $PostgresContainer, "pg_restore", "-U", $PgUser, "-d", $script:RehearsalDb,
    "--no-owner", "--role=$PgUser", "--exit-on-error", $tmpRestore
  ) | Out-Null
  Invoke-DockerCaptured -What "rm restore tmp" -DockerArgs @("exec", $PostgresContainer, "rm", "-f", $tmpRestore) | Out-Null
  [void]$script:ContainerTmps.Remove($tmpRestore)

  $rev0 = Invoke-Psql $script:RehearsalDb "SELECT version_num FROM alembic_version"
  if ($rev0 -ne "042_task_occurrence_dispositions") { Fail "after restore alembic != 042" }

  $userCount0 = [int](Invoke-Psql $script:RehearsalDb "SELECT COUNT(*)::text FROM users")
  $taskCount0 = [int](Invoke-Psql $script:RehearsalDb "SELECT COUNT(*)::text FROM tasks")
  $settingsCount0 = [int](Invoke-Psql $script:RehearsalDb "SELECT COUNT(*)::text FROM user_settings")
  if ($settingsCount0 -lt 1) { Fail "user_settings empty" }
  $userIds0 = Invoke-Psql $script:RehearsalDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM users"
  $taskIds0 = Invoke-Psql $script:RehearsalDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM tasks"
  Write-Host "pre_migrate users=$userCount0 tasks=$taskCount0 settings=$settingsCount0"

  $enc = [Uri]::EscapeDataString($PgPassword)
  $env:DATABASE_URL = "postgresql+psycopg://${PgUser}:${enc}@127.0.0.1:5432/$($script:RehearsalDb)"
  $parsedDb = Parse-DbNameFromUrl $env:DATABASE_URL
  if ($parsedDb -ne $script:RehearsalDb) { Fail "parsed DSN db != rehearsal" }
  if ($parsedDb -ceq "theplan") { Fail "REFUSE: alembic DSN targets household" }
  Write-Host "alembic_dsn_db=$parsedDb"

  # Preflight + migrate: use get_settings().database_url (same as alembic/env.py)
  $preflight = @'
set -e
python - <<'PY'
import os, sys
from urllib.parse import urlparse
from app.config import get_settings

settings = get_settings()
resolved = settings.database_url
env_url = os.environ.get("DATABASE_URL", "")
# Never print URLs. Compare normalized DB names / hosts.
def db_name(url: str) -> str:
    u = url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
    return urlparse(u).path.lstrip("/")

want = os.environ["G3B_EXPECT_DB"]
got = db_name(resolved)
if got != want:
    sys.stderr.write("settings_db_mismatch\n")
    sys.exit(3)
if db_name(env_url) != want:
    sys.stderr.write("env_db_mismatch\n")
    sys.exit(3)
if resolved != env_url and db_name(resolved) == db_name(env_url):
    # password encoding differences OK if db matches; still require same target db
    pass

from sqlalchemy import create_engine, text
e = create_engine(resolved)
with e.connect() as c:
    db = c.execute(text("select current_database()")).scalar()
    ver = c.execute(text("select version_num from alembic_version")).scalar()
if db != want:
    sys.stderr.write("preflight_db_mismatch\n")
    sys.exit(3)
if ver != "042_task_occurrence_dispositions":
    sys.stderr.write("preflight_alembic_mismatch\n")
    sys.exit(4)
print("preflight_ok_via_get_settings", db, ver)
PY
test -f /app/alembic/env.py
test -f /app/alembic/versions/043_recovery_epoch.py
test -f /app/alembic/versions/044_agent_cli_access.py
alembic upgrade 043_recovery_epoch
alembic upgrade 044_agent_cli_access
python - <<'PY'
import os, sys
from app.config import get_settings
from sqlalchemy import create_engine, text
resolved = get_settings().database_url
e = create_engine(resolved)
with e.connect() as c:
    ver = c.execute(text("select version_num from alembic_version")).scalar()
    db = c.execute(text("select current_database()")).scalar()
want = os.environ["G3B_EXPECT_DB"]
if db != want or ver != "044_agent_cli_access":
    sys.stderr.write("postcheck_mismatch\n")
    sys.exit(5)
print("postcheck_ok_via_get_settings", db, ver)
PY
'@

  $preflightHostDir = Join-Path ([System.IO.Path]::GetTempPath()) ("g3b_preflight_" + $inv)
  New-Item -ItemType Directory -Force -Path $preflightHostDir | Out-Null
  Register-HostTmpDir $preflightHostDir
  Write-Utf8NoBom (Join-Path $preflightHostDir "preflight.sh") $preflight

  Invoke-DockerCaptured -What "alembic preflight+043+044" -DockerArgs @(
    "run", "--rm",
    "--network", "container:$PostgresContainer",
    "-v", "${ApiSrc}:/app:ro",
    "-v", "${preflightHostDir}:/g3b:ro",
    "-w", "/app",
    "-e", "DATABASE_URL",
    "-e", "G3B_EXPECT_DB=$($script:RehearsalDb)",
    "-e", "SEED_DEMO_USER=false",
    "-e", "ASSIST_ENABLED=false",
    "-e", "SCHEDULE_DISPATCH=external",
    "--entrypoint", "sh",
    $ApiImage,
    "/g3b/preflight.sh"
  ) | Out-Null

  $rev1 = Invoke-Psql $parsedDb "SELECT version_num FROM alembic_version"
  if ($rev1 -ne "044_agent_cli_access") { Fail "post-migrate alembic != 044" }

  $gf = Invoke-Psql $parsedDb @"
SELECT COUNT(*)::text || '|' ||
       COUNT(*) FILTER (WHERE allow_agent_cli_access IS TRUE)::text || '|' ||
       COUNT(*) FILTER (WHERE allow_agent_cli_access_grandfathered IS TRUE)::text
FROM user_settings
"@
  $parts = $gf -split '\|'
  $sc = [int]$parts[0]; $allowN = [int]$parts[1]; $gfN = [int]$parts[2]
  if ($sc -ne $settingsCount0 -or $allowN -ne $sc -or $gfN -ne $sc) { Fail "grandfather incomplete" }

  $tbl = Invoke-Psql $parsedDb "SELECT CASE WHEN to_regclass('public.agent_credentials') IS NULL THEN 'f' ELSE 't' END"
  if ($tbl -ne "t") { Fail "agent_credentials missing" }

  $userCount1 = [int](Invoke-Psql $parsedDb "SELECT COUNT(*)::text FROM users")
  $taskCount1 = [int](Invoke-Psql $parsedDb "SELECT COUNT(*)::text FROM tasks")
  $userIds1 = Invoke-Psql $parsedDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM users"
  $taskIds1 = Invoke-Psql $parsedDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM tasks"
  if ($userCount1 -ne $userCount0 -or $userIds1 -ne $userIds0) { Fail "user inventory mismatch" }
  if ($taskCount1 -ne $taskCount0 -or $taskIds1 -ne $taskIds0) { Fail "task inventory mismatch" }

  $script:RehearsalOk = $true
  Write-Host "rehearsal_ok=True"

  Invoke-Psql "postgres" ("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{0}' AND pid <> pg_backend_pid()" -f $script:RehearsalDb) | Out-Null
  Invoke-Psql "postgres" ("DROP DATABASE `"{0}`"" -f $script:RehearsalDb) | Out-Null
  $script:CreatedByThisRun = $false
  Invoke-Psql "postgres" ("CREATE DATABASE `"{0}`" OWNER `"{1}`"" -f $script:RehearsalDb, $PgUser) | Out-Null
  $script:CreatedByThisRun = $true

  $tmpRestore2 = "/tmp/g3b_restore2_$inv.dump"
  Register-ContainerTmp $tmpRestore2
  Invoke-DockerCaptured -What "docker cp restore2" -DockerArgs @("cp", $DumpPath, "${PostgresContainer}:${tmpRestore2}") | Out-Null
  Invoke-DockerCaptured -What "pg_restore drill" -DockerArgs @(
    "exec", $PostgresContainer, "pg_restore", "-U", $PgUser, "-d", $script:RehearsalDb,
    "--no-owner", "--role=$PgUser", "--exit-on-error", $tmpRestore2
  ) | Out-Null
  Invoke-DockerCaptured -What "rm restore2" -DockerArgs @("exec", $PostgresContainer, "rm", "-f", $tmpRestore2) | Out-Null
  [void]$script:ContainerTmps.Remove($tmpRestore2)

  $rev2 = Invoke-Psql $script:RehearsalDb "SELECT version_num FROM alembic_version"
  if ($rev2 -ne "042_task_occurrence_dispositions") { Fail "restore drill alembic != 042" }
  $userCount2 = [int](Invoke-Psql $script:RehearsalDb "SELECT COUNT(*)::text FROM users")
  $taskCount2 = [int](Invoke-Psql $script:RehearsalDb "SELECT COUNT(*)::text FROM tasks")
  $userIds2 = Invoke-Psql $script:RehearsalDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM users"
  $taskIds2 = Invoke-Psql $script:RehearsalDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM tasks"
  if ($userCount2 -ne $userCount0 -or $userIds2 -ne $userIds0) { Fail "restore drill user mismatch" }
  if ($taskCount2 -ne $taskCount0 -or $taskIds2 -ne $taskIds0) { Fail "restore drill task mismatch" }

  $script:RestoreOk = $true
  Write-Host "restore_ok=True"
}
catch {
  Write-Host ("g3b_error=" + (Redact $_.Exception.Message))
  $script:RehearsalOk = $false
  $script:RestoreOk = $false
  # fall through to finally; then exit 2
}
finally {
  try { Remove-ContainerTmps } catch {
    Write-Host ("tmp_cleanup_error=" + (Redact $_.Exception.Message))
    $script:TmpCleanupOk = $false
  }
  try { Remove-RehearsalDb } catch {
    Write-Host ("db_cleanup_error=" + (Redact $_.Exception.Message))
    $script:DbCleanupOk = $false
  }
  Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue

  $script:CleanupOk = ($script:TmpCleanupOk -and $script:DbCleanupOk)
  Write-Host "tmp_cleanup_ok=$($script:TmpCleanupOk)"
  Write-Host "db_cleanup_ok=$($script:DbCleanupOk)"
  Write-Host "cleanup_ok=$($script:CleanupOk)"
  Write-Host "rehearsal_ok=$($script:RehearsalOk)"
  Write-Host "restore_ok=$($script:RestoreOk)"
  Write-Host "kept_db=$($script:KeptDb)"

  # SkipCleanup / incomplete cleanup => overall failure (retained DB is separate outcome)
  $script:OverallOk = ($script:RehearsalOk -and $script:RestoreOk -and $script:CleanupOk -and (-not $script:KeptDb))
  Write-Host "overall_ok=$($script:OverallOk)"
}

if (-not $script:OverallOk) { exit 2 }
exit 0
