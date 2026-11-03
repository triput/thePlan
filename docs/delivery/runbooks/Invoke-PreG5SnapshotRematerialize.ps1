#Requires -Version 5.1
<#
.SYNOPSIS
  Staged pre-G5 api/web rematerialize: Export (pause/export/unpause/audit) then Import (after approval).

.PARAMETER Stage
  Export — pause by ID, timed export, unpause, path audit, write review receipt (NO import).
  Import — requires -AuditApprovalPath matching tar SHA256; sanitized import + inert probes.

.NOTES
  PLANNING artifact until Trish EXECUTE. Local DropFolder scratch only.
  creation_ok ≠ rollback_acceptance. Pin replacement is separate after disposable evidence.
  Windows PowerShell 5.1.
#>
[CmdletBinding()]
param(
  [switch] $Execute,
  [ValidateSet("Export", "Import")][string] $Stage = "Export",
  [string] $ScratchRoot = "F:\DropFolder\scratch",
  [string] $ExportStamp = "",
  [string] $AuditApprovalPath = "",
  [int] $ExportTimeoutMs = 180000,
  [int] $ImportTimeoutMs = 180000,
  [int] $ProbeTimeoutMs = 60000,
  [string] $ExpectedApiImage = "sha256:9aac7395a068d0761ad81c2339d60b69f5bd90e0cb7ef498f26d2634b0edfa36",
  [string] $ExpectedWebImage = "sha256:bff14006fb87757ce5c5ce28be24223195a01e4154de0d437430dfaa3f89c928",
  [string] $ReleaseApiId = "sha256:71b94263ee96433f66b2db6e05c5c784eeb9770fe5d1151b58b3ff4f204f33be",
  [string] $ReleaseWebId = "sha256:b503f3a5c7e1515eb6e73e69c4f3d12eaefe15d6bb578f61d53421a91592ab3e",
  [string] $ReleaseShaShort = "0c9430e8"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "PreG5-SnapshotHelpers.ps1")

$script:PauseLedger = New-PauseLedger
$script:ImportIntent = New-ImportIntentLedger
$script:ProbeLedger = New-ProbeLedger
$script:OwnedScratch = $null
$script:OwnedTags = New-Object System.Collections.Generic.List[string]
$script:DurableNotes = New-Object System.Collections.Generic.List[string]
$script:ExitCode = 0
$script:RecoveryAttempted = $false
$script:FinalDurableWritten = $false
$script:HealthOk = $false
$script:ImportCreationOk = $false
$script:ImportUncertain = $false

$script:ApiEnvAllow = [ordered]@{
  PATH                    = "/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin"
  PYTHONUNBUFFERED        = "1"
  PYTHONDONTWRITEBYTECODE = "1"
  LANG                    = "C.UTF-8"
}
$script:WebEnvAllow = [ordered]@{
  PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
}

function Fail([string] $msg) { throw ("PREG5_SNAP_FAIL: " + $msg) }

