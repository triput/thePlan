#Requires -Version 5.1
<#
  Injected-runner orchestration tests for disposable 042 reachability Core (no live Docker).
  Dot-sourced by Validate-PreG5SnapshotFailurePaths.ps1.
#>
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "PreG5-SnapshotHelpers.ps1")
. (Join-Path $PSScriptRoot "PreG5-DisposableValidationLib.ps1")
. (Join-Path $PSScriptRoot "PreG5-ReachabilityDiagnosisLib.ps1")
. (Join-Path $PSScriptRoot "Validate-PreG5DisposableOrchestration.ps1")

function New-ReachabilityOrchestrationHarness {
  param(
    [Parameter(Mandatory = $true)] $BaseHarness,
    [string] $ExecApiMode = "ok401",
    [string] $ExecWebMode = "ok401",
    [string] $ExecRunMeshMode = "ok401",
    [bool] $PublishOk = $true,
    [bool] $PublishPortFail = $false,
    [string] $ContextHost = "npipe://./pipe/docker_engine"
  )
  $state = $BaseHarness.State
  $state.ExecApiMode = $ExecApiMode
  $state.ExecWebMode = $ExecWebMode
  $state.ExecRunMeshMode = $ExecRunMeshMode
  $state.PublishOk = $PublishOk
  $state.PublishPortFail = $PublishPortFail
  $state.ContextHost = $ContextHost
  $inner = $BaseHarness.Runner

  $runner = {
    param([string[]]$DockerArgs, [string]$What, [int]$TimeoutMs)
    $cmd = $DockerArgs[0]
    $joined = ($DockerArgs -join ' ')

    if ($cmd -eq 'context') {
      if ($DockerArgs -contains 'show') {
        return @{ Code = 0; StdOut = "reach-test-context"; StdErr = ""; TimedOut = $false }
      }
      if ($joined -match 'inspect') {
        $json = (@{
            Name      = "reach-test-context"
            Endpoints = @{
              docker = @{ Host = $state.ContextHost }
            }
          } | ConvertTo-Json -Compress)
        return @{ Code = 0; StdOut = $json; StdErr = ""; TimedOut = $false }
      }
    }

    if ($cmd -eq 'version' -and $joined -match 'Server') {
      return @{ Code = 0; StdOut = "linux/24.0.0"; StdErr = ""; TimedOut = $false }
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
      if ($fmt -match 'PortBindings') {
        if ($state.PublishOk) {
          $b = '{"8000/tcp":[{"HostIp":"127.0.0.1","HostPort":"18000"}]}'
          return @{ Code = 0; StdOut = $b; StdErr = ""; TimedOut = $false }
        }
        return @{ Code = 0; StdOut = "{}"; StdErr = ""; TimedOut = $false }
      }
      if ($fmt -match 'NetworkSettings\.Ports') {
        if ($state.PublishOk) {
          $p = '{"8000/tcp":[{"HostIp":"127.0.0.1","HostPort":"18000"}]}'
          return @{ Code = 0; StdOut = $p; StdErr = ""; TimedOut = $false }
        }
        return @{ Code = 0; StdOut = "{}"; StdErr = ""; TimedOut = $false }
      }
    }

    if ($cmd -eq 'network' -and $joined -match 'inspect' -and $joined -match 'Internal') {
      return @{ Code = 0; StdOut = "true"; StdErr = ""; TimedOut = $false }
    }

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
        $mode = "ok401"
        if ($isRun) { $mode = $state.ExecRunMeshMode }
        elseif ($svc -eq 'web') { $mode = $state.ExecWebMode }
        elseif ($svc -eq 'api') { $mode = $state.ExecApiMode }
        if ($mode -eq 'missing') {
          return @{ Code = 127; StdOut = ""; StdErr = "python: not found"; TimedOut = $false }
        }
        if ($mode -eq 'transport') {
          return @{ Code = 2; StdOut = "TRANSPORT URLError connection refused"; StdErr = ""; TimedOut = $false }
        }
        $body = '{"code":"UNAUTHENTICATED","detail":"Not authenticated"}'
        if ($joined -match ' curl ') {
          return @{ Code = 0; StdOut = ($body + "`nSTATUS 401`n"); StdErr = ""; TimedOut = $false }
        }
        return @{ Code = 0; StdOut = ("STATUS 401`n" + $body); StdErr = ""; TimedOut = $false }
      }
    }

    return & $inner $DockerArgs $What $TimeoutMs
  }.GetNewClosure()

  return @{ State = $state; Runner = $runner }
}

