#Requires -Version 5.1
<#
  Injected-runner orchestration tests for reconstruction adoption preservation Core (no live Docker).

  OFFLINE BY DEFAULT: uses read-only cached save fixtures under
  F:\DropFolder\scratch\preg5-recon-save-fixtures only. Does NOT docker save unless
  -AllowGenerateFromDocker is passed explicitly (one-time RO seed; not adoption EXECUTE).
#>
[CmdletBinding()]
param(
  [switch] $AllowGenerateFromDocker
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "PreG5-ReconstructionAdoptionLib.ps1")

$failed = 0
function Assert-True([bool]$cond, [string]$msg) {
  if ($cond) { Write-Host "OK: $msg" }
  else { Write-Host "FAIL: $msg"; $script:failed++ }
}

function New-ReconstructionAdoptionTestRoot {
  $root = Join-Path "F:\DropFolder\backups" ("preg5-recon-adopt-test-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $root | Out-Null
  return $root
}

function New-TestApprovalJson {
  param(
    [Parameter(Mandatory = $true)][string] $Path,
    [Parameter(Mandatory = $true)][string] $DestDir,
    [Parameter(Mandatory = $true)][string] $ComposePinsPath,
    [Parameter(Mandatory = $true)][string] $DecisionSheetPath,
    [string] $Stamp = $script:PreG5ReconstructionDefaultStamp,
    [string] $ApiDigest = $script:PreG5ReconstructionDefaultApiDigest,
    [string] $WebDigest = $script:PreG5ReconstructionDefaultWebDigest,
    [switch] $NotApproved,
    [switch] $ApplyOptionalAdoptedTags,
    [hashtable] $ExtraFields = @{}
  )
  $plan = Get-PreG5ReconstructionAdoptionImagePlan -ExportStamp $Stamp -DestDir $DestDir `
    -ApiDigest $ApiDigest -WebDigest $WebDigest
  $obj = [ordered]@{
    approved                     = $(if ($NotApproved) { $false } else { $true })
    operation                    = $script:PreG5ReconstructionAdoptionOperation
    stamp                        = $Stamp
    api_image_id                 = $ApiDigest
    web_image_id                 = $WebDigest
    dest_dir                     = ([System.IO.Path]::GetFullPath($DestDir))
    api_tar_basename             = $plan.ApiTarBasename
    web_tar_basename             = $plan.WebTarBasename
    compose_pins_path            = ([System.IO.Path]::GetFullPath($ComposePinsPath))
    decision_sheet_path          = ([System.IO.Path]::GetFullPath($DecisionSheetPath))
    apply_optional_adopted_tags  = [bool]$ApplyOptionalAdoptedTags
  }
  foreach ($k in $ExtraFields.Keys) { $obj[$k] = $ExtraFields[$k] }
  ($obj | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $Path -Encoding utf8
}

function Copy-TestPinsTemplate {
  param([Parameter(Mandatory = $true)][string] $DestPath)
  @(
    '$script:ApiImageBaseline = "sha256:9aac7395a068d0761ad81c2339d60b69f5bd90e0cb7ef498f26d2634b0edfa36"'
    '$script:WebImageBaseline = "sha256:bff14006fb87757ce5c5ce28be24223195a01e4154de0d437430dfaa3f89c928"'
  ) | Set-Content -LiteralPath $DestPath -Encoding utf8
}

function Copy-TestDecisionSheetTemplate {
  param([Parameter(Mandatory = $true)][string] $DestPath)
  @(
    "## 1. Pre-rebuild image baseline (rollback reference)"
    ""
    "| Component | Digest (full — rollback target) |"
    "| --- | --- |"
    "| **API** (`compose-api-1`) | **`sha256:9aac7395a068d0761ad81c2339d60b69f5bd90e0cb7ef498f26d2634b0edfa36`** |"
    "| **Web** (`compose-web-1`) | **`sha256:bff14006fb87757ce5c5ce28be24223195a01e4154de0d437430dfaa3f89c928`** |"
    ""
    "## 7. Paired rollback (digest-pinned)"
    ""
    "| Mid-G4 | Restore API **`sha256:9aac7395a068d0761ad81c2339d60b69f5bd90e0cb7ef498f26d2634b0edfa36`** |"
    "| Post-G5 | web **`sha256:bff14006fb87757ce5c5ce28be24223195a01e4154de0d437430dfaa3f89c928`** |"
  ) | Set-Content -LiteralPath $DestPath -Encoding utf8
}

function New-FakeReconstructionAdoptionDockerHarness {
  param(
    [string] $ApiDigest = $script:PreG5ReconstructionDefaultApiDigest,
    [string] $WebDigest = $script:PreG5ReconstructionDefaultWebDigest,
    [bool] $AllowGenerateFromDocker = $false
  )
  $state = @{
    Images              = @{
      $ApiDigest = $ApiDigest
      $WebDigest = $WebDigest
    }
    Containers          = @{
      $script:PreG5ReconstructionHouseholdApiContainer = @{
        Image  = $script:PreG5ReconstructionOldOperationalApi
        Health = 'healthy'
      }
      $script:PreG5ReconstructionHouseholdWebContainer = @{
        Image  = $script:PreG5ReconstructionOldOperationalWeb
        Health = 'healthy'
      }
    }
    SaveFailDigest      = $null
    SaveSynthMode       = $null
    SaveSynthDigest     = $null
    TagInspectFailTag   = $null
    AllowGenerateFromDocker = $AllowGenerateFromDocker
    CallLog             = New-Object System.Collections.Generic.List[string]
  }
  $runner = {
    param([string[]]$DockerArgs, [string]$What, [int]$TimeoutMs)
    $state.CallLog.Add(($DockerArgs -join ' '))
    $cmd = $DockerArgs[0]
    if ($cmd -eq 'image' -and $DockerArgs.Count -ge 2 -and $DockerArgs[1] -eq 'inspect') {
      $ref = $DockerArgs[2]
      $fmt = ""
      for ($i = 0; $i -lt $DockerArgs.Count; $i++) {
        if ($DockerArgs[$i] -eq '--format' -and ($i + 1) -lt $DockerArgs.Count) { $fmt = $DockerArgs[$i + 1] }
      }
      if (-not $state.Images.ContainsKey($ref)) {
        return @{ Code = 1; StdOut = ""; StdErr = "Error: No such object: $ref"; TimedOut = $false }
      }
      $id = $state.Images[$ref]
      if ($null -ne $state.TagInspectFailTag -and $ref -eq $state.TagInspectFailTag) {
        $id = "sha256:0000000000000000000000000000000000000000000000000000000000000001"
      }
      if ($fmt -eq '{{.Id}}') {
        return @{ Code = 0; StdOut = ($id + "`n"); StdErr = ""; TimedOut = $false }
      }
      if ($fmt -eq '{{json .RepoTags}}') {
        return @{ Code = 0; StdOut = '["compose-api:latest"]'; StdErr = ""; TimedOut = $false }
      }
      return @{ Code = 0; StdOut = $id; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'inspect') {
      $name = $DockerArgs[1]
      $fmt = ""
      for ($i = 0; $i -lt $DockerArgs.Count; $i++) {
        if ($DockerArgs[$i] -eq '--format' -and ($i + 1) -lt $DockerArgs.Count) { $fmt = $DockerArgs[$i + 1] }
      }
      if (-not $state.Containers.ContainsKey($name)) {
        return @{ Code = 1; StdOut = ""; StdErr = "Error: No such object: $name"; TimedOut = $false }
      }
      $c = $state.Containers[$name]
      if ($fmt -eq '{{.Image}}') {
        return @{ Code = 0; StdOut = ($c.Image + "`n"); StdErr = ""; TimedOut = $false }
      }
      if ($fmt -match 'Health') {
        return @{ Code = 0; StdOut = ($c.Health + "`n"); StdErr = ""; TimedOut = $false }
      }
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'save') {
      $ref = $DockerArgs[1]
      $outPath = $null
      for ($i = 0; $i -lt $DockerArgs.Count; $i++) {
        if ($DockerArgs[$i] -eq '-o' -and ($i + 1) -lt $DockerArgs.Count) { $outPath = $DockerArgs[$i + 1] }
      }
      if ([string]::IsNullOrWhiteSpace($outPath)) { throw "FAIL: save missing -o path" }
      if ($state.SaveFailDigest -eq $ref) { throw "FAIL: docker save $ref exited 1" }
      if (-not $state.Images.ContainsKey($ref)) { throw "FAIL: save unknown ref $ref" }
      if ($null -ne $state.SaveSynthMode -and $state.SaveSynthDigest -eq $ref) {
        New-PreG5SyntheticDockerSaveTar -Path $outPath -ImageId $state.Images[$ref] -Mode $state.SaveSynthMode | Out-Null
      } else {
        Copy-PreG5ReconstructionSaveFixture -Digest $ref -DestPath $outPath `
          -AllowGenerateFromDocker:([bool]$state.AllowGenerateFromDocker)
      }
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'tag') {
      $src = $DockerArgs[1]; $dst = $DockerArgs[2]
      $state.Images[$dst] = $src
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'load') {
      throw "REFUSE: docker load must not be invoked by reconstruction adoption runner"
    }
    return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
  }.GetNewClosure()
  return @{ State = $state; Runner = $runner }
}

Write-Host ("ps_version={0}" -f $PSVersionTable.PSVersion.ToString())
Assert-True ($PSVersionTable.PSVersion.Major -eq 5) "Windows PowerShell 5.x runtime"

$api = $script:PreG5ReconstructionDefaultApiDigest
$web = $script:PreG5ReconstructionDefaultWebDigest
$stamp = $script:PreG5ReconstructionDefaultStamp

if ($AllowGenerateFromDocker) {
  Write-Host "preg5_recon_fixture_mode=explicit_generate"
  Get-PreG5ReconstructionSaveFixturePath -Digest $api -AllowGenerateFromDocker | Out-Null
  Get-PreG5ReconstructionSaveFixturePath -Digest $web -AllowGenerateFromDocker | Out-Null
} else {
  Write-Host "preg5_recon_fixture_mode=offline_cache_only"
}
try {
  Assert-PreG5ReconstructionSaveFixturesCached -Digests @($api, $web) -AllowGenerateFromDocker:$AllowGenerateFromDocker
  Assert-True $true "save fixtures cached for offline orchestration"
} catch {
  Assert-True $false ("save fixtures cached: " + $_.Exception.Message)
}

# --- refuse without -Execute ---
try {
  & (Join-Path $PSScriptRoot "Invoke-PreG5ReconstructionAdoptionPreservation.ps1") -AuditApprovalPath "x"
  Assert-True $false "invoke wrapper should refuse without -Execute"
} catch {
  Assert-True ($_.Exception.Message -match 'PLANNING ONLY') "invoke wrapper planning refuse"
}

# --- OCI fixture identity (content hash, not filename) ---
$fixtureApi = Get-PreG5ReconstructionSaveFixturePath -Digest $api
if ($null -ne $fixtureApi) {
  try {
    Assert-PreG5DockerSaveTarIdentity -TarPath $fixtureApi -ExpectedImageId $api | Out-Null
    Assert-True $true "real OCI fixture identity ok"
  } catch {
    Assert-True $false ("real OCI fixture identity: " + $_.Exception.Message)
  }
}

# --- wrong config bytes under right filename (legacy synthetic) ---
$tarWrongBytes = Join-Path $env:TEMP ("preg5-recon-wrongbytes-" + [guid]::NewGuid().ToString("N") + ".tar")
New-PreG5SyntheticDockerSaveTar -Path $tarWrongBytes -ImageId $api -Mode 'wrong_config_bytes' | Out-Null
try {
  Assert-PreG5DockerSaveTarIdentity -TarPath $tarWrongBytes -ExpectedImageId $api | Out-Null
  Assert-True $false "wrong config bytes should fail identity"
} catch {
  Assert-True ($_.Exception.Message -match 'config content digest mismatch|config blob empty') "wrong config bytes refused"
}
Remove-Item -LiteralPath $tarWrongBytes -Force -ErrorAction SilentlyContinue

# --- missing layer ---
$tarMissing = Join-Path $env:TEMP ("preg5-recon-missinglayer-" + [guid]::NewGuid().ToString("N") + ".tar")
$synth = New-PreG5SyntheticDockerSaveTar -Path $tarMissing -ImageId $api -Mode 'missing_layer'
try {
  Assert-PreG5DockerSaveTarIdentity -TarPath $tarMissing -ExpectedImageId $synth.ImageId | Out-Null
  Assert-True $false "missing layer should fail"
} catch {
  Assert-True ($_.Exception.Message -match 'layer path missing|layer blob missing') "missing layer refused"
}
Remove-Item -LiteralPath $tarMissing -Force -ErrorAction SilentlyContinue

# --- import approval reuse refuse ---
$rootImp = New-ReconstructionAdoptionTestRoot
try {
  $destImp = Join-Path $rootImp "rollback-images"
  $apImp = Join-Path $rootImp "approval-import-reuse.json"
  New-TestApprovalJson -Path $apImp -DestDir $destImp -ComposePinsPath (Join-Path $rootImp "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootImp "sheet.md") -ExtraFields @{ snapshot_api_image_id = $api }
  $hImp = New-FakeReconstructionAdoptionDockerHarness -AllowGenerateFromDocker:$AllowGenerateFromDocker
  $script:PreG5DockerRunner = $hImp.Runner
  $rImp = Invoke-PreG5ReconstructionAdoptionPreservationCore -DestDir $destImp -ExportStamp $stamp `
    -AuditApprovalPath $apImp -ComposePinsPath (Join-Path $rootImp "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootImp "sheet.md") -SkipHouseholdGuard
  Assert-True ($rImp.ExitCode -ne 0) "import approval reuse refuse"
  Assert-True ($rImp.Phase -eq 'approval') "import approval reuse phase"
} finally {
  $script:PreG5DockerRunner = $null
  Remove-Item -LiteralPath $rootImp -Recurse -Force -ErrorAction SilentlyContinue
}

# --- existing custody refuse ---
$rootA = New-ReconstructionAdoptionTestRoot
try {
  $destA = Join-Path $rootA "rollback-images"
  New-Item -ItemType Directory -Path $destA | Out-Null
  $planA = Get-PreG5ReconstructionAdoptionImagePlan -DestDir $destA -ExportStamp $stamp
  New-Item -ItemType File -Path $planA.ApiTar | Out-Null
  $apA = Join-Path $rootA "approval.json"
  New-TestApprovalJson -Path $apA -DestDir $destA -ComposePinsPath (Join-Path $rootA "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootA "sheet.md")
  $hA = New-FakeReconstructionAdoptionDockerHarness -AllowGenerateFromDocker:$AllowGenerateFromDocker
  $script:PreG5DockerRunner = $hA.Runner
  $rA = Invoke-PreG5ReconstructionAdoptionPreservationCore -DestDir $destA -ExportStamp $stamp `
    -AuditApprovalPath $apA -ComposePinsPath (Join-Path $rootA "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootA "sheet.md") -SkipHouseholdGuard
  Assert-True ($rA.ExitCode -ne 0) "existing tar refuse nonzero exit"
  Assert-True ($rA.Phase -eq 'preflight_custody_absent') "existing tar refuse phase"
  Assert-True ($rA.Changed.Count -eq 0) "existing tar refuse no pin changes"
  Assert-True ($null -ne $rA.FailureReceiptPath) "existing tar failure receipt"
} finally {
  $script:PreG5DockerRunner = $null
  Remove-Item -LiteralPath $rootA -Recurse -Force -ErrorAction SilentlyContinue
}

# --- api save failure ---
$rootB = New-ReconstructionAdoptionTestRoot
try {
  $destB = Join-Path $rootB "rollback-images"
  $apB = Join-Path $rootB "approval.json"
  New-TestApprovalJson -Path $apB -DestDir $destB -ComposePinsPath (Join-Path $rootB "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootB "sheet.md")
  Copy-TestPinsTemplate -DestPath (Join-Path $rootB "pins.ps1")
  $pinsBefore = Get-Content -LiteralPath (Join-Path $rootB "pins.ps1") -Raw
  $hB = New-FakeReconstructionAdoptionDockerHarness -AllowGenerateFromDocker:$AllowGenerateFromDocker
  $hB.State.SaveFailDigest = $api
  $script:PreG5DockerRunner = $hB.Runner
  $rB = Invoke-PreG5ReconstructionAdoptionPreservationCore -DestDir $destB -ExportStamp $stamp `
    -AuditApprovalPath $apB -ComposePinsPath (Join-Path $rootB "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootB "sheet.md") -SkipHouseholdGuard
  $pinsAfter = Get-Content -LiteralPath (Join-Path $rootB "pins.ps1") -Raw
  Assert-True ($rB.ExitCode -ne 0) "api save fail nonzero"
  Assert-True ($rB.Phase -eq 'save_api') "api save fail phase"
  Assert-True ($pinsBefore -eq $pinsAfter) "api save fail pins unchanged"
} finally {
  $script:PreG5DockerRunner = $null
  Remove-Item -LiteralPath $rootB -Recurse -Force -ErrorAction SilentlyContinue
}

# --- empty save output ---
$rootC = New-ReconstructionAdoptionTestRoot
try {
  $destC = Join-Path $rootC "rollback-images"
  $apC = Join-Path $rootC "approval.json"
  New-TestApprovalJson -Path $apC -DestDir $destC -ComposePinsPath (Join-Path $rootC "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootC "sheet.md")
  $hC = New-FakeReconstructionAdoptionDockerHarness -AllowGenerateFromDocker:$AllowGenerateFromDocker
  $hC.State.SaveSynthMode = 'empty_archive'
  $hC.State.SaveSynthDigest = $api
  $script:PreG5DockerRunner = $hC.Runner
  $rC = Invoke-PreG5ReconstructionAdoptionPreservationCore -DestDir $destC -ExportStamp $stamp `
    -AuditApprovalPath $apC -ComposePinsPath (Join-Path $rootC "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootC "sheet.md") -SkipHouseholdGuard
  Assert-True ($rC.ExitCode -ne 0) "empty save refuse"
  Assert-True ($rC.Phase -eq 'save_api') "empty save phase save_api"
} finally {
  $script:PreG5DockerRunner = $null
  Remove-Item -LiteralPath $rootC -Recurse -Force -ErrorAction SilentlyContinue
}

# --- web fails after api finalized ---
$rootE = New-ReconstructionAdoptionTestRoot
try {
  $destE = Join-Path $rootE "rollback-images"
  $apE = Join-Path $rootE "approval.json"
  New-TestApprovalJson -Path $apE -DestDir $destE -ComposePinsPath (Join-Path $rootE "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootE "sheet.md")
  Copy-TestPinsTemplate -DestPath (Join-Path $rootE "pins.ps1")
  Copy-TestDecisionSheetTemplate -DestPath (Join-Path $rootE "sheet.md")
  $hE = New-FakeReconstructionAdoptionDockerHarness -AllowGenerateFromDocker:$AllowGenerateFromDocker
  $hE.State.SaveFailDigest = $web
  $script:PreG5DockerRunner = $hE.Runner
  $rE = Invoke-PreG5ReconstructionAdoptionPreservationCore -DestDir $destE -ExportStamp $stamp `
    -AuditApprovalPath $apE -ComposePinsPath (Join-Path $rootE "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootE "sheet.md") -SkipHouseholdGuard
  $planE = Get-PreG5ReconstructionAdoptionImagePlan -DestDir $destE -ExportStamp $stamp
  Assert-True ($rE.ExitCode -ne 0) "web fail after api nonzero"
  Assert-True ($rE.Phase -eq 'save_web') "web fail phase save_web"
  Assert-True (Test-Path -LiteralPath $planE.ApiTar) "api archive preserved"
  Assert-True (-not $rE.ArchivesFinalized) "web fail archives not both finalized"
} finally {
  $script:PreG5DockerRunner = $null
  Remove-Item -LiteralPath $rootE -Recurse -Force -ErrorAction SilentlyContinue
}

# --- household guard fail after archives (injected) ---
$rootHg = New-ReconstructionAdoptionTestRoot
try {
  $destHg = Join-Path $rootHg "rollback-images"
  $apHg = Join-Path $rootHg "approval.json"
  $pinsHg = Join-Path $rootHg "pins.ps1"
  $sheetHg = Join-Path $rootHg "sheet.md"
  New-TestApprovalJson -Path $apHg -DestDir $destHg -ComposePinsPath $pinsHg -DecisionSheetPath $sheetHg
  Copy-TestPinsTemplate -DestPath $pinsHg
  Copy-TestDecisionSheetTemplate -DestPath $sheetHg
  $pinsBeforeHg = Get-Content -LiteralPath $pinsHg -Raw
  $hHg = New-FakeReconstructionAdoptionDockerHarness -AllowGenerateFromDocker:$AllowGenerateFromDocker
  $hHg.State.Containers[$script:PreG5ReconstructionHouseholdApiContainer].Image = $api
  $script:PreG5DockerRunner = $hHg.Runner
  $rHg = Invoke-PreG5ReconstructionAdoptionPreservationCore -DestDir $destHg -ExportStamp $stamp `
    -AuditApprovalPath $apHg -ComposePinsPath $pinsHg -DecisionSheetPath $sheetHg
  Assert-True ($rHg.ExitCode -ne 0) "household guard fail nonzero"
  Assert-True ($rHg.Phase -eq 'household_guard') "household guard phase"
  Assert-True ($rHg.ArchivesFinalized) "household guard archives finalized"
  Assert-True ((Get-Content -LiteralPath $pinsHg -Raw) -eq $pinsBeforeHg) "household guard pins unchanged"
  Assert-True ($null -ne $rHg.FailureReceiptPath) "household guard failure receipt"
} finally {
  $script:PreG5DockerRunner = $null
  Remove-Item -LiteralPath $rootHg -Recurse -Force -ErrorAction SilentlyContinue
}

# --- partial pin failure (api applied, web blocked) ---
$rootPp = New-ReconstructionAdoptionTestRoot
try {
  $destPp = Join-Path $rootPp "rollback-images"
  $apPp = Join-Path $rootPp "approval.json"
  $pinsPp = Join-Path $rootPp "pins.ps1"
  $sheetPp = Join-Path $rootPp "sheet.md"
  New-TestApprovalJson -Path $apPp -DestDir $destPp -ComposePinsPath $pinsPp -DecisionSheetPath $sheetPp
  Copy-TestPinsTemplate -DestPath $pinsPp
  Copy-TestDecisionSheetTemplate -DestPath $sheetPp
  $script:PreG5ReconstructionOrchBlockPinWeb = $true
  $hPp = New-FakeReconstructionAdoptionDockerHarness -AllowGenerateFromDocker:$AllowGenerateFromDocker
  $script:PreG5DockerRunner = $hPp.Runner
  $rPp = Invoke-PreG5ReconstructionAdoptionPreservationCore -DestDir $destPp -ExportStamp $stamp `
    -AuditApprovalPath $apPp -ComposePinsPath $pinsPp -DecisionSheetPath $sheetPp -SkipHouseholdGuard
  $gotPins = Get-PreG5ComposePinsBaselines -PinsPath $pinsPp
  Assert-True ($rPp.ExitCode -ne 0) "partial pin fail nonzero"
  Assert-True ($rPp.Phase -eq 'pin_web_baseline') "partial pin fail phase"
  Assert-True ($gotPins.Api -eq $api) "partial pin api applied"
  Assert-True ($gotPins.Web -eq $script:PreG5ReconstructionOldOperationalWeb) "partial pin web unchanged"
  Assert-True ($rPp.Changed.Count -ge 1) "partial pin changed list includes api"
  if ($null -ne $rPp.FailureReceiptPath) {
    $rcptPp = Get-Content -LiteralPath $rPp.FailureReceiptPath -Raw | ConvertFrom-Json
    $webUnc = @($rcptPp.changed_uncertain | Where-Object { $_ -match 'WebImageBaseline' }).Count -ge 1
    Assert-True $webUnc "partial pin web mutation uncertain in failure receipt"
  }
} finally {
  $script:PreG5ReconstructionOrchBlockPinWeb = $false
  $script:PreG5DockerRunner = $null
  Remove-Item -LiteralPath $rootPp -Recurse -Force -ErrorAction SilentlyContinue
}

# --- partial tag failure ---
$rootPt = New-ReconstructionAdoptionTestRoot
try {
  $destPt = Join-Path $rootPt "rollback-images"
  $apPt = Join-Path $rootPt "approval.json"
  $pinsPt = Join-Path $rootPt "pins.ps1"
  $sheetPt = Join-Path $rootPt "sheet.md"
  New-TestApprovalJson -Path $apPt -DestDir $destPt -ComposePinsPath $pinsPt -DecisionSheetPath $sheetPt -ApplyOptionalAdoptedTags
  Copy-TestPinsTemplate -DestPath $pinsPt
  Copy-TestDecisionSheetTemplate -DestPath $sheetPt
  $script:PreG5ReconstructionOrchBlockTagWeb = $true
  $hPt = New-FakeReconstructionAdoptionDockerHarness -AllowGenerateFromDocker:$AllowGenerateFromDocker
  $script:PreG5DockerRunner = $hPt.Runner
  $rPt = Invoke-PreG5ReconstructionAdoptionPreservationCore -DestDir $destPt -ExportStamp $stamp `
    -AuditApprovalPath $apPt -ComposePinsPath $pinsPt -DecisionSheetPath $sheetPt `
    -ApplyOptionalAdoptedTags -SkipHouseholdGuard
  Assert-True ($rPt.ExitCode -ne 0) "partial tag fail nonzero"
  Assert-True ($rPt.Phase -eq 'optional_tag_web') "partial tag fail phase"
  $apiTagChanged = @($rPt.Changed | Where-Object { $_ -match 'docker_tag:.*adopted-e4221a0e' }).Count -ge 1
  Assert-True $apiTagChanged "partial tag api tag recorded"
} finally {
  $script:PreG5ReconstructionOrchBlockTagWeb = $false
  $script:PreG5DockerRunner = $null
  Remove-Item -LiteralPath $rootPt -Recurse -Force -ErrorAction SilentlyContinue
}

# --- uncertain: tag applied then inspect/readback fails (case: uncertain_tag_inspect_fail_after_tag) ---
$rootUt = New-ReconstructionAdoptionTestRoot
try {
  $destUt = Join-Path $rootUt "rollback-images"
  $apUt = Join-Path $rootUt "approval.json"
  $pinsUt = Join-Path $rootUt "pins.ps1"
  $sheetUt = Join-Path $rootUt "sheet.md"
  New-TestApprovalJson -Path $apUt -DestDir $destUt -ComposePinsPath $pinsUt -DecisionSheetPath $sheetUt -ApplyOptionalAdoptedTags
  Copy-TestPinsTemplate -DestPath $pinsUt
  Copy-TestDecisionSheetTemplate -DestPath $sheetUt
  $planUt = Get-PreG5ReconstructionAdoptionImagePlan -DestDir $destUt -ExportStamp $stamp
  $hUt = New-FakeReconstructionAdoptionDockerHarness -AllowGenerateFromDocker:$AllowGenerateFromDocker
  $hUt.State.TagInspectFailTag = $planUt.ApiAdoptedTag
  $script:PreG5DockerRunner = $hUt.Runner
  $rUt = Invoke-PreG5ReconstructionAdoptionPreservationCore -DestDir $destUt -ExportStamp $stamp `
    -AuditApprovalPath $apUt -ComposePinsPath $pinsUt -DecisionSheetPath $sheetUt `
    -ApplyOptionalAdoptedTags -SkipHouseholdGuard
  Assert-True ($rUt.ExitCode -ne 0) "uncertain tag inspect fail nonzero"
  Assert-True ($rUt.Phase -eq 'optional_tag_api') "uncertain tag inspect fail phase"
  $tagKey = "docker_tag:" + $planUt.ApiAdoptedTag
  $uncertainHasTag = @($rUt.Uncertain | Where-Object { $_ -eq $tagKey }).Count -ge 1
  Assert-True $uncertainHasTag "uncertain tag in result Uncertain list"
  $changedHasTag = @($rUt.Changed | Where-Object { $_ -eq $tagKey }).Count -ge 1
  Assert-True (-not $changedHasTag) "uncertain tag not promoted to Changed"
  Assert-True ($null -ne $rUt.FailureReceiptPath) "uncertain tag failure receipt path"
  $rcptUt = Get-Content -LiteralPath $rUt.FailureReceiptPath -Raw | ConvertFrom-Json
  $receiptUncertainTag = @($rcptUt.changed_uncertain | Where-Object { $_ -eq $tagKey }).Count -ge 1
  Assert-True $receiptUncertainTag "uncertain_tag_inspect_fail_after_tag in failure receipt"
} finally {
  $script:PreG5DockerRunner = $null
  Remove-Item -LiteralPath $rootUt -Recurse -Force -ErrorAction SilentlyContinue
}

# --- happy path ---
$rootF = New-ReconstructionAdoptionTestRoot
try {
  $destF = Join-Path $rootF "rollback-images"
  $apF = Join-Path $rootF "approval.json"
  $pinsF = Join-Path $rootF "pins.ps1"
  $sheetF = Join-Path $rootF "sheet.md"
  New-TestApprovalJson -Path $apF -DestDir $destF -ComposePinsPath $pinsF -DecisionSheetPath $sheetF
  Copy-TestPinsTemplate -DestPath $pinsF
  Copy-TestDecisionSheetTemplate -DestPath $sheetF
  $hF = New-FakeReconstructionAdoptionDockerHarness -AllowGenerateFromDocker:$AllowGenerateFromDocker
  $script:PreG5DockerRunner = $hF.Runner
  $rF = Invoke-PreG5ReconstructionAdoptionPreservationCore -DestDir $destF -ExportStamp $stamp `
    -AuditApprovalPath $apF -ComposePinsPath $pinsF -DecisionSheetPath $sheetF -SkipHouseholdGuard
  $planF = Get-PreG5ReconstructionAdoptionImagePlan -DestDir $destF -ExportStamp $stamp
  Assert-True ($rF.ExitCode -eq 0) "happy path exit 0"
  Assert-True (Test-Path -LiteralPath $planF.ApiTar) "happy api tar"
  Assert-True (Test-Path -LiteralPath $planF.WebTar) "happy web tar"
  Assert-PreG5ComposePinsBaselinesMatch -PinsPath $pinsF -ApiDigest $api -WebDigest $web
  Assert-True $true "happy path pin readback both baselines"
} finally {
  $script:PreG5DockerRunner = $null
  Remove-Item -LiteralPath $rootF -Recurse -Force -ErrorAction SilentlyContinue
}

# --- approval gate ---
$rootG = New-ReconstructionAdoptionTestRoot
try {
  $destG = Join-Path $rootG "rollback-images"
  $apG = Join-Path $rootG "approval.json"
  New-TestApprovalJson -Path $apG -DestDir $destG -ComposePinsPath (Join-Path $rootG "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootG "sheet.md") -NotApproved
  $hG = New-FakeReconstructionAdoptionDockerHarness -AllowGenerateFromDocker:$AllowGenerateFromDocker
  $script:PreG5DockerRunner = $hG.Runner
  $rG = Invoke-PreG5ReconstructionAdoptionPreservationCore -DestDir $destG -ExportStamp $stamp `
    -AuditApprovalPath $apG -ComposePinsPath (Join-Path $rootG "pins.ps1") `
    -DecisionSheetPath (Join-Path $rootG "sheet.md") -SkipHouseholdGuard
  Assert-True ($rG.ExitCode -ne 0) "approval gate refuse"
  Assert-True ($rG.Phase -eq 'approval') "approval gate phase"
} finally {
  $script:PreG5DockerRunner = $null
  Remove-Item -LiteralPath $rootG -Recurse -Force -ErrorAction SilentlyContinue
}

$script:PreG5DockerRunner = $null
if ($failed -eq 0) {
  Write-Host "VALIDATE_PREG5_RECONSTRUCTION_ADOPTION_OK"
  exit 0
}
Write-Host "VALIDATE_PREG5_RECONSTRUCTION_ADOPTION_FAIL count=$failed"
exit 1
