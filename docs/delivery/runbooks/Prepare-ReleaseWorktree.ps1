#Requires -Version 5.1
<#
.SYNOPSIS
  Build a clean release worktree that contains the Phase 1 candidate (Dex 1793592059 §1).

.DESCRIPTION
  - Creates/uses a separate directory (-ReleaseRoot), never stashes/resets the operator's original index.
  - Does not write Julie's theplan-cli-23f192e install or session file.
  - Copies reviewed uncommitted API/web/docs from -SourceRepo plus Bearer CLI modules from -BearerInstall.
  - Verifies source→release SHA256 for every transferred file and CLI pins.
  - Refuses if _tmp_seed_* would enter apps/api.

.PARAMETER AllowExecute
  Required to mutate the filesystem (create worktree / copy). Omit to dry-print the plan.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string] $ReleaseRoot,
  [string] $SourceRepo = "F:\Code Repo\ThePlan",
  [string] $BaseRef = "feature/0.7-s2-cutover",  # prefer reviewed RELEASE_SHA when known
  [string] $BearerInstall = "F:\Tools\theplan-cli-bearer-dev\Lib\site-packages\theplan",
  [string] $JulieInstall = "F:\Tools\theplan-cli-23f192e",
  [switch] $AllowExecute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail([string] $m) { Write-Error "RELEASE_PREP_FAIL: $m"; exit 2 }
function Sha([string] $p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToUpperInvariant() }

$CliPins = @{
  "commands\auth.py" = "50DFA682223D5F6C0D57DF9CE1337A1FF4DF414A9AF7EE3FA38ABB940E6DACCD"
  "api_client.py"    = "FE4C250C175566D75CD59DCACEAC198FE4AD6F5B15E560598F829655D147982A"
  "session_file.py"  = "84918ABC5635599576EBC031ACE179EA8572D9CF31D84CB3E0CAEF407E49C9B4"
}

# G3b ApiPinRels (22 files under apps/api) + Phase 1 route/schema/test overlays — deduped.
$ApiRel = @(
  "apps\api\alembic.ini",
  "apps\api\alembic\env.py",
  "apps\api\alembic\versions\043_recovery_epoch.py",
  "apps\api\alembic\versions\044_agent_cli_access.py",
  "apps\api\app\config.py",
  "apps\api\app\db.py",
  "apps\api\app\models\__init__.py",
  "apps\api\app\models\availability.py",
  "apps\api\app\models\calendar.py",
  "apps\api\app\models\enums.py",
  "apps\api\app\models\free_busy_policy.py",
  "apps\api\app\models\handoff.py",
  "apps\api\app\models\hierarchy.py",
  "apps\api\app\models\label.py",
  "apps\api\app\models\mixins.py",
  "apps\api\app\models\schedule.py",
  "apps\api\app\models\scheduling_assignment.py",
  "apps\api\app\models\scheduling_day_scoped.py",
  "apps\api\app\models\task.py",
  "apps\api\app\models\task_occurrence_disposition.py",
  "apps\api\app\models\time_map_override.py",
  "apps\api\app\models\user.py",
  "apps\api\app\api\deps.py",
  "apps\api\app\api\routes\auth.py",
  "apps\api\app\api\routes\settings.py",
  "apps\api\app\api\routes\agent_credentials.py",
  "apps\api\app\api\middleware\agent_boundary_a.py",
  "apps\api\app\main.py",
  "apps\api\app\schemas\__init__.py",
  "apps\api\app\schemas\settings.py",
  "apps\api\app\schemas\agent_credentials.py",
  "apps\api\app\services\agent_auth_context.py",
  "apps\api\app\services\agent_credentials.py",
  "apps\api\tests\conftest.py",
  "apps\api\tests\test_agent_cli_access.py",
  "apps\api\tests\test_agent_cli_access_concurrency.py",
  "apps\api\tests\test_agent_cli_access_http_boundary.py"
) | Sort-Object -Unique

$WebRel = @(
  "apps\web\package.json",
  "apps\web\package-lock.json",
  "apps\web\src\api.ts",
  "apps\web\src\components\SettingsPanel.tsx",
  "apps\web\src\styles\settings.css",
  "apps\web\src\components\settings\AgentAccessSection.tsx",
  "apps\web\src\components\settings\AgentCredentialsManager.tsx",
  "apps\web\tests\agentAccessSection.rtl.test.tsx",
  "apps\web\tests\agentAccessSection.test.ts",
  "apps\web\tests\setup.rtl.ts",
  "apps\web\vitest.config.ts"
)

$DocRel = @(
  "docs\delivery\0.7-AGENT-CLI-ACCESS-Contract-2026-10-27.md",
  "docs\delivery\0.7-AGENT-CLI-ACCESS-Phase1-CODING-UNLOCK-2026-10-27.md",
  "docs\delivery\0.7-AGENT-CLI-ACCESS-Phase1-EVIDENCE-MAP-2026-11-01.md",
  "docs\delivery\0.7-AGENT-CLI-ACCESS-Phase1-TIP-2026-10-27.md",
  "docs\delivery\0.7-AGENT-CLI-ACCESS-Phase1-RELEASE-TRANSITION-PACKET-2026-11-01.md",
  "docs\delivery\0.7-AGENT-CLI-ACCESS-Phase1-RELEASE-RUNBOOK-ADDENDUM-2026-11-01.md",
  "docs\delivery\runbooks\G3b-DockerProcess.ps1",
  "docs\delivery\runbooks\Invoke-G3bMigrateRehearsal.ps1",
  "docs\delivery\runbooks\Probe-G3bDockerArgv.ps1",
  "docs\delivery\runbooks\g3b-api-src-manifest-input.txt",
  "docs\delivery\runbooks\Prepare-ReleaseWorktree.ps1"
)

