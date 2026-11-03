#Requires -Version 5.1
<#
  Injected-runner orchestration tests for disposable 042 validation Core (no live Docker).
  Dot-sourced by Validate-PreG5SnapshotFailurePaths.ps1; increments $script:failed on failure.
#>
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "PreG5-DisposableValidationLib.ps1")

function New-TestDisposableSyntheticHttpEndpointObservation {
  <# Orchestration-only HTTP stubs (never called from PreG5-DisposableValidationLib.ps1). #>
  param(
    [Parameter(Mandatory = $true)][string] $Uri,
    [Parameter(Mandatory = $true)][int] $ExpectStatus,
    [string[]] $BodyMustContain = @(),
    [string] $ExpectJsonCode = "",
    [Parameter(Mandatory = $true)][ValidateSet('http_ok', 'mismatches', 'transport_fail', 'http_error')]
    [string] $Classification,
    [string] $ParsedCodeOverride = "",
    [Nullable[int]] $HttpStatusOverride = $null,
    [string] $ProbeError = $null,
    [AllowNull()] $BodyOverride = $null
  )
  $body = $BodyOverride
  if ($Classification -eq 'transport_fail' -or $Classification -eq 'http_error') {
    if ($null -eq $BodyOverride) { $body = $null }
  } elseif ($null -eq $body) {
    $body = ""
    if (-not [string]::IsNullOrWhiteSpace($ExpectJsonCode)) {
      $code = if ($Classification -eq 'http_ok') { $ExpectJsonCode } else { $(if ($ParsedCodeOverride) { $ParsedCodeOverride } else { "UNAUTHENTICATED" }) }
      $body = ('{"code":"' + $code + '"}')
    } elseif (@($BodyMustContain).Count -gt 0) {
      $body = "<html><title>thePlan</title></html>"
    }
  }
  $status = if ($null -ne $HttpStatusOverride) { [int]$HttpStatusOverride } else {
    if ($Classification -eq 'transport_fail') { $null } else { $ExpectStatus }
  }
  $parsed = if (-not [string]::IsNullOrWhiteSpace($ExpectJsonCode)) {
    if ($Classification -eq 'http_ok') { $ExpectJsonCode } else { $(if ($ParsedCodeOverride) { $ParsedCodeOverride } else { $null }) }
  } else { $null }
  $probeShape = [ordered]@{
    classification    = $(switch ($Classification) {
        'http_ok' { 'http_ok' }
        'transport_fail' { 'transport_fail' }
        'http_error' { 'http_error' }
        default { 'http_body_mismatch' }
      })
    http_status       = $status
    body              = $body
    acquisition_ok    = ($Classification -ne 'http_error')
    acquisition_error = $(if ($Classification -eq 'http_error') { "synthetic_acquisition_fail" } else { $null })
    parsed_code       = $parsed
    error             = $ProbeError
  }
  return New-DisposableHttpEndpointObservationEntry -Uri $Uri -ExpectStatus $ExpectStatus `
    -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -ProbeResult $probeShape
}

function Start-DisposableLocalHttpFixture {
  param(
    [Parameter(Mandatory = $true)][int] $StatusCode,
    [AllowNull()][string] $Body,
    [string] $ReasonPhrase = "OK",
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

function Stop-DisposableLocalHttpFixture {
  param($Server)
  if ($null -eq $Server) { return }
  try { if ($Server.ContainsKey('StopToken')) { $Server.StopToken.Cancel() } } catch { }
  try { $Server.Tcp.Stop() } catch { }
  try { $null = $Server.PS.EndInvoke($Server.Handle) } catch { }
  try { $Server.PS.Dispose() } catch { }
  try { $Server.Runspace.Close(); $Server.Runspace.Dispose() } catch { }
}

function Start-DisposableLocalHttpCloseOnlyFixture {
  $tcp = New-Object System.Net.Sockets.TcpListener ([System.Net.IPAddress]::Loopback, 0)
  $tcp.Start()
  $port = ([System.Net.IPEndPoint]$tcp.LocalEndpoint).Port
  $stopSrc = New-Object System.Threading.CancellationTokenSource
  $runspace = [runspacefactory]::CreateRunspace()
  $runspace.Open()
  $ps = [powershell]::Create()
  $ps.Runspace = $runspace
  [void]$ps.AddScript({
      param($tcpListener, $stopToken)
      Start-Sleep -Milliseconds 100
      while (-not $stopToken.IsCancellationRequested) {
        try {
          if (-not $tcpListener.Server.IsBound) { break }
          $client = $tcpListener.AcceptTcpClient()
        } catch {
          break
        }
        try {
          $stream = $client.GetStream()
          $buf = New-Object byte[] 8192
          $stream.ReadTimeout = 1500
          try {
            while ($stream.DataAvailable) { [void]$stream.Read($buf, 0, $buf.Length) }
            [void]$stream.Read($buf, 0, $buf.Length)
          } catch { }
          try { $stream.Close() } catch { }
        } catch { }
        finally {
          try { $client.Close() } catch { }
        }
      }
    }).AddArgument($tcp).AddArgument($stopSrc.Token)
  $handle = $ps.BeginInvoke()
  return @{
    Port      = $port
    Tcp       = $tcp
    PS        = $ps
    Handle    = $handle
    Runspace  = $runspace
    StopToken = $stopSrc
    Uri       = ("http://127.0.0.1:{0}/api/v1/auth/me" -f $port)
  }
}

function Start-DisposableLocalHttpConnectionCloseFixture {
  param(
    [int] $CloseAcceptCount = [int]::MaxValue,
    [int] $SuccessStatusCode = 401,
    [string] $SuccessBody = '{"code":"SETUP_REQUIRED"}',
    [string] $SuccessReason = "Unauthorized"
  )
  $tcp = New-Object System.Net.Sockets.TcpListener ([System.Net.IPAddress]::Loopback, 0)
  $tcp.Start()
  $port = ([System.Net.IPEndPoint]$tcp.LocalEndpoint).Port
  $stopSrc = New-Object System.Threading.CancellationTokenSource
  $runspace = [runspacefactory]::CreateRunspace()
  $runspace.Open()
  $ps = [powershell]::Create()
  $ps.Runspace = $runspace
  [void]$ps.AddScript({
      param($tcpListener, [int] $closeBudget, $stopToken, $okStatus, $okReason, $okBodyText)
      $enc = [System.Text.Encoding]::UTF8
      $remainingClose = $closeBudget
      Start-Sleep -Milliseconds 100
      while (-not $stopToken.IsCancellationRequested) {
        try {
          if (-not $tcpListener.Server.IsBound) { break }
          $client = $tcpListener.AcceptTcpClient()
        } catch {
          break
        }
        try {
          $stream = $client.GetStream()
          $buf = New-Object byte[] 8192
          $stream.ReadTimeout = 1500
          try {
            while ($stream.DataAvailable) { [void]$stream.Read($buf, 0, $buf.Length) }
            [void]$stream.Read($buf, 0, $buf.Length)
          } catch { }
          if ($remainingClose -gt 0) {
            $remainingClose = $remainingClose - 1
            try { $stream.Close() } catch { }
            try { $client.Close() } catch { }
            continue
          }
          $payload = $enc.GetBytes($okBodyText)
          $header = "HTTP/1.1 $okStatus $okReason`r`nContent-Type: application/json`r`nContent-Length: $($payload.Length)`r`nConnection: close`r`n`r`n"
          $hb = [System.Text.Encoding]::ASCII.GetBytes($header)
          $stream.Write($hb, 0, $hb.Length)
          if ($payload.Length -gt 0) { $stream.Write($payload, 0, $payload.Length) }
          $stream.Flush()
        } catch { }
        finally {
          try { $client.Close() } catch { }
        }
      }
    }).AddArgument($tcp).AddArgument([int]$CloseAcceptCount).AddArgument($stopSrc.Token).AddArgument($SuccessStatusCode).AddArgument($SuccessReason).AddArgument($SuccessBody)
  $handle = $ps.BeginInvoke()
  return @{
    Port      = $port
    Tcp       = $tcp
    PS        = $ps
    Handle    = $handle
    Runspace  = $runspace
    StopToken = $stopSrc
    Uri       = ("http://127.0.0.1:{0}/api/v1/auth/me" -f $port)
  }
}

function Get-TestUtf8BodySha256Hex {
  param([AllowNull()][string] $Body)
  if ($null -eq $Body) { return $null }
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    return ([BitConverter]::ToString($sha.ComputeHash($bytes)).Replace("-", "").ToUpperInvariant())
  } finally {
    $sha.Dispose()
  }
}

function New-DisposableOrchestrationHarness {
  param(
    [Parameter(Mandatory = $true)][string] $ProjectName,
    [Parameter(Mandatory = $true)][string] $ApiImage,
    [Parameter(Mandatory = $true)][string] $WebImage,
    [Parameter(Mandatory = $true)][string] $PgImage,
    [string] $ExpectAlembic = "042_task_occurrence_dispositions",
    [switch] $DualNet
  )
  $state = @{
    ProjectName           = $ProjectName
    ApiImage              = $ApiImage
    WebImage              = $WebImage
    PgImage               = $PgImage
    ExpectAlembic         = $ExpectAlembic
    Containers            = @{}
    Networks              = New-Object System.Collections.Generic.List[string]
    Volumes               = New-Object System.Collections.Generic.List[string]
    FailUpPostgres        = $false
    FailUpApiWeb          = $false
    PsListFail            = $false
    SchedulerListFail     = $false
    WrongApiImage         = $false
    CleanupLeavesContainer = $false
    DownVolOk             = $true
    PostgresHealthy       = $true
    PostgresPsPollCount   = 0
    PostgresForceUnhealthy = $false
    ApiForceExited        = $false
    WebServiceAbsent      = $false
    LogsFail              = $false
    HttpMode              = "ok"
    HttpProbeCount        = 0
    HttpDelayUntil        = 3
    NextCid               = 1
    BadConfigEmptyHostIp  = $false
    DownCallCount         = 0
    ExecPostgresSqlCount  = 0
    ConfigFixturePath     = (Join-Path $PSScriptRoot "fixtures\preg5-disposable-compose-config.v2.json")
    DualNet               = [bool]$DualNet
    RestoredDataMode      = $false
    DbRestored            = $false
    FailPgRestore         = $false
    InventoryMismatch     = $false
    InventoryManifest     = $null
    PgRestoreCallCount    = 0
    DockerCpCount         = 0
    AuthUnauthProbeCount  = 0
  }

  $resolveRestoredSql = {
    param([string] $JoinedSql)
    $m = $state.InventoryManifest
    if ($null -eq $m) { return $state.ExpectAlembic }
    if ($JoinedSql -match 'pg_catalog\.pg_class' -and $JoinedSql -match 'pg_namespace') {
      if (-not $state.DbRestored) { return '0' }
    }
    if ($JoinedSql -match 'alembic_version') {
      if (-not $state.DbRestored) { return '' }
      return [string]$m.expect_alembic
    }
    if ($JoinedSql -match 'string_agg' -and $JoinedSql -match 'FROM users') {
      if ($state.InventoryMismatch) { return 'wrong-user-id' }
      return [string]$m.user_ids_csv
    }
    if ($JoinedSql -match 'count\(\*\)' -and $JoinedSql -match 'FROM users') {
      if ($state.InventoryMismatch) { return '1' }
      return [string]$m.user_count
    }
    if ($JoinedSql -match 'string_agg' -and $JoinedSql -match 'FROM tasks') {
      if ($state.InventoryMismatch) { return 'wrong-task-id' }
      return [string]$m.task_ids_csv
    }
    if ($JoinedSql -match 'count\(\*\)' -and $JoinedSql -match 'FROM tasks') {
      if ($state.InventoryMismatch) { return '589' }
      return [string]$m.task_count
    }
    if ($JoinedSql -match 'count\(\*\)' -and $JoinedSql -match 'user_settings') {
      if ($state.InventoryMismatch) { return '1' }
      return [string]$m.settings_count
    }
    if ($JoinedSql -match 'pg_catalog\.pg_class' -and $JoinedSql -match 'agent_credentials') {
      return [string]$m.agent_credentials
    }
    if ($JoinedSql -match 'agent_credentials') {
      return [string]$m.agent_credentials
    }
    return $state.ExpectAlembic
  }.GetNewClosure()

  $runner = {
    param([string[]]$DockerArgs, [string]$What, [int]$TimeoutMs)
    $cmd = $DockerArgs[0]

    if ($cmd -eq 'cp') {
      $state.DockerCpCount = $state.DockerCpCount + 1
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }

    if ($cmd -eq 'compose') {
      $joined = ($DockerArgs -join ' ')
      $upServices = @()
      for ($ui = 0; $ui -lt $DockerArgs.Count; $ui++) {
        if ($DockerArgs[$ui] -eq 'up') {
          for ($uj = $ui + 1; $uj -lt $DockerArgs.Count; $uj++) {
            $tok = $DockerArgs[$uj]
            if ($tok -match '^-') { continue }
            $upServices += $tok
          }
          break
        }
      }
      if ($joined -match 'config' -and $joined -match 'json') {
        if (-not (Test-Path -LiteralPath $state.ConfigFixturePath)) {
          throw "FAIL: missing compose config fixture $($state.ConfigFixturePath)"
        }
        $cfgObj = Get-Content -LiteralPath $state.ConfigFixturePath -Raw | ConvertFrom-Json
        $cfgObj.services.api.image = $state.ApiImage
        $cfgObj.services.web.image = $state.WebImage
        $cfgObj.services.postgres.image = $state.PgImage
        if ($state.BadConfigEmptyHostIp) {
          $cfgObj.services.api.ports[0].host_ip = ""
        }
        return @{ Code = 0; StdOut = ($cfgObj | ConvertTo-Json -Depth 20 -Compress); StdErr = ""; TimedOut = $false }
      }
      if ($joined -match '\bconfig\b' -and $joined -notmatch 'json') {
        return @{ Code = 0; StdOut = "services:`n  api:`n    image: $($state.ApiImage)"; StdErr = ""; TimedOut = $false }
      }
      if ($upServices -contains 'postgres') {
        if ($state.FailUpPostgres) { throw "FAIL: compose up postgres simulated exit 1" }
        foreach ($svc in @("postgres")) {
          $cid = "cid-$($state.ProjectName)-$svc-$($state.NextCid)"
          $state.NextCid++
          $img = $state.PgImage
          $state.Containers[$cid] = @{
            Id = $cid; Name = "$($state.ProjectName)-$svc-1"; Service = $svc
            Image = $img; Project = $state.ProjectName; Running = $true; Healthy = $state.PostgresHealthy
            DockerStatus = "running"; ExitCode = 0
          }
        }
        $net = "${state.ProjectName}_preg5_net"
        if ($state.Networks -notcontains $net) { [void]$state.Networks.Add($net) }
        if ($state.DualNet) {
          $pub = "${state.ProjectName}_preg5_publish"
          if ($state.Networks -notcontains $pub) { [void]$state.Networks.Add($pub) }
        }
        $vol = "${state.ProjectName}_preg5_pgdata"
        if ($state.Volumes -notcontains $vol) { [void]$state.Volumes.Add($vol) }
        return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
      }
      if (($upServices -contains 'api') -or ($upServices -contains 'web')) {
        if ($state.FailUpApiWeb) { throw "FAIL: compose up api web simulated exit 1" }
        $wantSvcs = @()
        if ($upServices -contains 'api') { $wantSvcs += 'api' }
        if ($upServices -contains 'web') { $wantSvcs += 'web' }
        foreach ($svc in $wantSvcs) {
          if ($svc -eq "web" -and $state.WebServiceAbsent) { continue }
          $cid = "cid-$($state.ProjectName)-$svc-$($state.NextCid)"
          $state.NextCid++
          if ($svc -eq "api" -and $state.WrongApiImage) { $img = "sha256:wrongdeadbeef" }
          elseif ($svc -eq "api") { $img = $state.ApiImage }
          else { $img = $state.WebImage }
          $state.Containers[$cid] = @{
            Id = $cid; Name = "$($state.ProjectName)-$svc-1"; Service = $svc
            Image = $img; Project = $state.ProjectName; Running = $true; Healthy = $true
            DockerStatus = "running"; ExitCode = 0
          }
          if ($svc -eq "api" -and $state.ApiForceExited) {
            $state.Containers[$cid].Running = $false
            $state.Containers[$cid].DockerStatus = "exited"
            $state.Containers[$cid].ExitCode = 1
          }
        }
        if ($state.DualNet) {
          $pub = "${state.ProjectName}_preg5_publish"
          if ($state.Networks -notcontains $pub) { [void]$state.Networks.Add($pub) }
        }
        return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
      }
      if ($joined -match '\bdown\b') {
        $state.DownCallCount = $state.DownCallCount + 1
        if (-not $state.DownVolOk) { throw "FAIL: compose down -v simulated exit 1" }
        if ($state.CleanupLeavesContainer) {
          # leave one container
          $keys = @($state.Containers.Keys)
          if ($keys.Count -gt 0) {
            $keep = $keys[0]
            foreach ($k in $keys) {
              if ($k -ne $keep) { $state.Containers.Remove($k) }
            }
          }
        } else {
          $state.Containers = @{}
        }
        $state.Networks.Clear()
        $state.Volumes.Clear()
        return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
      }
      if ($joined -match 'alembic' -and $joined -match 'upgrade') {
        return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
      }
      if ($joined -match 'alembic' -and $joined -match 'current') {
        return @{ Code = 0; StdOut = $state.ExpectAlembic; StdErr = ""; TimedOut = $false }
      }
      if ($joined -match '\blogs\b') {
        if ($state.LogsFail) { throw "FAIL: compose logs simulated exit 1" }
        $svc = "api"
        if ($joined -match '\bweb\b') { $svc = "web" }
        return @{ Code = 0; StdOut = ("[$svc] simulated log line 1`n[$svc] simulated log line 2"); StdErr = ""; TimedOut = $false }
      }
      if ($joined -match '\bps\b' -and $joined -match 'json') {
        if ($state.PostgresForceUnhealthy) {
          return @{ Code = 0; StdOut = '[{"Service":"postgres","Health":"unhealthy"}]'; StdErr = ""; TimedOut = $false }
        }
        $h = "starting"
        if ($state.PostgresHealthy) {
          $h = "healthy"
        } else {
          $seq = @("starting", "starting", "healthy")
          $idx = $state.PostgresPsPollCount
          if ($idx -ge $seq.Length) { $idx = $seq.Length - 1 }
          $h = $seq[$idx]
          $state.PostgresPsPollCount = $state.PostgresPsPollCount + 1
        }
        return @{ Code = 0; StdOut = "[{`"Service`":`"postgres`",`"Health`":`"$h`"}]"; StdErr = ""; TimedOut = $false }
      }
      $isComposeExec = $false
      for ($ei = 0; $ei -lt $DockerArgs.Count; $ei++) {
        if ($DockerArgs[$ei] -eq 'exec') { $isComposeExec = $true; break }
      }
      if ($isComposeExec -and $joined -match 'postgres' -and $joined -match 'pg_restore') {
        $state.PgRestoreCallCount = $state.PgRestoreCallCount + 1
        if ($state.FailPgRestore) { throw "FAIL: pg_restore simulated exit 1" }
        $state.DbRestored = $true
        return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
      }
      if ($isComposeExec -and $joined -match 'postgres' -and $joined -match 'psql') {
        $state.ExecPostgresSqlCount = $state.ExecPostgresSqlCount + 1
        $answer = $state.ExpectAlembic
        if ($state.RestoredDataMode) {
          $answer = & $resolveRestoredSql $joined
        }
        return @{ Code = 0; StdOut = $answer; StdErr = ""; TimedOut = $false }
      }
      if ($joined -match '\brun\b') {
        if ($joined -match 'alembic') {
          return @{ Code = 0; StdOut = $state.ExpectAlembic; StdErr = ""; TimedOut = $false }
        }
      }
      return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
    }

    if ($cmd -eq 'ps') {
      $filterProj = ($DockerArgs -join ' ') -match [regex]::Escape("label=com.docker.compose.project=$($state.ProjectName)")
      $filterSched = ($DockerArgs -join ' ') -match 'service=scheduler'
      if ($filterSched) {
        if ($state.SchedulerListFail) {
          return @{ Code = 1; StdOut = ""; StdErr = "simulated scheduler list fail"; TimedOut = $false }
        }
        return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
      }
      if ($filterProj -and $state.PsListFail) {
        return @{ Code = 1; StdOut = ""; StdErr = "simulated ps list fail"; TimedOut = $false }
      }
      $fmt = ""
      for ($i = 0; $i -lt $DockerArgs.Count; $i++) {
        if ($DockerArgs[$i] -eq '--format' -and ($i + 1) -lt $DockerArgs.Count) { $fmt = $DockerArgs[$i + 1] }
      }
      $svcFilter = $null
      if (($DockerArgs -join ' ') -match 'service=api') { $svcFilter = "api" }
      if (($DockerArgs -join ' ') -match 'service=web') { $svcFilter = "web" }
      $lines = New-Object System.Collections.Generic.List[string]
      foreach ($c in @($state.Containers.Values)) {
        if ($c.Project -ne $state.ProjectName) { continue }
        if ($null -ne $svcFilter -and $c.Service -ne $svcFilter) { continue }
        if ($fmt -eq '{{.ID}}|{{.Names}}|{{.Image}}') {
          $lines.Add("$($c.Id)|$($c.Name)|$($c.Image)")
        } elseif ($fmt -eq '{{.ID}}') {
          $lines.Add($c.Id)
        } elseif ($fmt -eq '{{.ID}} {{.Names}} {{.Label "com.docker.compose.project"}}') {
          $lines.Add("$($c.Id) $($c.Name) $($c.Project)")
        } else {
          $lines.Add($c.Id)
        }
      }
      return @{ Code = 0; StdOut = ($lines -join "`n"); StdErr = ""; TimedOut = $false }
    }

    if ($cmd -eq 'inspect') {
      $target = $DockerArgs[1]
      $fmt = ""
      for ($i = 0; $i -lt $DockerArgs.Count; $i++) {
        if ($DockerArgs[$i] -eq '--format' -and ($i + 1) -lt $DockerArgs.Count) { $fmt = $DockerArgs[$i + 1] }
      }
      $c = $null
      if ($state.Containers.ContainsKey($target)) { $c = $state.Containers[$target] }
      if ($null -eq $c) {
        return @{ Code = 1; StdOut = ""; StdErr = "Error: No such object: $target"; TimedOut = $false }
      }
      if ($fmt -eq '{{.Image}}') {
        return @{ Code = 0; StdOut = $c.Image; StdErr = ""; TimedOut = $false }
      }
      if ($fmt -eq '{{json .State}}') {
        $running = $false
        if ($c.ContainsKey('Running')) { $running = [bool]$c.Running }
        $status = "exited"
        if ($c.ContainsKey('DockerStatus')) { $status = [string]$c.DockerStatus }
        elseif ($running) { $status = "running" }
        $exitCode = 0
        if ($c.ContainsKey('ExitCode')) { $exitCode = [int]$c.ExitCode }
        # Real api/web images often have no HEALTHCHECK — omit Health from State JSON unless explicitly modeled.
        $stateObj = [ordered]@{
          Status   = $status
          Running  = $running
          ExitCode = $exitCode
        }
        if ($c.ContainsKey('IncludeHealthInState') -and $c.IncludeHealthInState) {
          $stateObj.Health = [ordered]@{ Status = "healthy" }
        }
        return @{ Code = 0; StdOut = ($stateObj | ConvertTo-Json -Compress); StdErr = ""; TimedOut = $false }
      }
      return @{ Code = 0; StdOut = $c.Id; StdErr = ""; TimedOut = $false }
    }

    if ($cmd -eq 'image' -and $DockerArgs.Count -ge 3 -and $DockerArgs[1] -eq 'inspect') {
      $ref = $DockerArgs[2]
      $id = $ref
      if ($ref -eq $state.ApiImage) { $id = $state.ApiImage }
      elseif ($ref -eq $state.WebImage) { $id = $state.WebImage }
      elseif ($ref -eq $state.PgImage) { $id = $state.PgImage }
      return @{ Code = 0; StdOut = $id; StdErr = ""; TimedOut = $false }
    }

    if ($cmd -eq 'network' -and $DockerArgs[1] -eq 'ls') {
      return @{ Code = 0; StdOut = ($state.Networks -join "`n"); StdErr = ""; TimedOut = $false }
    }
    if ($cmd -eq 'volume' -and $DockerArgs[1] -eq 'ls') {
      return @{ Code = 0; StdOut = ($state.Volumes -join "`n"); StdErr = ""; TimedOut = $false }
    }

    return @{ Code = 0; StdOut = ""; StdErr = ""; TimedOut = $false }
  }.GetNewClosure()

  return @{ State = $state; Runner = $runner }
}

