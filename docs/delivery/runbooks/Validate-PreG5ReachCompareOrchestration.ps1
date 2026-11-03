#Requires -Version 5.1
<#
  Orchestration tests for dual-net reach-compare (no live Docker).
  Dot-sourced by Validate-PreG5SnapshotFailurePaths.ps1.
#>
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "PreG5-SnapshotHelpers.ps1")
. (Join-Path $PSScriptRoot "PreG5-DisposableValidationLib.ps1")
. (Join-Path $PSScriptRoot "PreG5-ReachabilityDiagnosisLib.ps1")
. (Join-Path $PSScriptRoot "PreG5-ReachabilityCompareLib.ps1")
. (Join-Path $PSScriptRoot "Validate-PreG5DisposableOrchestration.ps1")
. (Join-Path $PSScriptRoot "Validate-PreG5ReachabilityOrchestration.ps1")

function Get-ReachCompareSetupRequiredBody {
  return '{"code":"SETUP_REQUIRED","detail":"Initial setup required"}'
}

function New-ReachCompareOrchestrationHarness {
  param(
    [Parameter(Mandatory = $true)] $BaseHarness,
    [string] $ExecApiMode = "ok401setup",
    [string] $ExecWebMode = "ok401setup",
    [string] $ExecRunMeshMode = "ok401setup",
    [bool] $PublishOk = $true,
    [bool] $PublishPortFail = $false
  )
  $state = $BaseHarness.State
  $inner = $BaseHarness.Runner
  $setupBody = Get-ReachCompareSetupRequiredBody

  $runner = {
    param([string[]]$DockerArgs, [string]$What, [int]$TimeoutMs)
    $cmd = $DockerArgs[0]
    $joined = ($DockerArgs -join ' ')

    if ($cmd -eq 'compose') {
      $isExec = $false
      $isRun = $false
      $svc = ""
      for ($i = 0; $i -lt $DockerArgs.Count; $i++) {
        if ($DockerArgs[$i] -eq 'exec') { $isExec = $true }
        if ($DockerArgs[$i] -eq 'run') { $isRun = $true }
        if ($DockerArgs[$i] -eq 'api' -or $DockerArgs[$i] -eq 'web') { $svc = $DockerArgs[$i] }
      }
      if (($isExec -or $isRun) -and ($joined -match 'python' -or $joined -match ' curl ')) {
        $mode = "ok401setup"
        if ($isRun) { $mode = $state.ExecRunMeshMode }
        elseif ($svc -eq 'web') { $mode = $state.ExecWebMode }
        elseif ($svc -eq 'api') { $mode = $state.ExecApiMode }
        if ($mode -eq 'missing') {
          return @{ Code = 127; StdOut = ""; StdErr = "python: not found"; TimedOut = $false }
        }
        if ($mode -eq 'transport') {
          return @{ Code = 2; StdOut = "TRANSPORT URLError connection refused"; StdErr = ""; TimedOut = $false }
        }
        if ($mode -eq 'wrongauth') {
          $body = '{"code":"UNAUTHENTICATED","detail":"Not authenticated"}'
        } else {
          $body = $setupBody
        }
        if ($joined -match ' curl ') {
          return @{ Code = 0; StdOut = ($body + "`nSTATUS 401`n"); StdErr = ""; TimedOut = $false }
        }
        return @{ Code = 0; StdOut = ("STATUS 401`n" + $body); StdErr = ""; TimedOut = $false }
      }
    }

    if ($cmd -eq 'port') {
      if ($state.PublishPortFail) {
        return @{ Code = 1; StdOut = ""; StdErr = "simulated docker port daemon failure"; TimedOut = $false }
      }
      if ($state.PublishOk) {
        return @{ Code = 0; StdOut = "127.0.0.1:18000"; StdErr = ""; TimedOut = $false }
      }
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }

    if ($cmd -eq 'inspect') {
      $fmt = ""
      for ($i = 0; $i -lt $DockerArgs.Count; $i++) {
        if ($DockerArgs[$i] -eq '--format' -and ($i + 1) -lt $DockerArgs.Count) { $fmt = $DockerArgs[$i + 1] }
      }
      if ($fmt -match 'PortBindings|NetworkSettings\.Ports') {
        if ($state.PublishOk) {
          $b = '{"8000/tcp":[{"HostIp":"127.0.0.1","HostPort":"18000"}]}'
          return @{ Code = 0; StdOut = $b; StdErr = ""; TimedOut = $false }
        }
        return @{ Code = 0; StdOut = "{}"; StdErr = ""; TimedOut = $false }
      }
    }

    return & $inner $DockerArgs $What $TimeoutMs
  }.GetNewClosure()

  $state.ExecApiMode = $ExecApiMode
  $state.ExecWebMode = $ExecWebMode
  $state.ExecRunMeshMode = $ExecRunMeshMode
  $state.PublishOk = $PublishOk
  $state.PublishPortFail = $PublishPortFail

  return @{ State = $state; Runner = $runner }
}