$CliTestRel = @(
  "apps\cli\tests\test_auth_bearer_only.py",
  "apps\cli\tests\test_auth_password_retired.py"
)

$SourceRepo = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $SourceRepo).Path)
$ReleaseRoot = [System.IO.Path]::GetFullPath($ReleaseRoot)
$JulieFull = [System.IO.Path]::GetFullPath($JulieInstall)
if ($ReleaseRoot -eq $SourceRepo) { Fail "ReleaseRoot must differ from SourceRepo" }
if ($ReleaseRoot.StartsWith($JulieFull, [System.StringComparison]::OrdinalIgnoreCase)) {
  Fail "ReleaseRoot must not be under Julie install"
}
if ($BaseRef -match '^[0-9a-fA-F]{40}$') {
  Write-Host "base_ref_pinned_sha=$BaseRef"
} else {
  Write-Warning "BaseRef='$BaseRef' is a moving ref — pin to reviewed RELEASE_SHA when available (Dex 1793592510)"
}

Write-Host "source_repo=$SourceRepo"
Write-Host "release_root=$ReleaseRoot"
Write-Host "base_ref=$BaseRef"

# Seeds in source apps/api are OK only if not on the copy manifest (they are excluded).
# Still warn — operator must not later copy whole apps/api into release.
Get-ChildItem -Path (Join-Path $SourceRepo "apps\api") -Filter "_tmp_seed_*" -File -ErrorAction SilentlyContinue |
  ForEach-Object { Write-Warning "source has temp seed (excluded from manifest): $($_.Name)" }

foreach ($kv in $CliPins.GetEnumerator()) {
  $src = Join-Path $BearerInstall $kv.Key
  if (-not (Test-Path -LiteralPath $src)) { Fail "Bearer install missing $($kv.Key)" }
  $h = Sha $src
  if ($h -ne $kv.Value) { Fail "Bearer pin mismatch $($kv.Key) got=$h expected=$($kv.Value)" }
}

$missing = @()
foreach ($r in ($ApiRel + $WebRel + $DocRel + $CliTestRel)) {
  if (-not (Test-Path -LiteralPath (Join-Path $SourceRepo $r))) { $missing += $r }
}
if ($missing.Count) {
  Write-Host "missing_source_files:"
  $missing | ForEach-Object { Write-Host "  $_" }
  Fail "source candidate incomplete ($($missing.Count) missing) — abort"
}

if (-not $AllowExecute) {
  Write-Host "dry_run=True (pass -AllowExecute to create worktree and copy)"
  Write-Host "planned_api_files=$($ApiRel.Count) web=$($WebRel.Count) docs=$($DocRel.Count)"
  exit 0
}

# Fresh checkout of base branch into ReleaseRoot via git worktree (separate dir)
if (Test-Path -LiteralPath $ReleaseRoot) {
  Fail "ReleaseRoot already exists: $ReleaseRoot (refuse overwrite)"
}

Push-Location $SourceRepo
try {
  & git worktree add -b "release/agent-cli-phase1-g0b" $ReleaseRoot $BaseRef
  if ($LASTEXITCODE -ne 0) { Fail "git worktree add failed ($LASTEXITCODE)" }
}
finally { Pop-Location }

function Copy-Verified([string] $rel) {
  $from = Join-Path $SourceRepo $rel
  $to = Join-Path $ReleaseRoot $rel
  $dir = Split-Path $to -Parent
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Copy-Item -LiteralPath $from -Destination $to -Force
  $a = Sha $from; $b = Sha $to
  if ($a -ne $b) { Fail "hash mismatch after copy $rel" }
  Write-Host "copied_ok $rel sha=$a"
}

foreach ($r in ($ApiRel + $WebRel + $DocRel + $CliTestRel)) { Copy-Verified $r }

# CLI product modules from Bearer install (not SourceRepo cookie-era files)
foreach ($kv in $CliPins.GetEnumerator()) {
  $from = Join-Path $BearerInstall $kv.Key
  $to = Join-Path $ReleaseRoot "apps\cli\theplan\$($kv.Key)"
  New-Item -ItemType Directory -Force -Path (Split-Path $to -Parent) | Out-Null
  Copy-Item -LiteralPath $from -Destination $to -Force
  $h = Sha $to
  if ($h -ne $kv.Value) { Fail "release CLI pin fail $($kv.Key) got=$h" }
  Write-Host "cli_pin_ok $($kv.Key) sha=$h"
}

# Build-context seed refuse in release tree
Get-ChildItem -Path (Join-Path $ReleaseRoot "apps\api") -Filter "_tmp_seed_*" -File -ErrorAction SilentlyContinue |
  ForEach-Object { Fail "REFUSE: seed leaked into release apps/api: $($_.FullName)" }

# Real failing check: compose build context listing must not contain seeds
$ctx = Join-Path $ReleaseRoot "apps\api"
$seedHit = Get-ChildItem -Path $ctx -Filter "_tmp_seed_*" -Recurse -File -ErrorAction SilentlyContinue
if ($seedHit) { Fail "build context seed check failed" }

Write-Host "release_worktree_ok=$ReleaseRoot"
Write-Host "next=cd release root; review git status; commit RELEASE_SHA; then compose -f infra/compose/compose.yaml build api web"
Write-Host "note=do_not_touch_julie_install"
exit 0
