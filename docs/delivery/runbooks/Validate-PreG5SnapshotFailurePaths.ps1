#Requires -Version 5.1
<#
  Harmless failure-path evidence for pre-G5 pause/unpause orchestration, custody, audit, import gates.
  Exercises production helper transitions via controlled process/inspect inputs.
  Does NOT pause, export, or touch live household containers.
  Target runtime: Windows PowerShell 5.1.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "PreG5-SnapshotHelpers.ps1")

$failed = 0
function Assert-True([bool]$cond, [string]$msg) {
  if ($cond) { Write-Host "OK: $msg" }
  else { Write-Host "FAIL: $msg"; $script:failed++ }
}

Write-Host ("ps_version={0}" -f $PSVersionTable.PSVersion.ToString())
Assert-True ($PSVersionTable.PSVersion.Major -eq 5) "Windows PowerShell 5.x runtime"

# --- Fake docker harness (in-memory containers/images; no live Docker) ---
function New-FakeDockerHarness {
  $state = @{
    Containers         = @{}
    Images             = @{}   # tag -> id
    PauseFail          = @{}
    UnpauseFail        = @{}
    InspectFail        = @{}
    ImageInspectErr    = @{}
    ImportTimeoutTags       = @{}   # tag -> $true
    ImportLateCreate        = @{}   # tag -> $true : create image then TIMEOUT
    ProbeTimeoutNames       = @{}   # container name or id -> TIMEOUT on start (after create owns id)
    ProbeCreateTimeoutNames = @{}   # name -> TIMEOUT on create (no OwnedId returned)
    ProbeCreateLateNames    = @{}   # name -> late-create container then TIMEOUT (create outcome unknown)
    RmFailIds               = @{}   # id -> $true
    CallLog                 = New-Object System.Collections.Generic.List[string]
  }
  $runner = {
    param([string[]]$DockerArgs, [string]$What, [int]$TimeoutMs)
    $cmd = $DockerArgs[0]
    $state.CallLog.Add(($DockerArgs -join ' '))
    if ($cmd -eq 'pause') {
      $id = $DockerArgs[1]
      if ($state.PauseFail.ContainsKey($id)) { throw "FAIL: pause simulated exit 1" }
      if (-not $state.Containers.ContainsKey($id)) { throw "FAIL: pause unknown $id" }
      $state.Containers[$id].Paused = $true
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'unpause') {
      $id = $DockerArgs[1]
      if ($state.UnpauseFail.ContainsKey($id)) { throw "FAIL: unpause simulated exit 1" }
      if (-not $state.Containers.ContainsKey($id)) { throw "FAIL: unpause unknown $id" }
      $state.Containers[$id].Paused = $false
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'tag') {
      $srcId = $DockerArgs[1]
      $dstTag = $DockerArgs[2]
      $state.Images[$dstTag] = $srcId
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'import') {
      $tag = $DockerArgs[$DockerArgs.Count - 1]
      if ($state.ImportTimeoutTags.ContainsKey($tag)) {
        if ($state.ImportLateCreate.ContainsKey($tag)) {
          $state.Images[$tag] = "sha256:latecreated-$tag"
        }
        throw ("TIMEOUT: import $tag exceeded ${TimeoutMs}ms (client killed; daemon work may continue)")
      }
      $state.Images[$tag] = "sha256:imported-$tag"
      return @{ Code = 0; StdOut = $state.Images[$tag]; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'create') {
      $name = $null; $label = ""; $image = $null
      for ($i = 0; $i -lt $DockerArgs.Count; $i++) {
        if ($DockerArgs[$i] -eq '--name' -and ($i + 1) -lt $DockerArgs.Count) { $name = $DockerArgs[$i + 1] }
        if ($DockerArgs[$i] -eq '--label' -and ($i + 1) -lt $DockerArgs.Count) {
          $lv = $DockerArgs[$i + 1]
          if ($lv -match '^preg5\.attempt=(.+)$') { $label = $Matches[1] }
        }
      }
      # image is last non-flag token before args — approximate: last arg that doesn't start with - and isn't after entrypoint payload
      foreach ($a in $DockerArgs) {
        if ($a -match '^(theplan-|sha256:|preg5)') { $image = $a }
      }
      if (-not $image) { $image = $DockerArgs[$DockerArgs.Count - 3] }
      if (-not $name) { throw "FAIL: create without --name" }
      # foreign collision: name already mapped
      foreach ($k in @($state.Containers.Keys)) {
        if ($state.Containers[$k].Name -eq $name) { throw "FAIL: create name conflict $name exited 1" }
      }
      if ($state.ProbeCreateTimeoutNames.ContainsKey($name)) {
        if ($state.ProbeCreateLateNames.ContainsKey($name)) {
          $cidLate = "cid-late-$name"
          $state.Containers[$cidLate] = @{
            Id = $cidLate; Name = $name; Image = $image; Label = $label; Running = $false; Paused = $false; Status = "created"
          }
        }
        throw ("TIMEOUT: create $name exceeded ${TimeoutMs}ms (client killed; daemon work may continue)")
      }
      $cid = "cid-$name"
      $state.Containers[$cid] = @{
        Id = $cid; Name = $name; Image = $image; Label = $label; Running = $false; Paused = $false; Status = "created"
      }
      return @{ Code = 0; StdOut = $cid; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'start') {
      $id = $DockerArgs[$DockerArgs.Count - 1]
      if (-not $state.Containers.ContainsKey($id)) { throw "Error: No such object: $id" }
      $c = $state.Containers[$id]
      $c.Running = $true
      $c.Status = "running"
      if ($state.ProbeTimeoutNames.ContainsKey($c.Name)) {
        throw ("TIMEOUT: start $($c.Name) exceeded ${TimeoutMs}ms (client killed; daemon work may continue)")
      }
      if ($state.ProbeTimeoutNames.ContainsKey($id)) {
        throw ("TIMEOUT: start $id exceeded ${TimeoutMs}ms")
      }
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'rm') {
      $target = $DockerArgs[$DockerArgs.Count - 1]
      if ($state.RmFailIds.ContainsKey($target)) { throw "FAIL: rm $target exited 1" }
      $keys = @($state.Containers.Keys)
      foreach ($k in $keys) {
        if ($k -eq $target -or $state.Containers[$k].Name -eq $target -or $state.Containers[$k].Id -eq $target) {
          $state.Containers.Remove($k)
        }
      }
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'image' -and $DockerArgs.Count -ge 2 -and $DockerArgs[1] -eq 'inspect') {
      $tag = $DockerArgs[2]
      if ($state.ImageInspectErr.ContainsKey($tag)) {
        $kind = $state.ImageInspectErr[$tag]
        if ($kind -eq 'timeout') { throw "TIMEOUT: image inspect $tag exceeded ${TimeoutMs}ms" }
        if ($kind -eq 'daemon') {
          return @{ Code = 1; StdOut = ""; StdErr = "Cannot connect to the Docker daemon at unix:///var/run/docker.sock"; TimedOut = $false }
        }
        if ($kind -eq 'daemon-not-found') {
          return @{ Code = 1; StdOut = ""; StdErr = "Cannot connect to the Docker daemon: pipe not found"; TimedOut = $false }
        }
        if ($kind -eq 'generic-not-found') {
          return @{ Code = 1; StdOut = ""; StdErr = "Error: path not found while inspecting"; TimedOut = $false }
        }
        return @{ Code = 1; StdOut = ""; StdErr = "FAIL: image inspect $tag exited 1"; TimedOut = $false }
      }
      if (-not $state.Images.ContainsKey($tag)) {
        return @{ Code = 1; StdOut = ""; StdErr = "Error: No such object: $tag"; TimedOut = $false }
      }
      return @{ Code = 0; StdOut = $state.Images[$tag]; StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'inspect') {
      $target = $DockerArgs[1]
      $fmt = ""
      for ($i = 0; $i -lt $DockerArgs.Count; $i++) {
        if ($DockerArgs[$i] -eq '--format' -and ($i + 1) -lt $DockerArgs.Count) { $fmt = $DockerArgs[$i + 1] }
      }
      $c = $null
      if ($state.Containers.ContainsKey($target)) {
        $c = $state.Containers[$target]
      } else {
        foreach ($k in @($state.Containers.Keys)) {
          if ($state.Containers[$k].Name -eq $target) { $c = $state.Containers[$k]; break }
        }
      }
      if ($null -eq $c) { throw ("Error: No such object: $target") }
      if ($state.InspectFail.ContainsKey($c.Id)) { throw "FAIL: inspect simulated for $($c.Id)" }
      $running = if ($c.Running) { "true" } else { "false" }
      $paused = if ($c.Paused) { "true" } else { "false" }
      if ($fmt -eq '{{.Id}}') {
        return @{ Code = 0; StdOut = $c.Id; StdErr = ""; TimedOut = $false }
      }
      if ($fmt -match 'preg5\.attempt') {
        $lbl = ""
        if ($c.ContainsKey('Label')) { $lbl = $c.Label }
        $out = "{0}|/{1}|{2}|{3}" -f $c.Id, $c.Name, $c.Image, $lbl
        return @{ Code = 0; StdOut = $out; StdErr = ""; TimedOut = $false }
      }
      if ($fmt -match '\{\{\.Name\}\}') {
        $out = "{0}|/{1}|{2}|{3}|{4}|{5}" -f $c.Id, $c.Name, $c.Image, $running, $paused, $c.Status
      } else {
        $out = "{0}|{1}|{2}|{3}|{4}" -f $c.Id, $c.Image, $running, $paused, $c.Status
      }
      return @{ Code = 0; StdOut = $out; StdErr = ""; TimedOut = $false }
    }
    return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
  }.GetNewClosure()

  return @{ State = $state; Runner = $runner }
}

function Add-FakeContainer($harness, [string]$Id, [string]$Name, [string]$Image = "sha256:img") {
  $harness.State.Containers[$Id] = @{
    Id = $Id; Name = $Name; Image = $Image; Running = $true; Paused = $false; Status = "running"
  }
}

# =============================================================================
# 1) Custody: exact root / subdirectory; refuse scratch-other prefix wildcard
# =============================================================================
try {
  Assert-ScratchRootSafe "F:\DropFolder\scratch" | Out-Null
  Assert-True $true "ScratchRoot exact custody root allowed"
} catch { Assert-True $false "ScratchRoot allowed path threw: $($_.Exception.Message)" }
try {
  Assert-ScratchRootSafe "F:\DropFolder\scratch\child" | Out-Null
  Assert-True $true "ScratchRoot subdirectory allowed"
} catch { Assert-True $false "ScratchRoot subdir threw" }
try {
  Assert-ScratchRootSafe "F:\DropFolder\scratch-other"
  Assert-True $false "scratch-other prefix should refuse"
} catch { Assert-True ($_.Exception.Message -match 'REFUSE') "ScratchRoot refuses scratch-other prefix" }
try {
  Assert-ScratchRootSafe "F:\DropFolder\scratch\with space"
  Assert-True $false "space path should refuse"
} catch { Assert-True $true "ScratchRoot refuses spaces" }
try {
  Assert-ScratchRootSafe "C:\Temp\elsewhere"
  Assert-True $false "non-DropFolder should refuse"
} catch { Assert-True $true "ScratchRoot refuses non-custody path" }

try {
  Assert-ExportStampSafe "20261102T000000Z-abcd1234" | Out-Null
  Assert-True $true "valid ExportStamp"
} catch { Assert-True $false "valid stamp threw" }
try {
  Assert-ExportStampSafe "..\evil"
  Assert-True $false "traversal stamp should refuse"
} catch { Assert-True $true "ExportStamp refuses traversal" }
try {
  Assert-ExportStampSafe "a/b"
  Assert-True $false "separator stamp should refuse"
} catch { Assert-True $true "ExportStamp refuses separators" }

$owned = "F:\DropFolder\scratch\theplan-pre-g5-snap-testown"
try {
  Assert-PathWithinOwned -OwnedDir $owned -CandidatePath (Join-Path $owned "api.fs.tar") | Out-Null
  Assert-True $true "tar path within owned"
} catch { Assert-True $false "within-owned threw" }
try {
  Assert-PathWithinOwned -OwnedDir $owned -CandidatePath "F:\DropFolder\scratch\other\api.fs.tar"
  Assert-True $false "escape should refuse"
} catch { Assert-True $true "path custody refuses escape" }

# =============================================================================
# 2) Partial pause via real Invoke-PauseOneById (harnessed)
# =============================================================================
$h = New-FakeDockerHarness
Add-FakeContainer $h "id-api" "compose-api-1"
Add-FakeContainer $h "id-web" "compose-web-1"
$h.State.PauseFail["id-web"] = $true
$script:PreG5DockerRunner = $h.Runner

$ledger = New-PauseLedger
Register-PauseAttempt -Ledger $ledger -Id "id-api" -Name "compose-api-1"
Register-PauseAttempt -Ledger $ledger -Id "id-web" -Name "compose-web-1"
$eApi = Invoke-PauseOneById -Ledger $ledger -Id "id-api" -Name "compose-api-1"
$eWeb = Invoke-PauseOneById -Ledger $ledger -Id "id-web" -Name "compose-web-1"
Assert-True ($eApi.VerifiedPaused -eq $true -and $eApi.Unresolved -eq $true) "partial pause: api VerifiedPaused/Unresolved via real transition"
Assert-True ($eWeb.PauseAttempted -eq $true -and $eWeb.VerifiedPaused -eq $false -and $eWeb.Unresolved -eq $false) "partial pause: web fail+not-paused => not Unresolved"
Assert-True ($h.State.Containers["id-api"].Paused -eq $true) "harness api actually paused"
Assert-True ($h.State.Containers["id-web"].Paused -eq $false) "harness web not paused after fail"

# Real pair orchestration: API pause fail => web never registered; recovery must not unpause web.
$h2 = New-FakeDockerHarness
Add-FakeContainer $h2 "id-api" "compose-api-1"
Add-FakeContainer $h2 "id-web" "compose-web-1"
# Another operator paused web independently — we must NOT unpause it if we never PauseAttempted.
$h2.State.Containers["id-web"].Paused = $true
$h2.State.PauseFail["id-api"] = $true
$script:PreG5DockerRunner = $h2.Runner
$ledger2 = New-PauseLedger
$apiObj = [ordered]@{ Id = "id-api"; Name = "compose-api-1" }
$webObj = [ordered]@{ Id = "id-web"; Name = "compose-web-1" }
try {
  [void](Invoke-PausePairById -Ledger $ledger2 -Api $apiObj -Web $webObj)
  Assert-True $false "pair should fail when api pause not verified"
} catch {
  Assert-True ($_.Exception.Message -match 'refusing to register/pause web') "pair refuses web after api fail"
}
Assert-True ($ledger2.ContainsKey("id-api")) "api registered after attempt"
Assert-True (-not $ledger2.ContainsKey("id-web")) "web NOT registered when api pause failed"
Assert-True ((@($h2.State.CallLog | Where-Object { $_ -match '^pause id-web' })).Count -eq 0) "no web pause call"
[void](Invoke-UnpauseAllUnresolved -Ledger $ledger2)
Assert-True ((@($h2.State.CallLog | Where-Object { $_ -match '^unpause id-web' })).Count -eq 0) "recovery does not unpause never-paused web"
Assert-True ($h2.State.Containers["id-web"].Paused -eq $true) "foreign web pause left untouched"

# =============================================================================
# 3) Inspect failure for first unpause still attempts second
# =============================================================================
$h3 = New-FakeDockerHarness
Add-FakeContainer $h3 "id-api" "compose-api-1"
Add-FakeContainer $h3 "id-web" "compose-web-1"
$h3.State.Containers["id-api"].Paused = $true
$h3.State.Containers["id-web"].Paused = $true
$h3.State.InspectFail["id-api"] = $true
$script:PreG5DockerRunner = $h3.Runner
$ledger3 = New-PauseLedger
Register-PauseAttempt -Ledger $ledger3 -Id "id-api" -Name "compose-api-1"
Register-PauseAttempt -Ledger $ledger3 -Id "id-web" -Name "compose-web-1"
$ledger3["id-api"].PauseAttempted = $true
$ledger3["id-api"].VerifiedPaused = $true
$ledger3["id-api"].Unresolved = $true
$ledger3["id-web"].PauseAttempted = $true
$ledger3["id-web"].VerifiedPaused = $true
$ledger3["id-web"].Unresolved = $true

$escalations = @(Invoke-UnpauseAllUnresolved -Ledger $ledger3)
Assert-True ($ledger3["id-api"].Unresolved -eq $true) "inspect fail leaves api Unresolved durable"
Assert-True ($ledger3["id-api"].FailedRecoveryEscalation -eq $true) "api FailedRecoveryEscalation set"
Assert-True ($ledger3["id-web"].VerifiedUnpaused -eq $true) "web still unpaused despite api inspect fail"
Assert-True ($ledger3["id-web"].Unresolved -eq $false) "web resolved independently"
Assert-True ((@($h3.State.CallLog | Where-Object { $_ -match '^unpause id-web' })).Count -ge 1) "second container unpause attempted"
Assert-True ($escalations.Count -ge 1) "escalation messages returned"

# =============================================================================
# 4) Replacement identity sharing name must NOT clear old Unresolved
# =============================================================================
$h4 = New-FakeDockerHarness
# Old paused id gone from map; new container reuses name compose-api-1
Add-FakeContainer $h4 "id-api-NEW" "compose-api-1"
$h4.State.Containers["id-api-NEW"].Paused = $false
$script:PreG5DockerRunner = $h4.Runner
$ledger4 = New-PauseLedger
Register-PauseAttempt -Ledger $ledger4 -Id "id-api-OLD" -Name "compose-api-1"
$ledger4["id-api-OLD"].PauseAttempted = $true
$ledger4["id-api-OLD"].VerifiedPaused = $true
$ledger4["id-api-OLD"].Unresolved = $true
[void](Invoke-UnpauseOneById -Ledger $ledger4 -Id "id-api-OLD")
Assert-True ($ledger4["id-api-OLD"].Unresolved -eq $true) "replacement name does not resolve old id"
Assert-True ($ledger4["id-api-OLD"].VerifiedUnpaused -eq $false) "old id not VerifiedUnpaused"
Assert-True ($ledger4["id-api-OLD"].FailedRecoveryEscalation -eq $true) "escalation on missing old id"

# =============================================================================
# 5) Genuine short process timeout (not bad-argument exit)
# =============================================================================
try {
  Invoke-WindowsProcessCapturedTimed -FilePath "ping" -ArgumentList @("-t", "127.0.0.1") `
    -What "ping hang" -TimeoutMs 700 | Out-Null
  Assert-True $false "ping -t should timeout"
} catch {
  Assert-True ($_.Exception.Message -match 'TIMEOUT') "genuine short process TIMEOUT (not bad-arg exit)"
}

# =============================================================================
# 6) Unresolved recovery prevents Import; two-boolean stub rejected; binding required
# =============================================================================
$badExport = [pscustomobject]@{
  stamp                     = "stamp-A"
  source_api_container_id   = "id-api"
  source_web_container_id   = "id-web"
  health_exit_hint          = 3
  pause_ledger              = [pscustomobject]@{
    "id-api" = [pscustomobject]@{
      PauseAttempted   = $true
      VerifiedPaused   = $true
      Unresolved       = $true
      VerifiedUnpaused = $false
    }
  }
}
$tmpScratch = Join-Path $env:TEMP ("preg5-validate-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpScratch | Out-Null
try {
  try {
    Assert-ExportReadyForImport -ExportReceipt $badExport -ScratchDir $tmpScratch
    Assert-True $false "Import should refuse unresolved without recovery receipt"
  } catch {
    Assert-True ($_.Exception.Message -match 'REFUSE Import') "unresolved recovery blocks Import"
  }

  $stub = [ordered]@{ verified_resolved = $true; health_ok = $true }
  ($stub | ConvertTo-Json) | Set-Content -LiteralPath (Join-Path $tmpScratch "recovery.receipt.json") -Encoding utf8
  try {
    Assert-ExportReadyForImport -ExportReceipt $badExport -ScratchDir $tmpScratch
    Assert-True $false "two-boolean stub must not pass"
  } catch {
    Assert-True ($_.Exception.Message -match 'stamp|source_|pause_ledger') "two-boolean stub rejected"
  }
  Remove-Item -LiteralPath (Join-Path $tmpScratch "recovery.receipt.json") -Force

  $stale = [ordered]@{
    stamp                   = "stamp-OTHER"
    source_api_container_id = "id-api"
    source_web_container_id = "id-web"
    verified_resolved       = $true
    health_ok               = $true
    pause_ledger            = [pscustomobject]@{
      "id-api" = [pscustomobject]@{
        PauseAttempted = $true; VerifiedPaused = $true; Unresolved = $false; VerifiedUnpaused = $true
      }
    }
  }
  ($stale | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath (Join-Path $tmpScratch "recovery.receipt.json") -Encoding utf8
  try {
    Assert-ExportReadyForImport -ExportReceipt $badExport -ScratchDir $tmpScratch
    Assert-True $false "stale stamp recovery should refuse"
  } catch {
    Assert-True ($_.Exception.Message -match 'stamp') "stale/other-attempt recovery rejected"
  }
  Remove-Item -LiteralPath (Join-Path $tmpScratch "recovery.receipt.json") -Force

  $goodRec = [ordered]@{
    stamp                   = "stamp-A"
    source_api_container_id = "id-api"
    source_web_container_id = "id-web"
    verified_resolved       = $true
    health_ok               = $true
    pause_ledger            = [pscustomobject]@{
      "id-api" = [pscustomobject]@{
        PauseAttempted = $true; VerifiedPaused = $true; Unresolved = $false; VerifiedUnpaused = $true
      }
    }
  }
  # Same key present but not affirmatively unpaused => refuse (Import-only gate)
  $weakRec = [ordered]@{
    stamp                   = "stamp-A"
    source_api_container_id = "id-api"
    source_web_container_id = "id-web"
    verified_resolved       = $true
    health_ok               = $true
    pause_ledger            = [pscustomobject]@{
      "id-api" = [pscustomobject]@{
        PauseAttempted = $false; VerifiedPaused = $false; Unresolved = $true; VerifiedUnpaused = $false
      }
    }
  }
  ($weakRec | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath (Join-Path $tmpScratch "recovery.receipt.json") -Encoding utf8
  try {
    Assert-ExportReadyForImport -ExportReceipt $badExport -ScratchDir $tmpScratch -ExpectStamp "stamp-A"
    Assert-True $false "weak recovery entry (PauseAttempted=false covering export id) must refuse"
  } catch {
    Assert-True ($_.Exception.Message -match 'VerifiedUnpaused|Unresolved') "Import requires affirmative VerifiedUnpaused per attempted export id"
  }
  Remove-Item -LiteralPath (Join-Path $tmpScratch "recovery.receipt.json") -Force

  $goodRec = [ordered]@{
    stamp                   = "stamp-A"
    source_api_container_id = "id-api"
    source_web_container_id = "id-web"
    verified_resolved       = $true
    health_ok               = $true
    pause_ledger            = [pscustomobject]@{
      "id-api" = [pscustomobject]@{
        PauseAttempted = $true; VerifiedPaused = $true; Unresolved = $false; VerifiedUnpaused = $true
      }
    }
  }
  ($goodRec | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath (Join-Path $tmpScratch "recovery.receipt.json") -Encoding utf8
  try {
    Assert-ExportReadyForImport -ExportReceipt $badExport -ScratchDir $tmpScratch -ExpectStamp "stamp-A" | Out-Null
    Assert-True $true "bound recovery receipt with ledger evidence allows Import"
  } catch {
    Assert-True $false "bound recovery should allow Import: $($_.Exception.Message)"
  }

  $okExport = [pscustomobject]@{
    stamp                   = "stamp-B"
    source_api_container_id = "id-api"
    source_web_container_id = "id-web"
    health_exit_hint        = 0
    pause_ledger            = [pscustomobject]@{
      "id-api" = [pscustomobject]@{
        PauseAttempted = $true; VerifiedPaused = $true; Unresolved = $false; VerifiedUnpaused = $true
      }
    }
  }
  try {
    Assert-ExportReadyForImport -ExportReceipt $okExport -ScratchDir $tmpScratch | Out-Null
    Assert-True $true "healthy resolved export allows Import without needing recovery"
  } catch {
    Assert-True $false "healthy export should allow Import"
  }
} finally {
  Remove-Item -LiteralPath $tmpScratch -Recurse -Force -ErrorAction SilentlyContinue
}

# =============================================================================
# 6b) Preserve-ReleaseImageTags — real production function
# =============================================================================
$hp = New-FakeDockerHarness
$script:PreG5DockerRunner = $hp.Runner
$tag = "theplan-release-api:0c9430e8"
$want = "sha256:want111"
# same ID present
$hp.State.Images[$tag] = $want
try {
  Preserve-ReleaseImageTags -Pairs @(@{ Tag = $tag; Id = $want })
  Assert-True $true "preserve: same ID ok"
} catch { Assert-True $false "same ID should ok: $($_.Exception.Message)" }

# different ID present => REFUSE (must not tag/overwrite)
$hp.State.Images[$tag] = "sha256:wrong999"
$hp.State.CallLog.Clear()
try {
  Preserve-ReleaseImageTags -Pairs @(@{ Tag = $tag; Id = $want })
  Assert-True $false "different ID should REFUSE"
} catch {
  Assert-True ($_.Exception.Message -match 'REFUSE overwrite') "preserve: different ID refuses"
}
Assert-True ((@($hp.State.CallLog | Where-Object { $_ -match '^tag ' })).Count -eq 0) "preserve: no tag on mismatch"
Assert-True ($hp.State.Images[$tag] -eq "sha256:wrong999") "preserve: wrong ID not overwritten"

# missing => may create tag
$hp.State.Images.Remove($tag)
try {
  Preserve-ReleaseImageTags -Pairs @(@{ Tag = $tag; Id = $want })
  Assert-True ($hp.State.Images[$tag] -eq $want) "preserve: missing creates tag"
} catch { Assert-True $false "missing should tag: $($_.Exception.Message)" }

# inspect daemon failure aborts (does not treat as missing)
$hp.State.Images.Remove($tag)
$hp.State.ImageInspectErr[$tag] = "daemon"
try {
  Preserve-ReleaseImageTags -Pairs @(@{ Tag = $tag; Id = $want })
  Assert-True $false "daemon error should abort"
} catch {
  Assert-True ($_.Exception.Message -match 'daemon|cannot connect|FAIL') "preserve: daemon inspect aborts"
}
Assert-True (-not $hp.State.Images.ContainsKey($tag)) "preserve: daemon fail did not create tag"

# Regression: daemon error containing generic "not found" must NOT permit tag
$hp.State.ImageInspectErr[$tag] = "daemon-not-found"
$hp.State.CallLog.Clear()
try {
  Preserve-ReleaseImageTags -Pairs @(@{ Tag = $tag; Id = $want })
  Assert-True $false "daemon-not-found should abort"
} catch {
  Assert-True ($_.Exception.Message -match 'daemon|access') "preserve: daemon+not-found classified as infra abort"
}
Assert-True ((@($hp.State.CallLog | Where-Object { $_ -match '^tag ' })).Count -eq 0) "preserve: daemon-not-found did not tag"
Assert-True (-not $hp.State.Images.ContainsKey($tag)) "preserve: daemon-not-found no image created"

# Regression: bare generic "not found" (no No such object/image) must NOT permit tag
$hp.State.ImageInspectErr[$tag] = "generic-not-found"
try {
  Preserve-ReleaseImageTags -Pairs @(@{ Tag = $tag; Id = $want })
  Assert-True $false "generic-not-found should abort"
} catch {
  Assert-True ($_.Exception.Message -match 'not classified missing') "preserve: generic not-found is not Missing"
}
Assert-True (-not $hp.State.Images.ContainsKey($tag)) "preserve: generic-not-found no image created"
$hp.State.ImageInspectErr.Remove($tag)

# Assert-SnapshotImageTagAbsent: present refuses; missing ok; other aborts
$hp.State.ImageInspectErr.Remove($tag)
$hp.State.Images[$tag] = $want
try {
  Assert-SnapshotImageTagAbsent -Tag $tag
  Assert-True $false "present snapshot tag should refuse"
} catch {
  Assert-True ($_.Exception.Message -match 'REFUSE tag exists') "snapshot absent: present refuses"
}
$hp.State.Images.Remove($tag)
try {
  Assert-SnapshotImageTagAbsent -Tag $tag
  Assert-True $true "snapshot absent: missing ok"
} catch { Assert-True $false "missing should be ok: $($_.Exception.Message)" }
$hp.State.ImageInspectErr[$tag] = "other"
try {
  Assert-SnapshotImageTagAbsent -Tag $tag
  Assert-True $false "unclassified inspect should abort"
} catch {
  Assert-True ($_.Exception.Message -match 'not classified missing|FAIL') "snapshot absent: unclassified aborts"
}

# Resolve-ContainerPresenceByRef: Missing only on *complete* queried-ref match
function New-InspectStderrRunner([string] $StdErrText) {
  return {
    param([string[]]$DockerArgs, [string]$What, [int]$TimeoutMs)
    return @{ Code = 1; StdOut = ""; StdErr = $StdErrText; TimedOut = $false }
  }.GetNewClosure()
}
$qRef = "cid-exact-probe"
$script:PreG5DockerRunner = New-InspectStderrRunner "Error: No such object: $qRef"
try {
  $presExact = Resolve-ContainerPresenceByRef -Ref $qRef
  Assert-True ($presExact.Status -eq "Missing") "container presence: exact-ref Missing"
} catch { Assert-True $false "exact-ref Missing should not throw: $($_.Exception.Message)" }

$script:PreG5DockerRunner = New-InspectStderrRunner "Error: No such object: cid-different-other"
try {
  Resolve-ContainerPresenceByRef -Ref $qRef | Out-Null
  Assert-True $false "different-ref No such must not be Missing"
} catch {
  Assert-True ($_.Exception.Message -match 'not classified missing') "container presence: different ref unresolved"
}

$script:PreG5DockerRunner = New-InspectStderrRunner "Error: No such object: ${qRef}-suffix"
try {
  Resolve-ContainerPresenceByRef -Ref $qRef | Out-Null
  Assert-True $false "queried-ref-plus-suffix must not be Missing"
} catch {
  Assert-True ($_.Exception.Message -match 'not classified missing') "container presence: ref-plus-suffix unresolved"
}

$script:PreG5DockerRunner = New-InspectStderrRunner "Error: No such object:"
try {
  Resolve-ContainerPresenceByRef -Ref $qRef | Out-Null
  Assert-True $false "generic No such without ref text must not be Missing"
} catch {
  Assert-True ($_.Exception.Message -match 'not classified missing') "container presence: missing ref text unresolved"
}

$script:PreG5DockerRunner = New-InspectStderrRunner "Error: path not found while inspecting"
try {
  Resolve-ContainerPresenceByRef -Ref $qRef | Out-Null
  Assert-True $false "unclassified inspect must not be Missing"
} catch {
  Assert-True ($_.Exception.Message -match 'not classified missing') "container presence: unclassified unresolved"
}

# =============================================================================
# 6c) Import timeout + late-created tag; probe timeout/cleanup (production helpers)
# =============================================================================
$hi = New-FakeDockerHarness
$script:PreG5DockerRunner = $hi.Runner
$impTag = "theplan-pre-g5-api:snapshot-teststamp"
$intent = New-ImportIntentLedger
Register-IntendedSnapshotTag -Ledger $intent -Tag $impTag -Role "api"
$hi.State.ImportTimeoutTags[$impTag] = $true
$hi.State.ImportLateCreate[$impTag] = $true
try {
  Invoke-DockerImportWithIntent -IntentLedger $intent -Tag $impTag `
    -DockerArgs @("import", "dummy.tar", $impTag) -What "import api" -TimeoutMs 180000 | Out-Null
  Assert-True $false "import timeout should throw"
} catch {
  Assert-True ($_.Exception.Message -match 'IMPORT_TIMEOUT_UNCERTAIN') "import timeout => IMPORT_TIMEOUT_UNCERTAIN"
}
Assert-True ($intent[$impTag].Outcome -eq "uncertain") "import intent Outcome=uncertain"
Assert-True ($intent[$impTag].ImportTimedOut -eq $true) "import timed out flag"
Assert-True ($intent[$impTag].StampReuseRequiresReview -eq $true) "stamp reuse requires review"
Assert-True ($null -ne $intent[$impTag].ObservedId) "late-created tag observed on reconcile"
Assert-True ($hi.State.Images.ContainsKey($impTag)) "late-created image retained (no auto-delete)"
Assert-True ((@($hi.State.CallLog | Where-Object { $_ -match '^rm ' })).Count -eq 0) "no auto rm/delete on import timeout"

# Probe: create ownership + timeout cleanup ok
$hp2 = New-FakeDockerHarness
$script:PreG5DockerRunner = $hp2.Runner
$probes = New-ProbeLedger
$pname = "preg5-probe-api-teststamp-deadbeef"
$alabel = "preg5-teststamp-deadbeef"
Register-IntendedProbe -Ledger $probes -Name $pname -ImageTag $impTag -Role "api" -AttemptLabel $alabel
$hp2.State.ProbeTimeoutNames[$pname] = $true
try {
  Invoke-InertProbeOwned -ProbeLedger $probes -Name $pname -What "api probe" -TimeoutMs 5000 `
    -CreateArgs @("create", "--name", $pname, "--label", "preg5.attempt=$alabel", "--network", "none", "--entrypoint", "/bin/true", $impTag)
  Assert-True $false "probe timeout should throw"
} catch {
  Assert-True ($_.Exception.Message -match 'TIMEOUT') "probe surfaces TIMEOUT"
}
Assert-True ($null -ne $probes[$pname].OwnedId) "ownership from create before start timeout"
Assert-True ($probes[$pname].TimedOut -eq $true) "probe timed out"
$clean = @(Invoke-CleanupOwnedProbes -ProbeLedger $probes)
Assert-True ($probes[$pname].CleanupOk -eq $true) "owned probe cleanup ok after timeout-with-visible"
try { Assert-ProbesReadyForSuccess -ProbeLedger $probes | Out-Null; Assert-True $true "success gate passes after clean cleanup" }
catch { Assert-True $false "success gate should pass: $($_.Exception.Message)" }

# rm failure => success gate refuses creation_ok
$hp3 = New-FakeDockerHarness
$script:PreG5DockerRunner = $hp3.Runner
$probes3 = New-ProbeLedger
$p3 = "preg5-probe-api-rmfail"
Register-IntendedProbe -Ledger $probes3 -Name $p3 -ImageTag $impTag -Role "api" -AttemptLabel $alabel
Invoke-InertProbeOwned -ProbeLedger $probes3 -Name $p3 -What "api probe" -TimeoutMs 5000 `
  -CreateArgs @("create", "--name", $p3, "--label", "preg5.attempt=$alabel", "--network", "none", $impTag) | Out-Null
$hp3.State.RmFailIds[$probes3[$p3].OwnedId] = $true
[void](Invoke-CleanupOwnedProbes -ProbeLedger $probes3)
Assert-True ($probes3[$p3].CleanupOk -eq $false) "rm failure => CleanupOk false"
try {
  Assert-ProbesReadyForSuccess -ProbeLedger $probes3
  Assert-True $false "success gate must refuse when cleanup failed"
} catch {
  Assert-True ($_.Exception.Message -match 'cleanup not ok') "success/receipt gate blocks on rm failure"
}

# Foreign same-name collision: preflight refuses adopt
$hp4 = New-FakeDockerHarness
$script:PreG5DockerRunner = $hp4.Runner
$foreignName = "preg5-probe-collide"
Add-FakeContainer $hp4 "cid-foreign" $foreignName
$hp4.State.Containers["cid-foreign"].Image = "someone-else"
$hp4.State.Containers["cid-foreign"].Label = "other"
$probes4 = New-ProbeLedger
Register-IntendedProbe -Ledger $probes4 -Name $foreignName -ImageTag $impTag -Role "api" -AttemptLabel $alabel
try {
  Invoke-InertProbeOwned -ProbeLedger $probes4 -Name $foreignName -What "api probe" -TimeoutMs 5000 `
    -CreateArgs @("create", "--name", $foreignName, "--label", "preg5.attempt=$alabel", $impTag)
  Assert-True $false "foreign name should refuse"
} catch {
  Assert-True ($_.Exception.Message -match 'already exists|will not adopt|name conflict') "foreign same-name collision refused"
}
Assert-True ($null -eq $probes4[$foreignName].OwnedId) "no ownership on collision"
[void](Invoke-CleanupOwnedProbes -ProbeLedger $probes4)
Assert-True ($hp4.State.Containers.ContainsKey("cid-foreign")) "foreign same-name container NOT deleted"

# TIMEOUT + still-missing: CleanupUncertain, not CleanupOk already-absent
$hp5 = New-FakeDockerHarness
$script:PreG5DockerRunner = $hp5.Runner
$probes5 = New-ProbeLedger
$p5 = "preg5-probe-ghost"
Register-IntendedProbe -Ledger $probes5 -Name $p5 -ImageTag $impTag -Role "api" -AttemptLabel $alabel
# Manually simulate create owned then disappear + timeout flag
$probes5[$p5].CreateAttempted = $true
$probes5[$p5].OwnedId = "cid-ghost-missing"
$probes5[$p5].TimedOut = $true
$probes5[$p5].StartAttempted = $true
[void](Invoke-CleanupOwnedProbes -ProbeLedger $probes5)
Assert-True ($probes5[$p5].CleanupUncertain -eq $true) "timeout+missing => CleanupUncertain"
Assert-True ($probes5[$p5].CleanupOk -eq $false) "timeout+missing is NOT CleanupOk"
try {
  Assert-ProbesReadyForSuccess -ProbeLedger $probes5
  Assert-True $false "success gate must refuse uncertain cleanup"
} catch {
  Assert-True ($_.Exception.Message -match 'uncertain') "success gate blocks uncertain cleanup"
}

# Create TIMEOUT (no OwnedId): CreateOutcomeUnknown + CleanupUncertain — never skipped_never_owned
$hpCreateTo = New-FakeDockerHarness
$script:PreG5DockerRunner = $hpCreateTo.Runner
$probesCT = New-ProbeLedger
$pCT = "preg5-probe-create-timeout"
Register-IntendedProbe -Ledger $probesCT -Name $pCT -ImageTag $impTag -Role "api" -AttemptLabel $alabel
$hpCreateTo.State.ProbeCreateTimeoutNames[$pCT] = $true
try {
  Invoke-InertProbeOwned -ProbeLedger $probesCT -Name $pCT -What "api probe" -TimeoutMs 5000 `
    -CreateArgs @("create", "--name", $pCT, "--label", "preg5.attempt=$alabel", "--network", "none", $impTag)
  Assert-True $false "create timeout should throw"
} catch {
  Assert-True ($_.Exception.Message -match 'PROBE_CREATE_TIMEOUT_UNCERTAIN') "create timeout => PROBE_CREATE_TIMEOUT_UNCERTAIN"
}
Assert-True ($null -eq $probesCT[$pCT].OwnedId) "create timeout leaves OwnedId null"
Assert-True ($probesCT[$pCT].CreateAttempted -eq $true) "create was attempted"
Assert-True ($probesCT[$pCT].CreateOutcomeUnknown -eq $true) "create outcome unknown"
Assert-True ($probesCT[$pCT].CreateTimedOut -eq $true) "create timed out flag"
[void](Invoke-CleanupOwnedProbes -ProbeLedger $probesCT)
Assert-True ($probesCT[$pCT].CleanupUncertain -eq $true) "create-timeout cleanup uncertain (not skipped_never_owned)"
Assert-True ($probesCT[$pCT].CleanupOk -eq $false) "create-timeout is NOT CleanupOk"
Assert-True ($probesCT[$pCT].CleanupNotes -notmatch 'skipped_never') "must not classify as never-owned/never-attempted skip"
try {
  Assert-ProbesReadyForSuccess -ProbeLedger $probesCT
  Assert-True $false "success gate must refuse create-timeout uncertain"
} catch {
  Assert-True ($_.Exception.Message -match 'uncertain') "success gate blocks create-timeout uncertain"
}

# Create TIMEOUT + late matching container: reconcile by label+image+name, then rm => CleanupOk
$hpLate = New-FakeDockerHarness
$script:PreG5DockerRunner = $hpLate.Runner
$probesLate = New-ProbeLedger
$pLate = "preg5-probe-late-create"
Register-IntendedProbe -Ledger $probesLate -Name $pLate -ImageTag $impTag -Role "api" -AttemptLabel $alabel
$hpLate.State.ProbeCreateTimeoutNames[$pLate] = $true
$hpLate.State.ProbeCreateLateNames[$pLate] = $true
try {
  Invoke-InertProbeOwned -ProbeLedger $probesLate -Name $pLate -What "api probe" -TimeoutMs 5000 `
    -CreateArgs @("create", "--name", $pLate, "--label", "preg5.attempt=$alabel", "--network", "none", $impTag)
  Assert-True $false "late create timeout should throw"
} catch {
  Assert-True ($_.Exception.Message -match 'PROBE_CREATE_TIMEOUT_UNCERTAIN') "late create timeout surfaced"
}
Assert-True ($null -eq $probesLate[$pLate].OwnedId) "no OwnedId at throw time"
[void](Invoke-CleanupOwnedProbes -ProbeLedger $probesLate)
Assert-True ($probesLate[$pLate].CleanupOk -eq $true) "late-reconciled matching probe removed"
Assert-True ($probesLate[$pLate].CleanupUncertain -eq $false) "late reconcile cleared uncertain"
Assert-True (-not $hpLate.State.Containers.ContainsKey("cid-late-$pLate")) "late container removed"
try { Assert-ProbesReadyForSuccess -ProbeLedger $probesLate | Out-Null; Assert-True $true "success gate after late reconcile rm" }
catch { Assert-True $false "success gate should pass after late rm: $($_.Exception.Message)" }

# Create TIMEOUT + foreign same-name (wrong label): do NOT adopt
$hpForeignLate = New-FakeDockerHarness
$script:PreG5DockerRunner = $hpForeignLate.Runner
$pFL = "preg5-probe-foreign-late"
Add-FakeContainer $hpForeignLate "cid-fl" $pFL "someone-else"
$hpForeignLate.State.Containers["cid-fl"].Label = "other-attempt"
$probesFL = New-ProbeLedger
Register-IntendedProbe -Ledger $probesFL -Name $pFL -ImageTag $impTag -Role "api" -AttemptLabel $alabel
# Simulate create attempted+timeout without going through create (name already present would fail preflight);
# set ledger as if create timed out after preflight cleared then foreign appeared.
$probesFL[$pFL].CreateAttempted = $true
$probesFL[$pFL].CreateTimedOut = $true
$probesFL[$pFL].CreateOutcomeUnknown = $true
$probesFL[$pFL].TimedOut = $true
[void](Invoke-CleanupOwnedProbes -ProbeLedger $probesFL)
Assert-True ($probesFL[$pFL].CleanupUncertain -eq $true) "foreign late name => uncertain"
Assert-True ($probesFL[$pFL].CleanupNotes -match 'NOT adopting|mismatch') "refuses foreign adopt"
Assert-True ($hpForeignLate.State.Containers.ContainsKey("cid-fl")) "foreign container NOT deleted"

# Stamp reuse: prior failure UNCONDITIONALLY blocks — IMPORT_STAMP_RESOLUTION does not unlock
$tmpStamp = Join-Path $env:TEMP ("preg5-stamp-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpStamp | Out-Null
try {
  $failObj = [ordered]@{ failed = $true; import_uncertain = $true; stamp_reuse_requires_review = $true; creation_ok = $false }
  ($failObj | ConvertTo-Json) | Set-Content (Join-Path $tmpStamp "failure.receipt.json") -Encoding utf8
  try {
    Assert-ImportStampReusable -ScratchDir $tmpStamp
    Assert-True $false "uncertain failure should block stamp reuse"
  } catch {
    Assert-True ($_.Exception.Message -match 'unconditionally blocked|stamp reuse') "rerun refused while failure present"
  }
  $res = [ordered]@{ reviewed = $true; allow_stamp_reuse = $true; notes = "operator cleared late tag" }
  ($res | ConvertTo-Json) | Set-Content (Join-Path $tmpStamp "IMPORT_STAMP_RESOLUTION.json") -Encoding utf8
  try {
    Assert-ImportStampReusable -ScratchDir $tmpStamp | Out-Null
    Assert-True $false "resolution must NOT unlock first-Import stamp reuse"
  } catch {
    Assert-True ($_.Exception.Message -match 'unconditionally blocked|no resolution bypass') "IMPORT_STAMP_RESOLUTION does not bypass"
  }
} finally {
  Remove-Item -LiteralPath $tmpStamp -Recurse -Force -ErrorAction SilentlyContinue
}

# Household name not cleaned
$hp6 = New-FakeDockerHarness
$script:PreG5DockerRunner = $hp6.Runner
Add-FakeContainer $hp6 "cid-house" "compose-api-1"
$emptyProbes = New-ProbeLedger
[void](Invoke-CleanupOwnedProbes -ProbeLedger $emptyProbes)
Assert-True ($hp6.State.Containers.ContainsKey("cid-house")) "household container not cleaned"

# Assert-ImportedConfig: omitted Config.User (docker import) under StrictMode
$cfgNoUser = '{"Env":["PATH=/bin","PYTHONUNBUFFERED=1","PYTHONDONTWRITEBYTECODE=1","LANG=C.UTF-8"],"Cmd":["/bin/true"],"WorkingDir":"/app"}'
$script:PreG5DockerRunner = {
  param([string[]]$DockerArgs, [string]$What, [int]$TimeoutMs)
  if ($DockerArgs[0] -eq 'image' -and $DockerArgs[1] -eq 'inspect') {
    return @{ Code = 0; StdOut = $cfgNoUser; StdErr = ""; TimedOut = $false }
  }
  return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
}.GetNewClosure()
$envAllowApi = [ordered]@{
  PATH = "/bin"; PYTHONUNBUFFERED = "1"; PYTHONDONTWRITEBYTECODE = "1"; LANG = "C.UTF-8"
}
try {
  Assert-ImportedConfig -Tag "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b" -EnvAllow $envAllowApi `
    -ExpectWorkdir "/app" -ExpectUser "" -ExpectEntrypoint @() -ExpectCmd @("/bin/true") | Out-Null
  Assert-True $true "imported config by immutable image id tolerates omitted User"
} catch {
  Assert-True $false "omitted User should not StrictMode-fail: $($_.Exception.Message)"
}

# Assert-ImportAttemptDirClear: quarantine-only / success / failure refuse; evidence unchanged
$tmpAtt = Join-Path $env:TEMP ("preg5-att-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpAtt | Out-Null
try {
  $qOnly = Join-Path $tmpAtt "q-only"; New-Item -ItemType Directory -Path $qOnly | Out-Null
  Set-Content (Join-Path $qOnly "QUARANTINE_FAILED_ATTEMPT.txt") -Value "notes=interrupted" -Encoding ascii
  $beforeQ = Get-FileHash -LiteralPath (Join-Path $qOnly "QUARANTINE_FAILED_ATTEMPT.txt") -Algorithm SHA256
  try {
    Assert-ImportAttemptDirClear -AttemptDir $qOnly
    Assert-True $false "quarantine-only should refuse"
  } catch {
    Assert-True ($_.Exception.Message -match 'QUARANTINE_FAILED_ATTEMPT|prior attempt evidence') "quarantine-only refusal"
  }
  $afterQ = Get-FileHash -LiteralPath (Join-Path $qOnly "QUARANTINE_FAILED_ATTEMPT.txt") -Algorithm SHA256
  Assert-True ($beforeQ.Hash -eq $afterQ.Hash) "quarantine-only refuse leaves marker unchanged"
  Assert-True (-not (Test-Path (Join-Path $qOnly "failure.receipt.json"))) "quarantine-only refuse did not add failure receipt"

  $okDir = Join-Path $tmpAtt "ok"; New-Item -ItemType Directory -Path $okDir | Out-Null
  Set-Content (Join-Path $okDir "import.receipt.json") -Value '{"creation_ok":true}' -Encoding utf8
  $beforeOk = Get-FileHash -LiteralPath (Join-Path $okDir "import.receipt.json") -Algorithm SHA256
  try {
    Assert-ImportAttemptDirClear -AttemptDir $okDir
    Assert-True $false "prior success should refuse"
  } catch {
    Assert-True ($_.Exception.Message -match 'import\.receipt|prior attempt evidence') "prior success refusal"
  }
  $afterOk = Get-FileHash -LiteralPath (Join-Path $okDir "import.receipt.json") -Algorithm SHA256
  Assert-True ($beforeOk.Hash -eq $afterOk.Hash) "prior-success refuse leaves import.receipt unchanged"
  Assert-True (-not (Test-Path (Join-Path $okDir "QUARANTINE_FAILED_ATTEMPT.txt"))) "prior-success refuse did not add quarantine"
  Assert-True (-not (Test-Path (Join-Path $okDir "failure.receipt.json"))) "prior-success refuse did not add failure"

  $failDir = Join-Path $tmpAtt "fail"; New-Item -ItemType Directory -Path $failDir | Out-Null
  Set-Content (Join-Path $failDir "failure.receipt.json") -Value '{"failed":true}' -Encoding utf8
  $beforeF = Get-FileHash -LiteralPath (Join-Path $failDir "failure.receipt.json") -Algorithm SHA256
  try {
    Assert-ImportAttemptDirClear -AttemptDir $failDir
    Assert-True $false "prior failure should refuse"
  } catch {
    Assert-True ($_.Exception.Message -match 'failure\.receipt|prior attempt evidence') "prior failure refusal"
  }
  $afterF = Get-FileHash -LiteralPath (Join-Path $failDir "failure.receipt.json") -Algorithm SHA256
  Assert-True ($beforeF.Hash -eq $afterF.Hash) "prior-failure refuse leaves failure.receipt unchanged"

  $fresh = Join-Path $tmpAtt "fresh"; New-Item -ItemType Directory -Path $fresh | Out-Null
  try {
    Assert-ImportAttemptDirClear -AttemptDir $fresh | Out-Null
    Assert-True $true "empty attempt dir clears"
  } catch { Assert-True $false "fresh attempt dir should clear: $($_.Exception.Message)" }

  $valDir = Join-Path $tmpAtt "val"; New-Item -ItemType Directory -Path $valDir | Out-Null
  Set-Content (Join-Path $valDir "validation.receipt.json") -Value '{"ok":true}' -Encoding utf8
  try {
    Assert-ImportAttemptDirClear -AttemptDir $valDir
    Assert-True $false "prior validation.receipt should refuse"
  } catch {
    Assert-True ($_.Exception.Message -match 'validation\.receipt|prior attempt evidence') "validation.receipt refusal"
  }

  $clnDir = Join-Path $tmpAtt "cln"; New-Item -ItemType Directory -Path $clnDir | Out-Null
  Set-Content (Join-Path $clnDir "cleanup.receipt.json") -Value '{"cleanup_ok":true}' -Encoding utf8
  try {
    Assert-ImportAttemptDirClear -AttemptDir $clnDir
    Assert-True $false "prior cleanup.receipt should refuse"
  } catch {
    Assert-True ($_.Exception.Message -match 'cleanup\.receipt|prior attempt evidence') "cleanup.receipt refusal"
  }
} finally {
  Remove-Item -LiteralPath $tmpAtt -Recurse -Force -ErrorAction SilentlyContinue
}

# Probe ownership bound to immutable image id (not mutable tag)
$hpImm = New-FakeDockerHarness
$script:PreG5DockerRunner = $hpImm.Runner
$apiImm = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b"
$probesImm = New-ProbeLedger
$pImm = "preg5-probe-api-imid"
$alabelImm = "preg5-imid-label"
Register-IntendedProbe -Ledger $probesImm -Name $pImm -ImageTag $apiImm -Role "api" -AttemptLabel $alabelImm
Invoke-InertProbeOwned -ProbeLedger $probesImm -Name $pImm -What "api probe" -TimeoutMs 5000 `
  -CreateArgs @("create", "--name", $pImm, "--label", "preg5.attempt=$alabelImm", "--network", "none", $apiImm) | Out-Null
Assert-True ($probesImm[$pImm].OwnedId -ne $null) "id-bound probe got OwnedId"
Assert-True ($hpImm.State.Containers[$probesImm[$pImm].OwnedId].Image -eq $apiImm) "create recorded immutable image id"
Assert-True ($probesImm[$pImm].ImageTag -eq $apiImm) "ledger ImageTag is immutable id"
[void](Invoke-CleanupOwnedProbes -ProbeLedger $probesImm)
Assert-True ($probesImm[$pImm].CleanupOk -eq $true) "id-bound probe cleanup ok"

# =============================================================================
# 7) Tar path classification: .env-only + TrimStart fix; inventory not clearance
# =============================================================================
$clsEnv = Get-TarPathClasses -Paths @(".env")
Assert-True ($clsEnv.env_file_paths -eq 1) ".env-only inventory counts env file (TrimStart fix)"
Assert-True ($clsEnv.suspicious -eq $true) ".env-only => suspicious"
Assert-True ($clsEnv.note -match 'NOT.*clearance') "explicit non-clearance note"
$clsMixed = Get-TarPathClasses -Paths @("app/main.py", "secrets/foo.json", ".env", "var/cache/nginx/x")
Assert-True ($clsMixed.suspicious -eq $true) "mixed inventory suspicious"
$clsClean = Get-TarPathClasses -Paths @("app/main.py", "usr/bin/true")
Assert-True ($clsClean.suspicious -eq $false) "clean path inventory not suspicious"
Assert-True ($clsClean.note -match 'Lack of suspicious') "lack of suspicious filenames is not clearance"

# =============================================================================
# 8) Durable no-overwrite + compose collision helper
# =============================================================================
$ow = Join-Path $env:TEMP ("preg5-ow-" + [guid]::NewGuid().ToString("N") + ".json")
try {
  Set-Content -LiteralPath $ow -Value "{}" -Encoding utf8
  try {
    Assert-DurablePathWritable $ow
    Assert-True $false "should refuse overwrite"
  } catch {
    Assert-True ($_.Exception.Message -match 'no overwrite') "refuses prior stage evidence overwrite"
  }
} finally {
  Remove-Item -LiteralPath $ow -Force -ErrorAction SilentlyContinue
}

try {
  Assert-ComposeProjectResourcesFresh -ProjectName "theplanpreg5snaptest" `
    -NetworkLister { @("bridge", "other") } `
    -VolumeLister { @("vol_a") } | Out-Null
  Assert-True $true "fresh project collision check passes"
} catch { Assert-True $false "fresh project should pass: $($_.Exception.Message)" }
try {
  Assert-ComposeProjectResourcesFresh -ProjectName "theplanpreg5snaptest" `
    -NetworkLister { @("theplanpreg5snaptest_preg5_net") } `
    -VolumeLister { @() }
  Assert-True $false "network collision should refuse"
} catch { Assert-True ($_.Exception.Message -match 'network collision') "detects network collision" }

# Disposable preflight: project containers collide; refuse must not imply down -v
try {
  Assert-DisposableProjectPreflight -ProjectName "theplanpreg5snaptest" `
    -NetworkLister { @("bridge") } -VolumeLister { @() } `
    -ProjectContainerLister { @("cid-x name-x theplanpreg5snaptest") } `
    -HostPorts @() 
  Assert-True $false "project containers should refuse"
} catch {
  Assert-True ($_.Exception.Message -match 'project-labeled containers|will not down') "disposable preflight refuses preexisting project containers"
}
try {
  Assert-DisposableProjectPreflight -ProjectName "theplanpreg5snapfresh" `
    -NetworkLister { @("bridge") } -VolumeLister { @() } `
    -ProjectContainerLister { @() } `
    -HostPorts @() | Out-Null
  Assert-True $true "disposable preflight clear when empty"
} catch { Assert-True $false "clear disposable preflight threw: $($_.Exception.Message)" }

# Disposable orchestration (injected PreG5DockerRunner; no live compose up)
Write-Host "Validate-PreG5DisposableOrchestration begin"
. (Join-Path $PSScriptRoot "Validate-PreG5DisposableOrchestration.ps1")
Invoke-DisposableOrchestrationTests -AssertTrue {
  param([bool]$cond, [string]$msg)
  Assert-True $cond $msg
}
Write-Host "Validate-PreG5DisposableOrchestration end"

Write-Host "Validate-PreG5ReachabilityOrchestration begin"
. (Join-Path $PSScriptRoot "Validate-PreG5ReachabilityOrchestration.ps1")
Invoke-ReachabilityOrchestrationTests -AssertTrue {
  param([bool]$cond, [string]$msg)
  Assert-True $cond $msg
}
Write-Host "Validate-PreG5ReachabilityOrchestration end"

Write-Host "Validate-PreG5ReachCompareOrchestration begin"
. (Join-Path $PSScriptRoot "Validate-PreG5ReachCompareOrchestration.ps1")
Invoke-ReachCompareOrchestrationTests -AssertTrue {
  param([bool]$cond, [string]$msg)
  Assert-True $cond $msg
}
Write-Host "Validate-PreG5ReachCompareOrchestration end"

# Planning refuse for disposable runner
$dispExit = 0
$dispOut = ""
try {
  $dispOut = & powershell.exe -NoProfile -File (Join-Path $PSScriptRoot "Invoke-PreG5Disposable042Validation.ps1") 2>&1 | ForEach-Object { "$_" } | Out-String
  $dispExit = $LASTEXITCODE
} catch {
  $dispOut = $_.Exception.Message
  $dispExit = 1
}
Assert-True ($dispExit -ne 0) "disposable runner exits nonzero without -Execute"
Assert-True ($dispOut -match 'PLANNING ONLY|refuses without') "disposable runner planning refuse text"

$restoreExit = 0
$restoreOut = ""
try {
  $restoreOut = & powershell.exe -NoProfile -File (Join-Path $PSScriptRoot "Invoke-PreG5Disposable042RestoredDataProof.ps1") 2>&1 | ForEach-Object { "$_" } | Out-String
  $restoreExit = $LASTEXITCODE
} catch {
  $restoreOut = $_.Exception.Message
  $restoreExit = 1
}
Assert-True ($restoreExit -ne 0) "restored-data runner exits nonzero without -Execute"
Assert-True ($restoreOut -match 'PLANNING ONLY|refuses without') "restored-data runner planning refuse text"

$reachExit = 0
$reachOut = ""
try {
  $reachOut = & powershell.exe -NoProfile -File (Join-Path $PSScriptRoot "Invoke-PreG5Disposable042ReachabilityDiagnosis.ps1") 2>&1 | ForEach-Object { "$_" } | Out-String
  $reachExit = $LASTEXITCODE
} catch {
  $reachOut = $_.Exception.Message
  $reachExit = 1
}
Assert-True ($reachExit -ne 0) "reachability runner exits nonzero without -Execute"
Assert-True ($reachOut -match 'PLANNING ONLY|refuses without') "reachability runner planning refuse text"

$cmpExit = 0
$cmpOut = ""
try {
  $cmpOut = & powershell.exe -NoProfile -File (Join-Path $PSScriptRoot "Invoke-PreG5Disposable042ReachCompare.ps1") 2>&1 | ForEach-Object { "$_" } | Out-String
  $cmpExit = $LASTEXITCODE
} catch {
  $cmpOut = $_.Exception.Message
  $cmpExit = 1
}
Assert-True ($cmpExit -ne 0) "reach-compare runner exits nonzero without -Execute"
Assert-True ($cmpOut -match 'PLANNING ONLY|refuses without') "reach-compare runner planning refuse text"

# Clear injectable runner
$script:PreG5DockerRunner = $null

Write-Host "Validate-PreG5SnapshotFailurePaths done failed=$failed"
if ($failed -gt 0) { exit 1 }
exit 0