function Write-DurableReceipt([hashtable] $obj, [string] $path) {
  Assert-DurablePathWritable $path
  ($obj | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $path -Encoding utf8
  Write-Host "receipt=$path"
}

function Preserve-ReleaseTags {
  try {
    Preserve-ReleaseImageTags -Pairs @(
      @{ Tag = "theplan-release-api:$ReleaseShaShort"; Id = $ReleaseApiId },
      @{ Tag = "theplan-release-web:$ReleaseShaShort"; Id = $ReleaseWebId }
    )
  } catch {
    Fail $_.Exception.Message
  }
}

function Assert-SourceContainers {
  $api = Get-ContainerIdentity "compose-api-1"
  $web = Get-ContainerIdentity "compose-web-1"
  if ($api.Image -ne $ExpectedApiImage) {
    Fail "api Image=$($api.Image) want ExpectedApiImage=$ExpectedApiImage"
  }
  if ($web.Image -ne $ExpectedWebImage) {
    Fail "web Image=$($web.Image) want ExpectedWebImage=$ExpectedWebImage"
  }
  if (-not $api.Running -or $api.Paused) { Fail "api not Running/unpaused initially" }
  if (-not $web.Running -or $web.Paused) { Fail "web not Running/unpaused initially" }
  Write-Host ("source_ok apiId={0} webId={1}" -f $api.Id, $web.Id)
  return @{ Api = $api; Web = $web }
}

function Invoke-PausePairByIdLocal($api, $web) {
  try {
    [void](Invoke-PausePairById -Ledger $script:PauseLedger -Api $api -Web $web)
  } catch {
    Fail $_.Exception.Message
  }
}

function Invoke-SafeUnpauseAndHealth {
  <# Recovery before any final durable status. Sets ExitCode/HealthOk/DurableNotes. #>
  if ($script:RecoveryAttempted -and $script:FinalDurableWritten) {
    Write-Host "recovery_skip: final durable already written"
    return
  }
  $script:RecoveryAttempted = $true
  $escalations = @(Invoke-UnpauseAllUnresolved -Ledger $script:PauseLedger)
  foreach ($esc in $escalations) {
    $script:DurableNotes.Add($esc)
    Write-Host $esc
  }
  $resolved = Test-PauseLedgerAllResolved $script:PauseLedger
  if (-not $resolved) {
    $script:DurableNotes.Add("unpause_unresolved")
    $script:ExitCode = 3
    $script:HealthOk = $false
    Write-Host "UNPAUSE_UNRESOLVED ledger=$(ConvertTo-Json $script:PauseLedger -Compress)"
    Write-Host "FAILED_RECOVERY_ESCALATION: operator intervention required before Import"
  }
  try {
    foreach ($id in @($script:PauseLedger.Keys)) {
      $e = $script:PauseLedger[$id]
      if (-not $e.PauseAttempted) { continue }
      if (-not $e.VerifiedPaused -and -not $e.Unresolved) { continue }
      $st = Get-ContainerIdentityById $id
      if ($st.Paused) { throw "$($e.Name) ($id) still paused" }
      if (-not $st.Running) { throw "$($e.Name) ($id) not running" }
    }
    # Also observe household names for health endpoints (not used to clear ledger).
    foreach ($n in @("compose-api-1", "compose-web-1")) {
      $st = Get-ContainerIdentity $n
      if ($st.Paused) { throw "$n still paused (name observe)" }
      if (-not $st.Running) { throw "$n not running (name observe)" }
    }
    $h1 = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 20
    if ($h1.StatusCode -ne 200) { throw "api health $($h1.StatusCode)" }
    $h2 = Invoke-WebRequest -Uri "http://127.0.0.1:8080/" -UseBasicParsing -TimeoutSec 20
    if ($h2.StatusCode -ne 200) { throw "web health $($h2.StatusCode)" }
    $sch = Get-ContainerIdentity "compose-scheduler-1"
    Write-Host ("scheduler_observed Running={0} Image={1} (unaltered)" -f $sch.Running, $sch.Image)
    Write-Host "post_health_ok"
    if ($resolved) {
      $script:HealthOk = $true
      if ($script:ExitCode -eq 3) { $script:ExitCode = 0 }
    }
  } catch {
    $script:DurableNotes.Add("post_health_fail:" + $_.Exception.Message)
    $script:ExitCode = 3
    $script:HealthOk = $false
    Write-Host ("post_health_fail=" + $_.Exception.Message)
    Write-Host "FAILED_RECOVERY_ESCALATION: health/reconcile failed"
  }
}

function Write-RecoveryReceiptIfNeeded {
  param(
    [string] $scratch,
    [string] $stamp,
    [string] $SourceApiId,
    [string] $SourceWebId
  )
  $path = Join-Path $scratch "recovery.receipt.json"
  $resolved = Test-PauseLedgerAllResolved $script:PauseLedger
  $obj = [ordered]@{
    stage                     = "Recovery"
    stamp                     = $stamp
    taken_utc                 = (Get-Date).ToUniversalTime().ToString("o")
    source_api_container_id   = $SourceApiId
    source_web_container_id   = $SourceWebId
    verified_resolved         = [bool]$resolved
    health_ok                 = [bool]$script:HealthOk
    pause_ledger              = $script:PauseLedger
    durable_notes             = @($script:DurableNotes)
    health_exit_hint          = $script:ExitCode
  }
  # Only write when recovery was attempted; refuse overwrite.
  if (Test-Path -LiteralPath $path) {
    Write-Host "recovery_receipt_exists_retained=$path"
    return
  }
  Write-DurableReceipt $obj $path
}

function New-OwnedScratch([string] $stamp) {
  $root = Assert-ScratchRootSafe $ScratchRoot
  $stamp = Assert-ExportStampSafe $stamp
  $dir = Join-Path $root "theplan-pre-g5-snap-$stamp"
  $dir = [System.IO.Path]::GetFullPath($dir)
  Assert-PathWithinOwned -OwnedDir $root -CandidatePath $dir | Out-Null
  if (Test-Path -LiteralPath $dir) { Fail "REFUSE scratch exists (no reuse/overwrite): $dir" }
  New-Item -ItemType Directory -Path $dir | Out-Null
  $script:OwnedScratch = $dir
  Set-Content -LiteralPath (Join-Path $dir "CUSTODY.txt") -Encoding ascii -Value @"
Local custody only under F:\DropFolder\scratch. stamp=$stamp
On failure: quarantine in place; do not auto-delete owned artifacts.
"@
  return $dir
}

function Invoke-ExportTimed([string] $containerId, [string] $name, [string] $outTar) {
  Assert-PathWithinOwned -OwnedDir $script:OwnedScratch -CandidatePath $outTar | Out-Null
  if (Test-Path -LiteralPath $outTar) { Fail "REFUSE tar exists $outTar" }
  try {
    Invoke-DockerTimed -What "export $name" -TimeoutMs $ExportTimeoutMs -DockerArgs @(
      "export", $containerId, "-o", $outTar
    ) | Out-Null
  } catch {
    $script:DurableNotes.Add("export_fail_${name}:" + $_.Exception.Message)
    throw
  }
  if (-not (Test-Path -LiteralPath $outTar)) { Fail "export output missing $outTar" }
  $len = (Get-Item -LiteralPath $outTar).Length
  if ($len -lt 1MB) { Fail "export too small $name bytes=$len" }
  Write-Host ("export_ok name={0} bytes={1}" -f $name, $len)
}

function Invoke-ListTarPaths([string] $tarPath, [string] $listOut) {
  Assert-PathWithinOwned -OwnedDir $script:OwnedScratch -CandidatePath $tarPath | Out-Null
  Assert-PathWithinOwned -OwnedDir $script:OwnedScratch -CandidatePath $listOut | Out-Null
  Assert-DurablePathWritable $listOut
  $r = Invoke-WindowsProcessCapturedTimed -FilePath "tar" -ArgumentList @("-tf", $tarPath) `
    -What "tar -tf" -TimeoutMs 120000 -Redact { param($t) $t }
  Set-Content -LiteralPath $listOut -Value $r.StdOut -Encoding ascii
  return @(Get-Content -LiteralPath $listOut | Where-Object { $_ -and $_.Trim() })
}

function Get-Sha256([string] $path) {
  return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}

if (-not $Execute) {
  throw "PLANNING ONLY: Invoke-PreG5SnapshotRematerialize.ps1 refuses without -Execute."
}

$stamp = $ExportStamp
if ([string]::IsNullOrWhiteSpace($stamp)) {
  $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ") + "-" + [guid]::NewGuid().ToString("N").Substring(0, 8)
}
$stamp = Assert-ExportStampSafe $stamp

try {
  if ($Stage -eq "Export") {
    Write-Host "=== Stage Export stamp=$stamp ==="
    Preserve-ReleaseTags
    $src = Assert-SourceContainers
    $scratch = New-OwnedScratch $stamp
    $apiTar = Join-Path $scratch "api.fs.tar"
    $webTar = Join-Path $scratch "web.fs.tar"

    # Interruption budget (not "brief"): two sequential exports each up to ExportTimeoutMs
    # (default 180s) PLUS bounded pause/inspect/unpause control calls. Plan operator window accordingly.
    Write-Host ("export_interruption_budget_ms_per_tar={0} sequential_tars=2 control_timeout_ms={1}" -f $ExportTimeoutMs, $script:PreG5ControlTimeoutMs)

    $exportOk = $false
    try {
      Invoke-PausePairByIdLocal $src.Api $src.Web
      Invoke-ExportTimed $src.Api.Id $src.Api.Name $apiTar
      Invoke-ExportTimed $src.Web.Id $src.Web.Name $webTar
      $exportOk = $true
    }
    finally {
      # Recovery BEFORE durable export receipt. On recovery failure: escalate; do not continue to Import.
      Invoke-SafeUnpauseAndHealth
    }

    Write-RecoveryReceiptIfNeeded -scratch $scratch -stamp $stamp `
      -SourceApiId $src.Api.Id -SourceWebId $src.Web.Id

    if (-not $exportOk) { Fail "export did not complete" }
    if ($script:ExitCode -ne 0 -or -not $script:HealthOk) {
      Write-Host "EXPORT_RECOVERY_FAILED: operator escalation; Import must not proceed without verified recovery receipt bound to this stamp/source IDs"
    }

    $apiPaths = Invoke-ListTarPaths $apiTar (Join-Path $scratch "api.paths.txt")
    $webPaths = Invoke-ListTarPaths $webTar (Join-Path $scratch "web.paths.txt")
    $apiClass = Get-TarPathClasses -Paths $apiPaths
    $webClass = Get-TarPathClasses -Paths $webPaths
    $apiSha = Get-Sha256 $apiTar
    $webSha = Get-Sha256 $webTar

    Assert-PathWithinOwned -OwnedDir $scratch -CandidatePath $apiTar | Out-Null
    Assert-PathWithinOwned -OwnedDir $scratch -CandidatePath $webTar | Out-Null

    ($apiClass | ConvertTo-Json -Depth 5) | Set-Content (Join-Path $scratch "api.audit.json") -Encoding utf8
    ($webClass | ConvertTo-Json -Depth 5) | Set-Content (Join-Path $scratch "web.audit.json") -Encoding utf8

    # Always require private content review — lack of suspicious filenames is NOT clearance.
    $needsReview = $true
    $receipt = [ordered]@{
      stage                              = "Export"
      stamp                              = $stamp
      taken_utc                          = (Get-Date).ToUniversalTime().ToString("o")
      scratch                            = $scratch
      source_api_container_id            = $src.Api.Id
      source_web_container_id            = $src.Web.Id
      source_api_image                   = $src.Api.Image
      source_web_image                   = $src.Web.Image
      api_tar                            = $apiTar
      web_tar                            = $webTar
      api_tar_sha256                     = $apiSha
      web_tar_sha256                     = $webSha
      api_path_inventory                 = $apiClass
      web_path_inventory                 = $webClass
      path_inventory_is_not_sanitization = $true
      needs_private_content_review       = $needsReview
      suspicious_path_inventory          = [bool]($apiClass.suspicious -or $webClass.suspicious)
      import_allowed                     = $false
      approval_required                  = $true
      pause_ledger                       = $script:PauseLedger
      durable_notes                      = @($script:DurableNotes)
      health_exit_hint                   = $script:ExitCode
      health_ok                          = [bool]$script:HealthOk
      next                               = "Private content review REQUIRED (inventory is not clearance); write approval JSON with matching tar SHA256 + private_content_reviewed=true; run -Stage Import -ExportStamp $stamp -AuditApprovalPath <file>"
    }
    Write-DurableReceipt $receipt (Join-Path $scratch "export.receipt.json")
    $script:FinalDurableWritten = $true

    $tmpl = [ordered]@{
      approved                 = $false
      stamp                    = $stamp
      api_tar_sha256           = $apiSha
      web_tar_sha256           = $webSha
      private_content_reviewed = $false
      classification_notes     = ""
      reviewer                 = ""
      review_scope_note        = "Path inventory is not sanitization. Targeted private content review required for all exports."
    }
    Write-DurableReceipt $tmpl (Join-Path $scratch "approval.template.json")

    if ($script:ExitCode -ne 0) {
      Write-Host "EXPORT_COMPLETED_WITH_HEALTH_OR_UNPAUSE_ISSUES exit=$($script:ExitCode)"
      exit $script:ExitCode
    }
    Write-Host "EXPORT_OK awaiting approval file for Import stage (private content review required)"
    exit 0
  }

  if ($Stage -eq "Import") {
    Write-Host "=== Stage Import stamp=$stamp ==="
    if ([string]::IsNullOrWhiteSpace($ExportStamp)) { Fail "Import requires -ExportStamp" }
    if ([string]::IsNullOrWhiteSpace($AuditApprovalPath)) { Fail "Import requires -AuditApprovalPath" }
    $stamp = Assert-ExportStampSafe $ExportStamp
    $root = Assert-ScratchRootSafe $ScratchRoot
    $scratch = Join-Path $root "theplan-pre-g5-snap-$stamp"
    $scratch = [System.IO.Path]::GetFullPath($scratch)
    Assert-PathWithinOwned -OwnedDir $root -CandidatePath $scratch | Out-Null
    if (-not (Test-Path -LiteralPath $scratch)) { Fail "scratch missing $scratch" }
    $script:OwnedScratch = $scratch
    $exportReceiptPath = Join-Path $scratch "export.receipt.json"
    $importReceiptPath = Join-Path $scratch "import.receipt.json"
    if (-not (Test-Path -LiteralPath $exportReceiptPath)) { Fail "export.receipt.json missing" }
    try {
      Assert-ImportStampReusable -ScratchDir $scratch
    } catch {
      Fail $_.Exception.Message
    }
    $exportReceipt = Get-Content $exportReceiptPath -Raw | ConvertFrom-Json
    try {
      Assert-ExportReadyForImport -ExportReceipt $exportReceipt -ScratchDir $scratch -ExpectStamp $stamp
    } catch {
      Fail $_.Exception.Message
    }

    $approval = Get-Content -LiteralPath $AuditApprovalPath -Raw | ConvertFrom-Json
    if ($approval.approved -ne $true) { Fail "approval.approved != true" }
    if ($approval.stamp -ne $stamp) { Fail "approval stamp mismatch" }
    if ([string]$approval.api_tar_sha256 -ne [string]$exportReceipt.api_tar_sha256) { Fail "api tar sha mismatch vs approval" }
    if ([string]$approval.web_tar_sha256 -ne [string]$exportReceipt.web_tar_sha256) { Fail "web tar sha mismatch vs approval" }
    # Always required — lack of suspicious filenames is not clearance.
    if ($approval.private_content_reviewed -ne $true) {
      Fail "private_content_reviewed required for all exports (path inventory is not clearance)"
    }

    $apiTar = [string]$exportReceipt.api_tar
    $webTar = [string]$exportReceipt.web_tar
    Assert-PathWithinOwned -OwnedDir $scratch -CandidatePath $apiTar | Out-Null
    Assert-PathWithinOwned -OwnedDir $scratch -CandidatePath $webTar | Out-Null
    if ((Get-Sha256 $apiTar) -ne $exportReceipt.api_tar_sha256) { Fail "api tar sha drifted" }
    if ((Get-Sha256 $webTar) -ne $exportReceipt.web_tar_sha256) { Fail "web tar sha drifted" }

    Preserve-ReleaseTags

    $apiTag = "theplan-pre-g5-api:snapshot-$stamp"
    $webTag = "theplan-pre-g5-web:snapshot-$stamp"
    try {
      Assert-SnapshotImageTagAbsent -Tag $apiTag
      Assert-SnapshotImageTagAbsent -Tag $webTag
    } catch {
      Fail $_.Exception.Message
    }

    # Record intended tags BEFORE any import client call.
    Register-IntendedSnapshotTag -Ledger $script:ImportIntent -Tag $apiTag -Role "api"
    Register-IntendedSnapshotTag -Ledger $script:ImportIntent -Tag $webTag -Role "web"
    $script:OwnedTags.Add($apiTag)
    $script:OwnedTags.Add($webTag)
    Write-Host ("import_timeout_ms_per_image={0} probe_timeout_ms={1}" -f $ImportTimeoutMs, $ProbeTimeoutMs)

    function Import-One($tar, $tag, $envAllow, $workdir, $user, [string[]]$entrypointChange, [string[]]$cmdChange, $expectEp, $expectCmd, $role) {
      $args = @("import")
      foreach ($k in @($envAllow.Keys)) {
        $args += @("--change", ("ENV {0}={1}" -f $k, $envAllow[$k]))
      }
      $args += @("--change", "WORKDIR $workdir")
      if ($user -ne "") { $args += @("--change", "USER $user") }
      foreach ($c in $entrypointChange) { $args += @("--change", $c) }
      foreach ($c in $cmdChange) { $args += @("--change", $c) }
      $args += @($tar, $tag)
      $id = Invoke-DockerImportWithIntent -IntentLedger $script:ImportIntent -Tag $tag `
        -DockerArgs $args -What "import $role" -TimeoutMs $ImportTimeoutMs
      Assert-ImportedConfig -Tag $tag -EnvAllow $envAllow -ExpectWorkdir $workdir -ExpectUser $user `
        -ExpectEntrypoint $expectEp -ExpectCmd $expectCmd
      return $id
    }

    $apiId = Import-One $apiTar $apiTag $script:ApiEnvAllow "/app" "" `
      @('ENTRYPOINT []') @('CMD ["/bin/true"]') @() @("/bin/true") "api"
    $webId = Import-One $webTar $webTag $script:WebEnvAllow "/" "" `
      @('ENTRYPOINT ["/docker-entrypoint.sh"]') @('CMD ["/bin/true"]') @("/docker-entrypoint.sh") @("/bin/true") "web"

    # Ownership via create→ID→start (not name registration alone). API read-only; web writable layer.
    $nonce = [guid]::NewGuid().ToString("N").Substring(0, 8)
    $attemptLabel = "preg5-$stamp-$nonce"
    $apiProbeName = "preg5-probe-api-$stamp-$nonce"
    $webProbeName = "preg5-probe-web-$stamp-$nonce"
    Register-IntendedProbe -Ledger $script:ProbeLedger -Name $apiProbeName -ImageTag $apiTag -Role "api" -AttemptLabel $attemptLabel
    Register-IntendedProbe -Ledger $script:ProbeLedger -Name $webProbeName -ImageTag $webTag -Role "web" -AttemptLabel $attemptLabel
    $probeGateOk = $false
    try {
      Invoke-InertProbeOwned -ProbeLedger $script:ProbeLedger -Name $apiProbeName -What "api probe" `
        -TimeoutMs $ProbeTimeoutMs -CreateArgs @(
          "create", "--name", $apiProbeName, "--label", "preg5.attempt=$attemptLabel",
          "--network", "none", "--read-only", "--tmpfs", "/tmp",
          "--entrypoint", "/usr/local/bin/python", $apiTag,
          "-c", "import alembic,fastapi,uvicorn; print('imports_ok')"
        )
      Invoke-InertProbeOwned -ProbeLedger $script:ProbeLedger -Name $webProbeName -What "web nginx -t" `
        -TimeoutMs $ProbeTimeoutMs -CreateArgs @(
          "create", "--name", $webProbeName, "--label", "preg5.attempt=$attemptLabel",
          "--network", "none", "--add-host", "api:127.0.0.1",
          "--entrypoint", "/usr/sbin/nginx", $webTag, "-t"
        )
    }
    finally {
      $cleanup = @(Invoke-CleanupOwnedProbes -ProbeLedger $script:ProbeLedger)
      foreach ($c in $cleanup) {
        Write-Host ("probe_cleanup name={0} ok={1} uncertain={2} notes={3}" -f $c.Name, $c.CleanupOk, $c.CleanupUncertain, $c.Notes)
      }
    }
    try {
      Assert-ProbesReadyForSuccess -ProbeLedger $script:ProbeLedger | Out-Null
      $probeGateOk = $true
    } catch {
      Fail $_.Exception.Message
    }

    if (-not $probeGateOk) { Fail "probe success gate not satisfied" }
    $script:ImportCreationOk = $true
    $receipt = [ordered]@{
      stage                 = "Import"
      stamp                 = $stamp
      taken_utc             = (Get-Date).ToUniversalTime().ToString("o")
      reconstruction        = "container_fs_export_import"
      not_original_digest   = $true
      creation_ok           = $true
      rollback_acceptance   = $false
      rollback_pin_updated  = $false
      api_snapshot_tag      = $apiTag
      api_snapshot_id       = $apiId
      web_snapshot_tag      = $webTag
      web_snapshot_id       = $webId
      release_api_id        = $ReleaseApiId
      release_web_id        = $ReleaseWebId
      approval_path         = $AuditApprovalPath
      import_intent         = $script:ImportIntent
      probe_ledger          = $script:ProbeLedger
      probe_notes           = "create+label ownership; api --read-only+tmpfs; web writable disposable layer (nginx -t); network none; no household mounts"
      disposable_compose    = "docs/delivery/runbooks/compose.pre-g5-snapshot-disposable.yaml"
      next                  = "Separate authorize: disposable 042 bring-up of BOTH snapshots with fresh -p project + collision checks; then consider pin update"
    }
    Write-DurableReceipt $receipt $importReceiptPath
    $script:FinalDurableWritten = $true
    Write-Host "IMPORT_CREATION_OK rollback_acceptance=false"
    exit 0
  }
}
catch {
  $script:DurableNotes.Add("fail:" + $_.Exception.Message)
  Write-Host ("PREG5_SNAP_FAIL " + $_.Exception.Message)
  if ($_.Exception.Message -match 'IMPORT_TIMEOUT_UNCERTAIN') {
    $script:ImportUncertain = $true
    $script:DurableNotes.Add("import_outcome_uncertain_stamp_reuse_requires_review")
  }
  try {
    if ($script:ProbeLedger.Count -gt 0) {
      [void](Invoke-CleanupOwnedProbes -ProbeLedger $script:ProbeLedger)
    }
  } catch {
    $script:DurableNotes.Add("probe_cleanup:" + $_.Exception.Message)
  }
  try {
    if (-not $script:FinalDurableWritten) {
      Invoke-SafeUnpauseAndHealth
    }
  } catch {
    $script:DurableNotes.Add("catch_health:" + $_.Exception.Message)
  }
  if ($script:OwnedScratch) {
    if (-not $script:FinalDurableWritten -and $script:PauseLedger.Count -gt 0) {
      $srcApi = $null; $srcWeb = $null
      foreach ($id in @($script:PauseLedger.Keys)) {
        $n = $script:PauseLedger[$id].Name
        if ($n -eq "compose-api-1") { $srcApi = $id }
        if ($n -eq "compose-web-1") { $srcWeb = $id }
      }
      Write-RecoveryReceiptIfNeeded -scratch $script:OwnedScratch -stamp $stamp `
        -SourceApiId $srcApi -SourceWebId $srcWeb
    }
    $q = Join-Path $script:OwnedScratch "QUARANTINE_FAILED_ATTEMPT.txt"
    if (-not (Test-Path -LiteralPath $q)) {
      Set-Content $q -Encoding ascii -Value ("notes=" + ($script:DurableNotes -join " | "))
    }
    $failPath = Join-Path $script:OwnedScratch "failure.receipt.json"
    if (-not (Test-Path -LiteralPath $failPath)) {
      $failReceipt = [ordered]@{
        failed                       = $true
        creation_ok                  = $false
        import_uncertain             = [bool]$script:ImportUncertain
        stamp_reuse_requires_review  = [bool]$script:ImportUncertain
        notes                        = @($script:DurableNotes)
        pause_ledger                 = $script:PauseLedger
        import_intent                = $script:ImportIntent
        intended_tags                = @($script:OwnedTags)
        observed_tag_ids             = @($script:ImportIntent.Values | ForEach-Object { $_.ObservedId })
        probe_ledger                 = $script:ProbeLedger
        exit_code_hint               = if ($script:ImportUncertain) { 3 } else { 1 }
      }
      Write-DurableReceipt $failReceipt $failPath
    }
    $script:FinalDurableWritten = $true
    Write-Host "quarantine=$q (artifacts retained; no auto-delete/retry)"
  }
  if ($script:ImportUncertain) { exit 3 }
  exit 1
}
finally {
  # No silent post-receipt recovery. If still unresolved after durable write, escalate only.
  if ($script:PauseLedger.Count -gt 0 -and -not (Test-PauseLedgerAllResolved $script:PauseLedger)) {
    if (-not $script:FinalDurableWritten -and -not $script:RecoveryAttempted) {
      try { Invoke-SafeUnpauseAndHealth } catch { }
    } else {
      Write-Host "FAILED_RECOVERY_ESCALATION_FINAL: unresolved pause ledger after durable status; no silent retry"
    }
  }
}