function New-ReachCompareHostProbeScriptBlocks {
  param([string] $HttpMode = "ok401setup", [string] $TcpMode = "ok")
  $setupBody = Get-ReachCompareSetupRequiredBody
  $http = {
    param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
    if ($HttpMode -eq 'transport') {
      return [ordered]@{
        classification = "transport_fail"; uri = $Uri; http_status = $null
        body = $null; transport_fail = $true; error = "Unable to connect to the remote server"
      }
    }
    if ($HttpMode -eq 'wrongauth') {
      return [ordered]@{
        classification = "http_body_mismatch"; uri = $Uri; http_status = 401
        body = '{"code":"UNAUTHENTICATED","detail":"Not authenticated"}'
        transport_fail = $false; error = "missing_body_marker"
      }
    }
    return [ordered]@{
      classification = "http_ok"; uri = $Uri; http_status = 401
      body = $setupBody; transport_fail = $false; error = $null
    }
  }.GetNewClosure()
  $tcp = {
    param($ComputerName, $Port, [int] $TimeoutMs = 15000)
    $ok = ($TcpMode -eq 'ok')
    return [ordered]@{
      classification = $(if ($ok) { "tcp_ok" } else { "tcp_fail" })
      computer = $ComputerName; port = $Port; tcp_ok = $ok
      raw = "TcpTestSucceeded : $ok timeoutMs=$TimeoutMs"
    }
  }.GetNewClosure()
  return @{ HostHttp = $http; HostTcp = $tcp }
}

