#Requires -Version 5.1
<# Shared disposable-042 reachability diagnosis (sourced by runner + orchestration tests). #>
Set-StrictMode -Version Latest

function Get-DockerControlResultCode {
  param([AllowNull()] $Result)
  if ($null -eq $Result) { return 0 }
  if ($Result -is [hashtable] -and $Result.ContainsKey('Code')) { return [int]$Result.Code }
  if ($Result.PSObject.Properties['Code']) { return [int]$Result.Code }
  return 0
}

function Get-ProbeResultClassification {
  param([AllowNull()] $Result)
  if ($null -eq $Result) { return "" }
  if ($Result -is [string]) { return [string]$Result }
  if ($Result -is [System.Collections.IDictionary]) {
    if ($Result.Contains('classification')) { return [string]$Result['classification'] }
  }
  if ($Result -is [hashtable] -and $Result.ContainsKey('classification')) { return [string]$Result.classification }
  if ($Result.PSObject.Properties['classification']) { return [string]$Result.classification }
  return ""
}

function Get-ReachabilityRemainingMatrixMilliseconds {
  param([Parameter(Mandatory = $true)][datetime] $MatrixDeadlineUtc)
  $rem = ($MatrixDeadlineUtc - [datetime]::UtcNow).TotalMilliseconds
  if ($rem -lt 1) { return 0 }
  return [int][Math]::Min([int]$rem, 2147483647)
}

function Get-ReachabilityClampedProbeTimeoutMs {
  param(
    [Parameter(Mandatory = $true)][datetime] $MatrixDeadlineUtc,
    [Parameter(Mandatory = $true)][int] $RequestedMs,
    [int] $MinimumMs = 500
  )
  $remaining = Get-ReachabilityRemainingMatrixMilliseconds -MatrixDeadlineUtc $MatrixDeadlineUtc
  if ($remaining -le 0) { return 0 }
  $want = $RequestedMs
  if ($want -le 0) { $want = $remaining }
  if ($want -gt $remaining) { $want = $remaining }
  if ($want -lt $MinimumMs -and $remaining -ge $MinimumMs) { $want = $MinimumMs }
  if ($want -gt $remaining) { $want = $remaining }
  return [int]$want
}

function Test-ReachabilityMatrixRowInterpretablePass {
  param([Parameter(Mandatory = $true)][string] $Classification)
  switch ($Classification) {
    'http_ok' { return $true }
    'tcp_ok' { return $true }
    'tcp_fail' { return $true }
    'transport_fail' { return $true }
    'publish_ok' { return $true }
    'publish_missing' { return $true }
    'publish_instrumentation' { return $true }
    'http_status_mismatch' { return $true }
    'http_body_mismatch' { return $true }
    'http_error' { return $true }
    'tcp_error' { return $true }
    'tcp_timeout' { return $true }
    'netstat_timeout' { return $true }
    'matrix_deadline' { return $true }
    default { return $false }
  }
}

function Test-ReachabilityPublishObservationValid {
  param([Parameter(Mandatory = $true)][string] $Classification)
  return ($Classification -in @('publish_ok', 'publish_missing'))
}

function Test-ReachabilityPublishProbeInstrumentationFailure {
  param([Parameter(Mandatory = $true)][string] $Classification)
  return ($Classification -in @('publish_instrumentation', 'matrix_deadline'))
}

function Test-ReachabilityHostTcpObservationValid {
  param([Parameter(Mandatory = $true)][string] $Classification)
  return ($Classification -in @('tcp_ok', 'tcp_fail'))
}

function Test-ReachabilityHostHttpObservationValid {
  param([Parameter(Mandatory = $true)][string] $Classification)
  return ($Classification -in @('http_ok', 'transport_fail', 'http_status_mismatch', 'http_body_mismatch'))
}

function Test-ReachabilityHostProbeInstrumentationFailure {
  param(
    [Parameter(Mandatory = $true)][string] $ProbeId,
    [Parameter(Mandatory = $true)][string] $Classification
  )
  switch ($ProbeId) {
    'L1-I' {
      return ($Classification -in @('tcp_error', 'tcp_timeout', 'matrix_deadline', 'exec_fail', 'exec_unparsed'))
    }
    'L1-J' {
      return ($Classification -in @('http_error', 'matrix_deadline', 'exec_fail', 'exec_unparsed'))
    }
    default { return $false }
  }
}