function Start-ReachabilityLocalHttpFixture {
  <#
    Harmless loopback HTTP/1.1 responder for real PS5.1 Invoke-WebRequest exercises.
    Uses TcpListener (no HttpListener URLACL). One request then idle until stopped.
  #>
  param(
    [Parameter(Mandatory = $true)][int] $StatusCode,
    [AllowNull()][string] $Body,
    [string] $ReasonPhrase = "Unauthorized",
    [string] $ContentType = "application/json"
  )
  if ($null -eq $Body) { $Body = "" }
  $tcp = New-Object System.Net.Sockets.TcpListener ([System.Net.IPAddress]::Loopback, 0)
  $tcp.Start()
  $port = ([System.Net.IPEndPoint]$tcp.LocalEndpoint).Port
  $runspace = [runspacefactory]::CreateRunspace()
  $runspace.Open()
  $ps = [powershell]::Create()
  $ps.Runspace = $runspace
  [void]$ps.AddScript({
      param($tcpListener, $status, $reason, $bodyText, $contentType)
      try {
        $client = $tcpListener.AcceptTcpClient()
        $stream = $client.GetStream()
        $buf = New-Object byte[] 8192
        Start-Sleep -Milliseconds 50
        while ($stream.DataAvailable) { [void]$stream.Read($buf, 0, $buf.Length) }
        # Drain at least the request headers if DataAvailable was false on first tick.
        $stream.ReadTimeout = 2000
        try { [void]$stream.Read($buf, 0, $buf.Length) } catch { }
        $payload = [System.Text.Encoding]::UTF8.GetBytes($bodyText)
        $header = "HTTP/1.1 $status $reason`r`nContent-Type: $contentType`r`nContent-Length: $($payload.Length)`r`nConnection: close`r`n`r`n"
        $hb = [System.Text.Encoding]::ASCII.GetBytes($header)
        $stream.Write($hb, 0, $hb.Length)
        if ($payload.Length -gt 0) { $stream.Write($payload, 0, $payload.Length) }
        $stream.Flush()
        try { $client.Close() } catch { }
      } catch { }
    }).AddArgument($tcp).AddArgument($StatusCode).AddArgument($ReasonPhrase).AddArgument($Body).AddArgument($ContentType)
  $handle = $ps.BeginInvoke()
  return @{
    Port     = $port
    Tcp      = $tcp
    PS       = $ps
    Handle   = $handle
    Runspace = $runspace
    Uri      = ("http://127.0.0.1:{0}/api/v1/auth/me" -f $port)
  }
}

function Stop-ReachabilityLocalHttpFixture {
  param($Server)
  if ($null -eq $Server) { return }
  try { $Server.Tcp.Stop() } catch { }
  try { $null = $Server.PS.EndInvoke($Server.Handle) } catch { }
  try { $Server.PS.Dispose() } catch { }
  try { $Server.Runspace.Close(); $Server.Runspace.Dispose() } catch { }
}

