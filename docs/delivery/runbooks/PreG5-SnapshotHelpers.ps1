#Requires -Version 5.1
<#
  Shared helpers for pre-G5 snapshot rematerialize + harmless failure-path tests.
  Dot-source only. Windows PowerShell 5.1.
#>
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "G3b-DockerProcess.ps1")

# Injectable docker control seam for harmless tests (scriptblock: DockerArgs, What, TimeoutMs -> hashtable).
$script:PreG5DockerRunner = $null
$script:PreG5ControlTimeoutMs = 30000

function Get-PreG5CustodyRoot {
  return [System.IO.Path]::GetFullPath("F:\DropFolder\scratch")
}

function Assert-ScratchRootSafe([string] $root) {
  if ([string]::IsNullOrWhiteSpace($root)) { throw "ScratchRoot empty" }
  if ($root -match '\s') {
    throw "REFUSE: ScratchRoot must not contain spaces (tar/argv safety): $root"
  }
  $full = [System.IO.Path]::GetFullPath($root)
  $custody = Get-PreG5CustodyRoot
  $sep = [string][System.IO.Path]::DirectorySeparatorChar
  $under = $full.StartsWith(($custody + $sep), [System.StringComparison]::OrdinalIgnoreCase)
  if ($full -ne $custody -and -not $under) {
    throw "REFUSE: ScratchRoot must be exactly F:\DropFolder\scratch or a subdirectory (local custody)"
  }
  return $full
}

function Assert-ExportStampSafe([string] $stamp) {
  if ([string]::IsNullOrWhiteSpace($stamp)) { throw "ExportStamp empty" }
  if ($stamp.Length -gt 80) { throw "REFUSE: ExportStamp too long" }
  if ($stamp -match '[\\/]|^\.\.|/\.\.|\\\.\.|\.\.$') {
    throw "REFUSE: ExportStamp must not contain path separators or traversal: $stamp"
  }
  if ($stamp -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
    throw "REFUSE: ExportStamp charset invalid: $stamp"
  }
  return $stamp
}