function Get-ReachabilityDiagnosisVerdict {
  param(
    [Parameter(Mandatory = $true)] $MatrixRows,
    [bool] $CollectionCompleted,
    [bool] $CleanupOk,
    [bool] $LayerBWebToApiProven,
    [bool] $CollectionPartial = $false
  )
  $rows = @($MatrixRows)
  $mandatory = @('L1-B', 'L1-F', 'L1-H-web', 'L1-I', 'L1-J')
  $missingMandatory = @()
  $invalidPublishHost = @()
  $hostInstrumentation = @()

  foreach ($mandProbeId in $mandatory) {
    $row = @($rows | Where-Object { $_.probe_id -eq $mandProbeId } | Select-Object -First 1)
    if (-not $row) {
      $missingMandatory += $mandProbeId
      continue
    }
    $cls = [string]$row.classification
    switch ($mandProbeId) {
      'L1-B' {
        if (Test-ReachabilityPublishProbeInstrumentationFailure -Classification $cls) {
          $hostInstrumentation += $mandProbeId
        } elseif (-not (Test-ReachabilityPublishObservationValid -Classification $cls)) {
          $invalidPublishHost += $mandProbeId
        }
      }
      'L1-I' {
        if (Test-ReachabilityHostProbeInstrumentationFailure -ProbeId $mandProbeId -Classification $cls) {
          $hostInstrumentation += $mandProbeId
        } elseif (-not (Test-ReachabilityHostTcpObservationValid -Classification $cls)) {
          $invalidPublishHost += $mandProbeId
        }
      }
      'L1-J' {
        if (Test-ReachabilityHostProbeInstrumentationFailure -ProbeId $mandProbeId -Classification $cls) {
          $hostInstrumentation += $mandProbeId
        } elseif (-not (Test-ReachabilityHostHttpObservationValid -Classification $cls)) {
          $invalidPublishHost += $mandProbeId
        }
      }
    }
  }

  $fRow = @($rows | Where-Object { $_.probe_id -eq 'L1-F' } | Select-Object -First 1)
  $fCls = ""
  if ($fRow) { $fCls = [string]$fRow.classification }

  $blockingExec = @($rows | Where-Object {
      $_.probe_id -in @('L1-F', 'L1-H-web', 'L1-H') -and
      $_.classification -in @('exec_fail', 'exec_unparsed', 'exec_fail_nonzero_with_status', 'missing_tool', 'matrix_deadline')
    })

  $collectionOk = ($CollectionCompleted -and -not $CollectionPartial)
  $interpretable = ($collectionOk -and $CleanupOk -and ($fCls -eq 'http_ok') -and ($blockingExec.Count -eq 0) `
    -and ($missingMandatory.Count -eq 0) -and ($invalidPublishHost.Count -eq 0) -and ($hostInstrumentation.Count -eq 0))
  if (-not $LayerBWebToApiProven) {
    $interpretable = $false
  }

  $blockingAll = @($blockingExec | ForEach-Object { [string]$_.probe_id }) + $missingMandatory + $invalidPublishHost + $hostInstrumentation | Select-Object -Unique

  return [ordered]@{
    probe_collection_completed   = [bool]$collectionOk
    interpretable_diagnosis_ok   = [bool]$interpretable
    reachability_diagnosis_ok    = [bool]$interpretable
    layer_b_web_to_api_proven    = [bool]$LayerBWebToApiProven
    layer_a_in_container_ok      = ($fCls -eq 'http_ok')
    blocking_probe_ids           = @($blockingAll)
    missing_mandatory_probe_ids  = @($missingMandatory)
    host_instrumentation_probe_ids = @($hostInstrumentation)
  }
}

function Assert-ReachabilityAttemptDirClear {
  param([Parameter(Mandatory = $true)][string] $AttemptDir)
  Assert-DisposableAttemptDirClear -AttemptDir $AttemptDir | Out-Null
  $markers = @(
    "reach-diagnosis.receipt.json",
    "reach-probe-matrix-summary.json"
  )
  foreach ($name in $markers) {
    $m = Join-Path $AttemptDir $name
    if (Test-Path -LiteralPath $m) {
      throw ("REFUSE: prior reachability attempt evidence exists ($name) — will not mutate")
    }
  }
  return $true
}

function Get-ReachabilityAuthMeExpectation {
  return @{
    Uri              = "http://127.0.0.1:18000/api/v1/auth/me"
    ExpectStatus     = 401
    BodyMustContain  = @('"code":"UNAUTHENTICATED"', '"detail":"Not authenticated"')
    AuthContentCode  = "UNAUTHENTICATED"
    InContainerPath  = "/api/v1/auth/me"
    ServiceMeshUrl   = "http://api:8000/api/v1/auth/me"
    ApiLocalhostUrl  = "http://127.0.0.1:8000/api/v1/auth/me"
  }
}

function Get-ReachabilityAuthMeExpectationSetupRequired {
  <# Fresh disposable DB (SEED_DEMO_USER=false, no bootstrap) — pinned API image behavior. #>
  return @{
    Uri              = "http://127.0.0.1:18000/api/v1/auth/me"
    ExpectStatus     = 401
    BodyMustContain  = @('"code":"SETUP_REQUIRED"', 'Initial setup required')
    AuthContentCode  = "SETUP_REQUIRED"
    InContainerPath  = "/api/v1/auth/me"
    ServiceMeshUrl   = "http://api:8000/api/v1/auth/me"
    ApiLocalhostUrl  = "http://127.0.0.1:8000/api/v1/auth/me"
  }
}

function Get-PreG5DockerEngineContextCapture {
  $ctxShow = ""
  $ctxInspectHost = ""
  $ctxInspectRaw = ""
  $notes = New-Object System.Collections.Generic.List[string]
  $showR = Invoke-PreG5DockerControlAllowFail -What "context show" -DockerArgs @("context", "show")
  if ($showR.Code -eq 0) { $ctxShow = [string]$showR.StdOut.Trim() }
  else { $notes.Add("context_show:code=$($showR.Code):$($showR.StdErr)") }

  $inspR = Invoke-PreG5DockerControlAllowFail -What "context inspect" -DockerArgs @(
    "context", "inspect", "--format", "{{json .}}"
  )
  if ($inspR.Code -eq 0) {
    $ctxInspectRaw = [string]$inspR.StdOut.Trim()
    try {
      $obj = $ctxInspectRaw | ConvertFrom-Json
      $names = @($obj.PSObject.Properties | ForEach-Object { $_.Name })
      if ($names -contains 'Endpoints') {
        $ep = $obj.Endpoints
        $epNames = @($ep.PSObject.Properties | ForEach-Object { $_.Name })
        foreach ($en in $epNames) {
          $node = $ep.$en
          if ($null -eq $node) { continue }
          $nn = @($node.PSObject.Properties | ForEach-Object { $_.Name })
          if ($nn -contains 'Host') {
            $h = [string]$node.Host
            if (-not [string]::IsNullOrWhiteSpace($h)) {
              $ctxInspectHost = $h
              break
            }
          }
        }
      }
    } catch {
      $notes.Add("context_inspect_parse:$($_.Exception.Message)")
    }
  } else {
    $notes.Add("context_inspect:code=$($inspR.Code):$($inspR.StdErr)")
  }

  $dockerHost = [Environment]::GetEnvironmentVariable("DOCKER_HOST", 'Process')
  if ([string]::IsNullOrWhiteSpace($dockerHost)) {
    $dockerHost = [Environment]::GetEnvironmentVariable("DOCKER_HOST", 'User')
  }
  if ([string]::IsNullOrWhiteSpace($dockerHost)) {
    $dockerHost = [Environment]::GetEnvironmentVariable("DOCKER_HOST", 'Machine')
  }
  $dockerContext = [Environment]::GetEnvironmentVariable("DOCKER_CONTEXT", 'Process')
  if ([string]::IsNullOrWhiteSpace($dockerContext)) {
    $dockerContext = [Environment]::GetEnvironmentVariable("DOCKER_CONTEXT", 'User')
  }
  if ([string]::IsNullOrWhiteSpace($dockerContext)) {
    $dockerContext = [Environment]::GetEnvironmentVariable("DOCKER_CONTEXT", 'Machine')
  }

  return [ordered]@{
    context_show            = $ctxShow
    context_inspect_host    = $ctxInspectHost
    context_inspect_json    = $ctxInspectRaw
    docker_host             = $(if ($dockerHost) { $dockerHost } else { $null })
    docker_context_env      = $(if ($dockerContext) { $dockerContext } else { $null })
    capture_notes           = @($notes)
    captured_utc            = (Get-Date).ToUniversalTime().ToString("o")
  }
}

function Save-ReachabilityProbeArtifact {
  param(
    [Parameter(Mandatory = $true)][string] $ProbeDir,
    [Parameter(Mandatory = $true)][string] $FileName,
    [AllowNull()][string] $Text
  )
  if (-not (Test-Path -LiteralPath $ProbeDir)) {
    New-Item -ItemType Directory -Path $ProbeDir | Out-Null
  }
  $path = Join-Path $ProbeDir $FileName
  Set-Content -LiteralPath $path -Value $(if ($null -eq $Text) { "" } else { $Text }) -Encoding utf8
  return $path
}

function Test-ReachabilityExecMissingTool {
  param(
    [Parameter(Mandatory = $true)][int] $ExitCode,
    [AllowNull()][string] $StdOut,
    [AllowNull()][string] $StdErr
  )
  $blob = (($StdOut + "`n" + $StdErr).ToLowerInvariant())
  if ($ExitCode -eq 127) { return $true }
  if ($blob -match 'not found|no such file|command not found|executable file not found') { return $true }
  return $false
}

function New-ReachabilityPythonUrllibProbeCommand {
  param([Parameter(Mandatory = $true)][string] $Url)
  $escaped = $Url.Replace('\', '\\').Replace('"', '\"')
  $code = "import urllib.request,urllib.error,sys; url=""$escaped"";" +
    "exec(""try:\n r=urllib.request.urlopen(url, timeout=15)\n print('STATUS', r.status)\n sys.stdout.write(r.read().decode())\nexcept urllib.error.HTTPError as e:\n print('STATUS', e.code)\n sys.stdout.write(e.read().decode())\nexcept Exception as e:\n print('TRANSPORT', type(e).__name__, str(e)); sys.exit(2)"")"
  return @("python", "-c", $code)
}

function New-ReachabilityCurlHttpProbeCommand {
  param([Parameter(Mandatory = $true)][string] $Url)
  # Alpine web image: curl present, python absent — bounded --max-time; no -f (401 is success).
  $sh = 'curl -sS --max-time 15 -o - -w "\nSTATUS %{http_code}\n" "' + $Url.Replace('"', '\"') + '"'
  return @("sh", "-c", $sh)
}

function Invoke-ReachabilityComposeExecHttpProbe {
  param(
    [Parameter(Mandatory = $true)][scriptblock] $ComposeProbeInvoker,
    [Parameter(Mandatory = $true)][string] $ServiceName,
    [Parameter(Mandatory = $true)][string] $Url,
    [int] $ExpectStatus = 401,
    [string[]] $BodyMustContain = @(),
    [int] $TimeoutMs = 25000,
    [string] $ProbeLabel = "exec"
  )
  if ($TimeoutMs -le 0) {
    return [ordered]@{
      probe = $ProbeLabel; service = $ServiceName; url = $Url
      classification = "matrix_deadline"; exit_code = -1; stdout = ""; stderr = "matrix time exhausted"
      http_status = $null; transport_fail = $false; missing_tool = $false
      notes = @("probe_timeout_budget_zero")
    }
  }
  $pyArgs = New-ReachabilityPythonUrllibProbeCommand -Url $Url
  $composeArgs = @("exec", "-T", $ServiceName) + $pyArgs
  $r = & $ComposeProbeInvoker -ComposeArgs $composeArgs -What ("reach exec $ProbeLabel python $ServiceName") -TimeoutMs $TimeoutMs
  $exit = Get-DockerControlResultCode -Result $r
  $stdout = [string]$r.StdOut
  $stderr = [string]$r.StdErr
  $timedOut = $false
  if ($null -ne $r) {
    if ($r -is [hashtable] -and $r.ContainsKey('TimedOut')) { $timedOut = [bool]$r.TimedOut }
    elseif ($r.PSObject.Properties['TimedOut']) { $timedOut = [bool]$r.TimedOut }
  }
  if ($timedOut) {
    return [ordered]@{
      probe = $ProbeLabel; service = $ServiceName; url = $Url
      classification = "exec_fail"; exit_code = $exit; stdout = $stdout; stderr = $stderr
      http_status = $null; transport_fail = $false; missing_tool = $false
      notes = @("compose_exec_timed_out")
    }
  }
  return Convert-ReachabilityExecOutputToProbeResult -ProbeLabel $ProbeLabel -ServiceName $ServiceName -Url $Url `
    -ExitCode $exit -StdOut $stdout -StdErr $stderr -ExpectStatus $ExpectStatus -BodyMustContain $BodyMustContain
}

function Invoke-ReachabilityComposeExecWebHttpProbe {
  param(
    [Parameter(Mandatory = $true)][scriptblock] $ComposeProbeInvoker,
    [Parameter(Mandatory = $true)][datetime] $MatrixDeadlineUtc,
    [Parameter(Mandatory = $true)][string] $Url,
    [int] $ExpectStatus = 401,
    [string[]] $BodyMustContain = @(),
    [int] $TimeoutMs = 25000,
    [string] $ProbeLabel = "L1-H-web-exec"
  )
  $pyRes = Invoke-ReachabilityComposeExecHttpProbe -ComposeProbeInvoker $ComposeProbeInvoker `
    -ServiceName "web" -Url $Url -ExpectStatus $ExpectStatus -BodyMustContain $BodyMustContain `
    -TimeoutMs $TimeoutMs -ProbeLabel ($ProbeLabel + "-python")
  if ($pyRes.classification -ne 'missing_tool') {
    $pyRes.probe = $ProbeLabel
    return $pyRes
  }
  $curlTimeout = Get-ReachabilityClampedProbeTimeoutMs -MatrixDeadlineUtc $MatrixDeadlineUtc -RequestedMs $TimeoutMs
  if ($curlTimeout -le 0) {
    return [ordered]@{
      probe = $ProbeLabel; service = "web"; url = $Url
      classification = "matrix_deadline"; exit_code = -1; stdout = ""; stderr = "matrix time exhausted after python missing_tool"
      http_status = $null; transport_fail = $false; missing_tool = $false
      notes = @("web_curl_skipped_no_budget", "python_missing_tool")
    }
  }
  $curlArgs = New-ReachabilityCurlHttpProbeCommand -Url $Url
  $composeArgs = @("exec", "-T", "web") + $curlArgs
  $r = & $ComposeProbeInvoker -ComposeArgs $composeArgs -What ("reach exec $ProbeLabel curl web") -TimeoutMs $curlTimeout
  $exit = Get-DockerControlResultCode -Result $r
  $stdout = [string]$r.StdOut
  $stderr = [string]$r.StdErr
  $timedOut = $false
  if ($null -ne $r) {
    if ($r -is [hashtable] -and $r.ContainsKey('TimedOut')) { $timedOut = [bool]$r.TimedOut }
    elseif ($r.PSObject.Properties['TimedOut']) { $timedOut = [bool]$r.TimedOut }
  }
  if ($timedOut) {
    return [ordered]@{
      probe = $ProbeLabel; service = "web"; url = $Url
      classification = "exec_fail"; exit_code = $exit; stdout = $stdout; stderr = $stderr
      http_status = $null; transport_fail = $false; missing_tool = $false
      notes = @("web_curl_timed_out", "python_missing_tool")
    }
  }
  $curlRes = Convert-ReachabilityExecOutputToProbeResult -ProbeLabel $ProbeLabel -ServiceName "web" -Url $Url `
    -ExitCode $exit -StdOut $stdout -StdErr $stderr -ExpectStatus $ExpectStatus -BodyMustContain $BodyMustContain `
    -ExtraNotes @("web_probe_via_curl_after_python_missing") -StatusLinePosition Trailing
  if ($curlRes.classification -eq 'missing_tool') {
    $curlRes.notes = @($curlRes.notes) + @("web_python_and_curl_unavailable")
  }
  return $curlRes
}

function Get-ReachabilityExecHttpStatusAndBody {
  param(
    $StdOut = $null,
    [ValidateSet('Leading', 'Trailing', 'Auto')]
    [string] $StatusLinePosition = 'Auto'
  )
  $stdout = $(if ($null -eq $StdOut) { "" } else { [string]$StdOut })
  if ($StatusLinePosition -eq 'Leading' -or $StatusLinePosition -eq 'Auto') {
    if ($stdout -match '(?m)^STATUS\s+(\d+)') {
      $status = [int]$Matches[1]
      $body = $stdout
      if ($stdout -match '(?ms)^STATUS\s+\d+\r?\n(.*)$') { $body = $Matches[1] }
      return @{ Found = $true; Status = $status; Body = $body; Framing = 'Leading' }
    }
  }
  if ($StatusLinePosition -eq 'Trailing' -or $StatusLinePosition -eq 'Auto') {
    if ($stdout -match '(?ms)^(.+?)\r?\nSTATUS\s+(\d+)\s*$') {
      return @{
        Found  = $true
        Status = [int]$Matches[2]
        Body   = $Matches[1]
        Framing = 'Trailing'
      }
    }
  }
  return @{ Found = $false; Status = $null; Body = $null; Framing = $null }
}

function Convert-ReachabilityExecOutputToProbeResult {
  param(
    [Parameter(Mandatory = $true)][string] $ProbeLabel,
    [Parameter(Mandatory = $true)][string] $ServiceName,
    [Parameter(Mandatory = $true)][string] $Url,
    [int] $ExitCode = 0,
    $StdOut = $null,
    $StdErr = $null,
    [int] $ExpectStatus = 401,
    [string[]] $BodyMustContain = @(),
    [string[]] $ExtraNotes = @(),
    [ValidateSet('Leading', 'Trailing', 'Auto')]
    [string] $StatusLinePosition = 'Leading'
  )
  $stdout = $(if ($null -eq $StdOut) { "" } else { [string]$StdOut })
  $stderr = $(if ($null -eq $StdErr) { "" } else { [string]$StdErr })
  if (Test-ReachabilityExecMissingTool -ExitCode $ExitCode -StdOut $stdout -StdErr $stderr) {
    return [ordered]@{
      probe           = $ProbeLabel
      service         = $ServiceName
      url             = $Url
      classification  = "missing_tool"
      exit_code       = $ExitCode
      stdout          = $stdout
      stderr          = $stderr
      http_status     = $null
      transport_fail  = $false
      missing_tool    = $true
      notes           = @("missing_tool")
    }
  }
  $parsed = Get-ReachabilityExecHttpStatusAndBody -StdOut $stdout -StatusLinePosition $StatusLinePosition
  if ($parsed.Found) {
    $status = [int]$parsed.Status
    $body = [string]$parsed.Body
    if ($ExitCode -ne 0) {
      return [ordered]@{
        probe = $ProbeLabel; service = $ServiceName; url = $Url
        classification = "exec_fail_nonzero_with_status"; exit_code = $ExitCode
        stdout = $stdout; stderr = $stderr; http_status = $status
        transport_fail = $false; missing_tool = $false
        notes = @("reject_http_ok_on_nonzero_exit", "status_framing=$($parsed.Framing)")
      }
    }
    if ($status -ne $ExpectStatus) {
      return [ordered]@{
        probe = $ProbeLabel; service = $ServiceName; url = $Url
        classification = "http_status_mismatch"; exit_code = $ExitCode
        stdout = $stdout; stderr = $stderr; http_status = $status
        transport_fail = $false; missing_tool = $false
        notes = @("want_status=$ExpectStatus", "status_framing=$($parsed.Framing)")
      }
    }
    foreach ($frag in $BodyMustContain) {
      if ($body -notmatch [regex]::Escape($frag)) {
        return [ordered]@{
          probe = $ProbeLabel; service = $ServiceName; url = $Url
          classification = "http_body_mismatch"; exit_code = $ExitCode
          stdout = $stdout; stderr = $stderr; http_status = $status
          transport_fail = $false; missing_tool = $false
          notes = @("missing_body_marker=$frag", "status_framing=$($parsed.Framing)")
        }
      }
    }
    return [ordered]@{
      probe = $ProbeLabel; service = $ServiceName; url = $Url
      classification = "http_ok"; exit_code = $ExitCode
      stdout = $stdout; stderr = $stderr; http_status = $status
      transport_fail = $false; missing_tool = $false
      notes = @($ExtraNotes) + @("status_framing=$($parsed.Framing)")
    }
  }
  $curlTransport = ($StatusLinePosition -eq 'Trailing' -and (
      $ExitCode -in @(6, 7, 28) -or
      $stderr -match '(?i)failed to connect|could not resolve|connection refused|timed out'
    ))
  if ($stdout -match '(?m)^TRANSPORT\s' -or $ExitCode -eq 2 -or $curlTransport) {
    return [ordered]@{
      probe = $ProbeLabel; service = $ServiceName; url = $Url
      classification = "transport_fail"; exit_code = $ExitCode
      stdout = $stdout; stderr = $stderr; http_status = $null
      transport_fail = $true; missing_tool = $false
      notes = @("in_container_transport")
    }
  }
  return [ordered]@{
    probe = $ProbeLabel; service = $ServiceName; url = $Url
    classification = "exec_unparsed"; exit_code = $ExitCode
    stdout = $stdout; stderr = $stderr; http_status = $null
    transport_fail = $false; missing_tool = $false
    notes = @("unrecognized_exec_output")
  }
}

function Invoke-ReachabilityComposeRunMeshProbe {
  param(
    [Parameter(Mandatory = $true)][scriptblock] $ComposeProbeInvoker,
    [Parameter(Mandatory = $true)][string] $Url,
    [int] $ExpectStatus = 401,
    [string[]] $BodyMustContain = @(),
    [int] $TimeoutMs = 25000
  )
  if ($TimeoutMs -le 0) {
    return [ordered]@{
      probe = "L1-H-fallback-run"; service = "api-run"; url = $Url
      classification = "matrix_deadline"; exit_code = -1; stdout = ""; stderr = "matrix time exhausted"
      http_status = $null; transport_fail = $false; missing_tool = $false
      notes = @("fallback_not_web_to_api_proof")
    }
  }
  $pyArgs = New-ReachabilityPythonUrllibProbeCommand -Url $Url
  $composeArgs = @("run", "--rm", "--no-deps", "api") + $pyArgs
  $r = & $ComposeProbeInvoker -ComposeArgs $composeArgs -What "reach run mesh api python" -TimeoutMs $TimeoutMs
  $exit = Get-DockerControlResultCode -Result $r
  return Convert-ReachabilityExecOutputToProbeResult -ProbeLabel "L1-H-fallback-run" -ServiceName "api-run" `
    -Url $Url -ExitCode $exit -StdOut ([string]$r.StdOut) -StdErr ([string]$r.StdErr) `
    -ExpectStatus $ExpectStatus -BodyMustContain $BodyMustContain -ExtraNotes @("fallback_not_web_to_api_proof")
}

function Get-ReachabilityHostHttpProbeResult {
  <#
    Host L1-J path: capture status/body before classify. Prefer ExpectJsonCode (parsed JSON
    `code`) over whitespace-sensitive BodyMustContain markers. Never nulls status/body on
    content mismatch; acquisition failures stay http_error (instrumentation).
  #>
  param(
    [Parameter(Mandatory = $true)][string] $Uri,
    [Parameter(Mandatory = $true)][int] $ExpectStatus,
    [string[]] $BodyMustContain = @(),
    [string] $ExpectJsonCode = "",
    [int] $TimeoutSec = 20,
    [int] $MaxTimeoutSec = 0
  )
  if ($MaxTimeoutSec -gt 0 -and $TimeoutSec -gt $MaxTimeoutSec) { $TimeoutSec = $MaxTimeoutSec }
  if ($TimeoutSec -le 0) {
    return [ordered]@{
      classification = "matrix_deadline"; uri = $Uri; http_status = $null; body = $null
      transport_fail = $false; acquisition_ok = $false; acquisition_error = $null
      parsed_code = $null; error = "matrix time exhausted"
    }
  }
  try {
    $cap = Invoke-HttpJsonCapture -Uri $Uri -TimeoutSec $TimeoutSec
    return Convert-HttpJsonCaptureToProbeResult -Capture $cap -ExpectStatus $ExpectStatus `
      -ExpectJsonCode $ExpectJsonCode -BodyMustContain $BodyMustContain
  } catch {
    # Unexpected client/runtime failure — instrumentation, not content evidence.
    return [ordered]@{
      classification    = "http_error"
      uri               = $Uri
      http_status       = $null
      body              = $null
      transport_fail    = $false
      acquisition_ok    = $false
      acquisition_error = "probe_exception"
      parsed_code       = $null
      error             = $_.Exception.Message
    }
  }
}

function Get-ReachabilityHostTcpProbeResult {
  param(
    [Parameter(Mandatory = $true)][string] $ComputerName,
    [Parameter(Mandatory = $true)][int] $Port,
    [int] $TimeoutMs = 15000
  )
  if ($TimeoutMs -le 0) {
    return [ordered]@{
      classification = "matrix_deadline"; computer = $ComputerName; port = $Port
      tcp_ok = $false; raw = ""; error = "matrix time exhausted"
    }
  }
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $ar = $client.BeginConnect($ComputerName, $Port, $null, $null)
    if (-not $ar.AsyncWaitHandle.WaitOne($TimeoutMs)) {
      return [ordered]@{
        classification = "tcp_timeout"; computer = $ComputerName; port = $Port
        tcp_ok = $false; raw = "TcpClient.WaitOne timeout ${TimeoutMs}ms"; error = $null
      }
    }
    $client.EndConnect($ar)
    return [ordered]@{
      classification = "tcp_ok"; computer = $ComputerName; port = $Port
      tcp_ok = $true; raw = "TcpClient connected within ${TimeoutMs}ms"; error = $null
    }
  } catch {
    return [ordered]@{
      classification = "tcp_fail"; computer = $ComputerName; port = $Port
      tcp_ok = $false; raw = $_.Exception.Message; error = $_.Exception.Message
    }
  } finally {
    try { $client.Close() } catch { }
  }
}