function Initialize-DisposableOrchestrationFixture {
  param(
    [Parameter(Mandatory = $true)][string] $ScratchRoot,
    [Parameter(Mandatory = $true)][string] $ExportStamp,
    [Parameter(Mandatory = $true)][string] $AttemptId,
    [Parameter(Mandatory = $true)][string] $ApiImage,
    [Parameter(Mandatory = $true)][string] $WebImage
  )
  $stamp = $ExportStamp
  $parent = Join-Path $ScratchRoot "theplan-pre-g5-snap-$stamp"
  New-Item -ItemType Directory -Path $parent -Force | Out-Null
  $approvalPath = Join-Path $parent "audit-approval.json"
  if (-not (Test-Path -LiteralPath $approvalPath)) {
    (@{
        approved              = $true
        snapshot_api_image_id = $ApiImage
        snapshot_web_image_id = $WebImage
      } | ConvertTo-Json) | Set-Content -LiteralPath $approvalPath -Encoding utf8
  }
  return @{
    Parent       = $parent
    ApprovalPath = $approvalPath
    AttemptDir   = Join-Path $parent $AttemptId
  }
}

function Initialize-RestoredDataOrchestrationFixture {
  param(
    [Parameter(Mandatory = $true)][string] $ScratchRoot,
    [Parameter(Mandatory = $true)][string] $ExportStamp,
    [Parameter(Mandatory = $true)][string] $AttemptId,
    [Parameter(Mandatory = $true)][string] $ApiImage,
    [Parameter(Mandatory = $true)][string] $WebImage,
    [Parameter(Mandatory = $true)][string] $PgImage,
    [string] $InventoryManifestPath = ""
  )
  if ([string]::IsNullOrWhiteSpace($InventoryManifestPath)) {
    $InventoryManifestPath = Join-Path $PSScriptRoot "fixtures\preg5-g3b-042-restored-data-inventory-manifest.v1.json"
  }
  $manifest = Import-PreG5DisposableRestoredDataInventoryManifest -Path $InventoryManifestPath
  $manifestSha = (Get-PreG5FileSha256Hex -Path $InventoryManifestPath).ToUpperInvariant()
  $parent = Join-Path $ScratchRoot "theplan-pre-g5-snap-$ExportStamp"
  New-Item -ItemType Directory -Path $parent -Force | Out-Null
  $approvalPath = Join-Path $parent "audit-approval-restore.json"
  $authoritySource = [string]$manifest.inventory_authority_source
  if ([string]::IsNullOrWhiteSpace($authoritySource)) { $authoritySource = "G3B-1793594054" }
  (@{
      approved                    = $true
      snapshot_api_image_id       = $ApiImage
      snapshot_web_image_id       = $WebImage
      postgres_image_id           = $PgImage
      dump_path                   = [string]$manifest.dump_binding.path
      dump_sha256                 = ([string]$manifest.dump_binding.sha256).ToUpperInvariant()
      inventory_manifest_sha256   = $manifestSha
      dump_qualification          = "read_only_no_quiesce_not_g1"
      inventory_authority_source  = $authoritySource
    } | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath $approvalPath -Encoding utf8
  return @{
    Parent                = $parent
    ApprovalPath          = $approvalPath
    AttemptDir            = Join-Path $parent $AttemptId
    InventoryManifest     = $manifest
    InventoryManifestPath = $InventoryManifestPath
    DumpPath              = [string]$manifest.dump_binding.path
  }
}

function New-DisposableHttpProbeForState {
  param($State)
  return {
    param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
    $State.HttpProbeCount = $State.HttpProbeCount + 1
    if ($State.HttpMode -eq "refuse") {
      $obsRefuse = New-TestDisposableSyntheticHttpEndpointObservation -Uri $Uri -ExpectStatus $ExpectStatus `
        -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -Classification 'transport_fail' `
        -ProbeError ("FAIL: HTTP $Uri — Unable to connect to the remote server")
      Throw-DisposableHttpCheckFailed -Observation $obsRefuse
    }
    if ($State.HttpMode -eq "delay") {
      if ($State.HttpProbeCount -lt $State.HttpDelayUntil) {
        $obsDelay = New-TestDisposableSyntheticHttpEndpointObservation -Uri $Uri -ExpectStatus $ExpectStatus `
          -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -Classification 'transport_fail' `
          -ProbeError ("FAIL: HTTP $Uri — Unable to connect to the remote server")
        Throw-DisposableHttpCheckFailed -Observation $obsDelay
      }
      return (New-TestDisposableSyntheticHttpEndpointObservation -Uri $Uri -ExpectStatus $ExpectStatus `
          -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -Classification 'http_ok')
    }
    if ($State.HttpMode -eq "wrong") {
      if (-not [string]::IsNullOrWhiteSpace([string]$State.WrongHttpFixtureUri)) {
        $obs = Invoke-DisposableStartupHttpProbeCore -Uri $Uri -ExpectStatus $ExpectStatus `
          -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -TimeoutSec $TimeoutSec `
          -RequestUri ([string]$State.WrongHttpFixtureUri)
        Throw-DisposableHttpCheckFailed -Observation $obs
      }
      throw ("FAIL: HTTP $Uri status=502 want=$ExpectStatus body=bad gateway")
    }
    if ($State.HttpMode -eq "wrong_proxy_auth") {
      if ($Uri -match '18080/api/v1/auth/me') {
        $reqUri = [string]$State.WrongProxyFixtureUri
        if ([string]::IsNullOrWhiteSpace($reqUri)) {
          throw "orchestration: WrongProxyFixtureUri required for wrong_proxy_auth"
        }
        $obs = Invoke-DisposableStartupHttpProbeCore -Uri $Uri -ExpectStatus $ExpectStatus `
          -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -TimeoutSec $TimeoutSec `
          -RequestUri $reqUri
        Throw-DisposableHttpCheckFailed -Observation $obs
      }
      return (New-TestDisposableSyntheticHttpEndpointObservation -Uri $Uri -ExpectStatus $ExpectStatus `
          -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -Classification 'http_ok')
    }
    if ($State.HttpMode -eq "ok") {
      return (New-TestDisposableSyntheticHttpEndpointObservation -Uri $Uri -ExpectStatus $ExpectStatus `
          -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -Classification 'http_ok')
    }
    return (Invoke-DisposableStartupHttpProbe -Uri $Uri -ExpectStatus $ExpectStatus -BodyMustContain $BodyMustContain `
        -ExpectJsonCode $ExpectJsonCode -TimeoutSec $TimeoutSec)
  }.GetNewClosure()
}

function Invoke-DisposableOrchestrationTests {
  param(
    [scriptblock] $AssertTrue,
    [switch] $LiveSqlBoundary
  )

  $api = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b"
  $web = "sha256:636901afe16e8ffda36601af75f029e2b076287a2c5ca868ecedd42029351969"
  $pg  = "sha256:93d55776e04376e19adb2733e3ccebb4392ee7dd86d8ff238503b30fe719c84f"
  $compose = Join-Path $PSScriptRoot "compose.pre-g5-snapshot-disposable.yaml"
  $composeDual = Join-Path $PSScriptRoot "compose.pre-g5-snapshot-disposable-dual-net.yaml"
  $scratchBase = Join-Path (Get-PreG5CustodyRoot) ("preg5-disp-orch-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $scratchBase -Force | Out-Null

  $httpNoOp = {
    param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
  }

  try {
    $fixturePath = Join-Path $PSScriptRoot "fixtures\preg5-disposable-compose-config.v2.json"
    if (Test-Path -LiteralPath $fixturePath) {
      $fixtureRaw = Get-Content -LiteralPath $fixturePath -Raw
      try {
        Assert-DisposableComposeConfigStructured -ConfigJson $fixtureRaw `
          -ExpectApiImage $api -ExpectWebImage $web -ExpectPostgresImage $pg | Out-Null
        & $AssertTrue $true "real compose v2 fixture passes structured config (api/web omit volumes key)"
      } catch {
        & $AssertTrue $false "real fixture structured config: $($_.Exception.Message)"
      }
      try {
        $cfgBad = $fixtureRaw | ConvertFrom-Json
        $cfgBad.services.api.ports[0].host_ip = ""
        $badJson = ($cfgBad | ConvertTo-Json -Depth 25)
        Assert-DisposableComposeConfigStructured -ConfigJson $badJson `
          -ExpectApiImage $api -ExpectWebImage $web -ExpectPostgresImage $pg | Out-Null
        & $AssertTrue $false "empty host_ip should refuse"
      } catch {
        & $AssertTrue ($_.Exception.Message -match 'host_ip empty|127\.0\.0\.1') "empty host_ip refused"
      }
    } else {
      & $AssertTrue $false "missing compose config fixture at $fixturePath"
    }

    $dualFixturePath = Join-Path $PSScriptRoot "fixtures\preg5-disposable-compose-config.dual-net.v1.json"
    if (Test-Path -LiteralPath $dualFixturePath) {
      $dualRaw = Get-Content -LiteralPath $dualFixturePath -Raw
      try {
        Assert-DisposableComposeConfigStructuredDualNet -ConfigJson $dualRaw `
          -ExpectApiImage $api -ExpectWebImage $web -ExpectPostgresImage $pg | Out-Null
        & $AssertTrue $true "dual-net compose fixture passes structured DualNet config"
      } catch {
        & $AssertTrue $false "dual-net fixture structured config: $($_.Exception.Message)"
      }
    } else {
      & $AssertTrue $false "missing dual-net compose config fixture at $dualFixturePath"
    }

    # prior-success refusal (validation.receipt.json)
    $stampA = "20261102T055454Z-orchrefuse"
    $projA = "theplanpreg5snaporchrefusea"
    $attA = "disp-orch-refuse-val"
    $fxA = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampA `
      -AttemptId $attA -ApiImage $api -WebImage $web
    New-Item -ItemType Directory -Path $fxA.AttemptDir -Force | Out-Null
    Set-Content (Join-Path $fxA.AttemptDir "validation.receipt.json") -Value '{"startup_validation_ok":true}' -Encoding utf8
    $hA = New-DisposableOrchestrationHarness -ProjectName $projA -ApiImage $api -WebImage $web -PgImage $pg
    $script:PreG5DockerRunner = $hA.Runner
    $rA = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampA `
      -AttemptId $attA -ProjectName $projA -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxA.ApprovalPath `
      -SkipHttpChecks -HttpChecker $httpNoOp -ComposeTimeoutMs 5000 -PreflightHostPorts @()
    & $AssertTrue ($rA.ExitCode -ne 0) "disposable prior validation.receipt refuses rerun"
    & $AssertTrue ($rA.RefusalNoCleanup) "prior validation.receipt refuse skips cleanup"

    # partial first up after ownership
    $stampB = "20261102T055454Z-orchpgfail"
    $projB = "theplanpreg5snaporchpgfail"
    $attB = "disp-orch-pgfail"
    $fxB = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampB `
      -AttemptId $attB -ApiImage $api -WebImage $web
    $hB = New-DisposableOrchestrationHarness -ProjectName $projB -ApiImage $api -WebImage $web -PgImage $pg
    $hB.State.FailUpPostgres = $true
    $script:PreG5DockerRunner = $hB.Runner
    $rB = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampB `
      -AttemptId $attB -ProjectName $projB -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxB.ApprovalPath `
      -SkipHttpChecks -HttpChecker $httpNoOp -ComposeTimeoutMs 5000 -PreflightHostPorts @()
    & $AssertTrue ($rB.ExitCode -ne 0) "partial up postgres exits nonzero"
    & $AssertTrue (Test-Path (Join-Path $fxB.AttemptDir "failure.receipt.json")) "partial postgres writes failure.receipt"
    & $AssertTrue (-not (Test-Path (Join-Path $fxB.AttemptDir "validation.receipt.json"))) "partial postgres no success receipt"

    # partial api/web up
    $stampC = "20261102T055454Z-orchawfail"
    $projC = "theplanpreg5snaporchawfail"
    $attC = "disp-orch-awfail"
    $fxC = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampC `
      -AttemptId $attC -ApiImage $api -WebImage $web
    $hC = New-DisposableOrchestrationHarness -ProjectName $projC -ApiImage $api -WebImage $web -PgImage $pg
    $hC.State.FailUpApiWeb = $true
    $script:PreG5DockerRunner = $hC.Runner
    $rC = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampC `
      -AttemptId $attC -ProjectName $projC -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxC.ApprovalPath `
      -SkipHttpChecks -HttpChecker $httpNoOp -ComposeTimeoutMs 5000 -PreflightHostPorts @()
    & $AssertTrue ($rC.ExitCode -ne 0) "partial api/web up exits nonzero"
    & $AssertTrue (($rC.Notes -join ' ') -match 'refresh_owned:up_api_web_fail') "partial api/web failure refreshed owned capture"

    # list failure unresolved (Get-DisposableOwnedResources)
    $hList = New-DisposableOrchestrationHarness -ProjectName "proj-listfail" -ApiImage $api -WebImage $web -PgImage $pg
    $hList.State.PsListFail = $true
    $script:PreG5DockerRunner = $hList.Runner
    try {
      Get-DisposableOwnedResources -ProjectName "proj-listfail" | Out-Null
      & $AssertTrue $false "list fail should throw unresolved"
    } catch {
      & $AssertTrue ($_.Exception.Message -match 'UNRESOLVED') "list failure is unresolved not empty"
    }

    # wrong running image
    $stampD = "20261102T055454Z-orchwrongimg"
    $projD = "theplanpreg5snaporchwrongimg"
    $attD = "disp-orch-wrongimg"
    $fxD = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampD `
      -AttemptId $attD -ApiImage $api -WebImage $web
    $hD = New-DisposableOrchestrationHarness -ProjectName $projD -ApiImage $api -WebImage $web -PgImage $pg
    $hD.State.WrongApiImage = $true
    $script:PreG5DockerRunner = $hD.Runner
    $rD = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampD `
      -AttemptId $attD -ProjectName $projD -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxD.ApprovalPath `
      -SkipHttpChecks -HttpChecker $httpNoOp -ComposeTimeoutMs 5000 -PreflightHostPorts @()
    & $AssertTrue ($rD.ExitCode -ne 0) "wrong running image aborts"
    & $AssertTrue (-not (Test-Path (Join-Path $fxD.AttemptDir "validation.receipt.json"))) "wrong image no success receipt"

    # cleanup failure leaves container
    $stampE = "20261102T055454Z-orchclnfail"
    $projE = "theplanpreg5snaporchclnfail"
    $attE = "disp-orch-clnfail"
    $fxE = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampE `
      -AttemptId $attE -ApiImage $api -WebImage $web
    $hE = New-DisposableOrchestrationHarness -ProjectName $projE -ApiImage $api -WebImage $web -PgImage $pg
    $hE.State.CleanupLeavesContainer = $true
    $script:PreG5DockerRunner = $hE.Runner
    $rE = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampE `
      -AttemptId $attE -ProjectName $projE -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxE.ApprovalPath `
      -SkipHttpChecks -HttpChecker $httpNoOp -ComposeTimeoutMs 5000 -PreflightHostPorts @()
    & $AssertTrue ($rE.ExitCode -ne 0) "cleanup failure exits nonzero"
    & $AssertTrue (-not (Test-Path (Join-Path $fxE.AttemptDir "validation.receipt.json"))) "cleanup fail no validation.receipt"
    & $AssertTrue (-not (Test-Path (Join-Path $fxE.AttemptDir "cleanup.receipt.json"))) "cleanup fail no success cleanup.receipt"
    & $AssertTrue (Test-Path (Join-Path $fxE.AttemptDir "cleanup-outcome.final.json")) "cleanup fail writes cleanup-outcome.final"
    $failEPath = Join-Path $fxE.AttemptDir "failure.receipt.json"
    & $AssertTrue (Test-Path -LiteralPath $failEPath) "cleanup fail writes failure.receipt after cleanup"
    if (Test-Path -LiteralPath $failEPath) {
      $failE = Get-Content -LiteralPath $failEPath -Raw | ConvertFrom-Json
      & $AssertTrue ($null -ne $failE.cleanup_outcome) "failure receipt embeds cleanup outcome"
    }
    & $AssertTrue ($hE.State.DownCallCount -eq 1) "cleanup failure single down attempt"

    # rejected config before ownership: no down -v
    $stampH = "20261102T055454Z-orchbadcfg"
    $projH = "theplanpreg5snaporchbadcfg"
    $attH = "disp-orch-badcfg"
    $fxH = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampH `
      -AttemptId $attH -ApiImage $api -WebImage $web
    $hH = New-DisposableOrchestrationHarness -ProjectName $projH -ApiImage $api -WebImage $web -PgImage $pg
    $hH.State.BadConfigEmptyHostIp = $true
    $script:PreG5DockerRunner = $hH.Runner
    $rH = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampH `
      -AttemptId $attH -ProjectName $projH -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxH.ApprovalPath `
      -SkipHttpChecks -HttpChecker $httpNoOp -ComposeTimeoutMs 5000 -PreflightHostPorts @()
    & $AssertTrue ($rH.ExitCode -ne 0) "bad config exits nonzero"
    & $AssertTrue (-not $rH.OwnedProjectAtEnd) "bad config never owned project"
    & $AssertTrue ($hH.State.DownCallCount -eq 0) "bad config no compose down"
    & $AssertTrue (-not (Test-Path (Join-Path $fxH.AttemptDir "cleanup-outcome.final.json"))) "bad config no cleanup outcome"

    # happy path: success after cleanup
    $stampF = "20261102T055454Z-orchhappy"
    $projF = "theplanpreg5snaporchhappy"
    $attF = "disp-orch-happy"
    $fxF = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampF `
      -AttemptId $attF -ApiImage $api -WebImage $web
    $hF = New-DisposableOrchestrationHarness -ProjectName $projF -ApiImage $api -WebImage $web -PgImage $pg
    $script:PreG5DockerRunner = $hF.Runner
    $rF = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampF `
      -AttemptId $attF -ProjectName $projF -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxF.ApprovalPath `
      -SkipHttpChecks -HttpChecker $httpNoOp -ComposeTimeoutMs 5000 -PreflightHostPorts @()
    & $AssertTrue ($rF.ExitCode -eq 0) "happy path exit 0"
    & $AssertTrue (Test-Path (Join-Path $fxF.AttemptDir "validation.receipt.json")) "happy path validation.receipt after cleanup"
    & $AssertTrue (Test-Path (Join-Path $fxF.AttemptDir "cleanup.receipt.json")) "happy path cleanup.receipt"
    & $AssertTrue (Test-Path (Join-Path $fxF.AttemptDir "cleanup-outcome.final.json")) "happy path cleanup-outcome.final"
    & $AssertTrue ($hF.State.ExecPostgresSqlCount -eq 1) "happy path uses exec -T postgres for SQL"

    # DualNet happy path: SETUP_REQUIRED auth probes + receipt disclosure fields
    $stampDual = "20261102T055454Z-orchdualhappy"
    $projDual = "theplanpreg5snaporchdualhappy"
    $attDual = "disp-orch-dualhappy"
    $fxDual = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampDual `
      -AttemptId $attDual -ApiImage $api -WebImage $web
    $hDual = New-DisposableOrchestrationHarness -ProjectName $projDual -ApiImage $api -WebImage $web -PgImage $pg -DualNet
    $hDual.State.ConfigFixturePath = $dualFixturePath
    $hDual.State.AuthSetupProbeCount = 0
    $script:PreG5DockerRunner = $hDual.Runner
    $probeDual = {
      param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
      if ($Uri -match 'auth/me') {
        if ($ExpectJsonCode -cne 'SETUP_REQUIRED') {
          throw ("FAIL: auth/me ExpectJsonCode want SETUP_REQUIRED got=$ExpectJsonCode uri=$Uri")
        }
        $hDual.State.AuthSetupProbeCount = $hDual.State.AuthSetupProbeCount + 1
      }
      return (New-TestDisposableSyntheticHttpEndpointObservation -Uri $Uri -ExpectStatus $ExpectStatus `
          -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -Classification 'http_ok')
    }.GetNewClosure()
    $rDual = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampDual `
      -AttemptId $attDual -ProjectName $projDual -ComposeFile $composeDual -OwnedNetworkProfile DualNet -DualNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxDual.ApprovalPath `
      -HttpProbe $probeDual -HttpReadinessDeadlineMs 8000 -HttpReadinessPollSec 1 -ComposeTimeoutMs 8000 -PreflightHostPorts @()
    & $AssertTrue ($rDual.ExitCode -eq 0) "DualNet happy path exit 0"
    & $AssertTrue ($hDual.State.AuthSetupProbeCount -eq 2) "DualNet auth/me probes used SETUP_REQUIRED twice"
    $valDualPath = Join-Path $fxDual.AttemptDir "validation.receipt.json"
    & $AssertTrue (Test-Path -LiteralPath $valDualPath) "DualNet happy validation.receipt"
    if (Test-Path -LiteralPath $valDualPath) {
      $rcpDual = Get-Content -LiteralPath $valDualPath -Raw | ConvertFrom-Json
      & $AssertTrue ($rcpDual.dual_net -eq $true) "receipt dual_net=true"
      & $AssertTrue ($rcpDual.auth_content_expectation -ceq 'SETUP_REQUIRED') "receipt auth_content_expectation"
      & $AssertTrue ($rcpDual.option_b.option -ceq 'B') "receipt option_b.option"
      & $AssertTrue ($rcpDual.option_b.attempt_id_binding -ceq $attDual) "receipt option_b attempt binding"
      & $AssertTrue ($rcpDual.startup_validation_ok -eq $true) "receipt startup_validation_ok"
      & $AssertTrue ($rcpDual.restored_data_rollback_proof -eq $false) "receipt restored_data still false"
      & $AssertTrue ($rcpDual.next -match 'rollback') "receipt next still rollback-held"
      & $AssertTrue ($null -ne $rcpDual.http_endpoint_observations.path) "receipt references http-endpoint-observations"
      & $AssertTrue ($rcpDual.http_endpoint_observations.path -ceq 'http-endpoint-observations.json') "receipt http obs filename"
      & $AssertTrue ($rcpDual.http_endpoint_observations.sha256 -match '^[A-F0-9]{64}$') "receipt http obs sha256"
    }
    $httpObsDualPath = Join-Path $fxDual.AttemptDir "http-endpoint-observations.json"
    & $AssertTrue (Test-Path -LiteralPath $httpObsDualPath) "DualNet happy http-endpoint-observations.json"
    if (Test-Path -LiteralPath $httpObsDualPath) {
      $httpObsDual = Get-Content -LiteralPath $httpObsDualPath -Raw | ConvertFrom-Json
      & $AssertTrue ($httpObsDual.endpoint_count -eq 3) "DualNet http obs three endpoints"
      & $AssertTrue ($httpObsDual.endpoints.Count -eq 3) "DualNet http obs endpoints array"
      foreach ($row in @($httpObsDual.endpoints)) {
        & $AssertTrue ($row.classification -ceq 'http_ok') "DualNet http obs $($row.uri) http_ok"
        & $AssertTrue ($row.expected_status -eq $row.http_status) "DualNet http obs status match $($row.uri)"
      }
      $apiDirect = @($httpObsDual.endpoints | Where-Object { $_.uri -match '18000/api/v1/auth/me' } | Select-Object -First 1)
      $webShell = @($httpObsDual.endpoints | Where-Object { $_.uri -ceq 'http://127.0.0.1:18080/' } | Select-Object -First 1)
      $webProxy = @($httpObsDual.endpoints | Where-Object { $_.uri -match '18080/api/v1/auth/me' } | Select-Object -First 1)
      & $AssertTrue ($apiDirect.parsed_code -ceq 'SETUP_REQUIRED') "DualNet api direct parsed_code"
      & $AssertTrue ($webShell.body_must_contain -contains '<title>thePlan</title>') "DualNet web shell expectation recorded"
      & $AssertTrue ($webProxy.parsed_code -ceq 'SETUP_REQUIRED') "DualNet web proxy parsed_code"
    }

    # wrong web-proxied auth cannot succeed; artifact + owned cleanup still run
    $stampWrongProxy = "20261102T055454Z-orchwrongproxy"
    $projWrongProxy = "theplanpreg5snaporchwrongproxy"
    $attWrongProxy = "disp-orch-wrongproxy"
    $fxWrongProxy = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampWrongProxy `
      -AttemptId $attWrongProxy -ApiImage $api -WebImage $web
    $wrongProxyBody = '{"code":"UNAUTHENTICATED"}'
    $wrongProxySrv = Start-DisposableLocalHttpFixture -StatusCode 401 -Body $wrongProxyBody -ReasonPhrase "Unauthorized"
    try {
      $hWrongProxy = New-DisposableOrchestrationHarness -ProjectName $projWrongProxy -ApiImage $api -WebImage $web -PgImage $pg
      $hWrongProxy.State.HttpMode = "wrong_proxy_auth"
      $hWrongProxy.State.WrongProxyFixtureUri = $wrongProxySrv.Uri
      $script:PreG5DockerRunner = $hWrongProxy.Runner
      $probeWrongProxy = New-DisposableHttpProbeForState -State $hWrongProxy.State
      $rWrongProxy = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampWrongProxy `
        -AttemptId $attWrongProxy -ProjectName $projWrongProxy -ComposeFile $compose -OwnedNetworkProfile SingleNet `
        -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
        -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxWrongProxy.ApprovalPath `
        -HttpProbe $probeWrongProxy -HttpReadinessDeadlineMs 8000 -HttpReadinessPollSec 1 -ComposeTimeoutMs 8000 -PreflightHostPorts @()
      & $AssertTrue ($rWrongProxy.ExitCode -ne 0) "wrong web proxy auth exits nonzero"
      & $AssertTrue (-not (Test-Path (Join-Path $fxWrongProxy.AttemptDir "validation.receipt.json"))) "wrong proxy no validation.receipt"
      $httpObsWrongPath = Join-Path $fxWrongProxy.AttemptDir "http-endpoint-observations.json"
      & $AssertTrue (Test-Path -LiteralPath $httpObsWrongPath) "wrong proxy writes http-endpoint-observations before cleanup"
      if (Test-Path -LiteralPath $httpObsWrongPath) {
        $httpObsWrong = Get-Content -LiteralPath $httpObsWrongPath -Raw | ConvertFrom-Json
        & $AssertTrue ($httpObsWrong.endpoint_count -eq 3) "wrong proxy artifact has three endpoint rows"
        $badRow = @($httpObsWrong.endpoints | Where-Object { $_.uri -match '18080/api/v1/auth/me' } | Select-Object -First 1)
        & $AssertTrue ($badRow.classification -ceq 'mismatches') "wrong proxy endpoint classified mismatches"
        & $AssertTrue ($badRow.parsed_code -ceq 'UNAUTHENTICATED') "wrong proxy parsed_code from real body"
        & $AssertTrue ($badRow.body -ceq $wrongProxyBody) "wrong proxy artifact body matches loopback response"
        & $AssertTrue ($badRow.body_full_sha256 -ceq (Get-TestUtf8BodySha256Hex -Body $wrongProxyBody)) "wrong proxy body hash matches response"
      }
      & $AssertTrue (Test-Path (Join-Path $fxWrongProxy.AttemptDir "cleanup-outcome.final.json")) "wrong proxy owned cleanup still runs"
    } finally {
      Stop-DisposableLocalHttpFixture -Server $wrongProxySrv
    }

    # HTTP failure evidence integrity — real loopback responses, single probe per terminal content fail
    function Invoke-DisposableHttpEvidenceIntegrityCoreCase {
      param(
        [string] $CaseStamp,
        [string] $CaseAttempt,
        [string] $CaseProject,
        [int] $FixtureStatus,
        [string] $FixtureBody,
        [string] $ReasonPhrase = "Unauthorized",
        [scriptblock] $ExtraRowAsserts
      )
      $fx = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $CaseStamp `
        -AttemptId $CaseAttempt -ApiImage $api -WebImage $web
      $srv = Start-DisposableLocalHttpFixture -StatusCode $FixtureStatus -Body $FixtureBody -ReasonPhrase $ReasonPhrase
      try {
        $h = New-DisposableOrchestrationHarness -ProjectName $CaseProject -ApiImage $api -WebImage $web -PgImage $pg
        $h.State.HttpRealRequestCount = 0
        $script:PreG5DockerRunner = $h.Runner
        $probeEv = {
          param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
          if ($Uri -match '18000/api/v1/auth/me') {
            $h.State.HttpRealRequestCount = $h.State.HttpRealRequestCount + 1
            $obs = Invoke-DisposableStartupHttpProbeCore -Uri $Uri -ExpectStatus $ExpectStatus `
              -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -TimeoutSec $TimeoutSec `
              -RequestUri $srv.Uri
            Throw-DisposableHttpCheckFailed -Observation $obs
          }
          return (New-TestDisposableSyntheticHttpEndpointObservation -Uri $Uri -ExpectStatus $ExpectStatus `
              -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -Classification 'http_ok')
        }.GetNewClosure()
        $r = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $CaseStamp `
          -AttemptId $CaseAttempt -ProjectName $CaseProject -ComposeFile $compose -OwnedNetworkProfile SingleNet `
          -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
          -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fx.ApprovalPath `
          -HttpProbe $probeEv -HttpReadinessDeadlineMs 8000 -HttpReadinessPollSec 1 -ComposeTimeoutMs 8000 -PreflightHostPorts @()
        & $AssertTrue ($r.ExitCode -ne 0) "$CaseAttempt exits nonzero"
        & $AssertTrue ($h.State.HttpRealRequestCount -eq 1) "$CaseAttempt single real HTTP request on terminal content fail"
        $obsPath = Join-Path $fx.AttemptDir "http-endpoint-observations.json"
        & $AssertTrue (Test-Path -LiteralPath $obsPath) "$CaseAttempt writes http-endpoint-observations"
        if (Test-Path -LiteralPath $obsPath) {
          $doc = Get-Content -LiteralPath $obsPath -Raw | ConvertFrom-Json
          $row = @($doc.endpoints | Where-Object { $_.uri -match '18000/api/v1/auth/me' } | Select-Object -First 1)
          & $AssertTrue ($row.body -ceq $FixtureBody) "$CaseAttempt artifact body exact"
          & $AssertTrue ($row.body_full_sha256 -ceq (Get-TestUtf8BodySha256Hex -Body $FixtureBody)) "$CaseAttempt artifact body hash exact"
          & $ExtraRowAsserts $row
        }
      } finally {
        Stop-DisposableLocalHttpFixture -Server $srv
      }
    }

    Invoke-DisposableHttpEvidenceIntegrityCoreCase -CaseStamp "20261102T055454Z-orchhttpnocode" `
      -CaseAttempt "disp-orch-httpnocode" -CaseProject "theplanpreg5snaporchhttpnocode" `
      -FixtureStatus 401 -FixtureBody '{}' -ExtraRowAsserts {
        param($row)
        & $AssertTrue ($null -eq $row.parsed_code) "http missing code parsed_code null not invented"
        & $AssertTrue ($row.classification -ceq 'mismatches') "http missing code mismatches"
      }

    Invoke-DisposableHttpEvidenceIntegrityCoreCase -CaseStamp "20261102T055454Z-orchhttpbadjson" `
      -CaseAttempt "disp-orch-httpbadjson" -CaseProject "theplanpreg5snaporchbadjson" `
      -FixtureStatus 401 -FixtureBody '{not-json' -ExtraRowAsserts {
        param($row)
        & $AssertTrue ($null -eq $row.parsed_code) "malformed json parsed_code null"
        & $AssertTrue ($row.classification -ceq 'mismatches') "malformed json mismatches"
      }

    Invoke-DisposableHttpEvidenceIntegrityCoreCase -CaseStamp "20261102T055454Z-orchhttpwrongst" `
      -CaseAttempt "disp-orch-httpwrongst" -CaseProject "theplanpreg5snaporchwrongst" `
      -FixtureStatus 502 -FixtureBody 'bad gateway' -ReasonPhrase "Bad Gateway" -ExtraRowAsserts {
        param($row)
        & $AssertTrue ($row.http_status -eq 502) "wrong status records actual 502"
        & $AssertTrue ($row.classification -ceq 'mismatches') "wrong status mismatches"
      }

    # evidence write failure cannot yield startup success
    $stampObsFail = "20261102T055454Z-orchobsfail"
    $projObsFail = "theplanpreg5snaporchobsfail"
    $attObsFail = "disp-orch-obsfail"
    $fxObsFail = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampObsFail `
      -AttemptId $attObsFail -ApiImage $api -WebImage $web
    $hObsFail = New-DisposableOrchestrationHarness -ProjectName $projObsFail -ApiImage $api -WebImage $web -PgImage $pg
    $hObsFail.State.HttpMode = "ok"
    $script:PreG5DockerRunner = $hObsFail.Runner
    $script:PreG5DisposableFailHttpObservationsWrite = $true
    $probeObsFail = New-DisposableHttpProbeForState -State $hObsFail.State
    try {
      $rObsFail = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampObsFail `
        -AttemptId $attObsFail -ProjectName $projObsFail -ComposeFile $compose -OwnedNetworkProfile SingleNet `
        -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
        -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxObsFail.ApprovalPath `
        -HttpProbe $probeObsFail -HttpReadinessDeadlineMs 8000 -HttpReadinessPollSec 1 -ComposeTimeoutMs 8000 -PreflightHostPorts @()
      & $AssertTrue ($rObsFail.ExitCode -ne 0) "http obs write fail exits nonzero"
      & $AssertTrue (-not (Test-Path (Join-Path $fxObsFail.AttemptDir "validation.receipt.json"))) "http obs write fail no validation.receipt"
      & $AssertTrue (Test-Path (Join-Path $fxObsFail.AttemptDir "cleanup-outcome.final.json")) "http obs write fail owned cleanup still runs"
    } finally {
      $script:PreG5DisposableFailHttpObservationsWrite = $false
    }

    # scheduler list failure aborts
    $stampG = "20261102T055454Z-orchschedfail"
    $projG = "theplanpreg5snaporchsched"
    $attG = "disp-orch-schedfail"
    $fxG = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampG `
      -AttemptId $attG -ApiImage $api -WebImage $web
    $hG = New-DisposableOrchestrationHarness -ProjectName $projG -ApiImage $api -WebImage $web -PgImage $pg
    $hG.State.SchedulerListFail = $true
    $script:PreG5DockerRunner = $hG.Runner
    $rG = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampG `
      -AttemptId $attG -ProjectName $projG -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxG.ApprovalPath `
      -SkipHttpChecks -HttpChecker $httpNoOp -ComposeTimeoutMs 5000 -PreflightHostPorts @()
    & $AssertTrue ($rG.ExitCode -ne 0) "scheduler list fail aborts"

    try {
      Wait-DisposablePostgresHealthyExact -DeadlineUtc ([datetime]::UtcNow.AddSeconds(2)) `
        -GetPostgresPsJson { return '[{"Service":"postgres","Health":"unhealthy"}]' } -PollSec 1 | Out-Null
      & $AssertTrue $false "postgres unhealthy should fail immediately"
    } catch {
      & $AssertTrue ($_.Exception.Message -match 'unhealthy') "postgres exact Health=unhealthy fails fast"
    }

    # Real loopback: accept then close (ConnectionClosed) before valid SETUP_REQUIRED response
    $closeOnlySrv = Start-DisposableLocalHttpCloseOnlyFixture
    $closeOkSrv = Start-DisposableLocalHttpFixture -StatusCode 401 -Body '{"code":"SETUP_REQUIRED"}' -ReasonPhrase "Unauthorized"
    try {
      Start-Sleep -Milliseconds 200
      $closeProbeMetrics = @{ ProbeCount = 0 }
      $closeThenOkProbe = {
        param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
        $attempt = $closeProbeMetrics.ProbeCount + 1
        $closeProbeMetrics.ProbeCount = $attempt
        $fetchUri = if ($attempt -eq 1) { $closeOnlySrv.Uri } else { $closeOkSrv.Uri }
        $obs = Invoke-DisposableStartupHttpProbeCore -Uri $Uri -ExpectStatus $ExpectStatus `
          -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -TimeoutSec $TimeoutSec `
          -RequestUri $fetchUri
        if ($obs.classification -ne 'http_ok') { Throw-DisposableHttpCheckFailed -Observation $obs }
        $obs
      }.GetNewClosure()
      $closeObs = $null
      try {
        $closeObs = Invoke-DisposableHttpCheckWithReadiness -Uri "http://127.0.0.1:18000/api/v1/auth/me" `
          -ExpectStatus 401 -ExpectJsonCode "SETUP_REQUIRED" -DeadlineUtc ([datetime]::UtcNow.AddSeconds(12)) `
          -PerRequestTimeoutSec 5 -PollSec 1 -ProbeScriptBlock $closeThenOkProbe
      } catch {
        & $AssertTrue $false "loopback close-then-success readiness threw: $($_.Exception.Message)"
      }
      & $AssertTrue ($null -ne $closeObs) "loopback close-then-success returned observation"
      & $AssertTrue ($closeObs.classification -ceq 'http_ok') "loopback close-then-success readiness http_ok"
      & $AssertTrue ($closeProbeMetrics.ProbeCount -ge 2) "loopback close-then-success retried transport_fail"
      & $AssertTrue ($closeObs.parsed_code -ceq 'SETUP_REQUIRED') "loopback close-then-success parsed_code"
    } finally {
      Stop-DisposableLocalHttpFixture -Server $closeOnlySrv
      Stop-DisposableLocalHttpFixture -Server $closeOkSrv
    }

    # Real loopback: persistent close until deadline; transport_fail obs preserved (null body hash)
    $persistCloseSrv = Start-DisposableLocalHttpCloseOnlyFixture
    try {
      $persistCloseMetrics = @{ ProbeCount = 0 }
      $persistCloseProbe = {
        param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
        $persistCloseMetrics.ProbeCount = $persistCloseMetrics.ProbeCount + 1
        $obs = Invoke-DisposableStartupHttpProbeCore -Uri $Uri -ExpectStatus $ExpectStatus `
          -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -TimeoutSec $TimeoutSec `
          -RequestUri $persistCloseSrv.Uri
        if ($obs.classification -ne 'http_ok') { Throw-DisposableHttpCheckFailed -Observation $obs }
        $obs
      }.GetNewClosure()
      $persistErr = $null
      try {
        Invoke-DisposableHttpCheckWithReadiness -Uri "http://127.0.0.1:18000/api/v1/auth/me" `
          -ExpectStatus 401 -ExpectJsonCode "SETUP_REQUIRED" -DeadlineUtc ([datetime]::UtcNow.AddSeconds(6)) `
          -PerRequestTimeoutSec 2 -PollSec 1 -ProbeScriptBlock $persistCloseProbe | Out-Null
        & $AssertTrue $false "persistent loopback close should fail at deadline"
      } catch {
        $persistErr = $_
      }
      & $AssertTrue ($null -ne $persistErr) "persistent close threw"
      & $AssertTrue ($persistErr.Exception.Message -match 'transport-not-ready') "persistent close deadline message"
      $persistObs = Get-DisposableHttpEndpointObservationFromErrorRecord -ErrorRecord $persistErr
      & $AssertTrue ($null -ne $persistObs) "persistent close observation on exception"
      & $AssertTrue ($persistObs.classification -ceq 'transport_fail') "persistent close transport_fail classification"
      & $AssertTrue ($null -eq $persistObs.body) "persistent close null body not empty string"
      & $AssertTrue ($null -eq $persistObs.body_full_sha256) "persistent close null body hash not E3B0"
      & $AssertTrue ($persistCloseMetrics.ProbeCount -ge 2) "persistent close polled more than once"
    } finally {
      Stop-DisposableLocalHttpFixture -Server $persistCloseSrv
    }

    # HTTP delayed transport readiness then success
    $stampI = "20261102T055454Z-orchhttpdelay"
    $projI = "theplanpreg5snaporchhttpdelay"
    $attI = "disp-orch-httpdelay"
    $fxI = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampI `
      -AttemptId $attI -ApiImage $api -WebImage $web
    $hI = New-DisposableOrchestrationHarness -ProjectName $projI -ApiImage $api -WebImage $web -PgImage $pg
    $hI.State.HttpMode = "delay"
    $hI.State.HttpDelayUntil = 2
    $script:PreG5DockerRunner = $hI.Runner
    $probeI = New-DisposableHttpProbeForState -State $hI.State
    $rI = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampI `
      -AttemptId $attI -ProjectName $projI -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxI.ApprovalPath `
      -HttpProbe $probeI -HttpReadinessDeadlineMs 8000 -HttpReadinessPollSec 1 -ComposeTimeoutMs 8000 -PreflightHostPorts @()
    & $AssertTrue ($rI.ExitCode -eq 0) "delayed HTTP readiness eventual success"
    & $AssertTrue ($hI.State.HttpProbeCount -ge 2) "delayed HTTP polled transport before success"

    # permanent transport refusal until deadline
    $stampJ = "20261102T055454Z-orchhttpref"
    $projJ = "theplanpreg5snaporchhttpref"
    $attJ = "disp-orch-httpref"
    $fxJ = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampJ `
      -AttemptId $attJ -ApiImage $api -WebImage $web
    $hJ = New-DisposableOrchestrationHarness -ProjectName $projJ -ApiImage $api -WebImage $web -PgImage $pg
    $hJ.State.HttpMode = "refuse"
    $script:PreG5DockerRunner = $hJ.Runner
    $probeJ = New-DisposableHttpProbeForState -State $hJ.State
    $rJ = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampJ `
      -AttemptId $attJ -ProjectName $projJ -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxJ.ApprovalPath `
      -HttpProbe $probeJ -HttpReadinessDeadlineMs 2500 -HttpReadinessPollSec 1 -ComposeTimeoutMs 8000 -PreflightHostPorts @()
    & $AssertTrue ($rJ.ExitCode -ne 0) "permanent transport refusal exits nonzero"
    & $AssertTrue (($rJ.Notes -join ' ') -match 'transport-not-ready') "transport refusal fails at deadline"
    $httpObsJPath = Join-Path $fxJ.AttemptDir "http-endpoint-observations.json"
    if (Test-Path -LiteralPath $httpObsJPath) {
      $httpObsJ = Get-Content -LiteralPath $httpObsJPath -Raw | ConvertFrom-Json
      $rowJ = @($httpObsJ.endpoints | Select-Object -First 1)
      & $AssertTrue ($rowJ.classification -ceq 'transport_fail') "refuse deadline artifact transport_fail"
      & $AssertTrue ([string]::IsNullOrWhiteSpace([string]$rowJ.body_full_sha256)) "refuse deadline null body hash"
    }

    # unexpected HTTP status fails immediately (no wait-out)
    $stampK = "20261102T055454Z-orchhttp502"
    $projK = "theplanpreg5snaporchhttp502"
    $attK = "disp-orch-http502"
    $fxK = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampK `
      -AttemptId $attK -ApiImage $api -WebImage $web
    $http502Body = 'bad gateway'
    $http502Srv = Start-DisposableLocalHttpFixture -StatusCode 502 -Body $http502Body -ReasonPhrase "Bad Gateway"
    try {
      $hK = New-DisposableOrchestrationHarness -ProjectName $projK -ApiImage $api -WebImage $web -PgImage $pg
      $hK.State.HttpMode = "wrong"
      $hK.State.WrongHttpFixtureUri = $http502Srv.Uri
      $script:PreG5DockerRunner = $hK.Runner
      $probeK = New-DisposableHttpProbeForState -State $hK.State
      $rK = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampK `
        -AttemptId $attK -ProjectName $projK -ComposeFile $compose -OwnedNetworkProfile SingleNet `
        -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
        -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxK.ApprovalPath `
        -HttpProbe $probeK -HttpReadinessDeadlineMs 8000 -HttpReadinessPollSec 1 -ComposeTimeoutMs 8000 -PreflightHostPorts @()
      & $AssertTrue ($rK.ExitCode -ne 0) "unexpected HTTP status aborts"
      & $AssertTrue ($hK.State.HttpProbeCount -eq 1) "unexpected HTTP no readiness wait-out"
      $notesK = ($rK.Notes -join ' ')
      & $AssertTrue (($notesK -match 'status=502') -or ($notesK -match '502')) "unexpected HTTP status captured"
      $httpObsKPath = Join-Path $fxK.AttemptDir "http-endpoint-observations.json"
      if (Test-Path -LiteralPath $httpObsKPath) {
        $httpObsK = Get-Content -LiteralPath $httpObsKPath -Raw | ConvertFrom-Json
        $rowK = @($httpObsK.endpoints | Select-Object -First 1)
        & $AssertTrue ($rowK.body -ceq $http502Body) "http502 artifact body from loopback not inferred"
      }
    } finally {
      Stop-DisposableLocalHttpFixture -Server $http502Srv
    }

    # process exit captures diagnostics before cleanup
    $stampL = "20261102T055454Z-orchapiexit"
    $projL = "theplanpreg5snaporchapiexit"
    $attL = "disp-orch-apiexit"
    $fxL = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampL `
      -AttemptId $attL -ApiImage $api -WebImage $web
    $hL = New-DisposableOrchestrationHarness -ProjectName $projL -ApiImage $api -WebImage $web -PgImage $pg
    $hL.State.ApiForceExited = $true
    $script:PreG5DockerRunner = $hL.Runner
    $rL = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampL `
      -AttemptId $attL -ProjectName $projL -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxL.ApprovalPath `
      -SkipHttpChecks -HttpChecker $httpNoOp -ComposeTimeoutMs 8000 -PreflightHostPorts @()
    & $AssertTrue ($rL.ExitCode -ne 0) "api exited fails"
    & $AssertTrue (Test-Path (Join-Path $fxL.AttemptDir "failure-diagnostics.json")) "api exit writes failure-diagnostics"
    if (Test-Path (Join-Path $fxL.AttemptDir "failure-diagnostics.json")) {
      $diagL = Get-Content (Join-Path $fxL.AttemptDir "failure-diagnostics.json") -Raw | ConvertFrom-Json
      & $AssertTrue ($diagL.api.Status -ceq "exited") "exited api diagnostics capture real Status without Health"
      & $AssertTrue ($diagL.api.Running -eq $false) "exited api Running=false not parse_fail null"
      & $AssertTrue ($null -eq $diagL.api.Health) "exited api Health absent/null ok"
    }
    & $AssertTrue (Test-Path (Join-Path $fxL.AttemptDir "cleanup-outcome.final.json")) "api exit still cleans up"

    # real Docker State JSON: running, no Health key — runtime guard must pass
    $hN = New-DisposableOrchestrationHarness -ProjectName "theplanpreg5snaporchnostatehealth" -ApiImage $api -WebImage $web -PgImage $pg
    $cidN = "cid-theplanpreg5snaporchnostatehealth-api-1"
    $hN.State.Containers[$cidN] = @{
      Id = $cidN; Name = "theplanpreg5snaporchnostatehealth-api-1"; Service = "api"
      Image = $api; Project = "theplanpreg5snaporchnostatehealth"; Running = $true
      DockerStatus = "running"; ExitCode = 0
    }
    $script:PreG5DockerRunner = $hN.Runner
    $snapN = Get-DisposableContainerStateSnapshot -ContainerId $cidN
    & $AssertTrue ($snapN.Status -ceq "running") "state snapshot Status when Health omitted"
    & $AssertTrue ($snapN.Running -eq $true) "state snapshot Running when Health omitted"
    & $AssertTrue ($snapN.ExitCode -eq 0) "state snapshot ExitCode when Health omitted"
    & $AssertTrue ($null -eq $snapN.Health) "state snapshot Health null when omitted"
    & $AssertTrue ($snapN.Status -cne "inspect_parse_fail") "no inspect_parse_fail without Health"
    Assert-DisposableContainerRuntimeRunning -ContainerId $cidN -ServiceName "api" | Out-Null
    & $AssertTrue $true "runtime running guard accepts no-Health state"

    # absent web service id — api/web collected independently; cleanup still runs
    $stampO = "20261102T055454Z-orchwebabs"
    $projO = "theplanpreg5snaporchwebabs"
    $attO = "disp-orch-webabs"
    $fxO = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampO `
      -AttemptId $attO -ApiImage $api -WebImage $web
    $hO = New-DisposableOrchestrationHarness -ProjectName $projO -ApiImage $api -WebImage $web -PgImage $pg
    $hO.State.WebServiceAbsent = $true
    $script:PreG5DockerRunner = $hO.Runner
    $rO = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampO `
      -AttemptId $attO -ProjectName $projO -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxO.ApprovalPath `
      -SkipHttpChecks -HttpChecker $httpNoOp -ComposeTimeoutMs 8000 -PreflightHostPorts @()
    & $AssertTrue ($rO.ExitCode -ne 0) "absent web service fails validation"
    & $AssertTrue (Test-Path (Join-Path $fxO.AttemptDir "failure-diagnostics.json")) "absent web still writes diagnostics"
    $diagO = Get-Content (Join-Path $fxO.AttemptDir "failure-diagnostics.json") -Raw | ConvertFrom-Json
    & $AssertTrue ($diagO.api.Status -ceq "running") "absent web still captures api state"
    & $AssertTrue ($diagO.web.Status -ceq "missing") "absent web service reported missing not binding fail"
    & $AssertTrue (Test-Path (Join-Path $fxO.AttemptDir "cleanup-outcome.final.json")) "absent web still cleans up"

    # --- Restored-data proof corridor (injected; no live Docker restore) ---
    try {
      $boundarySql = Get-PreG5DisposableAgentCredentialsAbsentProbeSql
      Test-PreG5DisposableAgentCredentialsAbsentProbeSqlText -Sql $boundarySql | Out-Null
      & $AssertTrue $true "agent_credentials absent probe SQL text boundary ok"
      if ($LiveSqlBoundary) {
        $savedRunnerForBoundary = $script:PreG5DockerRunner
        $script:PreG5DockerRunner = $null
        try {
          $boundaryProof = Invoke-PreG5DisposableAgentCredentialsAbsentSqlBoundaryProof -DockerTimeoutMs 120000 -AllowLivePostgres
          & $AssertTrue ($boundaryProof.live_postgres -eq $true) "agent_credentials absent probe SQL live postgres boundary ok"
          & $AssertTrue ($boundaryProof.mode -ceq 'live_postgres') "agent_credentials SQL boundary mode live_postgres"
        } finally {
          $script:PreG5DockerRunner = $savedRunnerForBoundary
        }
      } else {
        $boundaryProof = Invoke-PreG5DisposableAgentCredentialsAbsentSqlBoundaryProof -DockerTimeoutMs 120000
        & $AssertTrue ($boundaryProof.mode -ceq 'skipped') "agent_credentials SQL live boundary skipped without opt-in"
        & $AssertTrue ($boundaryProof.live_postgres -eq $false) "agent_credentials SQL boundary not live in default suite"
        & $AssertTrue ($boundaryProof.skip_reason -ceq 'not_opt_in') "agent_credentials SQL boundary skip_reason not_opt_in"
      }
    } catch {
      & $AssertTrue $false "agent_credentials SQL boundary: $($_.Exception.Message)"
    }

    $restoreManifestPath = Join-Path $PSScriptRoot "fixtures\preg5-g3b-042-restored-data-inventory-manifest.v1.json"

    $stampRestoreHappy = "20261102T055454Z-orchrestorehappy"
    $projRestoreHappy = "theplanpreg5snaporchrestorehappy"
    $attRestoreHappy = "disp-orch-restore-happy"
    $fxRestoreHappy = Initialize-RestoredDataOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampRestoreHappy `
      -AttemptId $attRestoreHappy -ApiImage $api -WebImage $web -PgImage $pg -InventoryManifestPath $restoreManifestPath
    $hRestoreHappy = New-DisposableOrchestrationHarness -ProjectName $projRestoreHappy -ApiImage $api -WebImage $web -PgImage $pg -DualNet
    $hRestoreHappy.State.ConfigFixturePath = $dualFixturePath
    $hRestoreHappy.State.RestoredDataMode = $true
    $hRestoreHappy.State.InventoryManifest = $fxRestoreHappy.InventoryManifest
    $script:PreG5DockerRunner = $hRestoreHappy.Runner
    $probeRestoreHappy = {
      param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
      if ($Uri -match 'auth/me') {
        if ($ExpectJsonCode -cne 'UNAUTHENTICATED') {
          throw ("FAIL: restored auth/me ExpectJsonCode want UNAUTHENTICATED got=$ExpectJsonCode uri=$Uri")
        }
        $hRestoreHappy.State.AuthUnauthProbeCount = $hRestoreHappy.State.AuthUnauthProbeCount + 1
      }
      return (New-TestDisposableSyntheticHttpEndpointObservation -Uri $Uri -ExpectStatus $ExpectStatus `
          -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -Classification 'http_ok')
    }.GetNewClosure()
    $rRestoreHappy = Invoke-PreG5Disposable042RestoredDataProofCore -ScratchRoot $scratchBase -ExportStamp $stampRestoreHappy `
      -AttemptId $attRestoreHappy -ProjectName $projRestoreHappy -ComposeFile $composeDual -OwnedNetworkProfile DualNet -DualNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxRestoreHappy.ApprovalPath `
      -DumpPath $fxRestoreHappy.DumpPath -InventoryManifestPath $restoreManifestPath `
      -HttpProbe $probeRestoreHappy -HttpReadinessDeadlineMs 8000 -HttpReadinessPollSec 1 -ComposeTimeoutMs 8000 -PreflightHostPorts @()
    & $AssertTrue ($rRestoreHappy.ExitCode -eq 0) "restored-data happy path exit 0"
    & $AssertTrue ($hRestoreHappy.State.PgRestoreCallCount -eq 1) "restored-data pg_restore invoked once"
    & $AssertTrue ($hRestoreHappy.State.DockerCpCount -ge 1) "restored-data docker cp dump"
    & $AssertTrue ($hRestoreHappy.State.AuthUnauthProbeCount -eq 2) "restored-data UNAUTHENTICATED auth probes"
    $valRestorePath = Join-Path $fxRestoreHappy.AttemptDir "validation.receipt.json"
    if (Test-Path -LiteralPath $valRestorePath) {
      $rcpRestore = Get-Content -LiteralPath $valRestorePath -Raw | ConvertFrom-Json
      & $AssertTrue ($rcpRestore.restored_data_rollback_proof -eq $true) "restored receipt proof flag true"
      & $AssertTrue ($rcpRestore.not_backup_restore -eq $false) "restored receipt not_backup_restore false"
      & $AssertTrue ($rcpRestore.schema_method -ceq 'pg_restore_bound_dump_into_disposable_042') "restored receipt schema_method"
      & $AssertTrue ($rcpRestore.startup_validation_ok -eq $false) "restored receipt startup_validation_ok false"
      & $AssertTrue ($rcpRestore.auth_content_expectation -ceq 'UNAUTHENTICATED') "restored receipt auth expectation"
      & $AssertTrue ($null -ne $rcpRestore.dump_binding.path) "restored receipt dump_binding"
      & $AssertTrue ($rcpRestore.agent_credentials_absent -eq $true) "restored receipt agent_credentials_absent"
      & $AssertTrue ($rcpRestore.inventory_authority.user_settings -eq 2) "restored receipt inventory_authority user_settings"
      & $AssertTrue ($null -ne $rcpRestore.inventory_observations.path) "restored receipt inventory_observations ref"
      & $AssertTrue (Test-Path (Join-Path $fxRestoreHappy.AttemptDir "inventory-observations.json")) "restored inventory-observations artifact"
      & $AssertTrue (Test-Path (Join-Path $fxRestoreHappy.AttemptDir "pg-restore-outcome.json")) "restored pg-restore-outcome artifact"
      $invObs = Get-Content (Join-Path $fxRestoreHappy.AttemptDir "inventory-observations.json") -Raw | ConvertFrom-Json
      & $AssertTrue ($invObs.user_ids_csv.Length -gt 10) "inventory observations persist user_ids_csv"
      & $AssertTrue ($invObs.task_ids_csv.Length -gt 10) "inventory observations persist task_ids_csv"
    }

    $stampRestoreInv = "20261102T055454Z-orchrestoreinv"
    $projRestoreInv = "theplanpreg5snaporchrestoreinv"
    $attRestoreInv = "disp-orch-restore-inv"
    $fxRestoreInv = Initialize-RestoredDataOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampRestoreInv `
      -AttemptId $attRestoreInv -ApiImage $api -WebImage $web -PgImage $pg -InventoryManifestPath $restoreManifestPath
    $hRestoreInv = New-DisposableOrchestrationHarness -ProjectName $projRestoreInv -ApiImage $api -WebImage $web -PgImage $pg -DualNet
    $hRestoreInv.State.ConfigFixturePath = $dualFixturePath
    $hRestoreInv.State.RestoredDataMode = $true
    $hRestoreInv.State.InventoryManifest = $fxRestoreInv.InventoryManifest
    $hRestoreInv.State.InventoryMismatch = $true
    $script:PreG5DockerRunner = $hRestoreInv.Runner
    $rRestoreInv = Invoke-PreG5Disposable042RestoredDataProofCore -ScratchRoot $scratchBase -ExportStamp $stampRestoreInv `
      -AttemptId $attRestoreInv -ProjectName $projRestoreInv -ComposeFile $composeDual -OwnedNetworkProfile DualNet -DualNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxRestoreInv.ApprovalPath `
      -DumpPath $fxRestoreInv.DumpPath -InventoryManifestPath $restoreManifestPath `
      -SkipHttpChecks -ComposeTimeoutMs 8000 -PreflightHostPorts @()
    & $AssertTrue ($rRestoreInv.ExitCode -ne 0) "restored inventory mismatch exits nonzero"
    & $AssertTrue (-not (Test-Path (Join-Path $fxRestoreInv.AttemptDir "validation.receipt.json"))) "inventory mismatch no success receipt"
    & $AssertTrue (Test-Path (Join-Path $fxRestoreInv.AttemptDir "inventory-observations.json")) "inventory mismatch writes observations before fail"
    & $AssertTrue (Test-Path (Join-Path $fxRestoreInv.AttemptDir "cleanup-outcome.final.json")) "inventory mismatch still cleans up"

    $stampRestoreWrongAuth = "20261102T055454Z-orchrestorewrongauth"
    $projRestoreWrongAuth = "theplanpreg5snaporchrestorewrongauth"
    $attRestoreWrongAuth = "disp-orch-restore-wrongauth"
    $fxRestoreWrongAuth = Initialize-RestoredDataOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampRestoreWrongAuth `
      -AttemptId $attRestoreWrongAuth -ApiImage $api -WebImage $web -PgImage $pg -InventoryManifestPath $restoreManifestPath
    $wrongAuthBody = '{"code":"SETUP_REQUIRED"}'
    $wrongAuthSrv = Start-DisposableLocalHttpFixture -StatusCode 401 -Body $wrongAuthBody -ReasonPhrase "Unauthorized"
    try {
      $hRestoreWrongAuth = New-DisposableOrchestrationHarness -ProjectName $projRestoreWrongAuth -ApiImage $api -WebImage $web -PgImage $pg -DualNet
      $hRestoreWrongAuth.State.ConfigFixturePath = $dualFixturePath
      $hRestoreWrongAuth.State.RestoredDataMode = $true
      $hRestoreWrongAuth.State.InventoryManifest = $fxRestoreWrongAuth.InventoryManifest
      $hRestoreWrongAuth.State.HttpMode = "wrong_proxy_auth"
      $hRestoreWrongAuth.State.WrongProxyFixtureUri = $wrongAuthSrv.Uri
      $script:PreG5DockerRunner = $hRestoreWrongAuth.Runner
      $probeRestoreWrongAuth = {
        param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
        if ($Uri -match '18080/api/v1/auth/me') {
          $obs = Invoke-DisposableStartupHttpProbeCore -Uri $Uri -ExpectStatus $ExpectStatus `
            -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -TimeoutSec $TimeoutSec `
            -RequestUri $wrongAuthSrv.Uri
          Throw-DisposableHttpCheckFailed -Observation $obs
        }
        return (New-TestDisposableSyntheticHttpEndpointObservation -Uri $Uri -ExpectStatus $ExpectStatus `
            -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -Classification 'http_ok')
      }.GetNewClosure()
      $rRestoreWrongAuth = Invoke-PreG5Disposable042RestoredDataProofCore -ScratchRoot $scratchBase -ExportStamp $stampRestoreWrongAuth `
        -AttemptId $attRestoreWrongAuth -ProjectName $projRestoreWrongAuth -ComposeFile $composeDual -OwnedNetworkProfile DualNet -DualNet `
        -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
        -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxRestoreWrongAuth.ApprovalPath `
        -DumpPath $fxRestoreWrongAuth.DumpPath -InventoryManifestPath $restoreManifestPath `
        -HttpProbe $probeRestoreWrongAuth -HttpReadinessDeadlineMs 8000 -HttpReadinessPollSec 1 -ComposeTimeoutMs 8000 -PreflightHostPorts @()
      & $AssertTrue ($rRestoreWrongAuth.ExitCode -ne 0) "restored SETUP_REQUIRED vs UNAUTHENTICATED exits nonzero"
      $httpObsWrongAuthPath = Join-Path $fxRestoreWrongAuth.AttemptDir "http-endpoint-observations.json"
      & $AssertTrue (Test-Path -LiteralPath $httpObsWrongAuthPath) "restored wrong auth writes http-endpoint-observations"
      if (Test-Path -LiteralPath $httpObsWrongAuthPath) {
        $httpObsWrongAuth = Get-Content -LiteralPath $httpObsWrongAuthPath -Raw | ConvertFrom-Json
        $badAuthRow = @($httpObsWrongAuth.endpoints | Where-Object { $_.uri -match '18080/api/v1/auth/me' } | Select-Object -First 1)
        & $AssertTrue ($badAuthRow.parsed_code -ceq 'SETUP_REQUIRED') "wrong auth parsed_code SETUP_REQUIRED"
        & $AssertTrue ($badAuthRow.classification -ceq 'mismatches') "wrong auth classification mismatches"
      }
      & $AssertTrue (Test-Path (Join-Path $fxRestoreWrongAuth.AttemptDir "cleanup-outcome.final.json")) "restored wrong auth still cleans up"
    } finally {
      Stop-DisposableLocalHttpFixture -Server $wrongAuthSrv
    }

    # diagnostic log collection failure still cleans up
    $stampM = "20261102T055454Z-orchlogfail"
    $projM = "theplanpreg5snaporchlogfail"
    $attM = "disp-orch-logfail"
    $fxM = Initialize-DisposableOrchestrationFixture -ScratchRoot $scratchBase -ExportStamp $stampM `
      -AttemptId $attM -ApiImage $api -WebImage $web
    $hM = New-DisposableOrchestrationHarness -ProjectName $projM -ApiImage $api -WebImage $web -PgImage $pg
    $hM.State.ApiForceExited = $true
    $hM.State.LogsFail = $true
    $script:PreG5DockerRunner = $hM.Runner
    $rM = Invoke-PreG5Disposable042ValidationCore -ScratchRoot $scratchBase -ExportStamp $stampM `
      -AttemptId $attM -ProjectName $projM -ComposeFile $compose -OwnedNetworkProfile SingleNet `
      -SnapshotApiImage $api -SnapshotWebImage $web -PostgresImage $pg `
      -ExpectAlembic "042_task_occurrence_dispositions" -AuditApprovalPath $fxM.ApprovalPath `
      -SkipHttpChecks -HttpChecker $httpNoOp -ComposeTimeoutMs 8000 -PreflightHostPorts @()
    & $AssertTrue ($rM.ExitCode -ne 0) "logfail path exits nonzero"
    & $AssertTrue (Test-Path (Join-Path $fxM.AttemptDir "failure-diagnostics.json")) "logfail still writes diagnostics json"
    $diagM = Get-Content (Join-Path $fxM.AttemptDir "failure-diagnostics.json") -Raw | ConvertFrom-Json
    & $AssertTrue ($diagM.log_notes.Count -ge 1) "logfail records log_notes"
    & $AssertTrue (Test-Path (Join-Path $fxM.AttemptDir "cleanup-outcome.final.json")) "logfail still cleans up"

  }
  finally {
    $script:PreG5DockerRunner = $null
    Remove-Item -LiteralPath $scratchBase -Recurse -Force -ErrorAction SilentlyContinue
  }
}

