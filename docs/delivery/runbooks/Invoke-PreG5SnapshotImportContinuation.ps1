#Requires -Version 5.1
<#
.SYNOPSIS
  Import continuation after attempt-1 failure: bind retained API image by exact ID;
  import web only; inspect/probe by immutable image IDs; evidence under import-cont-1\ only.

.NOTES
  PLANNING until Trish EXECUTE after Dex plan ACCEPT.
  Does NOT clear parent quarantine / failure.receipt.json.
  Does NOT call Assert-ImportStampReusable against the parent stamp.
  Config inspect + probes target ExpectedApiImageId / returned webId (not mutable tags).
  Tag-to-ID provenance checks remain.
  AttemptDir gated (success|failure|quarantine) BEFORE dir assign / Docker mutations.
#>
[CmdletBinding()]
param(
  [switch] $Execute,
  [string] $ScratchRoot = "F:\DropFolder\scratch",
  [Parameter(Mandatory = $true)][string] $ExportStamp,
  [Parameter(Mandatory = $true)][string] $AuditApprovalPath,
  [string] $AttemptId = "cont-1",
  [string] $ExpectedApiImageId = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b",
  [int] $ImportTimeoutMs = 180000,
  [int] $ProbeTimeoutMs = 60000,
  [string] $ReleaseApiId = "sha256:71b94263ee96433f66b2db6e05c5c784eeb9770fe5d1151b58b3ff4f204f33be",
  [string] $ReleaseWebId = "sha256:b503f3a5c7e1515eb6e73e69c4f3d12eaefe15d6bb578f61d53421a91592ab3e",
  [string] $ReleaseShaShort = "0c9430e8",
  [string] $ExpectedApiTarSha = "53A32724236594867B660A83F666D2472F1B0B5AE9E831378C4838791C6C1A74",
  [string] $ExpectedWebTarSha = "B0F8EB16ACB8EADD3D98C07ADB8D926294B895189968EDAA97B564258CFD0562"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "PreG5-SnapshotHelpers.ps1")

$script:ImportIntent = New-ImportIntentLedger
$script:ProbeLedger = New-ProbeLedger
$script:OwnedScratch = $null
$script:AttemptDir = $null
$script:FinalDurableWritten = $false
$script:ImportUncertain = $false
$script:DurableNotes = New-Object System.Collections.Generic.List[string]
$script:RefusalNoAttemptWrite = $false

$script:ApiEnvAllow = [ordered]@{
  PATH                    = "/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin"
  PYTHONUNBUFFERED        = "1"
  PYTHONDONTWRITEBYTECODE = "1"
  LANG                    = "C.UTF-8"
}
$script:WebEnvAllow = [ordered]@{
  PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
}

function Fail([string] $msg) { throw ("PREG5_CONT_FAIL: " + $msg) }
function FailRefuseAttempt([string] $msg) {
  $script:RefusalNoAttemptWrite = $true
  throw ("PREG5_CONT_FAIL: " + $msg)
}

