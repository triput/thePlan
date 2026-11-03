#Requires -Version 5.1
<#
.SYNOPSIS
  G1 authoritative household backup (theplan @ 042) with SHA256 sidecar + restore drill + receipt.

.NOTES
  PLANNING ARTIFACT until Trish EXECUTE.
  Single final receipt written ONLY after owned cleanup completes.
  Cleanup failure → g1_pass/g4_eligible=false, nonzero exit.
  -SkipRestoreDrill never yields G1_PASS / G4-eligible receipt.
#>
[CmdletBinding()]
param(
  [switch] $Execute,
  [switch] $SkipRestoreDrill,
  [Parameter(Mandatory = $true)][string] $ExternalWritersQuiescedConfirm,
  [string] $DumpDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Household-ComposePins.ps1")
. (Join-Path $PSScriptRoot "Household-ReceiptDisposition.ps1")
. (Join-Path $PSScriptRoot "G3b-DockerProcess.ps1")

$script:HostTmpDirs = New-Object System.Collections.Generic.List[string]
$script:ContainerTmps = New-Object System.Collections.Generic.List[string]
$script:OwnedDrillDb = $null
$script:DrillDbCreated = $false
$script:CleanupOk = $true
$script:CleanupNotes = New-Object System.Collections.Generic.List[string]
$script:ReceiptWritten = $false

function Redact([string] $t) {
  if ([string]::IsNullOrEmpty($t)) { return $t }
  if ($env:THEPLAN_PGPASSWORD) {
    $t = $t -replace [regex]::Escape($env:THEPLAN_PGPASSWORD), "***"
  }
  return $t
}

function Fail([string] $msg) { throw ("G1_FAIL: " + (Redact $msg)) }

function Invoke-DockerCaptured {
  param([string[]] $DockerArgs, [string] $What)
  try {
    return Invoke-DockerCapturedCore -DockerArgs $DockerArgs -What $What -Redact { param($t) Redact $t }
  } catch {
    if ($_.Exception.Message -match '^G1_FAIL:') { throw $_.Exception.Message }
    Fail $_.Exception.Message
  }
}

function Get-Sha256File([string] $path) {
  return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
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

  if ($script:DrillDbCreated -and $script:OwnedDrillDb) {
    try {
      if (Test-DbExists $script:OwnedDrillDb) {
        Invoke-Psql "postgres" ("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{0}' AND pid <> pg_backend_pid()" -f $script:OwnedDrillDb) | Out-Null
        Invoke-DockerCaptured -What "drop owned drill db" -DockerArgs @(
          "exec", $script:PostgresContainer,
          "psql", "-U", $script:PgUser, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
          "-c", "DROP DATABASE $($script:OwnedDrillDb)"
        ) | Out-Null
      }
      if (Test-DbExists $script:OwnedDrillDb) {
        $script:CleanupOk = $false
        $script:CleanupNotes.Add("drill_db_still_exists_after_drop")
      } else {
        $script:DrillDbCreated = $false
        $script:OwnedDrillDb = $null
      }
    } catch {
      $script:CleanupOk = $false
      $script:CleanupNotes.Add("drill_db_drop_fail:" + (Redact $_.Exception.Message))
    }
  }

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

  Write-Host ("g1_cleanup_ok=" + $script:CleanupOk.ToString().ToLowerInvariant())
  if ($script:CleanupNotes.Count -gt 0) {
    Write-Host ("g1_cleanup_notes=" + ($script:CleanupNotes -join "|"))
  }
  return $script:CleanupOk
}

function Write-G1Receipt([hashtable] $receipt, [string] $path) {
  ($receipt | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $path -Encoding utf8
  $script:ReceiptWritten = $true
}

if (-not $Execute) {
  throw "PLANNING ONLY: Invoke-G1HouseholdBackup.ps1 refuses without -Execute (Trish G1 EXECUTE stamp required)."
}

$inv = (Get-Date -Format "yyyyMMddHHmmss") + ([guid]::NewGuid().ToString("N").Substring(0, 8))
$DumpPath = $null
$ReceiptPath = $null
$sha = $null
$ver = $null
$restoreDrillPass = $false
$drillDb = $null
$userCount0 = 0; $taskCount0 = 0; $settingsCount0 = 0
$workFailed = $false
$workError = $null

try {
  Assert-HouseholdRuntimePins
  Assert-ExternalWritersQuiesced -Evidence $ExternalWritersQuiescedConfirm -Phase "G1"
  Assert-WriterContainersStopped -Phase "G1"

  if ([string]::IsNullOrWhiteSpace($env:THEPLAN_PGPASSWORD)) {
    Fail "THEPLAN_PGPASSWORD not set in process env"
  }

  $ver = Invoke-Psql $script:HouseholdDb "SELECT version_num FROM alembic_version"
  if ($ver -ne $script:ExpectAlembic042) {
    Fail "household alembic_version=$ver want $($script:ExpectAlembic042)"
  }

  $userCount0 = [int](Invoke-Psql $script:HouseholdDb "SELECT COUNT(*)::text FROM users")
  $taskCount0 = [int](Invoke-Psql $script:HouseholdDb "SELECT COUNT(*)::text FROM tasks")
  $settingsCount0 = [int](Invoke-Psql $script:HouseholdDb "SELECT COUNT(*)::text FROM user_settings")
  $userIds0 = Invoke-Psql $script:HouseholdDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM users"
  $taskIds0 = Invoke-Psql $script:HouseholdDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM tasks"
  if ($settingsCount0 -lt 1) { Fail "user_settings empty" }

  if ([string]::IsNullOrWhiteSpace($DumpDir)) { $DumpDir = $script:BackupRoot }
  New-Item -ItemType Directory -Force -Path $DumpDir | Out-Null

  $DumpPath = Join-Path $DumpDir "theplan-g1-$inv.dump"
  $ReceiptPath = "$DumpPath.g1-receipt.json"
  if (Test-Path -LiteralPath $DumpPath) { Fail "REFUSE: dump path already exists $DumpPath" }
  if (Test-Path -LiteralPath "$DumpPath.sha256") { Fail "REFUSE: dump sha sidecar already exists" }
  if (Test-Path -LiteralPath "$DumpPath.meta.json") { Fail "REFUSE: dump meta already exists" }
  if (Test-Path -LiteralPath $ReceiptPath) { Fail "REFUSE: receipt already exists" }

  $ctmp = "/tmp/g1_household_$inv.dump"
  $script:ContainerTmps.Add($ctmp)

  Write-Host "g1_dump_begin path=$DumpPath inv=$inv"
  Invoke-DockerCaptured -What "pg_dump" -DockerArgs @(
    "exec", $script:PostgresContainer,
    "pg_dump", "-U", $script:PgUser, "-d", $script:HouseholdDb, "-Fc", "--no-owner", "-f", $ctmp
  ) | Out-Null
  Invoke-DockerCaptured -What "docker cp dump" -DockerArgs @(
    "cp", "${script:PostgresContainer}:${ctmp}", $DumpPath
  ) | Out-Null
  Invoke-DockerCaptured -What "rm dump in container" -DockerArgs @(
    "exec", $script:PostgresContainer, "rm", "-f", $ctmp
  ) | Out-Null
  [void]$script:ContainerTmps.Remove($ctmp)

  $sha = Get-Sha256File $DumpPath
  $size = (Get-Item -LiteralPath $DumpPath).Length
  $meta = [ordered]@{
    taken_utc               = (Get-Date).ToUniversalTime().ToString("o")
    invocation_id           = $inv
    source_database         = $script:HouseholdDb
    source_alembic          = $ver
    dump_path               = $DumpPath
    dump_bytes              = $size
    dump_sha256             = $sha
    postgres_container      = $script:PostgresContainer
    mode                    = "g1_authoritative_quiesced"
    source_users            = $userCount0
    source_tasks            = $taskCount0
    source_settings         = $settingsCount0
    source_user_ids         = $userIds0
    source_task_ids         = $taskIds0
    writers_stopped         = $script:WriterContainers
    external_writers_attest = "EXTERNAL_WRITERS_QUIESCED"
  }
  Set-Content -LiteralPath "$DumpPath.sha256" -Value "$sha  $(Split-Path $DumpPath -Leaf)" -Encoding ascii
  ($meta | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath "$DumpPath.meta.json" -Encoding utf8
  Write-Host "g1_dump_ok sha=$sha bytes=$size alembic=$ver"

  if ($SkipRestoreDrill) {
    Write-Host "g1_restore_drill=SKIPPED"
  } else {
    $drillDb = "theplan_g1_drill_$inv"
    if ($drillDb.Length -gt 63) { Fail "drill db name too long" }
    if ($drillDb -notmatch '^[a-z][a-z0-9_]{0,62}$') { Fail "drill db name unsafe" }
    if (Test-DbExists $drillDb) { Fail "REFUSE: drill db already exists $drillDb" }

    $script:OwnedDrillDb = $drillDb
    Write-Host "g1_restore_drill_begin db=$drillDb"
    Invoke-DockerCaptured -What "create drill db" -DockerArgs @(
      "exec", $script:PostgresContainer,
      "psql", "-U", $script:PgUser, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
      "-c", "CREATE DATABASE $drillDb OWNER $($script:PgUser)"
    ) | Out-Null
    $script:DrillDbCreated = $true

    $drillCtmp = "/tmp/g1_drill_$inv.dump"
    $script:ContainerTmps.Add($drillCtmp)
    Invoke-DockerCaptured -What "cp dump into container" -DockerArgs @(
      "cp", $DumpPath, "${script:PostgresContainer}:${drillCtmp}"
    ) | Out-Null
    Invoke-DockerCaptured -What "pg_restore drill" -DockerArgs @(
      "exec", $script:PostgresContainer,
      "pg_restore", "-U", $script:PgUser, "-d", $drillDb, "--no-owner", "--exit-on-error", $drillCtmp
    ) | Out-Null
    Invoke-DockerCaptured -What "rm drill dump" -DockerArgs @(
      "exec", $script:PostgresContainer, "rm", "-f", $drillCtmp
    ) | Out-Null
    [void]$script:ContainerTmps.Remove($drillCtmp)

    $drillVer = Invoke-Psql $drillDb "SELECT version_num FROM alembic_version"
    if ($drillVer -ne $script:ExpectAlembic042) {
      Fail "drill alembic=$drillVer want $($script:ExpectAlembic042)"
    }
    $users1 = [int](Invoke-Psql $drillDb "SELECT COUNT(*)::text FROM users")
    $tasks1 = [int](Invoke-Psql $drillDb "SELECT COUNT(*)::text FROM tasks")
    $settings1 = [int](Invoke-Psql $drillDb "SELECT COUNT(*)::text FROM user_settings")
    $userIds1 = Invoke-Psql $drillDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM users"
    $taskIds1 = Invoke-Psql $drillDb "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM tasks"
    if ($users1 -ne $userCount0 -or $userIds1 -ne $userIds0) { Fail "drill user inventory mismatch vs source" }
    if ($tasks1 -ne $taskCount0 -or $taskIds1 -ne $taskIds0) { Fail "drill task inventory mismatch vs source" }
    if ($settings1 -ne $settingsCount0) { Fail "drill settings count mismatch vs source" }

    $ac = Invoke-Psql $drillDb "SELECT CASE WHEN to_regclass('public.agent_credentials') IS NULL THEN 'absent' ELSE 'present' END"
    if ($ac -ne "absent") { Fail "drill unexpectedly has agent_credentials" }

    $restoreDrillPass = $true
    Write-Host "g1_restore_drill_ok alembic=$drillVer users=$users1 tasks=$tasks1 settings=$settings1 match=source"
  }
}
catch {
  $workFailed = $true
  $workError = Redact $_.Exception.Message
  Write-Host ("G1_FAIL work err=" + $workError)
}
finally {
  # Disposition order: cleanup FIRST, then one final receipt, then PASS/FAIL.
  $null = Invoke-OwnedCleanup
  if (Test-Path Env:DATABASE_URL) { Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue }

  if ($ReceiptPath -and $DumpPath -and $sha) {
    $receipt = New-G1ReceiptObject `
      -InvocationId $inv `
      -DumpPath $DumpPath `
      -DumpSha256 $sha `
      -SourceAlembic $ver `
      -SourceDatabase $script:HouseholdDb `
      -RestoreDrillPass $restoreDrillPass `
      -RestoreDrillDb $drillDb `
      -RestoreDrillDbDropped (-not $script:DrillDbCreated) `
      -SourceUsers $userCount0 `
      -SourceTasks $taskCount0 `
      -SourceSettings $settingsCount0 `
      -WritersStopped $script:WriterContainers `
      -CleanupOk $script:CleanupOk `
      -CleanupNotes $script:CleanupNotes `
      -WorkFailed $workFailed `
      -WorkError $workError
    Write-G1Receipt -receipt $receipt -path $ReceiptPath
  }
}

if ($workFailed) {
  throw ("G1_FAIL: " + $workError)
}
if (-not $script:CleanupOk) {
  throw ("G1_FAIL: cleanup incomplete — " + ($script:CleanupNotes -join "; "))
}
if (-not $restoreDrillPass) {
  Write-Host "G1_DUMP_ONLY_NO_DRILL dump=$DumpPath sha=$sha receipt=$ReceiptPath g4_eligible=false"
  exit 2
}

Write-Host "G1_PASS dump=$DumpPath sha=$sha receipt=$ReceiptPath g4_eligible=true cleanup_ok=true"
exit 0
