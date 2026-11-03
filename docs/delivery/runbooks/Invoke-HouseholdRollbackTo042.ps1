#Requires -Version 5.1
<#
.SYNOPSIS
  Paired household rollback to 042: recreate empty theplan + pin API and pre-cutover web digests.

.NOTES
  PLANNING ARTIFACT until Trish EXECUTE.
  Always pins API + web to pre-cutover digests and verifies .Image.
  Renamed hold DB is ALWAYS retained by this package — disposal is a separate reviewed op later.
  Emits ROLLBACK_BASIC_OK (exit 4) or unclean/fail — never drops the recovery copy.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string] $G1DumpPath,
  [Parameter(Mandatory = $true)][string] $ExternalWritersQuiescedConfirm,
  [switch] $Execute,
  [string] $ApiImage = "",
  [string] $WebImage = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Household-ComposePins.ps1")
. (Join-Path $PSScriptRoot "Household-ReceiptDisposition.ps1")
. (Join-Path $PSScriptRoot "G3b-DockerProcess.ps1")

$script:ContainerTmps = New-Object System.Collections.Generic.List[string]
$script:OwnedHoldDb = $null
$script:HoldDbCreated = $false
$script:CleanupOk = $true
$script:CleanupNotes = New-Object System.Collections.Generic.List[string]

function Redact([string] $t) {
  if ([string]::IsNullOrEmpty($t)) { return $t }
  if ($env:THEPLAN_PGPASSWORD) {
    $t = $t -replace [regex]::Escape($env:THEPLAN_PGPASSWORD), "***"
  }
  return $t
}

function Fail([string] $msg) { throw ("ROLLBACK_FAIL: " + (Redact $msg)) }

function Invoke-DockerCaptured {
  param([string[]] $DockerArgs, [string] $What)
  try {
    return Invoke-DockerCapturedCore -DockerArgs $DockerArgs -What $What -Redact { param($t) Redact $t }
  } catch {
    if ($_.Exception.Message -match '^ROLLBACK_FAIL:') { throw $_.Exception.Message }
    Fail $_.Exception.Message
  }
}

function Invoke-Psql([string] $db, [string] $sql) {
  $r = Invoke-DockerCaptured -What "psql" -DockerArgs @(
    "exec", "-i", $script:PostgresContainer,
    "psql", "-v", "ON_ERROR_STOP=1", "-U", $script:PgUser, "-d", $db, "-tAc", $sql
  )
  return (($r.StdOut | Out-String).Trim())
}

function Test-DbExists([string] $name) {
  $n = Invoke-Psql "postgres" ("SELECT 1 FROM pg_database WHERE datname = '{0}'" -f $name)
  return ($n -eq "1")
}

function Invoke-OwnedCleanup {
  # Container tmps only. Hold DB is never dropped by this package.
  foreach ($p in @($script:ContainerTmps)) {
    try {
      Invoke-DockerCaptured -What "rm container tmp" -DockerArgs @(
        "exec", $script:PostgresContainer, "rm", "-f", $p
      ) | Out-Null
    } catch {
      $script:CleanupOk = $false
      $script:CleanupNotes.Add("container_tmp_rm_fail:" + (Redact $_.Exception.Message))
    }
  }
  $script:ContainerTmps.Clear()

  if ($script:HoldDbCreated -and $script:OwnedHoldDb) {
    $script:CleanupNotes.Add("hold_db_retained_by_design:" + $script:OwnedHoldDb)
    Write-Host ("rollback_hold_retained=" + $script:OwnedHoldDb + " (disposal out of scope for this package)")
  }

  Write-Host ("rollback_cleanup_ok=" + $script:CleanupOk.ToString().ToLowerInvariant())
  if ($script:CleanupNotes.Count -gt 0) {
    Write-Host ("rollback_cleanup_notes=" + ($script:CleanupNotes -join "|"))
  }
  return $script:CleanupOk
}

function Assert-DumpSidecar([string] $dumpFile) {
  if (-not (Test-Path -LiteralPath $dumpFile)) { Fail "dump missing: $dumpFile" }
  if (-not (Test-Path -LiteralPath "$dumpFile.sha256")) { Fail "dump .sha256 missing" }
  if (-not (Test-Path -LiteralPath "$dumpFile.meta.json")) { Fail "dump .meta.json missing" }
  $expected = ((Get-Content -LiteralPath "$dumpFile.sha256" -Raw).Trim() -split "\s+")[0].ToUpperInvariant()
  $actual = (Get-FileHash -LiteralPath $dumpFile -Algorithm SHA256).Hash.ToUpperInvariant()
  if ($expected -ne $actual) { Fail "dump sha mismatch" }
  $meta = Get-Content -LiteralPath "$dumpFile.meta.json" -Raw | ConvertFrom-Json
  if ($meta.source_alembic -ne $script:ExpectAlembic042) { Fail "dump meta alembic != 042" }
  if ($meta.source_database -ne $script:HouseholdDb) { Fail "dump meta source_database mismatch" }
  Write-Host "dump_ok sha=$actual taken_utc=$($meta.taken_utc)"
  return $meta
}