function Get-Sha256([string] $path) {
  return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Write-DurableReceipt([hashtable] $obj, [string] $path) {
  Assert-DurablePathWritable $path
  ($obj | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $path -Encoding utf8
  Write-Host "receipt=$path"
}

if (-not $Execute) {
  throw "PLANNING ONLY: Invoke-PreG5SnapshotImportContinuation.ps1 refuses without -Execute."
}

try {
  $stamp = Assert-ExportStampSafe $ExportStamp
  if ($AttemptId -notmatch '^[a-z0-9][a-z0-9_-]*$') { Fail "AttemptId charset invalid" }
  $root = Assert-ScratchRootSafe $ScratchRoot
  $parent = Join-Path $root "theplan-pre-g5-snap-$stamp"
  $parent = [System.IO.Path]::GetFullPath($parent)
  Assert-PathWithinOwned -OwnedDir $root -CandidatePath $parent | Out-Null
  if (-not (Test-Path -LiteralPath $parent)) { Fail "parent custody missing $parent" }

  $parentFail = Join-Path $parent "failure.receipt.json"
  $parentQuarantine = Join-Path $parent "QUARANTINE_FAILED_ATTEMPT.txt"
  if (-not (Test-Path -LiteralPath $parentFail)) { Fail "expected parent failure.receipt.json (continuation requires attempt-1 evidence)" }
  if (-not (Test-Path -LiteralPath $parentQuarantine)) { Fail "expected parent QUARANTINE_FAILED_ATTEMPT.txt" }
  Write-Host "parent_failure_preserved=true (stamp_reuse_requires_review flag on that receipt is historical; parent Import remains unconditionally blocked)"

  $exportReceiptPath = Join-Path $parent "export.receipt.json"
  if (-not (Test-Path -LiteralPath $exportReceiptPath)) { Fail "export.receipt.json missing" }
  $exportReceipt = Get-Content $exportReceiptPath -Raw | ConvertFrom-Json
  try {
    Assert-ExportReadyForImport -ExportReceipt $exportReceipt -ScratchDir $parent -ExpectStamp $stamp
  } catch {
    Fail $_.Exception.Message
  }

  $apiTar = [string]$exportReceipt.api_tar
  $webTar = [string]$exportReceipt.web_tar
  Assert-PathWithinOwned -OwnedDir $parent -CandidatePath $apiTar | Out-Null
  Assert-PathWithinOwned -OwnedDir $parent -CandidatePath $webTar | Out-Null
  if ((Get-Sha256 $apiTar) -ne $ExpectedApiTarSha) { Fail "api tar sha mismatch vs continuation pin" }
  if ((Get-Sha256 $webTar) -ne $ExpectedWebTarSha) { Fail "web tar sha mismatch vs continuation pin" }
  if ((Get-Sha256 $apiTar) -ne [string]$exportReceipt.api_tar_sha256) { Fail "api tar sha drifted vs export receipt" }
  if ((Get-Sha256 $webTar) -ne [string]$exportReceipt.web_tar_sha256) { Fail "web tar sha drifted vs export receipt" }

  $approval = Get-Content -LiteralPath $AuditApprovalPath -Raw | ConvertFrom-Json
  if ($approval.approved -ne $true) { Fail "approval.approved != true" }
  if ($approval.stamp -ne $stamp) { Fail "approval stamp mismatch" }
  if ($approval.continuation_attempt -ne $AttemptId) { Fail "approval.continuation_attempt mismatch want=$AttemptId" }
  if ([string]$approval.api_tar_sha256 -ne $ExpectedApiTarSha) { Fail "approval api tar sha mismatch" }
  if ([string]$approval.web_tar_sha256 -ne $ExpectedWebTarSha) { Fail "approval web tar sha mismatch" }
  if ([string]$approval.retained_api_image_id -ne $ExpectedApiImageId) { Fail "approval retained_api_image_id mismatch" }
  if ($approval.private_content_reviewed -ne $true) { Fail "private_content_reviewed required" }
  if ($approval.parent_failure_receipt_preserved -ne $true) { Fail "approval must affirm parent_failure_receipt_preserved=true" }

  # Gate BEFORE creating dir, BEFORE AttemptDir assign, BEFORE any Docker mutation.
  $attemptDir = Join-Path $parent ("import-" + $AttemptId)
  $attemptDir = [System.IO.Path]::GetFullPath($attemptDir)
  Assert-PathWithinOwned -OwnedDir $parent -CandidatePath $attemptDir | Out-Null
  try {
    Assert-ImportAttemptDirClear -AttemptDir $attemptDir
  } catch {
    FailRefuseAttempt $_.Exception.Message
  }

  $apiTag = "theplan-pre-g5-api:snapshot-$stamp"
  $webTag = "theplan-pre-g5-web:snapshot-$stamp"

  # Provenance: tag → exact expected ID; config + probes use immutable ID only.
  try {
    Assert-ImageIdMatchesTag -Tag $apiTag -ExpectedId $ExpectedApiImageId
  } catch {
    FailRefuseAttempt $_.Exception.Message
  }
  Assert-ImportedConfig -Tag $ExpectedApiImageId -EnvAllow $script:ApiEnvAllow `
    -ExpectWorkdir "/app" -ExpectUser "" -ExpectEntrypoint @() -ExpectCmd @("/bin/true")

  try {
    Preserve-ReleaseImageTags -Pairs @(
      @{ Tag = "theplan-release-api:$ReleaseShaShort"; Id = $ReleaseApiId },
      @{ Tag = "theplan-release-web:$ReleaseShaShort"; Id = $ReleaseWebId }
    )
  } catch {
    Fail $_.Exception.Message
  }

  try {
    Assert-SnapshotImageTagAbsent -Tag $webTag
  } catch {
    Fail $_.Exception.Message
  }

  # Commit attempt dir only after gates + preflight that should not leave attempt quarantine on refuse-rerun.
  if (-not (Test-Path -LiteralPath $attemptDir)) {
    New-Item -ItemType Directory -Path $attemptDir | Out-Null
  }
  # Re-check after create race: still clear of markers before assigning failure-writing path.
  try {
    Assert-ImportAttemptDirClear -AttemptDir $attemptDir
  } catch {
    FailRefuseAttempt $_.Exception.Message
  }
  $script:OwnedScratch = $parent
  $script:AttemptDir = $attemptDir
  $importReceiptPath = Join-Path $attemptDir "import.receipt.json"

  Register-IntendedSnapshotTag -Ledger $script:ImportIntent -Tag $apiTag -Role "api"
  $script:ImportIntent[$apiTag].ImportAttempted = $false
  $script:ImportIntent[$apiTag].ImportClientOk = $true
  $script:ImportIntent[$apiTag].Outcome = "reused_retained"
  $script:ImportIntent[$apiTag].ObservedId = $ExpectedApiImageId
  $script:ImportIntent[$apiTag].Notes = "bound retained attempt-1 image by id; config/probes use id not tag"
  Write-Host ("api_reused id={0}" -f $ExpectedApiImageId)

  Register-IntendedSnapshotTag -Ledger $script:ImportIntent -Tag $webTag -Role "web"
  Write-Host ("import_timeout_ms_web={0} probe_timeout_ms={1}" -f $ImportTimeoutMs, $ProbeTimeoutMs)

  $webArgs = @("import")
  foreach ($k in @($script:WebEnvAllow.Keys)) {
    $webArgs += @("--change", ("ENV {0}={1}" -f $k, $script:WebEnvAllow[$k]))
  }
  $webArgs += @(
    "--change", "WORKDIR /",
    "--change", 'ENTRYPOINT ["/docker-entrypoint.sh"]',
    "--change", 'CMD ["/bin/true"]',
    $webTar, $webTag
  )
  $webId = Invoke-DockerImportWithIntent -IntentLedger $script:ImportIntent -Tag $webTag `
    -DockerArgs $webArgs -What "import web continuation" -TimeoutMs $ImportTimeoutMs
  # Provenance + immutable inspect/probe targets.
  Assert-ImageIdMatchesTag -Tag $webTag -ExpectedId $webId
  Assert-ImportedConfig -Tag $webId -EnvAllow $script:WebEnvAllow `
    -ExpectWorkdir "/" -ExpectUser "" -ExpectEntrypoint @("/docker-entrypoint.sh") -ExpectCmd @("/bin/true")

  $nonce = [guid]::NewGuid().ToString("N").Substring(0, 8)
  $attemptLabel = "preg5-$stamp-$AttemptId-$nonce"
  $apiProbeName = "preg5-probe-api-$stamp-$AttemptId-$nonce"
  $webProbeName = "preg5-probe-web-$stamp-$AttemptId-$nonce"
  # Ownership image ref = immutable IDs (same IDs used in create).
  Register-IntendedProbe -Ledger $script:ProbeLedger -Name $apiProbeName -ImageTag $ExpectedApiImageId -Role "api" -AttemptLabel $attemptLabel
  Register-IntendedProbe -Ledger $script:ProbeLedger -Name $webProbeName -ImageTag $webId -Role "web" -AttemptLabel $attemptLabel
  $probeGateOk = $false
  try {
    Invoke-InertProbeOwned -ProbeLedger $script:ProbeLedger -Name $apiProbeName -What "api probe" `
      -TimeoutMs $ProbeTimeoutMs -CreateArgs @(
        "create", "--name", $apiProbeName, "--label", "preg5.attempt=$attemptLabel",
        "--network", "none", "--read-only", "--tmpfs", "/tmp",
        "--entrypoint", "/usr/local/bin/python", $ExpectedApiImageId,
        "-c", "import alembic,fastapi,uvicorn; print('imports_ok')"
      )
    Invoke-InertProbeOwned -ProbeLedger $script:ProbeLedger -Name $webProbeName -What "web nginx -t" `
      -TimeoutMs $ProbeTimeoutMs -CreateArgs @(
        "create", "--name", $webProbeName, "--label", "preg5.attempt=$attemptLabel",
        "--network", "none", "--add-host", "api:127.0.0.1",
        "--entrypoint", "/usr/sbin/nginx", $webId, "-t"
      )
  } finally {
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

  $receipt = [ordered]@{
    stage                            = "ImportContinuation"
    stamp                            = $stamp
    attempt_id                       = $AttemptId
    taken_utc                        = (Get-Date).ToUniversalTime().ToString("o")
    reconstruction                   = "container_fs_export_import"
    not_original_digest              = $true
    creation_ok                      = $true
    rollback_acceptance              = $false
    rollback_pin_updated             = $false
    api_provenance                   = "retained_attempt1_id"
    api_snapshot_tag                 = $apiTag
    api_snapshot_id                  = $ExpectedApiImageId
    web_snapshot_tag                 = $webTag
    web_snapshot_id                  = $webId
    probe_image_refs                 = @{ api = $ExpectedApiImageId; web = $webId }
    parent_failure_receipt           = $parentFail
    parent_quarantine                = $parentQuarantine
    parent_failure_receipt_preserved = $true
    stamp_reuse_note                 = "Parent failure.receipt.json stamp_reuse_requires_review=false is historical (non-timeout fail). Parent Import remains unconditionally blocked. This continuation uses separate attempt evidence only."
    approval_path                    = $AuditApprovalPath
    import_intent                    = $script:ImportIntent
    probe_ledger                     = $script:ProbeLedger
    next                             = "STOP — disposable pair / pin update remain separately held"
  }
  Write-DurableReceipt $receipt $importReceiptPath
  $script:FinalDurableWritten = $true
  Write-Host "IMPORT_CONTINUATION_OK rollback_acceptance=false"
  exit 0
}
catch {
  $script:DurableNotes.Add("fail:" + $_.Exception.Message)
  Write-Host ("PREG5_CONT_FAIL " + $_.Exception.Message)
  if ($_.Exception.Message -match 'IMPORT_TIMEOUT_UNCERTAIN') {
    $script:ImportUncertain = $true
  }
  try {
    if ($script:ProbeLedger.Count -gt 0) {
      [void](Invoke-CleanupOwnedProbes -ProbeLedger $script:ProbeLedger)
    }
  } catch {
    $script:DurableNotes.Add("probe_cleanup:" + $_.Exception.Message)
  }
  # Refusal before attempt commit: never write into a prior attempt dir.
  if ($script:RefusalNoAttemptWrite -or [string]::IsNullOrWhiteSpace($script:AttemptDir)) {
    Write-Host "attempt_evidence_untouched=true (refusal before attempt commit / no AttemptDir)"
    exit 1
  }
  if ($script:AttemptDir) {
    $q = Join-Path $script:AttemptDir "QUARANTINE_FAILED_ATTEMPT.txt"
    if (-not (Test-Path -LiteralPath $q)) {
      Set-Content $q -Encoding ascii -Value ("notes=" + ($script:DurableNotes -join " | "))
    }
    $failPath = Join-Path $script:AttemptDir "failure.receipt.json"
    if (-not (Test-Path -LiteralPath $failPath)) {
      $failReceipt = [ordered]@{
        failed                       = $true
        creation_ok                  = $false
        import_uncertain             = [bool]$script:ImportUncertain
        stamp_reuse_requires_review  = $true
        notes                        = @($script:DurableNotes)
        import_intent                = $script:ImportIntent
        probe_ledger                 = $script:ProbeLedger
        parent_failure_untouched     = $true
        exit_code_hint               = if ($script:ImportUncertain) { 3 } else { 1 }
      }
      Write-DurableReceipt $failReceipt $failPath
    }
    $script:FinalDurableWritten = $true
    Write-Host "attempt_quarantine=$q (parent failure/quarantine untouched; no auto-delete/retry)"
  }
  if ($script:ImportUncertain) { exit 3 }
  exit 1
}