function Invoke-ReachabilityBoundedNetstat18000 {
  param([int] $TimeoutMs = 10000)
  if ($TimeoutMs -le 0) { return "matrix_deadline: netstat skipped (no time budget)" }
  $job = Start-Job -ScriptBlock {
    cmd.exe /c "netstat -ano | findstr :18000" 2>&1 | Out-String
  }
  $completed = Wait-Job -Job $job -Timeout ([Math]::Max(1, [int]($TimeoutMs / 1000)))
  if (-not $completed) {
    try { Stop-Job -Job $job -ErrorAction SilentlyContinue } catch { }
    try { Remove-Job -Job $job -Force -ErrorAction SilentlyContinue } catch { }
    return "netstat_timeout: exceeded ${TimeoutMs}ms"
  }
  $text = Receive-Job -Job $job
  Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
  return [string]$text
}

function New-ReachabilityDockerAllowFailProbeRecord {
  param([AllowNull()] $Result)
  $code = Get-DockerControlResultCode -Result $Result
  $timedOut = $false
  $budgetZero = $false
  $stdout = ""
  $stderr = ""
  if ($null -ne $Result) {
    if ($Result -is [System.Collections.IDictionary]) {
      if ($Result.Contains('TimedOut')) { $timedOut = [bool]$Result['TimedOut'] }
      if ($Result.Contains('MatrixBudgetZero')) { $budgetZero = [bool]$Result['MatrixBudgetZero'] }
      if ($Result.Contains('StdOut')) { $stdout = [string]$Result['StdOut'] }
      if ($Result.Contains('StdErr')) { $stderr = [string]$Result['StdErr'] }
    } else {
      if ($Result.PSObject.Properties['TimedOut']) { $timedOut = [bool]$Result.TimedOut }
      if ($Result.PSObject.Properties['MatrixBudgetZero']) { $budgetZero = [bool]$Result.MatrixBudgetZero }
      if ($Result.PSObject.Properties['StdOut']) { $stdout = [string]$Result.StdOut }
      if ($Result.PSObject.Properties['StdErr']) { $stderr = [string]$Result.StdErr }
    }
  }
  return [ordered]@{
    code               = $code
    timed_out          = $timedOut
    matrix_budget_zero = $budgetZero
    stdout             = $stdout.Trim()
    stderr             = $stderr.Trim()
  }
}