function Invoke-ReachCompareOrchestrationTests {
  param([scriptblock] $AssertTrue)

  $api = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b"
  $web = "sha256:636901afe16e8ffda36601af75f029e2b076287a2c5ca868ecedd42029351969"
  $pg  = "sha256:93d55776e04376e19adb2733e3ccebb4392ee7dd86d8ff238503b30fe719c84f"
  $dualCompose = Get-PreG5ReachCompareDualNetComposeFile -RunbooksRoot $PSScriptRoot
  $dualFixture = Join-Path $PSScriptRoot "fixtures\preg5-disposable-compose-config.dual-net.v1.json"
  $scratchBase = Join-Path (Get-PreG5CustodyRoot) ("preg5-reach-cmp-orch-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $scratchBase -Force | Out-Null

  try {
    $setupExpect = Get-ReachabilityAuthMeExpectationSetupRequired
    $curlSetup = Convert-ReachabilityExecOutputToProbeResult -ProbeLabel 'cmp' -ServiceName 'api' -Url 'u' `
      -ExitCode 0 -StdOut ("STATUS 401`n" + (Get-ReachCompareSetupRequiredBody)) -ExpectStatus 401 `
      -BodyMustContain $setupExpect.BodyMustContain
    & $AssertTrue ($curlSetup.classification -eq 'http_ok') "SETUP_REQUIRED body classifies http_ok"

    $curlWrong = Convert-ReachabilityExecOutputToProbeResult -ProbeLabel 'cmp' -ServiceName 'api' -Url 'u' `
      -ExitCode 0 -StdOut "STATUS 401`n{""code"":""UNAUTHENTICATED""}" -ExpectStatus 401 `
      -BodyMustContain $setupExpect.BodyMustContain
    & $AssertTrue ($curlWrong.classification -eq 'http_body_mismatch') "UNAUTHENTICATED rejected when SETUP_REQUIRED expected"

    if (Test-Path -LiteralPath $dualFixture) {
      $fixtureRaw = Get-Content -LiteralPath $dualFixture -Raw
      Assert-DisposableComposeConfigStructuredDualNet -ConfigJson $fixtureRaw `
        -ExpectApiImage $api -ExpectWebImage $web -ExpectPostgresImage $pg | Out-Null
      & $AssertTrue $true "dual-net fixture passes structured config guard"
      $rendered = $fixtureRaw | ConvertFrom-Json
      $pubProps = @($rendered.networks.preg5_publish.PSObject.Properties | ForEach-Object { $_.Name })
      & $AssertTrue ($pubProps -notcontains 'internal') "rendered preg5_publish omits internal (harmless unset)"
      $bad = $fixtureRaw | ConvertFrom-Json
      $bad.services.postgres.networks | Add-Member -NotePropertyName 'preg5_publish' -NotePropertyValue $null -Force
      try {
        Assert-DisposableComposeConfigStructuredDualNet -ConfigJson ($bad | ConvertTo-Json -Depth 25) `
          -ExpectApiImage $api -ExpectWebImage $web -ExpectPostgresImage $pg | Out-Null
        & $AssertTrue $false "postgres on publish net should refuse"
      } catch {
        & $AssertTrue ($_.Exception.Message -match 'postgres network membership') "postgres publish membership refused"
      }

      $ext = $fixtureRaw | ConvertFrom-Json
      $ext.networks.preg5_publish | Add-Member -NotePropertyName 'external' -NotePropertyValue $true -Force
      try {
        Assert-DisposableComposeConfigStructuredDualNet -ConfigJson ($ext | ConvertTo-Json -Depth 30) `
          -ExpectApiImage $api -ExpectWebImage $web -ExpectPostgresImage $pg | Out-Null
        & $AssertTrue $false "external publish net should refuse"
      } catch {
        & $AssertTrue ($_.Exception.Message -match 'external=true forbidden') "external publish net refused"
      }

      $shared = $fixtureRaw | ConvertFrom-Json
      $shared.networks.preg5_publish.name = 'shared-unowned'
      try {
        Assert-DisposableComposeConfigStructuredDualNet -ConfigJson ($shared | ConvertTo-Json -Depth 30) `
          -ExpectApiImage $api -ExpectWebImage $web -ExpectPostgresImage $pg | Out-Null
        & $AssertTrue $false "shared-unowned publish name should refuse"
      } catch {
        & $AssertTrue ($_.Exception.Message -match 'project-owned') "shared publish name refused"
      }

      $pubInt = $fixtureRaw | ConvertFrom-Json
      $pubInt.networks.preg5_publish | Add-Member -NotePropertyName 'internal' -NotePropertyValue $true -Force
      try {
        Assert-DisposableComposeConfigStructuredDualNet -ConfigJson ($pubInt | ConvertTo-Json -Depth 30) `
          -ExpectApiImage $api -ExpectWebImage $web -ExpectPostgresImage $pg | Out-Null
        & $AssertTrue $false "internal publish net should refuse"
      } catch {
        & $AssertTrue ($_.Exception.Message -match 'preg5_publish must be non-internal') "explicit internal publish refused"
      }
    } else {
      & $AssertTrue $false "missing dual-net fixture"
    }

    $goneState = @{ Nets = "" }
    $dockerListRunner = {
      param([string[]]$DockerArgs, [string]$What, [int]$TimeoutMs)
      $cmd = $DockerArgs[0]
      if ($cmd -eq 'network' -and $DockerArgs.Count -ge 2 -and $DockerArgs[1] -eq 'ls') {
        return @{ Code = 0; StdOut = [string]$goneState.Nets; StdErr = ""; TimedOut = $false }
      }
      if ($cmd -eq 'volume' -and $DockerArgs.Count -ge 2 -and $DockerArgs[1] -eq 'ls') {
        return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
      }
      if ($cmd -eq 'ps') {
        return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
      }
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }.GetNewClosure()

    $script:PreG5DockerRunner = $dockerListRunner
    $ownedRev = Get-DisposableOwnedResources -ProjectName "revcmp" -DualNet
    & $AssertTrue ($ownedRev -is [System.Collections.Specialized.OrderedDictionary] -or $ownedRev -is [hashtable]) "DualNet owned capture is dictionary-shaped for cleanup handoff"

    $goneState.Nets = "revcmp_preg5_publish"
    try {
      Assert-DisposableResourcesGone -Owned $ownedRev -ProjectName "revcmp" | Out-Null
      & $AssertTrue $false "resources gone must fail when publish net remains"
    } catch {
      & $AssertTrue ($_.Exception.Message -match 'revcmp_preg5_publish') "publish net leftover detected via OrderedDictionary Owned"
    }

    $goneState.Nets = "revcmp_preg5_net"
    try {
      Assert-DisposableResourcesGone -Owned $ownedRev -ProjectName "revcmp" | Out-Null
      & $AssertTrue $false "resources gone must fail when internal net remains"
    } catch {
      & $AssertTrue ($_.Exception.Message -match 'revcmp_preg5_net') "internal net leftover detected"
    }

    $goneState.Nets = ""
    $goneOk = Assert-DisposableResourcesGone -Owned $ownedRev -ProjectName "revcmp"
    & $AssertTrue ($goneOk.Ok -eq $true) "both nets gone returns Ok for DualNet Owned handoff"
    $script:PreG5DockerRunner = $null

    try {
      Assert-ComposeProjectResourcesFresh -ProjectName "cmpdualpreflight" -DualNet `
        -NetworkLister { @("cmpdualpreflight_preg5_publish") } -VolumeLister { @() } | Out-Null
      & $AssertTrue $false "dual-net preflight should refuse publish net collision"
    } catch {
      & $AssertTrue ($_.Exception.Message -match 'preg5_publish') "dual-net preflight detects publish collision"
    }

    $hOwned = New-DisposableOrchestrationHarness -ProjectName "cmpowned" -ApiImage $api -WebImage $web -PgImage $pg -DualNet
    $script:PreG5DockerRunner = $hOwned.Runner
    $owned = Get-DisposableOwnedResources -ProjectName "cmpowned" -DualNet
    & $AssertTrue ($owned.Networks.Count -eq 2) "dual-net owned inventory lists both networks"
    & $AssertTrue ($owned.PublishNetwork -eq 'cmpowned_preg5_publish') "publish network name captured"
    $script:PreG5DockerRunner = $null

    $stamp = "20261102T055454Z-reachcmp"
    $proj = "theplanpreg5snapreachcmp1"
    $att = "disposable-042-reach-compare-1"
    $fx = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stamp `
      -AttemptId $att -ApiImage $api -WebImage $web
    $hBase = New-DisposableOrchestrationHarness -ProjectName $proj -ApiImage $api -WebImage $web -PgImage $pg -DualNet
    $hBase.State.ConfigFixturePath = $dualFixture
    $hCmp = New-ReachCompareOrchestrationHarness -BaseHarness $hBase -PublishOk $true
    $probes = New-ReachCompareHostProbeScriptBlocks -HttpMode ok401setup -TcpMode ok
    $script:PreG5DockerRunner = $hCmp.Runner
    $r = Invoke-PreG5Disposable042ReachCompareCore -ScratchRoot $scratchBase -ExportStamp $stamp `
      -AttemptId $att -ProjectName $proj -ComposeFile $dualCompose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fx.ApprovalPath `
      -ComposeTimeoutMs 8000 -PreflightHostPorts @() `
      -HostHttpProbe $probes.HostHttp -HostTcpProbe $probes.HostTcp
    & $AssertTrue ($r.ExitCode -eq 0) "dual-net SETUP_REQUIRED corridor exit 0"
    $rec = Get-Content (Join-Path $fx.AttemptDir "reach-diagnosis.receipt.json") -Raw | ConvertFrom-Json
    & $AssertTrue ($rec.auth_content_expectation -eq 'SETUP_REQUIRED') "receipt pins SETUP_REQUIRED expectation"
    & $AssertTrue ($rec.egress_disclosure.option -eq 'B') "receipt carries Option B egress disclosure"
    & $AssertTrue ($rec.egress_disclosure.attempt_id_binding -eq $att) "egress duration binds to LIVE AttemptId not sealed compare-1"
    & $AssertTrue ($rec.egress_disclosure.duration_bound -match [regex]::Escape($att)) "duration_bound names current attempt"
    & $AssertTrue ($rec.egress_disclosure.duration_bound -match 'not authority') "duration_bound supersedes prior attempt wording"
    & $AssertTrue ($rec.reachability_diagnosis_ok -eq $true) "compare diagnosis ok with host tcp/http ok"
    $ownedPre = Get-Content (Join-Path $fx.AttemptDir "owned-resources-before-cleanup.json") -Raw | ConvertFrom-Json
    & $AssertTrue ($ownedPre.Networks.Count -eq 2) "cleanup inventory captured both networks before down"
    & $AssertTrue (Test-Path (Join-Path $fx.AttemptDir "cleanup-outcome.final.json")) "compare cleanup final written"

    $stampPf = "20261102T055454Z-reachcmppf"
    $projPf = "theplanpreg5snapreachcmppf"
    $attPf = "disposable-042-reach-compare-pf"
    $fxPf = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampPf `
      -AttemptId $attPf -ApiImage $api -WebImage $web
    $hPfBase = New-DisposableOrchestrationHarness -ProjectName $projPf -ApiImage $api -WebImage $web -PgImage $pg -DualNet
    $hPfBase.State.ConfigFixturePath = $dualFixture
    $hPf = New-ReachCompareOrchestrationHarness -BaseHarness $hPfBase -PublishPortFail $true -PublishOk $false
    $script:PreG5DockerRunner = $hPf.Runner
    $rPf = Invoke-PreG5Disposable042ReachCompareCore -ScratchRoot $scratchBase -ExportStamp $stampPf `
      -AttemptId $attPf -ProjectName $projPf -ComposeFile $dualCompose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxPf.ApprovalPath `
      -ComposeTimeoutMs 8000 -PreflightHostPorts @() `
      -HostHttpProbe $probes.HostHttp -HostTcpProbe $probes.HostTcp
    & $AssertTrue ($rPf.ExitCode -ne 0) "publish instrumentation blocks compare diagnosis"
    $recPf = Get-Content (Join-Path $fxPf.AttemptDir "reach-diagnosis.receipt.json") -Raw | ConvertFrom-Json
    & $AssertTrue ($recPf.reachability_diagnosis_ok -eq $false) "port fail diagnosis not ok"
    $matrixPf = Get-Content (Join-Path $fxPf.AttemptDir "reach-probe-matrix-summary.json") -Raw | ConvertFrom-Json
    $bPf = @($matrixPf.matrix | Where-Object { $_.probe_id -eq 'L1-B' } | Select-Object -First 1)
    & $AssertTrue ($bPf -and $bPf.classification -eq 'publish_instrumentation') "L1-B publish_instrumentation on port fail"

    $stampW = "20261102T055454Z-reachcmpw"
    $projW = "theplanpreg5snapreachcmpw"
    $attW = "disposable-042-reach-compare-wrong"
    $fxW = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampW `
      -AttemptId $attW -ApiImage $api -WebImage $web
    $hWBase = New-DisposableOrchestrationHarness -ProjectName $projW -ApiImage $api -WebImage $web -PgImage $pg -DualNet
    $hWBase.State.ConfigFixturePath = $dualFixture
    $hW = New-ReachCompareOrchestrationHarness -BaseHarness $hWBase -ExecWebMode wrongauth
    $script:PreG5DockerRunner = $hW.Runner
    $rW = Invoke-PreG5Disposable042ReachCompareCore -ScratchRoot $scratchBase -ExportStamp $stampW `
      -AttemptId $attW -ProjectName $projW -ComposeFile $dualCompose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxW.ApprovalPath `
      -ComposeTimeoutMs 8000 -PreflightHostPorts @() `
      -HostHttpProbe $probes.HostHttp -HostTcpProbe $probes.HostTcp
    & $AssertTrue ($rW.ExitCode -ne 0) "wrong auth content fails compare matrix"
    $hRow = Get-Content (Join-Path $fxW.AttemptDir "reach-probes\L1-H-exec-web-to-api.txt") -Raw
    & $AssertTrue ($hRow -match 'http_body_mismatch|classification=http_body_mismatch') "web-to-api wrong code recorded"

  } finally {
    $script:PreG5DockerRunner = $null
    if (Test-Path -LiteralPath $scratchBase) {
      Remove-Item -LiteralPath $scratchBase -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
}