function New-ReachabilityHostProbeScriptBlocks {
  param(
    [string] $HttpMode = "ok401",
    [string] $TcpMode = "ok"
  )
  $http = {
    param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
    if ($HttpMode -eq 'transport') {
      return [ordered]@{
        classification = "transport_fail"; uri = $Uri; http_status = $null
        body = $null; transport_fail = $true; error = "Unable to connect to the remote server"
      }
    }
    return [ordered]@{
      classification = "http_ok"; uri = $Uri; http_status = 401
      body = '{"code":"UNAUTHENTICATED","detail":"Not authenticated"}'
      transport_fail = $false; error = $null
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

function Invoke-ReachabilityOrchestrationTests {
  param([scriptblock] $AssertTrue)

  $api = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b"
  $web = "sha256:636901afe16e8ffda36601af75f029e2b076287a2c5ca868ecedd42029351969"
  $pg  = "sha256:93d55776e04376e19adb2733e3ccebb4392ee7dd86d8ff238503b30fe719c84f"
  $compose = Join-Path $PSScriptRoot "compose.pre-g5-snapshot-disposable.yaml"
  $scratchBase = Join-Path (Get-PreG5CustodyRoot) ("preg5-reach-orch-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $scratchBase -Force | Out-Null

  try {
    $comspec = $env:ComSpec
    if ([string]::IsNullOrWhiteSpace($comspec)) { $comspec = "cmd.exe" }
    $r127 = Invoke-WindowsProcessCapturedTimedAllowFail -FilePath $comspec -ArgumentList @('/c', 'exit 127') `
      -What 'harmless exit 127 fixture' -TimeoutMs 5000
    & $AssertTrue ($r127.Code -eq 127) "allow-fail preserves exit 127 from process wrapper"
    $p127 = Convert-ReachabilityExecOutputToProbeResult -ProbeLabel 'fixture' -ServiceName 'web' -Url 'http://api:8000/x' `
      -ExitCode $r127.Code -StdOut $r127.StdOut -StdErr 'python: not found' -ExpectStatus 401
    & $AssertTrue ($p127.classification -eq 'missing_tool') "exit 127 stderr classifies missing_tool"

    $r2 = Invoke-WindowsProcessCapturedTimedAllowFail -FilePath $comspec -ArgumentList @('/c', 'echo TRANSPORT URLError& exit 2') `
      -What 'harmless exit 2 transport fixture' -TimeoutMs 5000
    & $AssertTrue ($r2.Code -eq 2) "allow-fail preserves exit 2"
    $p2 = Convert-ReachabilityExecOutputToProbeResult -ProbeLabel 'fixture' -ServiceName 'api' -Url 'http://127.0.0.1:8000/x' `
      -ExitCode $r2.Code -StdOut $r2.StdOut -StdErr $r2.StdErr -ExpectStatus 401
    & $AssertTrue ($p2.classification -eq 'transport_fail') "exit 2 TRANSPORT classifies transport_fail"

    $bad = Convert-ReachabilityExecOutputToProbeResult -ProbeLabel 'fixture' -ServiceName 'api' -Url 'u' `
      -ExitCode 1 -StdOut "STATUS 401`nbody" -StdErr "" -ExpectStatus 401
    & $AssertTrue ($bad.classification -eq 'exec_fail_nonzero_with_status') "nonzero exit with STATUS not http_ok"

    $authBody = '{"code":"UNAUTHENTICATED","detail":"Not authenticated"}'
    $curl401Out = ($authBody + "`nSTATUS 401`n")
    $curl401 = Convert-ReachabilityExecOutputToProbeResult -ProbeLabel 'L1-H-web-exec' -ServiceName 'web' `
      -Url 'http://api:8000/api/v1/auth/me' -ExitCode 0 -StdOut $curl401Out -ExpectStatus 401 `
      -BodyMustContain @('"code":"UNAUTHENTICATED"', '"detail":"Not authenticated"') -StatusLinePosition Trailing
    & $AssertTrue ($curl401.classification -eq 'http_ok') "curl trailing STATUS 401 parses http_ok with UNAUTHENTICATED body"

    $curlBadBody = Convert-ReachabilityExecOutputToProbeResult -ProbeLabel 'curl' -ServiceName 'web' -Url 'u' `
      -ExitCode 0 -StdOut ("{""wrong"":true}`nSTATUS 401`n") -ExpectStatus 401 `
      -BodyMustContain @('"code":"UNAUTHENTICATED"') -StatusLinePosition Trailing
    & $AssertTrue ($curlBadBody.classification -eq 'http_body_mismatch') "curl trailing STATUS with wrong body is http_body_mismatch"

    $curlTransport = Convert-ReachabilityExecOutputToProbeResult -ProbeLabel 'curl' -ServiceName 'web' -Url 'u' `
      -ExitCode 7 -StdErr 'Failed to connect to api port 8000' -ExpectStatus 401 -StatusLinePosition Trailing
    & $AssertTrue ($curlTransport.classification -eq 'transport_fail') "curl connect failure classifies transport_fail"

    $optBRows = @(
      @{ probe_id = 'L1-B'; classification = 'publish_ok' }
      @{ probe_id = 'L1-F'; classification = 'http_ok' }
      @{ probe_id = 'L1-H-web'; classification = 'http_ok' }
      @{ probe_id = 'L1-I'; classification = 'tcp_fail' }
      @{ probe_id = 'L1-J'; classification = 'transport_fail' }
    )
    $vOptB = Get-ReachabilityDiagnosisVerdict -MatrixRows $optBRows -CollectionCompleted $true -CleanupOk $true `
      -LayerBWebToApiProven $true -CollectionPartial $false
    & $AssertTrue ($vOptB.interpretable_diagnosis_ok -eq $true) "verdict allows host tcp_fail/transport_fail with F/H/publish ok"

    $vHostInfra = Get-ReachabilityDiagnosisVerdict -MatrixRows @(
      @{ probe_id = 'L1-B'; classification = 'publish_ok' }
      @{ probe_id = 'L1-F'; classification = 'http_ok' }
      @{ probe_id = 'L1-H-web'; classification = 'http_ok' }
      @{ probe_id = 'L1-I'; classification = 'tcp_error' }
      @{ probe_id = 'L1-J'; classification = 'http_ok' }
    ) -CollectionCompleted $true -CleanupOk $true -LayerBWebToApiProven $true
    & $AssertTrue ($vHostInfra.interpretable_diagnosis_ok -eq $false) "tcp_error blocks diagnosis despite F/H ok"
    & $AssertTrue ($vHostInfra.host_instrumentation_probe_ids -contains 'L1-I') "tcp_error recorded as host instrumentation"

    $vMissingRow = Get-ReachabilityDiagnosisVerdict -MatrixRows @(
      @{ probe_id = 'L1-F'; classification = 'http_ok' }
      @{ probe_id = 'L1-H-web'; classification = 'http_ok' }
    ) -CollectionCompleted $true -CleanupOk $true -LayerBWebToApiProven $true
    & $AssertTrue ($vMissingRow.interpretable_diagnosis_ok -eq $false) "missing publish/host rows block diagnosis"
    & $AssertTrue ($vMissingRow.missing_mandatory_probe_ids.Count -ge 3) "missing mandatory ids surfaced"

    $vPartial = Get-ReachabilityDiagnosisVerdict -MatrixRows $optBRows -CollectionCompleted $false -CleanupOk $true `
      -LayerBWebToApiProven $true -CollectionPartial $true
    & $AssertTrue ($vPartial.probe_collection_completed -eq $false) "partial matrix does not claim collection completed"
    & $AssertTrue ($vPartial.interpretable_diagnosis_ok -eq $false) "partial matrix does not claim diagnosis ok"

    $script:PreG5DockerRunner = {
      param([string[]]$DockerArgs, [string]$What, [int]$TimeoutMs)
      if ($What -match 'reach exec') { throw ("FAIL: $What exited 127") }
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }
    $allow = Invoke-PreG5DockerControlAllowFail -DockerArgs @('compose', 'exec') -What 'reach exec probe python web' -TimeoutMs 5000
    & $AssertTrue ($allow.Code -eq 127) "AllowFail maps thrown exited 127 for diagnostic exec"
    $script:PreG5DockerRunner = $null

    # PS5.1 host HTTP: real Invoke-WebRequest against local fixtures (not stubs)
    try {
      $refuse = Get-ReachabilityHostHttpProbeResult -Uri "http://127.0.0.1:1/not-used" -ExpectStatus 401 `
        -ExpectJsonCode "SETUP_REQUIRED" -TimeoutSec 1
      & $AssertTrue ($refuse.classification -eq 'transport_fail') "host http classifies connection refuse as transport_fail"
      & $AssertTrue ($null -eq $refuse.http_status) "transport_fail keeps http_status null"
    } catch {
      & $AssertTrue $false "host http transport classification threw: $($_.Exception.Message)"
    }

    $fxCases = @(
      @{ Name = "compact401"; Status = 401; Body = '{"code":"SETUP_REQUIRED","detail":"Initial setup required"}'; ExpectClass = "http_ok"; ExpectCode = "SETUP_REQUIRED" },
      @{ Name = "spaced401"; Status = 401; Body = '{ "code": "SETUP_REQUIRED", "detail": "Initial setup required" }'; ExpectClass = "http_ok"; ExpectCode = "SETUP_REQUIRED" },
      @{ Name = "wrongCode"; Status = 401; Body = '{"code":"UNAUTHENTICATED","detail":"Not authenticated"}'; ExpectClass = "http_body_mismatch"; ExpectCode = "SETUP_REQUIRED" },
      @{ Name = "wrongStatus"; Status = 200; Body = '{"code":"SETUP_REQUIRED","detail":"Initial setup required"}'; ExpectClass = "http_status_mismatch"; ExpectCode = "SETUP_REQUIRED" },
      @{ Name = "malformed"; Status = 401; Body = 'not-json{'; ExpectClass = "http_body_mismatch"; ExpectCode = "SETUP_REQUIRED" },
      @{ Name = "emptyBody"; Status = 401; Body = ""; ExpectClass = "http_body_mismatch"; ExpectCode = "SETUP_REQUIRED" }
    )
    foreach ($fx in $fxCases) {
      $srv = $null
      try {
        $srv = Start-ReachabilityLocalHttpFixture -StatusCode ([int]$fx.Status) -Body ([string]$fx.Body)
        Start-Sleep -Milliseconds 150
        $got = Get-ReachabilityHostHttpProbeResult -Uri $srv.Uri -ExpectStatus 401 `
          -ExpectJsonCode $fx.ExpectCode -TimeoutSec 5
        & $AssertTrue ($got.classification -eq $fx.ExpectClass) ("fixture $($fx.Name) class want=$($fx.ExpectClass) got=$($got.classification) err=$($got.error)")
        if ($fx.ExpectClass -eq 'http_ok') {
          & $AssertTrue ($got.http_status -eq 401) ("fixture $($fx.Name) preserves status 401")
          & $AssertTrue ($got.body -eq $fx.Body) ("fixture $($fx.Name) preserves raw body")
          & $AssertTrue ($got.parsed_code -eq 'SETUP_REQUIRED') ("fixture $($fx.Name) parsed_code SETUP_REQUIRED")
          & $AssertTrue ($got.acquisition_ok -eq $true) ("fixture $($fx.Name) acquisition_ok")
        } elseif ($fx.ExpectClass -eq 'http_status_mismatch') {
          & $AssertTrue ($got.http_status -eq 200) ("fixture $($fx.Name) preserves wrong status")
          & $AssertTrue ($null -ne $got.body) ("fixture $($fx.Name) preserves body on status mismatch")
        } elseif ($fx.ExpectClass -eq 'http_body_mismatch') {
          & $AssertTrue ($got.http_status -eq 401) ("fixture $($fx.Name) preserves 401 on body mismatch")
          & $AssertTrue ($null -ne $got.body) ("fixture $($fx.Name) preserves body on content mismatch (not null)")
          & $AssertTrue ($got.acquisition_ok -eq $true) ("fixture $($fx.Name) content mismatch is not acquisition failure")
        }
      } finally {
        Stop-ReachabilityLocalHttpFixture -Server $srv
      }
    }

    # Shared Assert-HttpJsonExpectation: spaced JSON + ExpectJsonCode; refuse stays throw/transport
    $srvAssert = $null
    try {
      $srvAssert = Start-ReachabilityLocalHttpFixture -StatusCode 401 `
        -Body '{ "code": "UNAUTHENTICATED", "detail": "Not authenticated" }'
      Start-Sleep -Milliseconds 150
      $assertOk = Assert-HttpJsonExpectation -Uri $srvAssert.Uri -ExpectStatus 401 `
        -ExpectJsonCode "UNAUTHENTICATED" -TimeoutSec 5
      & $AssertTrue ($assertOk.Status -eq 401) "Assert-HttpJsonExpectation accepts spaced JSON via ExpectJsonCode"
      & $AssertTrue ($assertOk.ParsedCode -eq 'UNAUTHENTICATED') "Assert-HttpJsonExpectation returns ParsedCode"
    } finally {
      Stop-ReachabilityLocalHttpFixture -Server $srvAssert
    }
    $srvWrong = $null
    try {
      $srvWrong = Start-ReachabilityLocalHttpFixture -StatusCode 401 `
        -Body '{"code":"SETUP_REQUIRED","detail":"Initial setup required"}'
      Start-Sleep -Milliseconds 150
      $threw = $false
      try {
        Assert-HttpJsonExpectation -Uri $srvWrong.Uri -ExpectStatus 401 `
          -ExpectJsonCode "UNAUTHENTICATED" -TimeoutSec 5 | Out-Null
      } catch {
        $threw = $true
        & $AssertTrue ($_.Exception.Message -match 'JSON code want=') "Assert throws JSON code mismatch (not missing marker)"
        & $AssertTrue (-not (Test-DisposableHttpTransportNotReady -ErrorMessage $_.Exception.Message)) "JSON code mismatch is not transport-not-ready"
      }
      & $AssertTrue $threw "Assert-HttpJsonExpectation fail-closed on wrong JSON code"
    } finally {
      Stop-ReachabilityLocalHttpFixture -Server $srvWrong
    }

    # Option B corridor: F/H/publish ok, host transport fail — matrix completes, cleanup ok
    $stampB = "20261102T055454Z-reachoptb"
    $projB = "theplanpreg5snapreachoptb"
    $attB = "disp-reach-optb"
    $fxB = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampB `
      -AttemptId $attB -ApiImage $api -WebImage $web
    $hB = New-DisposableOrchestrationHarness -ProjectName $projB -ApiImage $api -WebImage $web -PgImage $pg
    $hB2 = New-ReachabilityOrchestrationHarness -BaseHarness $hB -PublishOk $true
    $probesB = New-ReachabilityHostProbeScriptBlocks -HttpMode transport -TcpMode fail
    $script:PreG5DockerRunner = $hB2.Runner
    $rB = Invoke-PreG5Disposable042ReachabilityDiagnosisCore -ScratchRoot $scratchBase -ExportStamp $stampB `
      -AttemptId $attB -ProjectName $projB -ComposeFile $compose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxB.ApprovalPath `
      -ComposeTimeoutMs 8000 -ProbeMatrixDeadlineMs 60000 -ComposeExecProbeTimeoutMs 5000 `
      -PreflightHostPorts @() -HostHttpProbe $probesB.HostHttp -HostTcpProbe $probesB.HostTcp `
      -NetstatProbe { param([int]$TimeoutMs = 0) return "simulated no listener timeoutMs=$TimeoutMs" }
    & $AssertTrue ($rB.ExitCode -eq 0) "reach Option-B corridor completes with host transport fail"
    $receiptB = Get-Content (Join-Path $fxB.AttemptDir "reach-diagnosis.receipt.json") -Raw | ConvertFrom-Json
    & $AssertTrue ($receiptB.reachability_diagnosis_ok -eq $true) "reach diagnosis ok despite host fail"
    & $AssertTrue ($receiptB.layer_b_web_to_api_proven -eq $true) "Option B corridor requires web-to-api proven"
    & $AssertTrue ($receiptB.option_b_note -match 'does NOT establish internal:true') "Option B wording preserved"
    & $AssertTrue (Test-Path (Join-Path $fxB.AttemptDir "cleanup-outcome.final.json")) "reach cleanup final written"
    $matrixB = Get-Content (Join-Path $fxB.AttemptDir "reach-probe-matrix-summary.json") -Raw | ConvertFrom-Json
    $jRow = @($matrixB.matrix | Where-Object { $_.probe_id -eq 'L1-J' } | Select-Object -First 1)
    & $AssertTrue ($jRow -and $jRow.classification -eq 'transport_fail') "L1-J recorded transport_fail"

    # Expected 401 on exec + host
    $stamp401 = "20261102T055454Z-reach401"
    $proj401 = "theplanpreg5snapreach401"
    $att401 = "disp-reach-401"
    $fx401 = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stamp401 `
      -AttemptId $att401 -ApiImage $api -WebImage $web
    $h401 = New-ReachabilityOrchestrationHarness -BaseHarness (New-DisposableOrchestrationHarness -ProjectName $proj401 -ApiImage $api -WebImage $web -PgImage $pg)
    $probesOk = New-ReachabilityHostProbeScriptBlocks -HttpMode ok401 -TcpMode ok
    $script:PreG5DockerRunner = $h401.Runner
    $r401 = Invoke-PreG5Disposable042ReachabilityDiagnosisCore -ScratchRoot $scratchBase -ExportStamp $stamp401 `
      -AttemptId $att401 -ProjectName $proj401 -ComposeFile $compose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fx401.ApprovalPath `
      -ComposeTimeoutMs 8000 -PreflightHostPorts @() -HostHttpProbe $probesOk.HostHttp -HostTcpProbe $probesOk.HostTcp
    & $AssertTrue ($r401.ExitCode -eq 0) "reach 401 corridor exit 0"
    $fTxt = Get-Content (Join-Path $fx401.AttemptDir "reach-probes\L1-F-exec-api-localhost.txt") -Raw
    & $AssertTrue ($fTxt -match 'STATUS 401|classification=http_ok') "L1-F exec captured 401"

    # Missing probe tool on web exec → mesh run fallback (not mesh fail)
    $stampM = "20261102T055454Z-reachmiss"
    $projM = "theplanpreg5snapreachmiss"
    $attM = "disp-reach-missing-tool"
    $fxM = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampM `
      -AttemptId $attM -ApiImage $api -WebImage $web
    $hBaseM = New-DisposableOrchestrationHarness -ProjectName $projM -ApiImage $api -WebImage $web -PgImage $pg
    $hM = New-ReachabilityOrchestrationHarness -BaseHarness $hBaseM -ExecWebMode missing -ExecRunMeshMode ok401
    $script:PreG5DockerRunner = $hM.Runner
    $rM = Invoke-PreG5Disposable042ReachabilityDiagnosisCore -ScratchRoot $scratchBase -ExportStamp $stampM `
      -AttemptId $attM -ProjectName $projM -ComposeFile $compose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxM.ApprovalPath `
      -ComposeTimeoutMs 8000 -PreflightHostPorts @() `
      -HostHttpProbe $probesOk.HostHttp -HostTcpProbe $probesOk.HostTcp
    & $AssertTrue ($rM.ExitCode -ne 0) "missing web tool leaves web-to-api unproven (diagnosis not ok)"
    $recM = Get-Content (Join-Path $fxM.AttemptDir "reach-diagnosis.receipt.json") -Raw | ConvertFrom-Json
    & $AssertTrue ($recM.layer_b_web_to_api_proven -eq $false) "fallback does not prove web-to-api"
    & $AssertTrue ($recM.probe_collection_completed -eq $true) "collection still completed"
    $hTxt = Get-Content (Join-Path $fxM.AttemptDir "reach-probes\L1-H-exec-web-to-api.txt") -Raw
    & $AssertTrue ($hTxt -match 'missing_tool') "web artifact records missing_tool only"
    & $AssertTrue (Test-Path (Join-Path $fxM.AttemptDir "reach-probes\L1-H-mesh-run-api-fallback.txt")) "fallback artifact separate"

    # Partial startup (postgres up fail) — refuse, no cleanup
    $stampP = "20261102T055454Z-reachpartial"
    $projP = "theplanpreg5snapreachpartial"
    $attP = "disp-reach-partial"
    $fxP = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampP `
      -AttemptId $attP -ApiImage $api -WebImage $web
    $hP = New-DisposableOrchestrationHarness -ProjectName $projP -ApiImage $api -WebImage $web -PgImage $pg
    $hP.State.FailUpPostgres = $true
    $script:PreG5DockerRunner = $hP.Runner
    $rP = Invoke-PreG5Disposable042ReachabilityDiagnosisCore -ScratchRoot $scratchBase -ExportStamp $stampP `
      -AttemptId $attP -ProjectName $projP -ComposeFile $compose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxP.ApprovalPath `
      -ComposeTimeoutMs 5000 -PreflightHostPorts @()
    & $AssertTrue ($rP.ExitCode -ne 0) "partial startup fails"
    & $AssertTrue ($rP.RefusalNoCleanup -eq $false) "partial startup owned path"
    & $AssertTrue (Test-Path (Join-Path $fxP.AttemptDir "cleanup-outcome.final.json")) "partial owned failure still cleans up"
    if (Test-Path (Join-Path $fxP.AttemptDir "reach-diagnosis.receipt.json")) {
      $recP = Get-Content (Join-Path $fxP.AttemptDir "reach-diagnosis.receipt.json") -Raw | ConvertFrom-Json
      & $AssertTrue ($recP.reachability_diagnosis_ok -eq $false) "partial startup diagnosis not ok"
    }

    # L1-F transport fail stops matrix but cleanup final exists
    $stampF = "20261102T055454Z-reachlfail"
    $projF = "theplanpreg5snapreachlfail"
    $attF = "disp-reach-l1f-fail"
    $fxF = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampF `
      -AttemptId $attF -ApiImage $api -WebImage $web
    $hF = New-ReachabilityOrchestrationHarness -BaseHarness (New-DisposableOrchestrationHarness -ProjectName $projF -ApiImage $api -WebImage $web -PgImage $pg) `
      -ExecApiMode transport
    $script:PreG5DockerRunner = $hF.Runner
    $rF = Invoke-PreG5Disposable042ReachabilityDiagnosisCore -ScratchRoot $scratchBase -ExportStamp $stampF `
      -AttemptId $attF -ProjectName $projF -ComposeFile $compose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxF.ApprovalPath `
      -ComposeTimeoutMs 8000 -PreflightHostPorts @()
    & $AssertTrue ($rF.ExitCode -ne 0) "L1-F transport fail nonzero exit"
    & $AssertTrue (Test-Path (Join-Path $fxF.AttemptDir "cleanup-outcome.final.json")) "L1-F fail still writes cleanup final"
    $portsJson = Get-Content (Join-Path $fxF.AttemptDir "reach-probes\L1-D-networksettings-ports.json") -Raw
    & $AssertTrue ($portsJson -match '8000/tcp') "NetworkSettings.Ports uses 8000/tcp key"

    # Publish inspect HostPort=18000 under 8000/tcp
    $stampPub = "20261102T055454Z-reachpub"
    $projPub = "theplanpreg5snapreachpub"
    $attPub = "disp-reach-publish"
    $fxPub = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampPub `
      -AttemptId $attPub -ApiImage $api -WebImage $web
    $hPub = New-ReachabilityOrchestrationHarness -BaseHarness (New-DisposableOrchestrationHarness -ProjectName $projPub -ApiImage $api -WebImage $web -PgImage $pg)
    $script:PreG5DockerRunner = $hPub.Runner
    $null = Invoke-PreG5Disposable042ReachabilityDiagnosisCore -ScratchRoot $scratchBase -ExportStamp $stampPub `
      -AttemptId $attPub -ProjectName $projPub -ComposeFile $compose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxPub.ApprovalPath `
      -ComposeTimeoutMs 8000 -PreflightHostPorts @() `
      -HostHttpProbe $probesOk.HostHttp -HostTcpProbe $probesOk.HostTcp
    $portsJsonFile = Join-Path $fxPub.AttemptDir "reach-probes\L1-D-networksettings-ports.json"
    & $AssertTrue (Test-Path -LiteralPath $portsJsonFile) "L1-D artifact present"
    $portsParsed = Get-Content -LiteralPath $portsJsonFile -Raw | ConvertFrom-Json
    $pn = @($portsParsed.PSObject.Properties | ForEach-Object { $_.Name })
    & $AssertTrue ($pn -contains '8000/tcp') "L1-D uses 8000/tcp key not 18000/tcp"
    & $AssertTrue ($portsParsed.'8000/tcp'[0].HostPort -eq '18000') "L1-D HostPort is 18000"

    $stampPf = "20261102T055454Z-reachportfail"
    $projPf = "theplanpreg5snapreachportfail"
    $attPf = "disp-reach-port-fail"
    $fxPf = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampPf `
      -AttemptId $attPf -ApiImage $api -WebImage $web
    $hPf = New-ReachabilityOrchestrationHarness -BaseHarness (New-DisposableOrchestrationHarness -ProjectName $projPf -ApiImage $api -WebImage $web -PgImage $pg) `
      -PublishPortFail $true -PublishOk $false
    $script:PreG5DockerRunner = $hPf.Runner
    $rPf = Invoke-PreG5Disposable042ReachabilityDiagnosisCore -ScratchRoot $scratchBase -ExportStamp $stampPf `
      -AttemptId $attPf -ProjectName $projPf -ComposeFile $compose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxPf.ApprovalPath `
      -ComposeTimeoutMs 8000 -PreflightHostPorts @() `
      -HostHttpProbe $probesOk.HostHttp -HostTcpProbe $probesOk.HostTcp
    & $AssertTrue ($rPf.ExitCode -ne 0) "nonzero docker port without binding evidence fails diagnosis"
    $recPf = Get-Content (Join-Path $fxPf.AttemptDir "reach-diagnosis.receipt.json") -Raw | ConvertFrom-Json
    & $AssertTrue ($recPf.reachability_diagnosis_ok -eq $false) "port instrumentation blocks diagnosis"
    $matrixPf = Get-Content (Join-Path $fxPf.AttemptDir "reach-probe-matrix-summary.json") -Raw | ConvertFrom-Json
    $bPf = @($matrixPf.matrix | Where-Object { $_.probe_id -eq 'L1-B' } | Select-Object -First 1)
    & $AssertTrue ($bPf -and $bPf.classification -eq 'publish_instrumentation') "L1-B publish_instrumentation not publish_missing on port fail"

    $hPfRec = New-ReachabilityOrchestrationHarness -BaseHarness (New-DisposableOrchestrationHarness -ProjectName ($projPf + "r") -ApiImage $api -WebImage $web -PgImage $pg) `
      -PublishPortFail $true -PublishOk $true
    $stampPfr = "20261102T055454Z-reachportrec"
    $attPfr = "disp-reach-port-recover"
    $fxPfr = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampPfr `
      -AttemptId $attPfr -ApiImage $api -WebImage $web
    $script:PreG5DockerRunner = $hPfRec.Runner
    $null = Invoke-PreG5Disposable042ReachabilityDiagnosisCore -ScratchRoot $scratchBase -ExportStamp $stampPfr `
      -AttemptId $attPfr -ProjectName ($projPf + "r") -ComposeFile $compose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxPfr.ApprovalPath `
      -ComposeTimeoutMs 8000 -PreflightHostPorts @() `
      -HostHttpProbe $probesOk.HostHttp -HostTcpProbe $probesOk.HostTcp
    $matrixPfr = Get-Content (Join-Path $fxPfr.AttemptDir "reach-probe-matrix-summary.json") -Raw | ConvertFrom-Json
    $bPfr = @($matrixPfr.matrix | Where-Object { $_.probe_id -eq 'L1-B' } | Select-Object -First 1)
    & $AssertTrue ($bPfr -and $bPfr.classification -eq 'publish_ok') "port fail recovered from NetworkSettings inspect"

    # Matrix deadline before probes → partial row + cleanup, diagnosis not ok
    $stampDl = "20261102T055454Z-reachdead"
    $projDl = "theplanpreg5snapreachdead"
    $attDl = "disp-reach-deadline"
    $fxDl = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampDl `
      -AttemptId $attDl -ApiImage $api -WebImage $web
    $hDl = New-ReachabilityOrchestrationHarness -BaseHarness (New-DisposableOrchestrationHarness -ProjectName $projDl -ApiImage $api -WebImage $web -PgImage $pg)
    $script:PreG5DockerRunner = $hDl.Runner
    $rDl = Invoke-PreG5Disposable042ReachabilityDiagnosisCore -ScratchRoot $scratchBase -ExportStamp $stampDl `
      -AttemptId $attDl -ProjectName $projDl -ComposeFile $compose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxDl.ApprovalPath `
      -ComposeTimeoutMs 8000 -PreflightHostPorts @() -OrchestrationForceMatrixDeadlineBeforeProbes `
      -HostHttpProbe $probesOk.HostHttp -HostTcpProbe $probesOk.HostTcp
    & $AssertTrue ($rDl.ExitCode -ne 0) "matrix deadline path nonzero exit"
    & $AssertTrue (Test-Path (Join-Path $fxDl.AttemptDir "cleanup-outcome.final.json")) "deadline path still cleans up"
    & $AssertTrue (Test-Path (Join-Path $fxDl.AttemptDir "reach-probe-matrix-summary.json")) "deadline path writes partial matrix summary"
    $recDl = Get-Content (Join-Path $fxDl.AttemptDir "reach-diagnosis.receipt.json") -Raw | ConvertFrom-Json
    & $AssertTrue ($recDl.reachability_diagnosis_ok -eq $false) "deadline path diagnosis not ok"
    & $AssertTrue ($recDl.probe_collection_completed -eq $false) "deadline partial does not claim collection completed"

    $tcpInfra = New-ReachabilityHostProbeScriptBlocks -HttpMode ok401 -TcpMode ok
    $tcpInfra.HostTcp = {
      param($ComputerName, $Port, [int] $TimeoutMs = 15000)
      return [ordered]@{
        classification = "tcp_error"; computer = $ComputerName; port = $Port; tcp_ok = $false
        raw = "simulated host tcp probe infrastructure failure"; error = "tcp_error"
      }
    }.GetNewClosure()
    $stampTi = "20261102T055454Z-reachtcpinf"
    $projTi = "theplanpreg5snapreachtcpinf"
    $attTi = "disp-reach-tcp-infra"
    $fxTi = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampTi `
      -AttemptId $attTi -ApiImage $api -WebImage $web
    $hTi = New-ReachabilityOrchestrationHarness -BaseHarness (New-DisposableOrchestrationHarness -ProjectName $projTi -ApiImage $api -WebImage $web -PgImage $pg)
    $script:PreG5DockerRunner = $hTi.Runner
    $rTi = Invoke-PreG5Disposable042ReachabilityDiagnosisCore -ScratchRoot $scratchBase -ExportStamp $stampTi `
      -AttemptId $attTi -ProjectName $projTi -ComposeFile $compose `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxTi.ApprovalPath `
      -ComposeTimeoutMs 8000 -PreflightHostPorts @() -HostHttpProbe $tcpInfra.HostHttp -HostTcpProbe $tcpInfra.HostTcp
    & $AssertTrue ($rTi.ExitCode -ne 0) "host tcp instrumentation failure nonzero exit"
    $recTi = Get-Content (Join-Path $fxTi.AttemptDir "reach-diagnosis.receipt.json") -Raw | ConvertFrom-Json
    & $AssertTrue ($recTi.reachability_diagnosis_ok -eq $false) "tcp_error path diagnosis not ok"
    & $AssertTrue ($recTi.probe_collection_completed -eq $true) "full matrix still completed before tcp_error row"

  } finally {
    $script:PreG5DockerRunner = $null
    if (Test-Path -LiteralPath $scratchBase) {
      Remove-Item -LiteralPath $scratchBase -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
}