function Get-ReachabilityPublishL1BClassification {
  param([Parameter(Mandatory = $true)] $PublishEvidence)
  $dp = $PublishEvidence.docker_port_probe
  $portsProbe = $PublishEvidence.networksettings_ports_probe
  $host18000 = ($true -eq $PublishEvidence.host_port_18000)
  $portTextOk = (-not [string]::IsNullOrWhiteSpace($dp.stdout)) -and ($dp.stdout -match '127\.0\.0\.1:18000')

  if ($dp.matrix_budget_zero -or $dp.timed_out) { return 'publish_instrumentation' }
  if ($portTextOk) { return 'publish_ok' }
  if ($host18000 -and $portsProbe.code -eq 0 -and -not $portsProbe.matrix_budget_zero -and -not $portsProbe.timed_out) {
    return 'publish_ok'
  }
  if ($dp.code -ne 0) { return 'publish_instrumentation' }
  if ($portsProbe.matrix_budget_zero -or $portsProbe.timed_out -or ($portsProbe.code -ne 0)) {
    return 'publish_instrumentation'
  }
  if ($host18000) { return 'publish_ok' }
  return 'publish_missing'
}

function Invoke-ReachabilityMatrixBoundedAllowFail {
  param(
    [Parameter(Mandatory = $true)][datetime] $MatrixDeadlineUtc,
    [Parameter(Mandatory = $true)][int] $RequestedMs,
    [Parameter(Mandatory = $true)][string] $What,
    [Parameter(Mandatory = $true)][string[]] $DockerArgs
  )
  $budget = Get-ReachabilityClampedProbeTimeoutMs -MatrixDeadlineUtc $MatrixDeadlineUtc -RequestedMs $RequestedMs
  if ($budget -le 0) {
    return @{
      Code = -1; StdOut = ""; StdErr = "matrix time exhausted before $What"
      TimedOut = $false; MatrixBudgetZero = $true
    }
  }
  $r = Invoke-PreG5DockerControlAllowFail -What $What -DockerArgs $DockerArgs -TimeoutMs $budget
  if ($r -is [System.Collections.IDictionary]) {
    if (-not $r.Contains('MatrixBudgetZero')) { $r['MatrixBudgetZero'] = $false }
  } elseif ($null -ne $r -and -not ($r.PSObject.Properties['MatrixBudgetZero'])) {
    $r | Add-Member -NotePropertyName MatrixBudgetZero -NotePropertyValue $false -Force
  }
  return $r
}