function Wait-HttpStatus {
  param(
    [string] $Uri,
    [int[]] $AcceptStatus,
    [int] $TimeoutSec = 90,
    [string] $Label
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  do {
    try {
      try {
        $resp = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
        $code = [int]$resp.StatusCode
      } catch [System.Net.WebException] {
        $hr = $_.Exception.Response
        if ($hr) { $code = [int]$hr.StatusCode } else { throw }
      }
      if ($AcceptStatus -contains $code) {
        Write-Host ("{0}_ok status={1} uri={2}" -f $Label, $code, $Uri)
        return $code
      }
    } catch {
      Start-Sleep -Seconds 2
    }
  } while ((Get-Date) -lt $deadline)
  Fail "$Label not in [$($AcceptStatus -join ',')] within ${TimeoutSec}s ($Uri)"
}

if (-not $Execute) {
  throw "PLANNING ONLY: Invoke-HouseholdRollbackTo042.ps1 refuses without -Execute (Trish rollback EXECUTE stamp required)."
}

if ([string]::IsNullOrWhiteSpace($ApiImage)) { $ApiImage = $script:ApiImageBaseline }
if ([string]::IsNullOrWhiteSpace($WebImage)) { $WebImage = $script:WebImageBaseline }
if ($ApiImage -notmatch '^sha256:[a-f0-9]{64}$') { Fail "ApiImage must be full sha256 digest" }
if ($WebImage -notmatch '^sha256:[a-f0-9]{64}$') { Fail "WebImage must be full sha256 digest" }

$inv = (Get-Date -Format "yyyyMMddHHmmss") + ([guid]::NewGuid().ToString("N").Substring(0, 8))
$holdDb = "theplan_rb_hold_$inv"
if ($holdDb.Length -gt 63) { Fail "hold db name too long" }

$workFailed = $false
$workError = $null
$basicRecoveryOk = $false
$ver = $null

try {
  Assert-HouseholdRuntimePins
  Assert-ExternalWritersQuiesced -Evidence $ExternalWritersQuiescedConfirm -Phase "rollback"
  Assert-WriterContainersStopped -Phase "rollback"
  $meta = Assert-DumpSidecar $G1DumpPath

  Invoke-DockerCaptured -What "inspect api baseline" -DockerArgs @(
    "image", "inspect", $ApiImage, "--format", "{{.Id}}"
  ) | Out-Null
  Invoke-DockerCaptured -What "inspect web pre-cutover" -DockerArgs @(
    "image", "inspect", $WebImage, "--format", "{{.Id}}"
  ) | Out-Null

  $wantUsers = [int]$meta.source_users
  $wantTasks = [int]$meta.source_tasks
  $wantSettings = [int]$meta.source_settings
  $wantUserIds = [string]$meta.source_user_ids
  $wantTaskIds = [string]$meta.source_task_ids
  if ($wantUsers -lt 1) { Fail "dump meta missing source_users" }

  $composeArgs = Get-HouseholdComposeArgs
  Invoke-DockerCaptured -What "stop api web scheduler" -DockerArgs (
    @("compose") + $composeArgs + @("stop", "api", "web", "scheduler")
  ) | Out-Null

  Write-Host "rollback_rename_household_to_hold db=$holdDb"
  if (Test-DbExists $holdDb) { Fail "REFUSE: hold db already exists $holdDb" }
  Invoke-Psql "postgres" @"
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$($script:HouseholdDb)' AND pid <> pg_backend_pid()
"@ | Out-Null

  Invoke-DockerCaptured -What "rename theplan to hold" -DockerArgs @(
    "exec", $script:PostgresContainer,
    "psql", "-U", $script:PgUser, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
    "-c", "ALTER DATABASE $($script:HouseholdDb) RENAME TO $holdDb"
  ) | Out-Null
  $script:OwnedHoldDb = $holdDb
  $script:HoldDbCreated = $true

  Invoke-DockerCaptured -What "create empty theplan" -DockerArgs @(
    "exec", $script:PostgresContainer,
    "psql", "-U", $script:PgUser, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
    "-c", "CREATE DATABASE $($script:HouseholdDb) OWNER $($script:PgUser)"
  ) | Out-Null

  $ctmp = "/tmp/rollback_g1_$inv.dump"
  $script:ContainerTmps.Add($ctmp)
  Invoke-DockerCaptured -What "cp dump into postgres" -DockerArgs @(
    "cp", $G1DumpPath, "${script:PostgresContainer}:${ctmp}"
  ) | Out-Null

  Write-Host "rollback_pg_restore_empty_target --exit-on-error"
  Invoke-DockerCaptured -What "pg_restore household empty" -DockerArgs @(
    "exec", $script:PostgresContainer,
    "pg_restore", "-U", $script:PgUser, "-d", $script:HouseholdDb,
    "--no-owner", "--exit-on-error", $ctmp
  ) | Out-Null
  Invoke-DockerCaptured -What "rm restore dump" -DockerArgs @(
    "exec", $script:PostgresContainer, "rm", "-f", $ctmp
  ) | Out-Null
  [void]$script:ContainerTmps.Remove($ctmp)

  $ver = Invoke-Psql $script:HouseholdDb "SELECT version_num FROM alembic_version"
  if ($ver -ne $script:ExpectAlembic042) {
    Fail "after restore alembic=$ver want $($script:ExpectAlembic042)"
  }

  $ac = Invoke-Psql $script:HouseholdDb "SELECT CASE WHEN to_regclass('public.agent_credentials') IS NULL THEN 'absent' ELSE 'present' END"
  if ($ac -ne "absent") { Fail "044-only object agent_credentials still present after recreate-restore" }

  $users1 = [int](Invoke-Psql $script:HouseholdDb "SELECT COUNT(*)::text FROM users")
  $tasks1 = [int](Invoke-Psql $script:HouseholdDb "SELECT COUNT(*)::text FROM tasks")
  $settings1 = [int](Invoke-Psql $script:HouseholdDb "SELECT COUNT(*)::text FROM user_settings")
  $userIds1 = Invoke-Psql $script:HouseholdDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM users"
  $taskIds1 = Invoke-Psql $script:HouseholdDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM tasks"
  if ($users1 -ne $wantUsers -or $userIds1 -ne $wantUserIds) { Fail "restored user inventory != dump meta" }
  if ($tasks1 -ne $wantTasks -or $taskIds1 -ne $wantTaskIds) { Fail "restored task inventory != dump meta" }
  if ($wantSettings -gt 0 -and $settings1 -ne $wantSettings) { Fail "restored settings count != dump meta" }

  Write-Host "rollback_db_ok alembic=$ver agent_credentials=absent inventories=match"

  Write-Host "rollback_api_image=$ApiImage"
  Invoke-DockerCaptured -What "tag api baseline" -DockerArgs @("tag", $ApiImage, "compose-api:latest") | Out-Null
  Write-Host "rollback_web_image_precutover=$WebImage"
  Invoke-DockerCaptured -What "tag web pre-cutover" -DockerArgs @("tag", $WebImage, "compose-web:latest") | Out-Null

  $composeApi = Get-HouseholdComposeArgs -With042Pin
  Invoke-DockerCaptured -What "up api with 042 pin" -DockerArgs (
    @("compose") + $composeApi + @("up", "-d", "--force-recreate", "--no-deps", "api")
  ) | Out-Null
  $apiId = (docker inspect compose-api-1 --format "{{.Image}}" 2>$null)
  if ($apiId -ne $ApiImage) { Fail "compose-api-1 Image=$apiId want $ApiImage" }

  $composeWeb = Get-HouseholdComposeArgs
  Invoke-DockerCaptured -What "up web pre-cutover digest" -DockerArgs (
    @("compose") + $composeWeb + @("up", "-d", "--force-recreate", "--no-deps", "web")
  ) | Out-Null
  $webId = (docker inspect compose-web-1 --format "{{.Image}}" 2>$null)
  if ($webId -ne $WebImage) { Fail "compose-web-1 Image=$webId want pre-cutover $WebImage" }
  Write-Host "rollback_web_digest_verified image=$webId"

  Wait-HttpStatus -Uri "http://127.0.0.1:8000/health" -AcceptStatus @(200) -Label "basic_api_health"
  Wait-HttpStatus -Uri "http://127.0.0.1:8080/" -AcceptStatus @(200) -Label "basic_web_health"
  Wait-HttpStatus -Uri "http://127.0.0.1:8000/api/v1/auth/me" -AcceptStatus @(401) -Label "basic_auth_stack_unauthenticated"

  $sched = (docker inspect compose-scheduler-1 --format "{{.State.Running}}" 2>$null)
  if ($sched -ne "false") { Fail "scheduler Running=$sched after rollback — stop it" }

  $basicRecoveryOk = $true
  Write-Host "ROLLBACK_BASIC_OK alembic=$ver api=$ApiImage web=$WebImage hold_retained=$holdDb"
}
catch {
  $workFailed = $true
  $workError = Redact $_.Exception.Message
  Write-Host ("ROLLBACK_FAIL err=" + $workError)
}
finally {
  $null = Invoke-OwnedCleanup
}

if ($workFailed) {
  throw ("ROLLBACK_FAIL: " + $workError)
}

# Cleanup failure evaluated BEFORE basic-only exit so unclean is never hidden.
if (-not $script:CleanupOk) {
  Write-Host "ROLLBACK_UNCLEAN basic_recovery=$basicRecoveryOk hold_retained=$($script:OwnedHoldDb) — cleanup failure blocks BASIC_OK disposition"
  exit 3
}

$disp = Get-RollbackBasicDisposition -BasicRecoveryOk $basicRecoveryOk -CleanupOk $script:CleanupOk -HoldDbName $script:OwnedHoldDb
Write-Host ("rollback_disposition=" + ($disp | ConvertTo-Json -Compress))

if (-not $basicRecoveryOk) {
  exit 1
}

# Success path for this package: basic recovery with hold retained. No ROLLBACK_PASS / no dispose.
Write-Host "ROLLBACK_BASIC_OK_ONLY hold_retained=$($script:OwnedHoldDb) cleanup_ok=true dispose=out_of_scope"
exit 4