function Assert-PathWithinOwned {
  param(
    [Parameter(Mandatory = $true)][string] $OwnedDir,
    [Parameter(Mandatory = $true)][string] $CandidatePath
  )
  $owned = [System.IO.Path]::GetFullPath($OwnedDir).TrimEnd('\', '/')
  $cand = [System.IO.Path]::GetFullPath($CandidatePath)
  $sep = [string][System.IO.Path]::DirectorySeparatorChar
  if ($cand -ne $owned -and -not $cand.StartsWith(($owned + $sep), [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "REFUSE: path escapes owned directory: $CandidatePath"
  }
  return $cand
}

function Assert-DurablePathWritable {
  <# Refuse overwrite of prior stage evidence. #>
  param([Parameter(Mandatory = $true)][string] $Path)
  if (Test-Path -LiteralPath $Path) {
    throw "REFUSE: prior stage evidence exists (no overwrite): $Path"
  }
}

function Invoke-WindowsProcessCapturedTimed {
  param(
    [Parameter(Mandatory = $true)][string] $FilePath,
    [Parameter(Mandatory = $true)][string[]] $ArgumentList,
    [Parameter(Mandatory = $true)][string] $What,
    [Parameter(Mandatory = $true)][int] $TimeoutMs,
    [scriptblock] $Redact = { param([string] $t) $t }
  )
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FilePath
  $psi.Arguments = ConvertTo-WindowsCommandLine -ArgumentList $ArgumentList
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true

  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi
  $timedOut = $false
  try {
    [void]$proc.Start()
    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()
    if (-not $proc.WaitForExit($TimeoutMs)) {
      $timedOut = $true
      try { $proc.Kill() } catch { }
      try { [void]$proc.WaitForExit(5000) } catch { }
      throw ("TIMEOUT: $What exceeded ${TimeoutMs}ms (client killed; daemon work may continue)")
    }
    [void]$stdoutTask.Wait()
    [void]$stderrTask.Wait()
    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result
    if ($stdout) { Write-Host (& $Redact $stdout.TrimEnd()) }
    if ($stderr) { Write-Host ("docker_stderr_redacted=" + (& $Redact $stderr.TrimEnd())) }
    if ($proc.ExitCode -ne 0) {
      throw ("FAIL: $What exited $($proc.ExitCode)")
    }
    return @{ Code = 0; StdOut = $stdout; StdErr = $stderr; TimedOut = $false }
  }
  catch {
    if ($timedOut) { throw }
    throw
  }
  finally {
    if ($proc -and -not $proc.HasExited) {
      try { $proc.Kill() } catch { }
    }
    if ($proc) { $proc.Dispose() }
  }
}

function Invoke-WindowsProcessCapturedTimedAllowFail {
  <# Like Invoke-WindowsProcessCapturedTimed but non-zero exit returns Code (TIMEOUT still throws). #>
  param(
    [Parameter(Mandatory = $true)][string] $FilePath,
    [Parameter(Mandatory = $true)][string[]] $ArgumentList,
    [Parameter(Mandatory = $true)][string] $What,
    [Parameter(Mandatory = $true)][int] $TimeoutMs,
    [scriptblock] $Redact = { param([string] $t) $t }
  )
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FilePath
  $psi.Arguments = ConvertTo-WindowsCommandLine -ArgumentList $ArgumentList
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true

  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi
  try {
    [void]$proc.Start()
    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()
    if (-not $proc.WaitForExit($TimeoutMs)) {
      try { $proc.Kill() } catch { }
      try { [void]$proc.WaitForExit(5000) } catch { }
      throw ("TIMEOUT: $What exceeded ${TimeoutMs}ms (client killed; daemon work may continue)")
    }
    [void]$stdoutTask.Wait()
    [void]$stderrTask.Wait()
    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result
    if ($stdout) { Write-Host (& $Redact $stdout.TrimEnd()) }
    if ($stderr) { Write-Host ("docker_stderr_redacted=" + (& $Redact $stderr.TrimEnd())) }
    return @{ Code = $proc.ExitCode; StdOut = $stdout; StdErr = $stderr; TimedOut = $false }
  }
  finally {
    if ($proc -and -not $proc.HasExited) {
      try { $proc.Kill() } catch { }
    }
    if ($proc) { $proc.Dispose() }
  }
}

function Invoke-DockerTimed {
  param([string[]] $DockerArgs, [string] $What, [int] $TimeoutMs)
  return Invoke-WindowsProcessCapturedTimed -FilePath "docker" -ArgumentList $DockerArgs -What $What -TimeoutMs $TimeoutMs
}

function Invoke-PreG5DockerControl {
  param(
    [Parameter(Mandatory = $true)][string[]] $DockerArgs,
    [Parameter(Mandatory = $true)][string] $What,
    [int] $TimeoutMs = 0
  )
  if ($TimeoutMs -le 0) { $TimeoutMs = [int]$script:PreG5ControlTimeoutMs }
  if ($null -ne $script:PreG5DockerRunner) {
    return & $script:PreG5DockerRunner $DockerArgs $What $TimeoutMs
  }
  return Invoke-DockerTimed -DockerArgs $DockerArgs -What $What -TimeoutMs $TimeoutMs
}

function Invoke-PreG5DockerControlAllowFail {
  param(
    [Parameter(Mandatory = $true)][string[]] $DockerArgs,
    [Parameter(Mandatory = $true)][string] $What,
    [int] $TimeoutMs = 0
  )
  if ($TimeoutMs -le 0) { $TimeoutMs = [int]$script:PreG5ControlTimeoutMs }
  if ($null -ne $script:PreG5DockerRunner) {
    # Runner may throw; classify via message. Prefer returning Code when runner cooperates.
    try {
      $r = & $script:PreG5DockerRunner $DockerArgs $What $TimeoutMs
      if ($null -eq $r.Code) { return @{ Code = 0; StdOut = $r.StdOut; StdErr = $r.StdErr; TimedOut = $false } }
      return $r
    } catch {
      $msg = $_.Exception.Message
      # Operational timeouts use "TIMEOUT:" token — do NOT match incidental "timeout" in names/paths.
      if ($msg -match '(?i)TIMEOUT:') { throw }
      $code = 1
      if ($msg -match 'exited\s+(\d+)') { $code = [int]$Matches[1] }
      return @{ Code = $code; StdOut = ""; StdErr = $msg; TimedOut = $false }
    }
  }
  return Invoke-WindowsProcessCapturedTimedAllowFail -FilePath "docker" -ArgumentList $DockerArgs `
    -What $What -TimeoutMs $TimeoutMs
}

function Invoke-DockerChecked {
  param([string[]] $DockerArgs, [string] $What)
  return Invoke-PreG5DockerControl -DockerArgs $DockerArgs -What $What
}

function Resolve-DockerImagePresence {
  <#
    Present | Missing | throw.
    Daemon/access failures classified FIRST (abort).
    Missing ONLY on explicit "No such object" / "No such image" naming the queried ref.
    Generic "not found" alone is NOT permission to tag.
  #>
  param([Parameter(Mandatory = $true)][string] $Ref)
  $r = Invoke-PreG5DockerControlAllowFail -What "image inspect $Ref" -DockerArgs @(
    "image", "inspect", $Ref, "--format", "{{.Id}}"
  )
  if ($r.Code -eq 0) {
    return @{ Status = "Present"; Id = ([string]$r.StdOut).Trim() }
  }
  $blob = ("{0}`n{1}" -f $r.StdOut, $r.StdErr)
  # Infrastructure / access first — never treat as Missing (even if blob also says "not found").
  if ($blob -match '(?i)cannot connect|docker daemon|access denied|permission denied|EOF|error during connect') {
    throw ("FAIL: docker daemon/access error inspecting $Ref : $blob")
  }
  $esc = [regex]::Escape($Ref)
  $refEnd = '(?![A-Za-z0-9._:-])'
  $objectPat = '(?i)No such object:\s*' + $esc + $refEnd
  $imagePat = '(?i)No such image:\s*' + $esc + $refEnd
  if ($blob -match $objectPat -or $blob -match $imagePat) {
    return @{ Status = "Missing"; Id = $null }
  }
  throw ("FAIL: image inspect $Ref exited $($r.Code) (not classified missing): $blob")
}

function Preserve-ReleaseImageTags {
  <#
    Production tag preservation. Same-ID ok; different-ID REFUSE; Missing may tag; inspect errors abort.
  #>
  param(
    [Parameter(Mandatory = $true)][object[]] $Pairs
  )
  foreach ($pair in $Pairs) {
    $tag = [string]$pair.Tag
    $want = [string]$pair.Id
    $pres = Resolve-DockerImagePresence -Ref $tag
    if ($pres.Status -eq "Present") {
      if ($pres.Id -ne $want) {
        throw ("REFUSE overwrite ${tag} have=$($pres.Id) want=$want")
      }
      continue
    }
    if ($pres.Status -ne "Missing") {
      throw ("REFUSE unexpected presence status for ${tag}: $($pres.Status)")
    }
    Invoke-PreG5DockerControl -What "tag $tag" -DockerArgs @("tag", $want, $tag) | Out-Null
    $verify = Resolve-DockerImagePresence -Ref $tag
    if ($verify.Status -ne "Present" -or $verify.Id -ne $want) {
      throw ("release tag mismatch after create ${tag}")
    }
  }
  Write-Host "release_tags_ok"
}

function Assert-SnapshotImageTagAbsent {
  <# Import: only Missing allows proceed; Present refuses; unclassified inspect errors abort. #>
  param([Parameter(Mandatory = $true)][string] $Tag)
  $pres = Resolve-DockerImagePresence -Ref $Tag
  if ($pres.Status -eq "Present") {
    throw ("REFUSE tag exists $Tag id=$($pres.Id)")
  }
  if ($pres.Status -ne "Missing") {
    throw ("REFUSE cannot confirm tag absence for $Tag status=$($pres.Status)")
  }
}

function Invoke-PausePairById {
  <#
    Register+pause API first; only register web immediately before its own pause.
    If API pause does not verify, do not register or pause web (recovery will not unpause web).
  #>
  param($Ledger, $Api, $Web)
  Register-PauseAttempt -Ledger $Ledger -Id $Api.Id -Name $Api.Name
  $e1 = Invoke-PauseOneById -Ledger $Ledger -Id $Api.Id -Name $Api.Name
  if (-not $e1.VerifiedPaused) {
    throw ("api not VerifiedPaused after pause attempt; refusing to register/pause web. err=$($e1.PauseClientErr)")
  }
  Register-PauseAttempt -Ledger $Ledger -Id $Web.Id -Name $Web.Name
  $e2 = Invoke-PauseOneById -Ledger $Ledger -Id $Web.Id -Name $Web.Name
  if (-not $e2.VerifiedPaused) {
    throw ("web not VerifiedPaused after pause attempt err=$($e2.PauseClientErr)")
  }
  return @{ Api = $e1; Web = $e2 }
}

function ConvertFrom-InspectPipeLine([string] $raw, [string] $fallbackName) {
  $p = $raw.Trim() -split '\|', 6
  if ($p.Count -lt 5) { throw "inspect format unexpected: $raw" }
  $name = $fallbackName
  $id = $p[0]
  $image = $p[1]
  $running = $p[2]
  $paused = $p[3]
  $status = $p[4]
  if ($p.Count -ge 6) {
    # Id|Name|Image|Running|Paused|Status
    $name = ($p[1] -replace '^/', '')
    $image = $p[2]
    $running = $p[3]
    $paused = $p[4]
    $status = $p[5]
  }
  return [ordered]@{
    Name    = $name
    Id      = $id
    Image   = $image
    Running = ($running -eq "true")
    Paused  = ($paused -eq "true")
    Status  = $status
  }
}

function Get-ContainerIdentity([string] $name) {
  $r = Invoke-PreG5DockerControl -What "inspect name $name" -DockerArgs @(
    "inspect", $name, "--format", "{{.Id}}|{{.Image}}|{{.State.Running}}|{{.State.Paused}}|{{.State.Status}}"
  )
  return ConvertFrom-InspectPipeLine -raw $r.StdOut -fallbackName $name
}

function Get-ContainerIdentityById([string] $id) {
  $r = Invoke-PreG5DockerControl -What "inspect id $id" -DockerArgs @(
    "inspect", $id, "--format", "{{.Id}}|{{.Name}}|{{.Image}}|{{.State.Running}}|{{.State.Paused}}|{{.State.Status}}"
  )
  $st = ConvertFrom-InspectPipeLine -raw $r.StdOut -fallbackName ""
  # Exact recorded ID only — never accept a replacement that merely shares the old name.
  if ($st.Id -ne $id) {
    throw "inspect-by-id identity mismatch want=$id got=$($st.Id)"
  }
  return $st
}

function New-PauseLedger {
  return @{}
}

function Register-PauseAttempt {
  param($Ledger, [string] $Id, [string] $Name)
  if ($Ledger.ContainsKey($Id)) { return }
  $Ledger[$Id] = [ordered]@{
    Name                     = $Name
    Id                       = $Id
    PauseAttempted           = $false
    PauseClientOk            = $false
    PauseClientErr           = $null
    VerifiedPaused           = $false
    UnpauseAttempted         = $false
    UnpauseClientOk          = $false
    UnpauseClientErr         = $null
    VerifiedUnpaused         = $false
    Unresolved               = $true
    FailedRecoveryEscalation = $false
  }
}

function Invoke-PauseOneById {
  <#
    Pause a single container by ID. Inspect-by-ID only after pause (never name-based resolve).
    Bounded control timeout. Always records attempt; reconciles VerifiedPaused from inspect-by-id.
  #>
  param($Ledger, [string] $Id, [string] $Name)
  if (-not $Ledger.ContainsKey($Id)) { Register-PauseAttempt -Ledger $Ledger -Id $Id -Name $Name }
  $e = $Ledger[$Id]
  $e.PauseAttempted = $true
  try {
    Invoke-PreG5DockerControl -What "pause $Name" -DockerArgs @("pause", $Id) | Out-Null
    $e.PauseClientOk = $true
  } catch {
    $e.PauseClientOk = $false
    $e.PauseClientErr = $_.Exception.Message
  }
  try {
    $st = Get-ContainerIdentityById $Id
    $e.VerifiedPaused = [bool]$st.Paused
    $e.Unresolved = [bool]$e.VerifiedPaused
  } catch {
    $e.VerifiedPaused = $false
    $e.Unresolved = $true
    $e.FailedRecoveryEscalation = $true
    $e.PauseClientErr = ("inspect-by-id after pause failed: " + $_.Exception.Message)
  }
  return $e
}

function Invoke-UnpauseOneById {
  <#
    Unpause + reconcile by recorded ID only. Inspect exceptions leave Unresolved durable;
    never mark resolved from a replacement container that merely shares the old name.
  #>
  param($Ledger, [string] $Id)
  if (-not $Ledger.ContainsKey($Id)) { return $null }
  $e = $Ledger[$Id]
  $e.UnpauseAttempted = $true
  try {
    Invoke-PreG5DockerControl -What "unpause $($e.Name)" -DockerArgs @("unpause", $Id) | Out-Null
    $e.UnpauseClientOk = $true
  } catch {
    $e.UnpauseClientOk = $false
    $e.UnpauseClientErr = $_.Exception.Message
  }
  try {
    $st = Get-ContainerIdentityById $Id
    $e.VerifiedUnpaused = (-not [bool]$st.Paused)
    $e.Unresolved = -not $e.VerifiedUnpaused
    if ($e.VerifiedUnpaused) { $e.FailedRecoveryEscalation = $false }
  } catch {
    # Do NOT fall back to name inspect — replacement sharing the name must not clear Unresolved.
    $e.VerifiedUnpaused = $false
    $e.Unresolved = $true
    $e.FailedRecoveryEscalation = $true
    $suffix = "inspect-by-id failed (unresolved durable; no name-based resolve): " + $_.Exception.Message
    if ($e.UnpauseClientErr) { $e.UnpauseClientErr = $e.UnpauseClientErr + " | " + $suffix }
    else { $e.UnpauseClientErr = $suffix }
  }
  return $e
}

function Invoke-UnpauseAllUnresolved {
  <#
    Independent per-container recovery. One entry's inspect/unpause failure must not abort the rest.
    Requires PauseAttempted before any unpause — never unpause a merely pre-registered ID.
    Returns list of escalation messages for any FailedRecoveryEscalation entries.
  #>
  param($Ledger)
  $escalations = New-Object System.Collections.Generic.List[string]
  foreach ($id in @($Ledger.Keys)) {
    try {
      $e = $Ledger[$id]
      if ($e.VerifiedUnpaused) { continue }
      # Ownership gate: only containers we actually attempted to pause.
      if (-not $e.PauseAttempted) { continue }
      [void](Invoke-UnpauseOneById -Ledger $Ledger -Id $id)
      if ($Ledger[$id].FailedRecoveryEscalation) {
        $escalations.Add(("FAILED_RECOVERY id={0} name={1} err={2}" -f $id, $Ledger[$id].Name, $Ledger[$id].UnpauseClientErr))
      }
    } catch {
      if ($Ledger.ContainsKey($id)) {
        $Ledger[$id].Unresolved = $true
        $Ledger[$id].VerifiedUnpaused = $false
        $Ledger[$id].FailedRecoveryEscalation = $true
        $Ledger[$id].UnpauseClientErr = ("unpause-all independent catch: " + $_.Exception.Message)
      }
      $escalations.Add(("FAILED_RECOVERY id={0} independent_error={1}" -f $id, $_.Exception.Message))
    }
  }
  return @($escalations)
}

function Test-PauseLedgerAllResolved($Ledger) {
  foreach ($id in $Ledger.Keys) {
    $e = $Ledger[$id]
    if (-not $e.PauseAttempted) { continue }
    # Attempted pause but never actually paused => nothing to unpause (resolved).
    if (-not $e.VerifiedPaused -and -not $e.Unresolved) { continue }
    if (-not $e.VerifiedUnpaused) { return $false }
    if ($e.Unresolved) { return $false }
  }
  return $true
}

function Test-PauseLedgerObjectResolved($PauseLedgerObject) {
  if ($null -eq $PauseLedgerObject) { return $true }
  foreach ($prop in @($PauseLedgerObject.PSObject.Properties)) {
    $e = $prop.Value
    $pauseAttempted = $false
    $verifiedPaused = $false
    $unresolved = $false
    $verifiedUnpaused = $false
    if ($null -ne $e.PauseAttempted) { $pauseAttempted = [bool]$e.PauseAttempted }
    if ($null -ne $e.VerifiedPaused) { $verifiedPaused = [bool]$e.VerifiedPaused }
    if ($null -ne $e.Unresolved) { $unresolved = [bool]$e.Unresolved }
    if ($null -ne $e.VerifiedUnpaused) { $verifiedUnpaused = [bool]$e.VerifiedUnpaused }
    if (-not $pauseAttempted) { continue }
    if (-not $verifiedPaused -and -not $unresolved) { continue }
    if (-not $verifiedUnpaused -or $unresolved) { return $false }
  }
  return $true
}

function Assert-ExportReadyForImport {
  <#
    Import gate: unresolved pause ledger or non-zero health_exit_hint requires a verified recovery
    receipt bound to this export stamp + exact source container IDs, with recovered ledger evidence.
    Two-boolean stubs are rejected.
  #>
  param(
    $ExportReceipt,
    [string] $ScratchDir,
    [string] $RecoveryReceiptPath = "",
    [string] $ExpectStamp = ""
  )
  $hint = 0
  if ($null -ne $ExportReceipt.health_exit_hint) { $hint = [int]$ExportReceipt.health_exit_hint }
  $ledgerResolved = Test-PauseLedgerObjectResolved $ExportReceipt.pause_ledger

  if ($hint -eq 0 -and $ledgerResolved) { return $true }

  $recPath = $RecoveryReceiptPath
  if ([string]::IsNullOrWhiteSpace($recPath)) {
    $recPath = Join-Path $ScratchDir "recovery.receipt.json"
  }
  if (-not (Test-Path -LiteralPath $recPath)) {
    throw ("REFUSE Import: export health_exit_hint=$hint ledger_resolved=$ledgerResolved; missing verified recovery receipt at $recPath")
  }
  $rec = Get-Content -LiteralPath $recPath -Raw | ConvertFrom-Json
  if ($rec.verified_resolved -ne $true) {
    throw "REFUSE Import: recovery.receipt.json verified_resolved != true"
  }
  if ($rec.health_ok -ne $true) {
    throw "REFUSE Import: recovery.receipt.json health_ok != true"
  }

  $exportStamp = [string]$ExportReceipt.stamp
  if (-not [string]::IsNullOrWhiteSpace($ExpectStamp) -and $exportStamp -ne $ExpectStamp) {
    throw "REFUSE Import: export stamp mismatch vs ExpectStamp"
  }
  if ([string]$rec.stamp -ne $exportStamp) {
    throw ("REFUSE Import: recovery stamp '$($rec.stamp)' != export stamp '$exportStamp'")
  }
  if ([string]$rec.source_api_container_id -ne [string]$ExportReceipt.source_api_container_id) {
    throw "REFUSE Import: recovery source_api_container_id mismatch"
  }
  if ([string]$rec.source_web_container_id -ne [string]$ExportReceipt.source_web_container_id) {
    throw "REFUSE Import: recovery source_web_container_id mismatch"
  }
  if ($null -eq $rec.pause_ledger) {
    throw "REFUSE Import: recovery.receipt.json missing pause_ledger evidence"
  }
  if (-not (Test-PauseLedgerObjectResolved $rec.pause_ledger)) {
    throw "REFUSE Import: recovery pause_ledger is not fully resolved"
  }
  # EACH PauseAttempted export ID must have affirmative VerifiedUnpaused=true and Unresolved=false.
  if ($null -ne $ExportReceipt.pause_ledger) {
    foreach ($prop in @($ExportReceipt.pause_ledger.PSObject.Properties)) {
      $id = $prop.Name
      $e = $prop.Value
      $pauseAttempted = $false
      if ($null -ne $e.PauseAttempted) { $pauseAttempted = [bool]$e.PauseAttempted }
      if (-not $pauseAttempted) { continue }
      $recProp = $rec.pause_ledger.PSObject.Properties[$id]
      if ($null -eq $recProp) {
        throw ("REFUSE Import: recovery pause_ledger missing export id $id")
      }
      $re = $recProp.Value
      if ($re.VerifiedUnpaused -ne $true) {
        throw ("REFUSE Import: recovery id $id VerifiedUnpaused != true")
      }
      # Unresolved must be explicitly false (not missing/null).
      if ($re.Unresolved -ne $false) {
        throw ("REFUSE Import: recovery id $id Unresolved must be false")
      }
    }
  }
  return $true
}

function Normalize-TarPath([string] $p) {
  $norm = ($p -replace '\\', '/')
  # Strip only a literal "./" prefix (NOT TrimStart('./') which eats leading '.' from ".env")
  while ($norm.StartsWith('./')) {
    $norm = $norm.Substring(2)
  }
  return $norm
}

function Get-TarPathClasses {
  param([string[]] $Paths)
  $stats = [ordered]@{
    path_count            = $Paths.Count
    secrets_tree_paths    = 0
    app_tree_paths        = 0
    nginx_cache_paths     = 0
    env_file_paths        = 0
    credential_name_paths = 0
    suspicious            = $false
    sample_secrets_tree   = @()
    sample_env_names      = @()
    sample_cred_names     = @()
    note                  = "Name/path inventory only — NOT content sanitization or secret-content clearance. Lack of suspicious filenames is NOT private-content clearance."
  }
  foreach ($p in $Paths) {
    $norm = Normalize-TarPath $p
    if ($norm -match '(?i)^secrets(/|$)') {
      $stats.secrets_tree_paths++
      if ($stats.sample_secrets_tree.Count -lt 8) { $stats.sample_secrets_tree += $norm }
    }
    if ($norm -match '(?i)^app(/|$)') { $stats.app_tree_paths++ }
    if ($norm -match '(?i)var/cache/nginx') { $stats.nginx_cache_paths++ }
    if ($norm -match '(?i)(^|/)\.env($|\.)|\.env\.|/env\.local') {
      $stats.env_file_paths++
      if ($stats.sample_env_names.Count -lt 8) { $stats.sample_env_names += $norm }
    }
    if ($norm -match '(?i)credential|client_secret|token.*\.json|id_rsa|\.pem$|secrets-backup') {
      $stats.credential_name_paths++
      if ($stats.sample_cred_names.Count -lt 8) { $stats.sample_cred_names += $norm }
    }
  }
  $stats.suspicious = ($stats.secrets_tree_paths -gt 0 -or $stats.env_file_paths -gt 0 -or $stats.credential_name_paths -gt 0)
  return $stats
}

function Assert-ImportedConfig {
  param(
    [string] $Tag,
    $EnvAllow,
    [string] $ExpectWorkdir,
    [string] $ExpectUser,
    [string[]] $ExpectEntrypoint,
    [string[]] $ExpectCmd
  )
  $r = Invoke-PreG5DockerControl -What "image inspect $Tag" -DockerArgs @(
    "image", "inspect", $Tag, "--format", "{{json .Config}}"
  )
  $cfg = $r.StdOut | ConvertFrom-Json
  $envMap = @{}
  foreach ($line in @($cfg.Env)) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $kv = $line -split "=", 2
    $envMap[$kv[0]] = if ($kv.Count -gt 1) { $kv[1] } else { "" }
  }
  foreach ($k in @($envMap.Keys)) {
    if (@($EnvAllow.Keys) -notcontains $k) { throw "non-allowlisted Env key $k on $Tag" }
    if ([string]$envMap[$k] -cne [string]$EnvAllow[$k]) {
      throw "Env value mismatch for $k on $Tag (allowlist equality)"
    }
  }
  foreach ($k in @($EnvAllow.Keys)) {
    if (-not $envMap.ContainsKey($k)) { throw "missing allowlist Env $k on $Tag" }
  }
  if ([string]$cfg.WorkingDir -cne $ExpectWorkdir) { throw "WORKDIR mismatch on $Tag" }
  # docker import Config often omits User entirely — StrictMode must not treat absence as hard fail.
  $gotUser = ""
  if ($null -ne $cfg.PSObject.Properties['User'] -and $null -ne $cfg.User) {
    $gotUser = [string]$cfg.User
  }
  if ($gotUser -cne $ExpectUser) { throw "USER mismatch on $Tag got='$gotUser'" }
  $ep = @()
  if ($null -ne $cfg.PSObject.Properties['Entrypoint'] -and $null -ne $cfg.Entrypoint) {
    $ep = @($cfg.Entrypoint)
  }
  $cmd = @()
  if ($null -ne $cfg.PSObject.Properties['Cmd'] -and $null -ne $cfg.Cmd) {
    $cmd = @($cfg.Cmd)
  }
  if (($ep -join '|') -cne ($ExpectEntrypoint -join '|')) { throw "ENTRYPOINT mismatch on $Tag" }
  if (($cmd -join '|') -cne ($ExpectCmd -join '|')) { throw "CMD mismatch on $Tag" }
}

function Assert-ComposeProjectResourcesFresh {
  <#
    Collision check for project-scoped network/volume names after removing literal name: fields.
    Compose will create {project}_preg5_net and {project}_preg5_pgdata.
  #>
  param(
    [Parameter(Mandatory = $true)][string] $ProjectName,
    [scriptblock] $NetworkLister = $null,
    [scriptblock] $VolumeLister = $null,
    [switch] $DualNet
  )
  if ($ProjectName -notmatch '^[a-z0-9][a-z0-9_-]*$') {
    throw "REFUSE: compose project name charset invalid: $ProjectName"
  }
  $expectNet = "${ProjectName}_preg5_net"
  $expectPubNet = "${ProjectName}_preg5_publish"
  $expectVol = "${ProjectName}_preg5_pgdata"
  $nets = @()
  $vols = @()
  if ($null -ne $NetworkLister) {
    $nets = @(& $NetworkLister)
  } else {
    $r = Invoke-PreG5DockerControl -What "network ls" -DockerArgs @("network", "ls", "--format", "{{.Name}}")
    $nets = @($r.StdOut -split "`r?`n" | Where-Object { $_ -and $_.Trim() })
  }
  if ($null -ne $VolumeLister) {
    $vols = @(& $VolumeLister)
  } else {
    $r = Invoke-PreG5DockerControl -What "volume ls" -DockerArgs @("volume", "ls", "--format", "{{.Name}}")
    $vols = @($r.StdOut -split "`r?`n" | Where-Object { $_ -and $_.Trim() })
  }
  if ($nets -contains $expectNet) { throw "REFUSE: network collision $expectNet" }
  if ($DualNet -and ($nets -contains $expectPubNet)) {
    throw "REFUSE: network collision $expectPubNet"
  }
  if ($vols -contains $expectVol) { throw "REFUSE: volume collision $expectVol" }
  $result = @{ Network = $expectNet; Volume = $expectVol; DualNet = [bool]$DualNet }
  if ($DualNet) { $result.PublishNetwork = $expectPubNet }
  return $result
}

function Assert-HostTcpPortFree {
  param([Parameter(Mandatory = $true)][int] $Port, [string] $BindHost = "127.0.0.1")
  try {
    $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse($BindHost), $Port)
    $l.Start()
    $l.Stop()
    return $true
  } catch {
    throw ("REFUSE: host port in use or unavailable ${BindHost}:$Port — $($_.Exception.Message)")
  }
}

function Assert-DisposableProjectPreflight {
  <#
    Full disposable collision gate BEFORE any compose up/down.
    On refuse: caller must NOT docker compose down -v (may be unowned/preexisting).
  #>
  param(
    [Parameter(Mandatory = $true)][string] $ProjectName,
    [int[]] $HostPorts = @(18000, 18080),
    [scriptblock] $NetworkLister = $null,
    [scriptblock] $VolumeLister = $null,
    [scriptblock] $ProjectContainerLister = $null,
    [switch] $DualNet
  )
  $res = Assert-ComposeProjectResourcesFresh -ProjectName $ProjectName `
    -NetworkLister $NetworkLister -VolumeLister $VolumeLister -DualNet:$DualNet
  $containers = @()
  if ($null -ne $ProjectContainerLister) {
    $containers = @(& $ProjectContainerLister)
  } else {
    $fmt = '{{.ID}} {{.Names}} {{.Label "com.docker.compose.project"}}'
    $r = Invoke-PreG5DockerControlAllowFail -What "ps project containers" -DockerArgs @(
      "ps", "-a", "--filter", "label=com.docker.compose.project=$ProjectName", "--format", $fmt
    )
    if ($r.Code -ne 0) {
      throw ("UNRESOLVED: project container list failed code=$($r.Code) err=$($r.StdErr)")
    }
    if (-not [string]::IsNullOrWhiteSpace($r.StdOut)) {
      $containers = @($r.StdOut -split "`r?`n" | Where-Object { $_ -and $_.Trim() })
    }
  }
  if ($containers.Count -gt 0) {
    throw ("REFUSE: project-labeled containers already exist for $ProjectName — will not down -v unowned/preexisting: " + ($containers -join '; '))
  }
  foreach ($p in $HostPorts) {
    Assert-HostTcpPortFree -Port $p | Out-Null
  }
  return @{
    Network    = $res.Network
    Volume     = $res.Volume
    Containers = @()
    HostPorts  = @($HostPorts)
  }
}

function Read-HttpWebResponseBodyBytes {
  <#
    PS5.1-safe response body acquisition. Prefer byte buffer over StreamReader so a
    partially-consumed / non-seekable error stream does not silently become "".
    Returns acquisition_ok=false when the stream cannot be read — distinct from empty body.
  #>
  param($Response)
  if ($null -eq $Response) {
    return [ordered]@{
      body             = $null
      acquisition_ok   = $false
      acquisition_error = "response_null"
    }
  }
  $stream = $null
  try {
    $stream = $Response.GetResponseStream()
  } catch {
    return [ordered]@{
      body              = $null
      acquisition_ok    = $false
      acquisition_error = ("get_response_stream:" + $_.Exception.Message)
    }
  }
  if ($null -eq $stream) {
    return [ordered]@{
      body              = $null
      acquisition_ok    = $false
      acquisition_error = "response_stream_null"
    }
  }
  try {
    try {
      if ($stream.CanSeek) { $stream.Position = 0 }
    } catch { }
    $ms = New-Object System.IO.MemoryStream
    $buffer = New-Object byte[] 8192
    while (($n = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
      $ms.Write($buffer, 0, $n)
    }
    $bytes = $ms.ToArray()
    $body = [System.Text.Encoding]::UTF8.GetString($bytes)
    return [ordered]@{
      body              = $body
      acquisition_ok    = $true
      acquisition_error = $null
    }
  } catch {
    return [ordered]@{
      body              = $null
      acquisition_ok    = $false
      acquisition_error = ("read_response_stream:" + $_.Exception.Message)
    }
  } finally {
    try { $stream.Dispose() } catch { }
  }
}

function Invoke-HttpJsonCapture {
  <#
    Capture HTTP status + raw body via Invoke-WebRequest (PS5.1). Never asserts.
    transport_fail: no HTTP response object obtained.
    acquisition_ok=false: response exists but body bytes could not be read.
  #>
  param(
    [Parameter(Mandatory = $true)][string] $Uri,
    [int] $TimeoutSec = 15
  )
  $out = [ordered]@{
    uri                    = $Uri
    transport_fail         = $false
    status                 = $null
    body                   = $null
    acquisition_ok         = $false
    acquisition_error      = $null
    error                  = $null
    web_exception_status   = $null
  }
  try {
    $resp = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec $TimeoutSec -MaximumRedirection 0
    $out.status = [int]$resp.StatusCode
    if ($null -ne $resp.Content) {
      $out.body = [string]$resp.Content
      $out.acquisition_ok = $true
    } else {
      $out.acquisition_ok = $false
      $out.acquisition_error = "success_response_content_null"
    }
    return $out
  } catch {
    $ex = $_.Exception
    $webEx = $ex
    if ($ex -isnot [System.Net.WebException] -and $null -ne $ex.InnerException -and $ex.InnerException -is [System.Net.WebException]) {
      $webEx = $ex.InnerException
    }
    $response = $null
    if ($webEx -is [System.Net.WebException]) {
      $response = $webEx.Response
    } elseif ($ex.PSObject.Properties['Response'] -and $ex.Response) {
      $response = $ex.Response
    }
    if ($null -eq $response) {
      $out.transport_fail = $true
      if ($webEx -is [System.Net.WebException]) {
        $out.web_exception_status = [string]$webEx.Status
      }
      $out.error = ("FAIL: HTTP $Uri — " + $ex.Message)
      return $out
    }
    try {
      if ($response.StatusCode -is [System.Net.HttpStatusCode]) {
        $out.status = [int]$response.StatusCode
      } else {
        $out.status = [int]$response.StatusCode.value__
      }
    } catch {
      $out.transport_fail = $true
      $out.error = ("FAIL: HTTP $Uri — status unreadable: " + $_.Exception.Message + " / " + $ex.Message)
      return $out
    }
    $read = Read-HttpWebResponseBodyBytes -Response $response
    $out.body = $read.body
    $out.acquisition_ok = [bool]$read.acquisition_ok
    $out.acquisition_error = $read.acquisition_error
    if (-not $out.acquisition_ok) {
      $out.error = ("FAIL: HTTP $Uri body acquisition failed: " + $read.acquisition_error)
    }
    return $out
  }
}

function Test-HttpJsonAuthContent {
  <#
    Fail-closed JSON `code` check (whitespace-insensitive). Optional substring markers remain supported.
    Returns ok + detail; does not throw.
  #>
  param(
    [AllowNull()][string] $Body,
    [string] $ExpectJsonCode = "",
    [string[]] $BodyMustContain = @()
  )
  $result = [ordered]@{
    ok           = $false
    parsed_code  = $null
    error        = $null
    mismatch_kind = $null
  }
  if (-not [string]::IsNullOrWhiteSpace($ExpectJsonCode)) {
    if ($null -eq $Body) {
      $result.mismatch_kind = "body_null"
      $result.error = "body_null while ExpectJsonCode=$ExpectJsonCode"
      return $result
    }
    $parsed = $null
    try {
      $parsed = $Body | ConvertFrom-Json
    } catch {
      $result.mismatch_kind = "malformed_json"
      $result.error = ("malformed JSON: " + $_.Exception.Message)
      return $result
    }
    $codeProp = $null
    if ($null -ne $parsed -and $parsed.PSObject.Properties['code']) {
      $codeProp = [string]$parsed.code
    }
    $result.parsed_code = $codeProp
    if ([string]::IsNullOrWhiteSpace($codeProp) -or $codeProp -ne $ExpectJsonCode) {
      $result.mismatch_kind = "wrong_or_missing_code"
      $got = $(if ($null -eq $codeProp) { "<missing>" } else { $codeProp })
      $result.error = ("JSON code want=$ExpectJsonCode got=$got")
      return $result
    }
  }
  foreach ($frag in @($BodyMustContain)) {
    if ([string]::IsNullOrEmpty($frag)) { continue }
    if ($null -eq $Body -or $Body -notmatch [regex]::Escape($frag)) {
      $result.mismatch_kind = "missing_body_marker"
      $result.error = ("missing expected body marker '$frag'")
      return $result
    }
  }
  $result.ok = $true
  return $result
}

function Convert-HttpJsonCaptureToProbeResult {
  <# Classify a capture into host-probe shape; always preserves status/body when known. #>
  param(
    [Parameter(Mandatory = $true)] $Capture,
    [Parameter(Mandatory = $true)][int] $ExpectStatus,
    [string] $ExpectJsonCode = "",
    [string[]] $BodyMustContain = @()
  )
  $uri = [string]$Capture.uri
  if ([bool]$Capture.transport_fail) {
    return [ordered]@{
      classification        = "transport_fail"
      uri                   = $uri
      http_status           = $null
      body                  = $null
      transport_fail        = $true
      acquisition_ok        = $false
      acquisition_error     = $null
      parsed_code           = $null
      web_exception_status  = $(if (@($Capture.PSObject.Properties.Name) -contains 'web_exception_status') {
          [string]$Capture.PSObject.Properties['web_exception_status'].Value
        } else { $null })
      error                 = $(if ($Capture.error) { [string]$Capture.error } else { "transport_fail" })
    }
  }
  $status = $Capture.status
  if (-not [bool]$Capture.acquisition_ok) {
    return [ordered]@{
      classification    = "http_error"
      uri               = $uri
      http_status       = $status
      body              = $null
      transport_fail    = $false
      acquisition_ok    = $false
      acquisition_error = [string]$Capture.acquisition_error
      parsed_code       = $null
      error             = $(if ($Capture.error) { [string]$Capture.error } else { "body acquisition failed" })
    }
  }
  $body = [string]$Capture.body
  if ($null -eq $status -or [int]$status -ne [int]$ExpectStatus) {
    return [ordered]@{
      classification    = "http_status_mismatch"
      uri               = $uri
      http_status       = $status
      body              = $body
      transport_fail    = $false
      acquisition_ok    = $true
      acquisition_error = $null
      parsed_code       = $null
      error             = ("FAIL: HTTP $uri status=$status want=$ExpectStatus body=$body")
    }
  }
  $content = Test-HttpJsonAuthContent -Body $body -ExpectJsonCode $ExpectJsonCode -BodyMustContain $BodyMustContain
  if (-not $content.ok) {
    return [ordered]@{
      classification    = "http_body_mismatch"
      uri               = $uri
      http_status       = $status
      body              = $body
      transport_fail    = $false
      acquisition_ok    = $true
      acquisition_error = $null
      parsed_code       = $content.parsed_code
      error             = ("FAIL: HTTP $uri " + $content.error)
      mismatch_kind     = $content.mismatch_kind
    }
  }
  return [ordered]@{
    classification    = "http_ok"
    uri               = $uri
    http_status       = $status
    body              = $body
    transport_fail    = $false
    acquisition_ok    = $true
    acquisition_error = $null
    parsed_code       = $content.parsed_code
    error             = $null
  }
}

function Assert-HttpJsonExpectation {
  <#
    Status + JSON code and/or required substrings. Uses Invoke-HttpJsonCapture so body
    acquisition failures are distinct from content mismatch. Throws on failure (disposable readiness).
  #>
  param(
    [Parameter(Mandatory = $true)][string] $Uri,
    [Parameter(Mandatory = $true)][int] $ExpectStatus,
    [string[]] $BodyMustContain = @(),
    [string] $ExpectJsonCode = "",
    [int] $TimeoutSec = 15
  )
  $cap = Invoke-HttpJsonCapture -Uri $Uri -TimeoutSec $TimeoutSec
  $probe = Convert-HttpJsonCaptureToProbeResult -Capture $cap -ExpectStatus $ExpectStatus `
    -ExpectJsonCode $ExpectJsonCode -BodyMustContain $BodyMustContain
  if ($probe.classification -ne 'http_ok') {
    if ($probe.error) { throw [string]$probe.error }
    throw ("FAIL: HTTP $Uri classification=$($probe.classification)")
  }
  return @{
    Status     = [int]$probe.http_status
    Body       = [string]$probe.body
    ParsedCode = $probe.parsed_code
  }
}

function New-ImportIntentLedger {
  return @{}
}

function Register-IntendedSnapshotTag {
  <# Record intended tag BEFORE docker import is invoked. #>
  param($Ledger, [string] $Tag, [string] $Role)
  if ($Ledger.ContainsKey($Tag)) { throw "intended tag already registered: $Tag" }
  $Ledger[$Tag] = [ordered]@{
    Tag                  = $Tag
    Role                 = $Role
    IntendedBeforeImport = $true
    ImportAttempted      = $false
    ImportClientOk       = $false
    ImportTimedOut       = $false
    Outcome              = "pending"  # pending|created|uncertain|failed
    ObservedId           = $null
    Notes                = $null
    StampReuseRequiresReview = $false
  }
}

function Invoke-DockerImportWithIntent {
  <#
    Dedicated Import timeout (not the general control timeout).
    On TIMEOUT: Outcome=uncertain; read-only reconcile; do NOT delete/retry/declare absence final;
    never treat as creation_ok. Stamp reuse requires review.
  #>
  param(
    [Parameter(Mandatory = $true)] $IntentLedger,
    [Parameter(Mandatory = $true)][string] $Tag,
    [Parameter(Mandatory = $true)][string[]] $DockerArgs,
    [Parameter(Mandatory = $true)][string] $What,
    [Parameter(Mandatory = $true)][int] $TimeoutMs
  )
  if (-not $IntentLedger.ContainsKey($Tag)) {
    throw "REFUSE: import invoked without prior intended-tag registration for $Tag"
  }
  $e = $IntentLedger[$Tag]
  $e.ImportAttempted = $true
  try {
    # Dedicated ImportTimeoutMs via control seam (injectable for tests); not the default 30s control budget alone.
    Invoke-PreG5DockerControl -DockerArgs $DockerArgs -What $What -TimeoutMs $TimeoutMs | Out-Null
    $e.ImportClientOk = $true
    $pres = Resolve-DockerImagePresence -Ref $Tag
    if ($pres.Status -ne "Present") {
      $e.Outcome = "failed"
      $e.Notes = "import client ok but tag not Present"
      throw $e.Notes
    }
    $e.Outcome = "created"
    $e.ObservedId = $pres.Id
    return $pres.Id
  } catch {
    $msg = $_.Exception.Message
    if ($msg -match '(?i)TIMEOUT:') {
      $e.ImportTimedOut = $true
      $e.Outcome = "uncertain"
      $e.StampReuseRequiresReview = $true
      # Bounded read-only reconciliation — no delete/overwrite/retry.
      try {
        $pres = Resolve-DockerImagePresence -Ref $Tag
        if ($pres.Status -eq "Present") {
          $e.ObservedId = $pres.Id
          $e.Notes = "TIMEOUT: tag Present id=$($pres.Id); daemon work may still be active; NOT creation_ok; stamp reuse requires review; absence NOT declared"
        } else {
          $e.Notes = "TIMEOUT: tag not classified Present; absence NOT declared final while daemon may still create; stamp reuse requires review"
        }
      } catch {
        $e.Notes = "TIMEOUT: reconcile inspect failed ($($_.Exception.Message)); absence NOT declared final; stamp reuse requires review"
      }
      throw ("IMPORT_TIMEOUT_UNCERTAIN tag=$Tag")
    }
    if ($e.Outcome -eq "pending") { $e.Outcome = "failed" }
    if (-not $e.Notes) { $e.Notes = $msg }
    throw
  }
}

function New-ProbeLedger {
  return @{}
}

function Register-IntendedProbe {
  param($Ledger, [string] $Name, [string] $ImageTag, [string] $Role, [string] $AttemptLabel)
  if ($Ledger.ContainsKey($Name)) { throw "probe name already registered: $Name" }
  $Ledger[$Name] = [ordered]@{
    Name                   = $Name
    ImageTag               = $ImageTag
    Role                   = $Role
    AttemptLabel           = $AttemptLabel
    IntendedBeforeCreate   = $true
    CreateAttempted        = $false
    CreateTimedOut         = $false
    CreateOutcomeUnknown   = $false
    OwnedId                = $null   # set only from successful create — ownership
    StartAttempted         = $false
    ClientOk               = $false
    TimedOut               = $false
    CleanupAttempted       = $false
    CleanupOk              = $false
    CleanupUncertain       = $false
    CleanupNotes           = $null
    Notes                  = $null
  }
}

function Resolve-ContainerPresenceByRef {
  <#
    Present | Missing | throw.
    Missing ONLY on explicit No such object/container naming the *complete* queried ref
    (not a prefix of a longer ref; not a generic No-such without the ref).
    Daemon/access/TIMEOUT/unclassified => throw (unresolved — never treat as absence).
  #>
  param(
    [Parameter(Mandatory = $true)][string] $Ref,
    [string] $Format = "{{.Id}}"
  )
  $r = Invoke-PreG5DockerControlAllowFail -What "inspect container $Ref" -DockerArgs @(
    "inspect", $Ref, "--format", $Format
  )
  if ($r.Code -eq 0) {
    return @{ Status = "Present"; StdOut = ([string]$r.StdOut).Trim(); Id = ([string]$r.StdOut).Trim() }
  }
  $blob = ("{0}`n{1}" -f $r.StdOut, $r.StdErr)
  if ($blob -match '(?i)TIMEOUT:' -or $blob -match '(?i)cannot connect|docker daemon|access denied|permission denied|EOF|error during connect') {
    throw ("FAIL: container inspect daemon/access/timeout for ${Ref}: $blob")
  }
  $esc = [regex]::Escape($Ref)
  # Complete ref only: reject prefix-of-longer-ref (e.g. cid-abc vs cid-abc-extra).
  $refEnd = '(?![A-Za-z0-9._:-])'
  if ($blob -match ('(?i)No such object:\s*' + $esc + $refEnd) -or
      $blob -match ('(?i)No such container:\s*' + $esc + $refEnd)) {
    return @{ Status = "Missing"; StdOut = ""; Id = $null }
  }
  throw ("FAIL: container inspect $Ref exited $($r.Code) (not classified missing): $blob")
}

function Get-ContainerIdByExactName {
  param([string] $Name)
  $pres = Resolve-ContainerPresenceByRef -Ref $Name -Format "{{.Id}}"
  if ($pres.Status -eq "Missing") { return $null }
  $id = $pres.Id
  if ([string]::IsNullOrWhiteSpace($id)) { return $null }
  return $id
}

function Get-ContainerOwnershipFacts {
  param([string] $Id)
  $fmt = '{{.Id}}|{{.Name}}|{{.Config.Image}}|{{index .Config.Labels "preg5.attempt"}}'
  $r = Invoke-PreG5DockerControl -What "inspect owned $Id" -DockerArgs @(
    "inspect", $Id, "--format", $fmt
  )
  $p = $r.StdOut.Trim() -split '\|', 4
  return [ordered]@{
    Id           = $p[0]
    Name         = ($p[1] -replace '^/', '')
    Image        = $p[2]
    AttemptLabel = $(if ($p.Count -ge 4) { $p[3] } else { "" })
  }
}

function Assert-ProbeNameAbsent {
  param([string] $Name)
  $id = Get-ContainerIdByExactName -Name $Name
  if ($null -ne $id) {
    throw ("REFUSE: probe name already exists (foreign or stale) name=$Name id=$id — will not adopt")
  }
}

function Invoke-InertProbeOwned {
  <#
    Ownership = create → capture ID (not name registration alone).
    Preflight name absence; label preg5.attempt; start by ID; never adopt arbitrary name match.
    Create TIMEOUT => CreateOutcomeUnknown (not skipped_never_owned).
  #>
  param(
    [Parameter(Mandatory = $true)] $ProbeLedger,
    [Parameter(Mandatory = $true)][string] $Name,
    [Parameter(Mandatory = $true)][string[]] $CreateArgs,
    [Parameter(Mandatory = $true)][string] $What,
    [Parameter(Mandatory = $true)][int] $TimeoutMs
  )
  if (-not $ProbeLedger.ContainsKey($Name)) {
    throw "REFUSE: probe without registration for $Name"
  }
  $e = $ProbeLedger[$Name]
  Assert-ProbeNameAbsent -Name $Name
  $e.CreateAttempted = $true
  try {
    $createOut = Invoke-PreG5DockerControl -DockerArgs $CreateArgs -What "$What create" -TimeoutMs $TimeoutMs
  } catch {
    $msg = $_.Exception.Message
    if ($msg -match '(?i)TIMEOUT:') {
      $e.CreateTimedOut = $true
      $e.CreateOutcomeUnknown = $true
      $e.TimedOut = $true
      $e.Notes = "TIMEOUT on create before OwnedId — outcome unknown; reconcile by label+image+name only; never adopt foreign"
      throw ("PROBE_CREATE_TIMEOUT_UNCERTAIN name=$Name")
    }
    $e.Notes = $msg
    throw
  }
  $ownedId = ([string]$createOut.StdOut).Trim()
  if ([string]::IsNullOrWhiteSpace($ownedId)) { throw "probe create returned empty id for $Name" }
  $e.OwnedId = $ownedId
  $facts = Get-ContainerOwnershipFacts -Id $ownedId
  if ($facts.Id -ne $ownedId) { throw "probe create id mismatch" }
  if ($facts.AttemptLabel -ne $e.AttemptLabel) {
    throw ("REFUSE: probe label mismatch want=$($e.AttemptLabel) got=$($facts.AttemptLabel) — not adopting")
  }
  if ($facts.Image -cne $e.ImageTag) {
    throw ("REFUSE: probe image mismatch want=$($e.ImageTag) got=$($facts.Image)")
  }
  $e.StartAttempted = $true
  try {
    Invoke-PreG5DockerControl -DockerArgs @("start", "-a", $ownedId) -What "$What start" -TimeoutMs $TimeoutMs | Out-Null
    $e.ClientOk = $true
  } catch {
    $msg = $_.Exception.Message
    if ($msg -match '(?i)TIMEOUT:') {
      $e.TimedOut = $true
      $e.Notes = "TIMEOUT on start -a for owned id=$ownedId; may still appear/run; cleanup must verify ownership"
    } else {
      $e.Notes = $msg
    }
    throw
  }
}

function Test-OwnedProbeFactsMatch {
  param($Entry, $Facts)
  if ($null -eq $Facts) { return $false }
  if ($Entry.OwnedId -and $Facts.Id -ne $Entry.OwnedId) { return $false }
  if ($Facts.AttemptLabel -ne $Entry.AttemptLabel) { return $false }
  if ($Facts.Image -cne $Entry.ImageTag) { return $false }
  if ($Facts.Name -ne $Entry.Name) { return $false }
  return $true
}

function Invoke-CleanupOwnedProbes {
  <#
    Never-attempted create => skip ok.
    CreateAttempted without OwnedId (create timeout/unknown) => CleanupUncertain; optional reconcile by label+image+name.
    OwnedId: presence via Resolve-ContainerPresenceByRef — only explicit Missing proves absence.
  #>
  param($ProbeLedger)
  $results = New-Object System.Collections.Generic.List[object]
  $fmt = '{{.Id}}|{{.Name}}|{{.Config.Image}}|{{index .Config.Labels "preg5.attempt"}}'
  foreach ($name in @($ProbeLedger.Keys)) {
    $e = $ProbeLedger[$name]
    $e.CleanupAttempted = $true
    $row = [ordered]@{ Name = $name; CleanupOk = $false; CleanupUncertain = $false; Notes = $null; ObservedId = $e.OwnedId }

    if (-not $e.CreateAttempted) {
      $row.CleanupOk = $true
      $row.Notes = "skipped_never_attempted"
      $e.CleanupOk = $true
      $e.CleanupNotes = $row.Notes
      $results.Add($row)
      continue
    }

    if (-not $e.OwnedId) {
      # Attempted create but no ID — do not treat as clean success.
      $row.CleanupUncertain = $true
      $e.CleanupUncertain = $true
      try {
        # Reconcile ONLY if exact name present AND label+image match — never adopt foreign.
        $pres = Resolve-ContainerPresenceByRef -Ref $name -Format $fmt
        if ($pres.Status -eq "Missing") {
          $row.Notes = "create outcome unknown and intended name Missing — still uncertain (daemon may late-create); review required"
        } else {
          $p = $pres.StdOut -split '\|', 4
          $facts = [ordered]@{ Id = $p[0]; Name = ($p[1] -replace '^/', ''); Image = $p[2]; AttemptLabel = $(if ($p.Count -ge 4) { $p[3] } else { "" }) }
          if (Test-OwnedProbeFactsMatch -Entry $e -Facts $facts) {
            $e.OwnedId = $facts.Id
            $row.ObservedId = $facts.Id
            $row.Notes = "late-reconciled owned id=$($facts.Id) after create timeout — will attempt rm"
            # fall through to rm via OwnedId path by re-entering logic inline
            Invoke-PreG5DockerControl -What "rm late probe $($e.OwnedId)" -DockerArgs @("rm", "-f", $e.OwnedId) | Out-Null
            $after = Resolve-ContainerPresenceByRef -Ref $e.OwnedId -Format "{{.Id}}"
            if ($after.Status -eq "Missing") {
              $row.CleanupOk = $true
              $row.CleanupUncertain = $false
              $e.CleanupOk = $true
              $e.CleanupUncertain = $false
              $row.Notes = "late-reconciled and removed $($e.OwnedId)"
            } else {
              $row.Notes = "late-reconciled rm but presence not explicitly Missing"
            }
          } else {
            $row.Notes = "intended name Present but label/image/name mismatch — NOT adopting foreign; uncertain"
          }
        }
      } catch {
        $row.Notes = "create outcome unknown; reconcile unresolved: $($_.Exception.Message)"
      }
      $e.CleanupNotes = $row.Notes
      if (-not $row.CleanupOk) { $e.CleanupOk = $false }
      $results.Add($row)
      continue
    }

    try {
      $pres = Resolve-ContainerPresenceByRef -Ref $e.OwnedId -Format $fmt
      if ($pres.Status -eq "Missing") {
        if ($e.TimedOut -or $e.CreateTimedOut -or $e.CreateOutcomeUnknown) {
          # Timeout means daemon work may still land — explicit Missing NOW is not final success.
          $row.CleanupUncertain = $true
          $row.Notes = "TIMEOUT and owned id explicitly Missing — absence not final; reconciliation required"
          $e.CleanupUncertain = $true
          $e.CleanupOk = $false
        } else {
          $row.CleanupOk = $true
          $row.Notes = "owned id explicitly Missing"
          $e.CleanupOk = $true
        }
        $e.CleanupNotes = $row.Notes
        $results.Add($row)
        continue
      }
      $p = $pres.StdOut -split '\|', 4
      $facts = [ordered]@{ Id = $p[0]; Name = ($p[1] -replace '^/', ''); Image = $p[2]; AttemptLabel = $(if ($p.Count -ge 4) { $p[3] } else { "" }) }
      if (-not (Test-OwnedProbeFactsMatch -Entry $e -Facts $facts)) {
        $row.Notes = "REFUSE cleanup: ownership facts mismatch — will not rm"
        $e.CleanupNotes = $row.Notes
        $results.Add($row)
        continue
      }
      try {
        Invoke-PreG5DockerControl -What "rm probe $($e.OwnedId)" -DockerArgs @("rm", "-f", $e.OwnedId) | Out-Null
      } catch {
        $row.Notes = "rm failed: $($_.Exception.Message)"
        $e.CleanupOk = $false
        $e.CleanupNotes = $row.Notes
        $results.Add($row)
        continue
      }
      try {
        $after = Resolve-ContainerPresenceByRef -Ref $e.OwnedId -Format "{{.Id}}"
        if ($after.Status -eq "Missing") {
          $row.CleanupOk = $true
          $row.Notes = "removed $($e.OwnedId)"
          $e.CleanupOk = $true
        } else {
          $row.Notes = "rm issued but owned id still Present"
        }
      } catch {
        $row.CleanupUncertain = $true
        $row.Notes = "rm issued; post-rm presence unresolved: $($_.Exception.Message)"
        $e.CleanupUncertain = $true
        $e.CleanupOk = $false
      }
      $e.CleanupNotes = $row.Notes
    } catch {
      # Daemon/access/unclassified on ownership inspect — NOT absence.
      $row.CleanupUncertain = $true
      $row.Notes = "cleanup presence unresolved: $($_.Exception.Message)"
      $e.CleanupUncertain = $true
      $e.CleanupOk = $false
      $e.CleanupNotes = $row.Notes
    }
    $results.Add($row)
  }
  $arr = New-Object object[] $results.Count
  if ($results.Count -gt 0) { $results.CopyTo($arr) }
  return ,$arr
}

function Assert-ProbesReadyForSuccess {
  <# All create-attempted probes must be CleanupOk and not CleanupUncertain before creation_ok. #>
  param($ProbeLedger)
  foreach ($name in @($ProbeLedger.Keys)) {
    $e = $ProbeLedger[$name]
    if (-not $e.CreateAttempted) { continue }
    if ($e.CleanupUncertain) {
      throw ("REFUSE success: probe cleanup uncertain name=$name id=$($e.OwnedId)")
    }
    if (-not $e.CleanupOk) {
      throw ("REFUSE success: probe cleanup not ok name=$name notes=$($e.CleanupNotes)")
    }
  }
  return $true
}

function Assert-ImportStampReusable {
  <#
    First-Import packet: any prior failure/quarantine UNCONDITIONALLY stops.
    No IMPORT_STAMP_RESOLUTION bypass. Future retry gets its own reviewed plan.
  #>
  param(
    [Parameter(Mandatory = $true)][string] $ScratchDir
  )
  $importReceipt = Join-Path $ScratchDir "import.receipt.json"
  if (Test-Path -LiteralPath $importReceipt) {
    throw "REFUSE: prior import.receipt.json exists (no overwrite)"
  }
  $failPath = Join-Path $ScratchDir "failure.receipt.json"
  $quarantine = Join-Path $ScratchDir "QUARANTINE_FAILED_ATTEMPT.txt"
  if (Test-Path -LiteralPath $failPath) {
    throw "REFUSE: prior failure.receipt.json exists — stamp reuse unconditionally blocked for this Import packet (no resolution bypass; will not overwrite)"
  }
  if (Test-Path -LiteralPath $quarantine) {
    throw "REFUSE: prior QUARANTINE_FAILED_ATTEMPT.txt exists — stamp reuse unconditionally blocked for this Import packet"
  }
  return $true
}

function Assert-ImportAttemptDirClear {
  <#
    Continuation/attempt evidence dir: refuse if success, failure, OR quarantine marker exists.
    Call BEFORE creating the dir for writing, BEFORE Docker mutations, and WITHOUT assigning
    a failure-writing AttemptDir — refusal must leave prior attempt evidence untouched.
  #>
  param(
    [Parameter(Mandatory = $true)][string] $AttemptDir
  )
  $markers = @(
    (Join-Path $AttemptDir "import.receipt.json"),
    (Join-Path $AttemptDir "failure.receipt.json"),
    (Join-Path $AttemptDir "QUARANTINE_FAILED_ATTEMPT.txt"),
    (Join-Path $AttemptDir "validation.receipt.json"),
    (Join-Path $AttemptDir "cleanup.receipt.json")
  )
  foreach ($m in $markers) {
    if (Test-Path -LiteralPath $m) {
      throw ("REFUSE: prior attempt evidence exists ($([IO.Path]::GetFileName($m))) — will not mutate attempt dir or overwrite")
    }
  }
  return $true
}

function Assert-ImageIdMatchesTag {
  <# Provenance: tag must resolve Present and Id must equal expected immutable id. #>
  param(
    [Parameter(Mandatory = $true)][string] $Tag,
    [Parameter(Mandatory = $true)][string] $ExpectedId
  )
  $pres = Resolve-DockerImagePresence -Ref $Tag
  if ($pres.Status -ne "Present") {
    throw "REFUSE: image tag Missing for provenance check: $Tag"
  }
  if ([string]$pres.Id -ne $ExpectedId) {
    throw ("REFUSE: tag-to-id mismatch tag=$Tag want=$ExpectedId got=$($pres.Id)")
  }
  return $true
}