function Get-ReachabilityApiPublishEvidence {
  param(
    [Parameter(Mandatory = $true)][string] $ProjectName,
    [Parameter(Mandatory = $true)][string] $ApiContainerId,
    [Parameter(Mandatory = $true)][string] $ProbeDir,
    [Parameter(Mandatory = $true)][datetime] $MatrixDeadlineUtc,
    [int] $RequestedPerCallMs = 15000
  )
  $notes = New-Object System.Collections.Generic.List[string]
  $portR = Invoke-ReachabilityMatrixBoundedAllowFail -MatrixDeadlineUtc $MatrixDeadlineUtc `
    -RequestedMs $RequestedPerCallMs -What "docker port api 8000" -DockerArgs @("port", $ApiContainerId, "8000")
  $dockerPortProbe = New-ReachabilityDockerAllowFailProbeRecord -Result $portR
  $portOut = [string]$dockerPortProbe.stdout
  if ($dockerPortProbe.matrix_budget_zero) { $notes.Add("docker_port:matrix_budget_zero") }
  elseif ($dockerPortProbe.timed_out) { $notes.Add("docker_port:timed_out") }
  elseif ($dockerPortProbe.code -ne 0) { $notes.Add("docker_port:code=$($dockerPortProbe.code):$($dockerPortProbe.stderr)") }
  Save-ReachabilityProbeArtifact -ProbeDir $ProbeDir -FileName "L1-B-docker-port.txt" -Text $(if ($portOut) { $portOut } else { $dockerPortProbe.stderr }) | Out-Null

  $bindingsJson = ""
  $bindR = Invoke-ReachabilityMatrixBoundedAllowFail -MatrixDeadlineUtc $MatrixDeadlineUtc `
    -RequestedMs $RequestedPerCallMs -What "inspect PortBindings" -DockerArgs @(
      "inspect", $ApiContainerId, "--format", "{{json .HostConfig.PortBindings}}"
    )
  $portBindingsProbe = New-ReachabilityDockerAllowFailProbeRecord -Result $bindR
  if ($portBindingsProbe.matrix_budget_zero) { $notes.Add("portbindings:matrix_budget_zero") }
  elseif ($portBindingsProbe.timed_out) { $notes.Add("portbindings:timed_out") }
  elseif ($portBindingsProbe.code -eq 0) { $bindingsJson = [string]$portBindingsProbe.stdout }
  else { $notes.Add("portbindings:code=$($portBindingsProbe.code):$($portBindingsProbe.stderr)") }
  Save-ReachabilityProbeArtifact -ProbeDir $ProbeDir -FileName "L1-C-portbindings.json" -Text $bindingsJson | Out-Null

  $portsJson = ""
  $portsR = Invoke-ReachabilityMatrixBoundedAllowFail -MatrixDeadlineUtc $MatrixDeadlineUtc `
    -RequestedMs $RequestedPerCallMs -What "inspect NetworkSettings.Ports" -DockerArgs @(
      "inspect", $ApiContainerId, "--format", "{{json .NetworkSettings.Ports}}"
    )
  $networkSettingsPortsProbe = New-ReachabilityDockerAllowFailProbeRecord -Result $portsR
  if ($networkSettingsPortsProbe.matrix_budget_zero) { $notes.Add("networksettings_ports:matrix_budget_zero") }
  elseif ($networkSettingsPortsProbe.timed_out) { $notes.Add("networksettings_ports:timed_out") }
  elseif ($networkSettingsPortsProbe.code -eq 0) { $portsJson = [string]$networkSettingsPortsProbe.stdout }
  else { $notes.Add("networksettings_ports:code=$($networkSettingsPortsProbe.code):$($networkSettingsPortsProbe.stderr)") }
  Save-ReachabilityProbeArtifact -ProbeDir $ProbeDir -FileName "L1-D-networksettings-ports.json" -Text $portsJson | Out-Null

  $hostPort18000 = $false
  $portsKeyOk = $false
  try {
    if (-not [string]::IsNullOrWhiteSpace($portsJson)) {
      $portsObj = $portsJson | ConvertFrom-Json
      $pNames = @($portsObj.PSObject.Properties | ForEach-Object { $_.Name })
      if ($pNames -contains '8000/tcp') {
        $portsKeyOk = $true
        $arr = @($portsObj.'8000/tcp')
        foreach ($entry in $arr) {
          if ($null -eq $entry) { continue }
          $en = @($entry.PSObject.Properties | ForEach-Object { $_.Name })
          $hp = ""
          if ($en -contains 'HostPort') { $hp = [string]$entry.HostPort }
          if ($hp -eq "18000") { $hostPort18000 = $true }
        }
      }
    }
  } catch {
    $notes.Add("ports_parse:$($_.Exception.Message)")
  }

  $netName = "${ProjectName}_preg5_net"
  $internalJson = ""
  $intR = Invoke-ReachabilityMatrixBoundedAllowFail -MatrixDeadlineUtc $MatrixDeadlineUtc `
    -RequestedMs $RequestedPerCallMs -What "network inspect internal" -DockerArgs @(
      "network", "inspect", $netName, "--format", "{{json .Internal}}"
    )
  if ($intR -is [System.Collections.IDictionary] -and $intR['MatrixBudgetZero']) { $notes.Add("network_internal:matrix_budget_zero") }
  elseif ($intR.Code -eq 0) { $internalJson = [string]$intR.StdOut.Trim() }
  else { $notes.Add("network_internal:code=$($intR.Code):$($intR.StdErr)") }
  Save-ReachabilityProbeArtifact -ProbeDir $ProbeDir -FileName "L1-E-network-internal.json" -Text $internalJson | Out-Null

  $evidence = [ordered]@{
    docker_port_stdout            = $portOut
    portbindings_json             = $bindingsJson
    networksettings_ports         = $portsJson
    ports_key_8000_tcp            = $portsKeyOk
    host_port_18000               = $hostPort18000
    network_internal_json         = $internalJson
    docker_port_probe             = $dockerPortProbe
    portbindings_probe            = $portBindingsProbe
    networksettings_ports_probe   = $networkSettingsPortsProbe
    notes                         = @($notes)
  }
  $evidence.l1_b_classification = Get-ReachabilityPublishL1BClassification -PublishEvidence $evidence
  return $evidence
}

function Invoke-PreG5Disposable042ReachabilityDiagnosisCore {
  <#
    Probe-first disposable reachability matrix. Caller must dot-source PreG5-SnapshotHelpers.ps1
    and PreG5-DisposableValidationLib.ps1 first.
  #>
  param(
    [Parameter(Mandatory = $true)][string] $ScratchRoot,
    [Parameter(Mandatory = $true)][string] $ExportStamp,
    [Parameter(Mandatory = $true)][string] $AttemptId,
    [Parameter(Mandatory = $true)][string] $ProjectName,
    [Parameter(Mandatory = $true)][string] $ComposeFile,
    [Parameter(Mandatory = $true)][string] $SnapshotApiImage,
    [Parameter(Mandatory = $true)][string] $SnapshotWebImage,
    [Parameter(Mandatory = $true)][string] $PostgresImage,
    [Parameter(Mandatory = $true)][string] $ExpectAlembic,
    [Parameter(Mandatory = $true)][string] $AuditApprovalPath,
    [int] $ComposeTimeoutMs = 180000,
    [int] $HostHttpTimeoutSec = 20,
    [int] $ProbeMatrixDeadlineMs = 180000,
    [int] $ComposeExecProbeTimeoutMs = 25000,
    [int] $ComposeCleanupTimeoutMs = 180000,
    [int] $PublishInspectTimeoutMs = 15000,
    [int] $HostTcpTimeoutMs = 15000,
    [int] $NetstatTimeoutMs = 10000,
    [int[]] $PreflightHostPorts = @(18000, 18080),
    [scriptblock] $HostHttpProbe = $null,
    [scriptblock] $HostTcpProbe = $null,
    [scriptblock] $NetstatProbe = $null,
    [switch] $OrchestrationForceMatrixDeadlineBeforeProbes,
    [ValidateSet('SingleNet', 'DualNet')]
    [string] $OwnedNetworkProfile = 'SingleNet',
    [hashtable] $AuthMeExpectationOverride = $null,
    [hashtable] $EgressDisclosure = $null
  )

  $envKeys = @(
    'SNAPSHOT_API_IMAGE', 'SNAPSHOT_WEB_IMAGE', 'POSTGRES_IMAGE',
    'PREG5_SESSION_SECRET', 'PREG5_TOKEN_ENCRYPTION_KEY'
  )
  $expect = if ($null -ne $AuthMeExpectationOverride) { $AuthMeExpectationOverride } else { Get-ReachabilityAuthMeExpectation }
  $useDualNet = ($OwnedNetworkProfile -eq 'DualNet')

  $st = @{
    OwnedProject     = $false
    OwnedResources   = $null
    EvidenceDir      = $null
    ProjectDir       = $null
    RefusalNoCleanup = $false
    ExitCode         = 1
    CleanupAttempted = $false
    MatrixCompleted  = $false
    MatrixRows       = @()
    LayerBWebToApiProven = $false
    CollectionPartial  = $false
    MatrixDeadlineUtc  = [datetime]::UtcNow.AddHours(2)
  }
  $durableNotes = New-Object System.Collections.Generic.List[string]

  function _Fail([string] $msg) { throw ("PREG5_REACH_FAIL: " + $msg) }
  function _FailRefuse([string] $msg) {
    $st.RefusalNoCleanup = $true
    throw ("PREG5_REACH_FAIL: " + $msg)
  }
  function _RefreshOwned([string] $why) {
    try {
      $st.OwnedResources = Get-DisposableOwnedResources -ProjectName $ProjectName -DualNet:$useDualNet
      $durableNotes.Add("refresh_owned:$why")
    } catch {
      $durableNotes.Add("refresh_owned_unresolved:${why}:$($_.Exception.Message)")
    }
  }
  function _AddMatrixRow($ProbeId, $Result, [string] $Layer) {
    $cls = Get-ProbeResultClassification -Result $Result
    $pass = Test-ReachabilityMatrixRowInterpretablePass -Classification $cls
    $st.MatrixRows = @($st.MatrixRows) + ,@{
      probe_id       = $ProbeId
      layer          = $Layer
      classification = $cls
      pass           = $pass
      detail         = $Result
    }
  }

  function _ClampMatrixTimeout([int] $RequestedMs) {
    return Get-ReachabilityClampedProbeTimeoutMs -MatrixDeadlineUtc $st.MatrixDeadlineUtc -RequestedMs $RequestedMs
  }

  $composeInvoker = {
    param([string[]] $ComposeArgs, [string] $What, [int] $TimeoutMs = 0)
    if ($TimeoutMs -le 0) { $TimeoutMs = $ComposeTimeoutMs }
    $savedEnv = Clear-DisposableInheritedEnv -Keys $envKeys
    try {
      $all = @(
        "compose", "-p", $ProjectName,
        "--project-directory", $st.ProjectDir,
        "--env-file", (Join-Path $st.ProjectDir ".env"),
        "-f", $ComposeFile
      ) + $ComposeArgs
      return Invoke-PreG5DockerControl -DockerArgs $all -What $What -TimeoutMs $TimeoutMs
    } finally {
      Restore-DisposableInheritedEnv -Saved $savedEnv
    }
  }.GetNewClosure()

  $composeProbeInvoker = {
    param([string[]] $ComposeArgs, [string] $What, [int] $TimeoutMs = 0)
    if ($TimeoutMs -le 0) { $TimeoutMs = $ComposeExecProbeTimeoutMs }
    $TimeoutMs = Get-ReachabilityClampedProbeTimeoutMs -MatrixDeadlineUtc $st.MatrixDeadlineUtc -RequestedMs $TimeoutMs
    $savedEnv = Clear-DisposableInheritedEnv -Keys $envKeys
    try {
      $all = @(
        "compose", "-p", $ProjectName,
        "--project-directory", $st.ProjectDir,
        "--env-file", (Join-Path $st.ProjectDir ".env"),
        "-f", $ComposeFile
      ) + $ComposeArgs
      return Invoke-PreG5DockerControlAllowFail -DockerArgs $all -What $What -TimeoutMs $TimeoutMs
    } finally {
      Restore-DisposableInheritedEnv -Saved $savedEnv
    }
  }.GetNewClosure()

  function _AttemptOwnedCleanup {
    param([switch] $WriteSuccessReceipt)
    if ($st.CleanupAttempted) {
      $finalPath = Join-Path $st.EvidenceDir "cleanup-outcome.final.json"
      if (Test-Path -LiteralPath $finalPath) {
        try { return Get-Content -LiteralPath $finalPath -Raw | ConvertFrom-Json } catch { return $null }
      }
      return $null
    }
    $st.CleanupAttempted = $true
    return Invoke-DisposableAttemptCleanup -ProjectName $ProjectName -EvidenceDir $st.EvidenceDir `
      -OwnedResources $st.OwnedResources -ComposeInvoker $composeInvoker -ComposeTimeoutMs $ComposeCleanupTimeoutMs `
      -WriteSuccessReceipt:$WriteSuccessReceipt
  }

  function _WriteReachReceipt {
    param(
      $DiagnosisVerdict,
      $CleanupOutcome = $null,
      $PublishEvidence = $null,
      $Session = $null
    )
    $diagOk = $false
    if ($null -ne $DiagnosisVerdict -and $DiagnosisVerdict.reachability_diagnosis_ok -eq $true) { $diagOk = $true }
    if (-not $st.EvidenceDir) { return }
    $path = Join-Path $st.EvidenceDir "reach-diagnosis.receipt.json"
    $obj = [ordered]@{
      failed                     = (-not $diagOk)
      reachability_diagnosis_ok  = $diagOk
      probe_collection_completed = $(if ($DiagnosisVerdict) { $DiagnosisVerdict.probe_collection_completed } else { $false })
      interpretable_diagnosis_ok = $(if ($DiagnosisVerdict) { $DiagnosisVerdict.interpretable_diagnosis_ok } else { $false })
      layer_b_web_to_api_proven  = $(if ($DiagnosisVerdict) { $DiagnosisVerdict.layer_b_web_to_api_proven } else { $false })
      layer_a_in_container_ok    = $(if ($DiagnosisVerdict) { $DiagnosisVerdict.layer_a_in_container_ok } else { $false })
      blocking_probe_ids         = $(if ($DiagnosisVerdict) { @($DiagnosisVerdict.blocking_probe_ids) } else { @() })
      startup_validation_ok      = $false
      not_backup_restore         = $true
      attempt_id                 = $AttemptId
      project                    = $ProjectName
      notes                      = @($durableNotes)
      owned                      = $st.OwnedResources
      cleanup_outcome            = $CleanupOutcome
      publish_evidence           = $PublishEvidence
      probe_session              = $Session
      option_b_note              = "F+H success with recorded bindings and host failure localizes failing path; does NOT establish internal:true as root cause."
      auth_content_expectation   = $(if ($expect.AuthContentCode) { [string]$expect.AuthContentCode } else { $null })
      egress_disclosure          = $EgressDisclosure
    }
    Assert-DurablePathWritable $path | Out-Null
    ($obj | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $path -Encoding utf8
  }

  function _WriteMatrixSummary {
    $summaryPath = Join-Path $st.EvidenceDir "reach-probe-matrix-summary.json"
    $matrixArr = @()
    foreach ($row in @($st.MatrixRows)) {
      $detailJson = ""
      if ($null -ne $row.detail) {
        try {
          $detailJson = ($row.detail | ConvertTo-Json -Depth 8 -Compress)
        } catch {
          $detailJson = [string]$row.detail
        }
      }
      $matrixArr += ,@{
        probe_id       = [string]$row.probe_id
        layer          = [string]$row.layer
        classification = [string]$row.classification
        pass           = ($row.pass -eq $true)
        detail_json    = $detailJson
      }
    }
    $payload = @{
      attempt_id    = $AttemptId
      completed_utc = (Get-Date).ToUniversalTime().ToString("o")
      matrix        = $matrixArr
      option_b_note = "F+H success with recorded bindings and host failure localizes failing path; does NOT establish internal:true as root cause."
    }
    ($payload | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $summaryPath -Encoding utf8
  }

  $sessionObj = $null
  $publishEvidence = $null
  $cleanupOutcome = $null

  try {
    if ([string]::IsNullOrWhiteSpace($AuditApprovalPath)) { _FailRefuse "AuditApprovalPath is required" }
    if (-not (Test-Path -LiteralPath $AuditApprovalPath)) { _FailRefuse "AuditApprovalPath missing" }

    $stamp = Assert-ExportStampSafe $ExportStamp
    if ($AttemptId -notmatch '^[a-z0-9][a-z0-9_-]*$') { _Fail "AttemptId charset invalid" }
    if ($ProjectName -notmatch '^[a-z0-9][a-z0-9_-]*$') { _Fail "ProjectName charset invalid" }

    $root = Assert-ScratchRootSafe $ScratchRoot
    $parent = Join-Path $root "theplan-pre-g5-snap-$stamp"
    $parent = [System.IO.Path]::GetFullPath($parent)
    Assert-PathWithinOwned -OwnedDir $root -CandidatePath $parent | Out-Null
    if (-not (Test-Path -LiteralPath $parent)) { _Fail "parent custody missing" }

    $evidence = Join-Path $parent $AttemptId
    $evidence = [System.IO.Path]::GetFullPath($evidence)
    Assert-PathWithinOwned -OwnedDir $parent -CandidatePath $evidence | Out-Null
    try {
      Assert-ImportAttemptDirClear -AttemptDir $evidence | Out-Null
      Assert-ReachabilityAttemptDirClear -AttemptDir $evidence | Out-Null
    } catch {
      _FailRefuse $_.Exception.Message
    }

    $approval = Get-Content -LiteralPath $AuditApprovalPath -Raw | ConvertFrom-Json
    if ($approval.approved -ne $true) { _FailRefuse "approval.approved != true" }
    if ([string]$approval.snapshot_api_image_id -ne $SnapshotApiImage) { _FailRefuse "approval api image mismatch" }
    if ([string]$approval.snapshot_web_image_id -ne $SnapshotWebImage) { _FailRefuse "approval web image mismatch" }

    Assert-ImageIdMatchesTag -Tag $SnapshotApiImage -ExpectedId $SnapshotApiImage | Out-Null
    Assert-ImageIdMatchesTag -Tag $SnapshotWebImage -ExpectedId $SnapshotWebImage | Out-Null
    Assert-ImageIdMatchesTag -Tag $PostgresImage -ExpectedId $PostgresImage | Out-Null

    try {
      Assert-DisposableProjectPreflight -ProjectName $ProjectName -HostPorts $PreflightHostPorts -DualNet:$useDualNet | Out-Null
    } catch {
      _FailRefuse $_.Exception.Message
    }

    New-Item -ItemType Directory -Path $evidence | Out-Null
    $st.EvidenceDir = $evidence
    $st.ProjectDir = Join-Path $evidence "compose-project"
    New-Item -ItemType Directory -Path $st.ProjectDir | Out-Null
    $probeDir = Join-Path $evidence "reach-probes"
    New-Item -ItemType Directory -Path $probeDir | Out-Null

    $envPath = Join-Path $st.ProjectDir ".env"
    $sessionSecret = -join ((1..48) | ForEach-Object { "{0:x}" -f (Get-Random -Max 16) })
    $tok = -join ((1..48) | ForEach-Object { "{0:x}" -f (Get-Random -Max 16) })
    @(
      "SNAPSHOT_API_IMAGE=$SnapshotApiImage"
      "SNAPSHOT_WEB_IMAGE=$SnapshotWebImage"
      "POSTGRES_IMAGE=$PostgresImage"
      "PREG5_SESSION_SECRET=$sessionSecret"
      "PREG5_TOKEN_ENCRYPTION_KEY=$tok"
    ) | Set-Content -LiteralPath $envPath -Encoding ascii

    $cfgJsonOut = & $composeInvoker -What "compose config json" -ComposeArgs @("config", "--format", "json")
    $cfgJsonPath = Join-Path $evidence "compose.rendered.json"
    Assert-DurablePathWritable $cfgJsonPath | Out-Null
    Set-Content -LiteralPath $cfgJsonPath -Value $cfgJsonOut.StdOut -Encoding utf8
    if ($useDualNet) {
      Assert-DisposableComposeConfigStructuredDualNet -ConfigJson $cfgJsonOut.StdOut `
        -ExpectApiImage $SnapshotApiImage -ExpectWebImage $SnapshotWebImage -ExpectPostgresImage $PostgresImage | Out-Null
    } else {
      Assert-DisposableComposeConfigStructured -ConfigJson $cfgJsonOut.StdOut `
        -ExpectApiImage $SnapshotApiImage -ExpectWebImage $SnapshotWebImage -ExpectPostgresImage $PostgresImage | Out-Null
    }

    $yamlOut = & $composeInvoker -What "compose config yaml" -ComposeArgs @("config")
    Set-Content -LiteralPath (Join-Path $evidence "compose.rendered.yaml") -Value $yamlOut.StdOut -Encoding utf8

    $engineCtx = Get-PreG5DockerEngineContextCapture
    $verR = Invoke-PreG5DockerControlAllowFail -What "docker version" -DockerArgs @(
      "version", "--format", "{{.Server.Os}}/{{.Server.Version}}"
    )
    $sessionObj = [ordered]@{
      started_utc     = (Get-Date).ToUniversalTime().ToString("o")
      attempt_id      = $AttemptId
      project         = $ProjectName
      engine_version  = $(if ($verR.Code -eq 0) { [string]$verR.StdOut.Trim() } else { $null })
      docker_engine   = $engineCtx
    }
    $sessionPath = Join-Path $evidence "reach-probe-session.json"
    ($sessionObj | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $sessionPath -Encoding utf8

    $st.OwnedProject = $true
    $st.OwnedResources = Get-DisposableOwnedResources -ProjectName $ProjectName -DualNet:$useDualNet

    try {
      & $composeInvoker -What "up postgres" -ComposeArgs @("up", "-d", "postgres") | Out-Null
    } catch {
      _RefreshOwned "up_postgres_fail"
      throw
    }
    _RefreshOwned "up_postgres_ok"

    $pgDeadline = [datetime]::UtcNow.AddMilliseconds($ComposeTimeoutMs)
    $getPgPs = {
      $r = & $composeInvoker -What "ps postgres" -ComposeArgs @("ps", "--format", "json")
      return [string]$r.StdOut
    }.GetNewClosure()
    Wait-DisposablePostgresHealthyExact -DeadlineUtc $pgDeadline -GetPostgresPsJson $getPgPs -PollSec 2 | Out-Null

    & $composeInvoker -What "alembic upgrade 042" -TimeoutMs $ComposeTimeoutMs -ComposeArgs @(
      "run", "--rm", "--no-deps", "api",
      "alembic", "upgrade", $ExpectAlembic
    ) | Out-Null

    $verOut = & $composeInvoker -What "alembic current" -ComposeArgs @(
      "run", "--rm", "--no-deps", "api",
      "alembic", "current"
    )
    if ($verOut.StdOut -notmatch [regex]::Escape($ExpectAlembic)) {
      _Fail "alembic current missing $ExpectAlembic — got $($verOut.StdOut)"
    }

    $sqlOut = & $composeInvoker -What "alembic_version sql exec" -ComposeArgs @(
      "exec", "-T", "postgres",
      "psql", "-U", "preg5", "-d", "theplan_preg5", "-tAc",
      "SELECT version_num FROM alembic_version;"
    )
    $sqlVer = ($sqlOut.StdOut -split "`r?`n" | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace($sqlVer)) { _Fail "alembic_version SQL empty" }
    if ($sqlVer.Trim() -cne $ExpectAlembic) {
      _Fail "alembic_version.version_num mismatch want=$ExpectAlembic got=$sqlVer"
    }

    try {
      & $composeInvoker -What "up api web" -ComposeArgs @("up", "-d", "api", "web") | Out-Null
    } catch {
      _RefreshOwned "up_api_web_fail"
      throw
    }
    _RefreshOwned "up_api_web_ok"

    $apiCid = Get-DisposableProjectServiceContainerId -ProjectName $ProjectName -ServiceName "api"
    $webCid = Get-DisposableProjectServiceContainerId -ProjectName $ProjectName -ServiceName "web"
    if ([string]::IsNullOrWhiteSpace($apiCid) -or [string]::IsNullOrWhiteSpace($webCid)) {
      _Fail "api/web containers not running"
    }
    Assert-DisposableContainerRuntimeRunning -ContainerId $apiCid -ServiceName "api" | Out-Null
    Assert-DisposableContainerRuntimeRunning -ContainerId $webCid -ServiceName "web" | Out-Null
    Assert-RunningContainerImagePin -ContainerId $apiCid -ExpectedImageId $SnapshotApiImage | Out-Null
    Assert-RunningContainerImagePin -ContainerId $webCid -ExpectedImageId $SnapshotWebImage | Out-Null

    if ($OrchestrationForceMatrixDeadlineBeforeProbes) {
      $st.MatrixDeadlineUtc = [datetime]::UtcNow.AddSeconds(-1)
    } else {
      $st.MatrixDeadlineUtc = [datetime]::UtcNow.AddMilliseconds($ProbeMatrixDeadlineMs)
    }
    function _AssertMatrixTime([string] $probeId) {
      if ([datetime]::UtcNow -ge $st.MatrixDeadlineUtc) {
        $st.CollectionPartial = $true
        _AddMatrixRow $probeId @{ classification = "matrix_deadline" } "meta"
        throw ("PREG5_REACH_FAIL: probe matrix deadline exceeded before $probeId")
      }
    }

    $psTimeout = _ClampMatrixTimeout $PublishInspectTimeoutMs
    if ($psTimeout -le 0) {
      _AddMatrixRow "L1-A" @{ classification = "matrix_deadline" } "meta"
      throw "PREG5_REACH_FAIL: probe matrix deadline exceeded before L1-A"
    }
    $psOut = & $composeInvoker -What "reach ps json" -ComposeArgs @("ps", "--format", "json") -TimeoutMs $psTimeout
    Save-ReachabilityProbeArtifact -ProbeDir $probeDir -FileName "L1-A-compose-ps.json" -Text $psOut.StdOut | Out-Null

    _AssertMatrixTime "L1-B"
    $publishEvidence = Get-ReachabilityApiPublishEvidence -ProjectName $ProjectName -ApiContainerId $apiCid `
      -ProbeDir $probeDir -MatrixDeadlineUtc $st.MatrixDeadlineUtc -RequestedPerCallMs $PublishInspectTimeoutMs
    _AddMatrixRow "L1-B" @{ classification = [string]$publishEvidence.l1_b_classification } "C"

    _AssertMatrixTime "L1-F"
    $fRes = Invoke-ReachabilityComposeExecHttpProbe -ComposeProbeInvoker $composeProbeInvoker `
      -ServiceName "api" -Url $expect.ApiLocalhostUrl -ExpectStatus $expect.ExpectStatus `
      -BodyMustContain $expect.BodyMustContain -TimeoutMs (_ClampMatrixTimeout $ComposeExecProbeTimeoutMs) -ProbeLabel "L1-F"
    Save-ReachabilityProbeArtifact -ProbeDir $probeDir -FileName "L1-F-exec-api-localhost.txt" `
      -Text ("exit=$($fRes.exit_code)`nstdout:`n$($fRes.stdout)`nstderr:`n$($fRes.stderr)") | Out-Null
    _AddMatrixRow "L1-F" $fRes "A"
    if ($fRes.classification -eq "transport_fail") {
      $durableNotes.Add("stop_matrix:L1-F in-container transport_fail")
      throw "L1-F in-container transport refused — stop matrix escalation per plan"
    }

    _AssertMatrixTime "L1-H"
    $hWebRes = Invoke-ReachabilityComposeExecWebHttpProbe -ComposeProbeInvoker $composeProbeInvoker `
      -MatrixDeadlineUtc $st.MatrixDeadlineUtc -Url $expect.ServiceMeshUrl -ExpectStatus $expect.ExpectStatus `
      -BodyMustContain $expect.BodyMustContain -TimeoutMs (_ClampMatrixTimeout $ComposeExecProbeTimeoutMs) -ProbeLabel "L1-H-web-exec"
    Save-ReachabilityProbeArtifact -ProbeDir $probeDir -FileName "L1-H-exec-web-to-api.txt" `
      -Text ("classification=$($hWebRes.classification)`nexit=$($hWebRes.exit_code)`nstdout:`n$($hWebRes.stdout)`nstderr:`n$($hWebRes.stderr)") | Out-Null
    _AddMatrixRow "L1-H-web" $hWebRes "B"
    $st.LayerBWebToApiProven = ($hWebRes.classification -eq "http_ok")
    if ($hWebRes.classification -eq "missing_tool") {
      $durableNotes.Add("L1-H:web_exec_missing_tool; web-to-api unproven; optional api-run fallback only")
      $fallbackRes = Invoke-ReachabilityComposeRunMeshProbe -ComposeProbeInvoker $composeProbeInvoker `
        -Url $expect.ServiceMeshUrl -ExpectStatus $expect.ExpectStatus `
        -BodyMustContain $expect.BodyMustContain -TimeoutMs (_ClampMatrixTimeout $ComposeExecProbeTimeoutMs)
      Save-ReachabilityProbeArtifact -ProbeDir $probeDir -FileName "L1-H-mesh-run-api-fallback.txt" `
        -Text ("classification=$($fallbackRes.classification)`nexit=$($fallbackRes.exit_code)`nstdout:`n$($fallbackRes.stdout)`nstderr:`n$($fallbackRes.stderr)") | Out-Null
      _AddMatrixRow "L1-H-fallback" $fallbackRes "B-alt"
      $st.LayerBWebToApiProven = $false
    } elseif ($hWebRes.classification -ne "http_ok") {
      $st.LayerBWebToApiProven = $false
    }

    _AssertMatrixTime "L1-I"
    $tcpBudget = _ClampMatrixTimeout $HostTcpTimeoutMs
    if ($null -ne $HostTcpProbe) {
      $tcpRes = & $HostTcpProbe -ComputerName "127.0.0.1" -Port 18000 -TimeoutMs $tcpBudget
    } else {
      $tcpRes = Get-ReachabilityHostTcpProbeResult -ComputerName "127.0.0.1" -Port 18000 -TimeoutMs $tcpBudget
    }
    Save-ReachabilityProbeArtifact -ProbeDir $probeDir -FileName "L1-I-test-netconnection.txt" -Text ([string]$tcpRes.raw) | Out-Null
    _AddMatrixRow "L1-I" $tcpRes "D"

    _AssertMatrixTime "L1-J"
    $httpBudgetSec = [int][Math]::Ceiling((_ClampMatrixTimeout ($HostHttpTimeoutSec * 1000)) / 1000.0)
    if ($httpBudgetSec -lt 1) { $httpBudgetSec = 1 }
    if ($null -ne $HostHttpProbe) {
      $httpRes = & $HostHttpProbe -Uri $expect.Uri -ExpectStatus $expect.ExpectStatus `
        -BodyMustContain $expect.BodyMustContain -ExpectJsonCode $expect.AuthContentCode `
        -TimeoutSec $httpBudgetSec
    } else {
      $httpRes = Get-ReachabilityHostHttpProbeResult -Uri $expect.Uri -ExpectStatus $expect.ExpectStatus `
        -BodyMustContain @() -ExpectJsonCode $expect.AuthContentCode `
        -TimeoutSec $httpBudgetSec -MaxTimeoutSec $httpBudgetSec
    }
    Save-ReachabilityProbeArtifact -ProbeDir $probeDir -FileName "L1-J-host-iwr-auth-me.txt" `
      -Text ($httpRes | ConvertTo-Json -Depth 6) | Out-Null
    _AddMatrixRow "L1-J" $httpRes "D"

    _AssertMatrixTime "L1-K"
    $netstatText = ""
    $netBudget = _ClampMatrixTimeout $NetstatTimeoutMs
    if ($null -ne $NetstatProbe) {
      $netstatText = [string](& $NetstatProbe -TimeoutMs $netBudget)
    } else {
      $netstatText = Invoke-ReachabilityBoundedNetstat18000 -TimeoutMs $netBudget
    }
    Save-ReachabilityProbeArtifact -ProbeDir $probeDir -FileName "L1-K-netstat-18000.txt" -Text $netstatText | Out-Null

    _AssertMatrixTime "matrix-complete"
    _WriteMatrixSummary
    $endedUtc = (Get-Date).ToUniversalTime().ToString("o")
    $sessionWrite = [ordered]@{
      started_utc    = $sessionObj.started_utc
      attempt_id     = $sessionObj.attempt_id
      project        = $sessionObj.project
      engine_version = $sessionObj.engine_version
      docker_engine  = $sessionObj.docker_engine
      ended_utc      = $endedUtc
    }
    ($sessionWrite | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $sessionPath -Encoding utf8
    $sessionObj = $sessionWrite
    $st.MatrixCompleted = $true

    $cleanupOutcome = _AttemptOwnedCleanup
    $st.OwnedProject = $false
    $verdict = Get-ReachabilityDiagnosisVerdict -MatrixRows $st.MatrixRows -CollectionCompleted $st.MatrixCompleted `
      -CleanupOk ($true -eq $cleanupOutcome.cleanup_ok) -LayerBWebToApiProven $st.LayerBWebToApiProven `
      -CollectionPartial $st.CollectionPartial
    _WriteReachReceipt -DiagnosisVerdict $verdict -CleanupOutcome $cleanupOutcome -PublishEvidence $publishEvidence -Session $sessionObj
    if (-not $verdict.reachability_diagnosis_ok) {
      _Fail "interpretable diagnosis not satisfied or cleanup failed"
    }
    $st.ExitCode = 0
  }
  catch {
    $durableNotes.Add("fail:" + $_.Exception.Message)
    if ($st.RefusalNoCleanup -or -not $st.OwnedProject) {
      $st.ExitCode = 1
    } else {
      if ($st.OwnedProject -and $st.EvidenceDir) {
        try {
          Capture-DisposableFailureDiagnostics -ProjectName $ProjectName -EvidenceDir $st.EvidenceDir `
            -ComposeInvoker $composeInvoker -LogMaxBytes 65536 -ComposeTimeoutMs $ComposeTimeoutMs | Out-Null
        } catch {
          $durableNotes.Add("diagnostics_collect_fail:" + $_.Exception.Message)
        }
        if (@($st.MatrixRows).Count -gt 0) {
          try { _WriteMatrixSummary } catch { }
        }
        try {
          _RefreshOwned "failure_path"
          $cleanupOutcome = _AttemptOwnedCleanup
        } catch {
          $durableNotes.Add("cleanup_fail:" + $_.Exception.Message)
          $finalPath = Join-Path $st.EvidenceDir "cleanup-outcome.final.json"
          if (Test-Path -LiteralPath $finalPath) {
            try { $cleanupOutcome = Get-Content -LiteralPath $finalPath -Raw | ConvertFrom-Json } catch { }
          }
        }
      }
      if ($st.CollectionPartial) { $st.MatrixCompleted = $false }
      $verdict = Get-ReachabilityDiagnosisVerdict -MatrixRows $st.MatrixRows -CollectionCompleted $st.MatrixCompleted `
        -CleanupOk ($null -ne $cleanupOutcome -and $true -eq $cleanupOutcome.cleanup_ok) -LayerBWebToApiProven $st.LayerBWebToApiProven `
        -CollectionPartial $st.CollectionPartial
      _WriteReachReceipt -DiagnosisVerdict $verdict -CleanupOutcome $cleanupOutcome -PublishEvidence $publishEvidence -Session $sessionObj
      if ($verdict.reachability_diagnosis_ok) { $st.ExitCode = 0 } else { $st.ExitCode = 1 }
    }
  }

  return ,[ordered]@{
    ExitCode           = $st.ExitCode
    RefusalNoCleanup   = $st.RefusalNoCleanup
    EvidenceDir        = $st.EvidenceDir
    OwnedProjectAtEnd  = $st.OwnedProject
    MatrixCompleted    = $st.MatrixCompleted
    Notes              = @($durableNotes)
  }
}
