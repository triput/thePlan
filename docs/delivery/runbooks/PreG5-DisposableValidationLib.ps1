#Requires -Version 5.1
<# Shared disposable-042 validation helpers (sourced by runner + orchestration tests). #>
Set-StrictMode -Version Latest
$script:PreG5DisposableFailHttpObservationsWrite = $false

function Get-PreG5DisposableDualNetComposeFile {
  param([string] $RunbooksRoot = $PSScriptRoot)
  return Join-Path $RunbooksRoot "compose.pre-g5-snapshot-disposable-dual-net.yaml"
}

function Test-PreG5DisposableComposeFileImpliesDualNet {
  param([Parameter(Mandatory = $true)][string] $ComposeFile)
  $leaf = [System.IO.Path]::GetFileName($ComposeFile)
  if ($leaf -ceq 'compose.pre-g5-snapshot-disposable-dual-net.yaml') { return $true }
  if ($ComposeFile -match 'disposable-dual-net') { return $true }
  return $false
}

function Get-DisposableStartupValidationEgressDisclosure {
  <#
    Option B — bounded temporary egress relaxation (api/web on preg5_publish only).
    Mirrors reach-compare disclosure shape without sourcing diagnosis lib.
  #>
  param([string] $AttemptId = "")
  $boundAttempt = if ([string]::IsNullOrWhiteSpace($AttemptId)) {
    "the named disposable startup-validation AttemptId at EXECUTE"
  } else {
    $AttemptId
  }
  return [ordered]@{
    option                         = "B"
    summary                        = "Dual-net adds preg5_publish (non-internal bridge) on api+web only; postgres remains internal-only on preg5_net. Bounded temporary relaxation for measured startup validation — not a claim that overall stack isolation is unchanged."
    api_web_egress                 = "Default bridge masqueraded egress may be available to api/web via preg5_publish; not tested or restricted in this prep packet."
    postgres_egress                = "postgres stays on preg5_net only (no publish net membership)."
    localhost_bind_scope           = "127.0.0.1:18000/18080 host binds limit off-container listeners only; they are not outbound egress controls."
    optional_measurable_control    = "driver_opts.com.docker.network.bridge.enable_ip_masquerade=false on preg5_publish — not applied until LIVE orchestration can assert/test."
    duration_bound                 = "Single attempt $boundAttempt only; sealed val-1/val-2/compare-* attempts are not authority; no standing household adoption without separate auth."
    attempt_id_binding             = $boundAttempt
    supersession_note              = "Dex compare-2 closed 1793639927 + fresh Trish EXECUTE for this AttemptId supersede stale single-net UNAUTHENTICATED startup wording."
    startup_validation_scope       = "Host probes: API 127.0.0.1:18000 and web 127.0.0.1:18080 (/ and /api/v1/auth/me proxy hop) with SETUP_REQUIRED on empty fresh 042."
  }
}

function Assert-DisposableAttemptDirClear {
  param([Parameter(Mandatory = $true)][string] $AttemptDir)
  $markers = @(
    "import.receipt.json",
    "failure.receipt.json",
    "QUARANTINE_FAILED_ATTEMPT.txt",
    "validation.receipt.json",
    "cleanup.receipt.json"
  )
  foreach ($name in $markers) {
    $m = Join-Path $AttemptDir $name
    if (Test-Path -LiteralPath $m) {
      throw ("REFUSE: prior disposable attempt evidence exists ($name) — will not mutate")
    }
  }
  return $true
}

function Get-DisposableOwnedResources {
  <# Nonzero docker ps = unresolved (NOT empty-list success). #>
  param(
    [Parameter(Mandatory = $true)][string] $ProjectName,
    [switch] $DualNet
  )
  $fmt = '{{.ID}}|{{.Names}}|{{.Image}}'
  $r = Invoke-PreG5DockerControlAllowFail -What "list project containers" -DockerArgs @(
    "ps", "-a", "--filter", "label=com.docker.compose.project=$ProjectName", "--format", $fmt
  )
  if ($r.Code -ne 0) {
    throw ("UNRESOLVED: project container list failed code=$($r.Code) err=$($r.StdErr)")
  }
  $rows = @()
  foreach ($line in @($r.StdOut -split "`r?`n")) {
    if (-not $line.Trim()) { continue }
    $p = $line -split '\|', 3
    $rows += [ordered]@{ Id = $p[0]; Name = $(if ($p.Count -gt 1) { $p[1] } else { "" }); Image = $(if ($p.Count -gt 2) { $p[2] } else { "" }) }
  }
  $netInternal = "${ProjectName}_preg5_net"
  $owned = [ordered]@{
    Project      = $ProjectName
    Network      = $netInternal
    Volume       = "${ProjectName}_preg5_pgdata"
    Containers   = @($rows)
    ContainerIds = @($rows | ForEach-Object { $_.Id })
    HostPorts    = @(18000, 18080)
    CapturedUtc  = (Get-Date).ToUniversalTime().ToString("o")
    ListOk       = $true
    DualNet      = [bool]$DualNet
  }
  if ($DualNet) {
    $pubNet = "${ProjectName}_preg5_publish"
    $owned.PublishNetwork = $pubNet
    $owned.Networks = @($netInternal, $pubNet)
  }
  return $owned
}

function Get-DisposableOwnedNetworkNames {
  <# OrderedDictionary, hashtable, and ConvertFrom-Json PSCustomObject shapes. #>
  param([Parameter(Mandatory = $true)] $Owned)
  $names = New-Object System.Collections.Generic.List[string]
  $add = {
    param([string] $n)
    if (-not [string]::IsNullOrWhiteSpace($n)) {
      if (-not $names.Contains($n)) { [void]$names.Add($n) }
    }
  }

  if ($Owned -is [System.Collections.IDictionary]) {
    if ($Owned.Contains('Networks') -and $null -ne $Owned['Networks']) {
      foreach ($n in @($Owned['Networks'])) { & $add ([string]$n) }
    }
    if ($Owned.Contains('Network') -and $null -ne $Owned['Network']) {
      & $add ([string]$Owned['Network'])
    }
    if ($Owned.Contains('PublishNetwork') -and $null -ne $Owned['PublishNetwork']) {
      & $add ([string]$Owned['PublishNetwork'])
    }
  } else {
    if ($Owned.PSObject.Properties['Networks'] -and $null -ne $Owned.Networks) {
      foreach ($n in @($Owned.Networks)) { & $add ([string]$n) }
    }
    if ($Owned.PSObject.Properties['Network'] -and $null -ne $Owned.Network) {
      & $add ([string]$Owned.Network)
    }
    if ($Owned.PSObject.Properties['PublishNetwork'] -and $null -ne $Owned.PublishNetwork) {
      & $add ([string]$Owned.PublishNetwork)
    }
  }
  return [string[]]@($names | ForEach-Object { [string]$_ })
}

function Assert-DisposableResourcesGone {
  param(
    [Parameter(Mandatory = $true)] $Owned,
    [Parameter(Mandatory = $true)][string] $ProjectName
  )
  $uncertain = $false
  $notes = New-Object System.Collections.Generic.List[string]
  foreach ($id in @($Owned.ContainerIds)) {
    try {
      $pres = Resolve-ContainerPresenceByRef -Ref $id
      if ($pres.Status -ne "Missing") {
        throw "container still Present id=$id"
      }
    } catch {
      if ($_.Exception.Message -match 'still Present') { throw }
      $uncertain = $true
      $notes.Add("container_presence_unresolved:${id}:$($_.Exception.Message)")
    }
  }
  # Re-query ALL project-labeled containers (not only prior capture).
  try {
    $reDual = $false
    if ($Owned -is [System.Collections.IDictionary] -and $Owned.Contains('DualNet')) {
      $reDual = [bool]$Owned['DualNet']
    } elseif ($null -ne $Owned.PSObject.Properties['DualNet']) {
      $reDual = [bool]$Owned.DualNet
    }
    $now = Get-DisposableOwnedResources -ProjectName $ProjectName -DualNet:$reDual
    if ($now.ContainerIds.Count -gt 0) {
      throw ("project-labeled containers remain: " + ($now.ContainerIds -join ','))
    }
  } catch {
    if ($_.Exception.Message -match 'UNRESOLVED') {
      $uncertain = $true
      $notes.Add($_.Exception.Message)
    } else {
      throw
    }
  }
  $nets = @()
  $vols = @()
  try {
    $nets = @((Invoke-PreG5DockerControl -What "network ls" -DockerArgs @("network", "ls", "--format", "{{.Name}}")).StdOut -split "`r?`n" | Where-Object { $_ })
    $vols = @((Invoke-PreG5DockerControl -What "volume ls" -DockerArgs @("volume", "ls", "--format", "{{.Name}}")).StdOut -split "`r?`n" | Where-Object { $_ })
  } catch {
    $uncertain = $true
    $notes.Add("net_vol_list:" + $_.Exception.Message)
  }
  $netsToVerify = @(Get-DisposableOwnedNetworkNames -Owned $Owned)
  if (@($netsToVerify).Count -eq 0) {
    if ($Owned -is [System.Collections.IDictionary] -and $Owned.Contains('Network')) {
      $netsToVerify = @([string]$Owned['Network'])
    } elseif ($Owned.PSObject.Properties['Network']) {
      $netsToVerify = @([string]$Owned.Network)
    }
  }
  foreach ($netName in @($netsToVerify | Select-Object -Unique)) {
    if ($nets -contains $netName) { throw "network still Present $netName" }
  }
  if ($vols -contains $Owned.Volume) { throw "volume still Present $($Owned.Volume)" }
  return [ordered]@{ Ok = (-not $uncertain); Uncertain = $uncertain; Notes = @($notes) }
}

function Assert-RunningContainerImagePin {
  param(
    [Parameter(Mandatory = $true)][string] $ContainerId,
    [Parameter(Mandatory = $true)][string] $ExpectedImageId
  )
  $got = (Invoke-PreG5DockerControl -What "inspect image field" -DockerArgs @(
      "inspect", $ContainerId, "--format", "{{.Image}}"
    )).StdOut.Trim()
  # .Image may be short id; resolve both to full ids via image inspect when needed
  $gotFull = $got
  if ($got -notmatch '^sha256:') {
    try {
      $gotFull = (Invoke-PreG5DockerControl -What "image inspect short" -DockerArgs @(
          "image", "inspect", $got, "--format", "{{.Id}}"
        )).StdOut.Trim()
    } catch { }
  }
  $want = $ExpectedImageId
  $g = ($gotFull -replace '^sha256:', '').ToLowerInvariant()
  $w = ($want -replace '^sha256:', '').ToLowerInvariant()
  if ($g -ne $w) {
    throw ("REFUSE: running container image mismatch id=$ContainerId got=$gotFull want=$want")
  }
  return $gotFull
}

function Get-DisposableComposeServiceVolumes {
  param($ServiceObj)
  if ($null -eq $ServiceObj) { return ,@() }
  $propNames = @($ServiceObj.PSObject.Properties | ForEach-Object { $_.Name })
  if ($propNames -notcontains 'volumes') { return ,@() }
  $raw = $ServiceObj.volumes
  if ($null -eq $raw) { return ,@() }
  if ($raw -is [System.Collections.IEnumerable] -and -not ($raw -is [string])) {
    return ,@($raw)
  }
  return ,@($raw)
}

function Assert-DisposableComposePortExact {
  param(
    [Parameter(Mandatory = $true)] $Ports,
    [Parameter(Mandatory = $true)][string] $ServiceName,
    [Parameter(Mandatory = $true)][string] $ExpectPublished
  )
  if ($null -eq $Ports) { throw "REFUSE: $ServiceName ports missing" }
  if ($Ports -is [System.Collections.IEnumerable] -and -not ($Ports -is [string])) {
    $list = @($Ports)
  } else {
    $list = @($Ports)
  }
  if ($list.Length -ne 1) {
    throw "REFUSE: $ServiceName must expose exactly one host port, found $($list.Length)"
  }
  $p = $list[0]
  $pNames = @($p.PSObject.Properties | ForEach-Object { $_.Name })
  $pub = ""
  if ($pNames -contains 'published') { $pub = [string]$p.published }
  elseif ($pNames -contains 'Published') { $pub = [string]$p.Published }
  $hip = ""
  if ($pNames -contains 'host_ip') { $hip = [string]$p.host_ip }
  elseif ($pNames -contains 'HostIp') { $hip = [string]$p.HostIp }
  if ([string]::IsNullOrWhiteSpace($hip)) {
    throw "REFUSE: $ServiceName host_ip empty or missing (require exactly 127.0.0.1)"
  }
  if ($hip -cne "127.0.0.1") {
    throw "REFUSE: $ServiceName host_ip must be 127.0.0.1 got=$hip"
  }
  if ($pub -cne $ExpectPublished) {
    throw "REFUSE: $ServiceName published port must be $ExpectPublished got=$pub"
  }
  return $true
}

function Assert-DisposableComposeVolumeShape {
  param(
    [Parameter(Mandatory = $true)][string] $ServiceName,
    [Parameter(Mandatory = $true)] $VolumeEntry
  )
  $typ = ""
  if ($VolumeEntry.PSObject.Properties['type']) { $typ = [string]$VolumeEntry.type }
  if ($typ -eq "bind") {
    throw "REFUSE: $ServiceName bind mount forbidden in disposable config"
  }
  if ($ServiceName -eq "postgres") {
    if ($typ -and $typ -ne "volume") {
      throw "REFUSE: postgres data mount must be type volume got=$typ"
    }
    $src = ""
    if ($VolumeEntry.PSObject.Properties['source']) { $src = [string]$VolumeEntry.source }
    if ($src -ne "preg5_pgdata") {
      throw "REFUSE: postgres volume source must be preg5_pgdata got=$src"
    }
    $tgt = ""
    if ($VolumeEntry.PSObject.Properties['target']) { $tgt = [string]$VolumeEntry.target }
    if ($tgt -ne "/var/lib/postgresql/data") {
      throw "REFUSE: postgres volume target unexpected got=$tgt"
    }
    return $true
  }
  throw "REFUSE: unexpected volume mount on $ServiceName"
}

function Assert-DisposableComposeConfigStructured {
  <# Expect JSON from `docker compose config --format json` (Compose v2). Fail closed. #>
  param(
    [Parameter(Mandatory = $true)][string] $ConfigJson,
    [Parameter(Mandatory = $true)][string] $ExpectApiImage,
    [Parameter(Mandatory = $true)][string] $ExpectWebImage,
    [Parameter(Mandatory = $true)][string] $ExpectPostgresImage
  )
  $cfg = $ConfigJson | ConvertFrom-Json
  if ($null -eq $cfg.services) { throw "REFUSE: rendered config missing services" }
  $svc = $cfg.services
  $allowedSvc = @("postgres", "api", "web")
  $foundSvc = @($svc.PSObject.Properties | ForEach-Object { $_.Name })
  foreach ($n in $foundSvc) {
    if ($allowedSvc -notcontains $n) {
      throw "REFUSE: unexpected service in config: $n"
    }
  }
  foreach ($need in $allowedSvc) {
    if ($null -eq $svc.$need) { throw "REFUSE: rendered config missing service $need" }
  }
  if ([string]$svc.api.image -cne $ExpectApiImage) {
    throw "REFUSE: api image mismatch in config want=$ExpectApiImage got=$($svc.api.image)"
  }
  if ([string]$svc.web.image -cne $ExpectWebImage) {
    throw "REFUSE: web image mismatch in config"
  }
  if ([string]$svc.postgres.image -cne $ExpectPostgresImage) {
    throw "REFUSE: postgres image mismatch in config"
  }
  if ($null -eq $cfg.networks) { throw "REFUSE: rendered config missing networks" }
  $netNames = @($cfg.networks.PSObject.Properties | ForEach-Object { $_.Name })
  if ($netNames.Count -ne 1 -or $netNames[0] -ne "preg5_net") {
    throw ("REFUSE: networks must be exactly preg5_net internal; got: " + ($netNames -join ','))
  }
  $preg5 = $cfg.networks.preg5_net
  $internal = $false
  if ($preg5.PSObject.Properties['internal']) { $internal = [bool]$preg5.internal }
  if (-not $internal) { throw "REFUSE: disposable network internal != true" }

  if ($null -eq $cfg.volumes) { throw "REFUSE: rendered config missing top-level volumes" }
  $volNames = @($cfg.volumes.PSObject.Properties | ForEach-Object { $_.Name })
  if ($volNames.Count -ne 1 -or $volNames[0] -ne "preg5_pgdata") {
    throw ("REFUSE: top-level volumes must be exactly preg5_pgdata; got: " + ($volNames -join ','))
  }

  Assert-DisposableComposePortExact -Ports $svc.api.ports -ServiceName "api" -ExpectPublished "18000" | Out-Null
  Assert-DisposableComposePortExact -Ports $svc.web.ports -ServiceName "web" -ExpectPublished "18080" | Out-Null
  $apiVols = Get-DisposableComposeServiceVolumes $svc.api
  if ($apiVols.Length -gt 0) { throw "REFUSE: api must not mount volumes" }
  $webVols = Get-DisposableComposeServiceVolumes $svc.web
  if ($webVols.Length -gt 0) { throw "REFUSE: web must not mount volumes" }

  $pgVols = Get-DisposableComposeServiceVolumes $svc.postgres
  if ($pgVols.Length -ne 1) {
    throw "REFUSE: postgres must have exactly one named volume mount, found $($pgVols.Length)"
  }
  Assert-DisposableComposeVolumeShape -ServiceName "postgres" -VolumeEntry $pgVols[0] | Out-Null

  return $true
}

function Assert-DisposableComposeServiceNetworkKeys {
  param(
    [Parameter(Mandatory = $true)] $ServiceNetworks,
    [Parameter(Mandatory = $true)][string[]] $ExpectKeys,
    [Parameter(Mandatory = $true)][string] $ServiceName
  )
  if ($null -eq $ServiceNetworks) {
    throw "REFUSE: $ServiceName networks missing"
  }
  $keys = @($ServiceNetworks.PSObject.Properties | ForEach-Object { $_.Name } | Sort-Object)
  $want = @($ExpectKeys | Sort-Object)
  if (($keys -join ',') -cne ($want -join ',')) {
    throw ("REFUSE: $ServiceName network membership must be [" + ($want -join ',') + "]; got [" + ($keys -join ',') + "]")
  }
  return $true
}

function Assert-DisposableComposeDualNetRenderedOwnership {
  param(
    [Parameter(Mandatory = $true)] $Cfg,
    [Parameter(Mandatory = $true)][string] $ComposeProjectName
  )
  if ([string]::IsNullOrWhiteSpace($ComposeProjectName)) {
    throw "REFUSE: rendered config missing top-level name (project scope)"
  }
  foreach ($logical in @('preg5_net', 'preg5_publish')) {
    $net = $Cfg.networks.$logical
    if ($null -eq $net) { throw "REFUSE: rendered config missing network $logical" }
    $expectName = "${ComposeProjectName}_${logical}"
    $hasName = $false
    $renderedName = ""
    if ($net.PSObject.Properties['name']) {
      $hasName = $true
      $renderedName = [string]$net.name
    }
    if (-not $hasName -or [string]::IsNullOrWhiteSpace($renderedName)) {
      throw "REFUSE: $logical must have project-scoped concrete name=$expectName"
    }
    if ($renderedName -cne $expectName) {
      throw ("REFUSE: $logical name must be project-owned ${expectName}; got=${renderedName}")
    }
    if ($net.PSObject.Properties['external'] -and [bool]$net.external) {
      throw "REFUSE: $logical external=true forbidden (shared/unowned escape)"
    }
  }
  if ($null -eq $Cfg.volumes -or $null -eq $Cfg.volumes.preg5_pgdata) {
    throw "REFUSE: rendered config missing volume preg5_pgdata"
  }
  $vol = $Cfg.volumes.preg5_pgdata
  $expectVol = "${ComposeProjectName}_preg5_pgdata"
  if ($vol.PSObject.Properties['external'] -and [bool]$vol.external) {
    throw "REFUSE: preg5_pgdata external=true forbidden"
  }
  if ($vol.PSObject.Properties['name']) {
    $vn = [string]$vol.name
    if ($vn -cne $expectVol) {
      throw ("REFUSE: preg5_pgdata name must be project-owned ${expectVol}; got=${vn}")
    }
  } else {
    throw "REFUSE: preg5_pgdata must have project-scoped concrete name in rendered config"
  }
  return $true
}

function Assert-DisposableComposeConfigStructuredDualNet {
  <# Dual-network reach-compare template: owned nets exactly preg5_net + preg5_publish. #>
  param(
    [Parameter(Mandatory = $true)][string] $ConfigJson,
    [Parameter(Mandatory = $true)][string] $ExpectApiImage,
    [Parameter(Mandatory = $true)][string] $ExpectWebImage,
    [Parameter(Mandatory = $true)][string] $ExpectPostgresImage
  )
  $cfg = $ConfigJson | ConvertFrom-Json
  if ($null -eq $cfg.services) { throw "REFUSE: rendered config missing services" }
  $svc = $cfg.services
  $allowedSvc = @("postgres", "api", "web")
  $foundSvc = @($svc.PSObject.Properties | ForEach-Object { $_.Name })
  foreach ($n in $foundSvc) {
    if ($allowedSvc -notcontains $n) {
      throw "REFUSE: unexpected service in config: $n"
    }
  }
  foreach ($need in $allowedSvc) {
    if ($null -eq $svc.$need) { throw "REFUSE: rendered config missing service $need" }
  }
  if ([string]$svc.api.image -cne $ExpectApiImage) {
    throw "REFUSE: api image mismatch in config want=$ExpectApiImage got=$($svc.api.image)"
  }
  if ([string]$svc.web.image -cne $ExpectWebImage) {
    throw "REFUSE: web image mismatch in config"
  }
  if ([string]$svc.postgres.image -cne $ExpectPostgresImage) {
    throw "REFUSE: postgres image mismatch in config"
  }
  if ($null -eq $cfg.networks) { throw "REFUSE: rendered config missing networks" }
  $netNames = @($cfg.networks.PSObject.Properties | ForEach-Object { $_.Name } | Sort-Object)
  if (($netNames -join ',') -cne 'preg5_net,preg5_publish') {
    throw ("REFUSE: networks must be exactly preg5_net,preg5_publish; got: " + ($netNames -join ','))
  }
  $internal = $false
  if ($cfg.networks.preg5_net.PSObject.Properties['internal']) {
    $internal = [bool]$cfg.networks.preg5_net.internal
  }
  if (-not $internal) { throw "REFUSE: preg5_net internal != true" }
  $pubHasInternal = $false
  $pubInternal = $false
  if ($cfg.networks.preg5_publish.PSObject.Properties['internal']) {
    $pubHasInternal = $true
    $pubInternal = [bool]$cfg.networks.preg5_publish.internal
  }
  if ($pubHasInternal -and $pubInternal) {
    throw "REFUSE: preg5_publish must be non-internal (internal=false or unset)"
  }

  $composeProjectName = ""
  if ($cfg.PSObject.Properties['name']) { $composeProjectName = [string]$cfg.name }
  Assert-DisposableComposeDualNetRenderedOwnership -Cfg $cfg -ComposeProjectName $composeProjectName | Out-Null

  Assert-DisposableComposeServiceNetworkKeys -ServiceNetworks $svc.postgres.networks -ExpectKeys @('preg5_net') -ServiceName 'postgres' | Out-Null
  Assert-DisposableComposeServiceNetworkKeys -ServiceNetworks $svc.api.networks -ExpectKeys @('preg5_net', 'preg5_publish') -ServiceName 'api' | Out-Null
  Assert-DisposableComposeServiceNetworkKeys -ServiceNetworks $svc.web.networks -ExpectKeys @('preg5_net', 'preg5_publish') -ServiceName 'web' | Out-Null

  if ($null -eq $cfg.volumes) { throw "REFUSE: rendered config missing top-level volumes" }
  $volNames = @($cfg.volumes.PSObject.Properties | ForEach-Object { $_.Name })
  if ($volNames.Count -ne 1 -or $volNames[0] -ne "preg5_pgdata") {
    throw ("REFUSE: top-level volumes must be exactly preg5_pgdata; got: " + ($volNames -join ','))
  }

  Assert-DisposableComposePortExact -Ports $svc.api.ports -ServiceName "api" -ExpectPublished "18000" | Out-Null
  Assert-DisposableComposePortExact -Ports $svc.web.ports -ServiceName "web" -ExpectPublished "18080" | Out-Null
  $apiVols = Get-DisposableComposeServiceVolumes $svc.api
  if ($apiVols.Length -gt 0) { throw "REFUSE: api must not mount volumes" }
  $webVols = Get-DisposableComposeServiceVolumes $svc.web
  if ($webVols.Length -gt 0) { throw "REFUSE: web must not mount volumes" }
  $pgVols = Get-DisposableComposeServiceVolumes $svc.postgres
  if ($pgVols.Length -ne 1) {
    throw "REFUSE: postgres must have exactly one named volume mount, found $($pgVols.Length)"
  }
  Assert-DisposableComposeVolumeShape -ServiceName "postgres" -VolumeEntry $pgVols[0] | Out-Null

  foreach ($svcName in @('postgres', 'api', 'web')) {
    $pull = ""
    if ($svc.$svcName.PSObject.Properties['pull_policy']) { $pull = [string]$svc.$svcName.pull_policy }
    if ($pull -and $pull -cne 'never') {
      throw "REFUSE: $svcName pull_policy must be never got=$pull"
    }
  }

  return $true
}

function Clear-DisposableInheritedEnv {
  param([string[]] $Keys)
  $saved = @{}
  foreach ($k in $Keys) {
    $saved[$k] = [Environment]::GetEnvironmentVariable($k, 'Process')
    if (Test-Path -LiteralPath "Env:$k") { Remove-Item -LiteralPath "Env:$k" -ErrorAction SilentlyContinue }
  }
  return $saved
}

function Restore-DisposableInheritedEnv {
  param([hashtable] $Saved)
  foreach ($k in @($Saved.Keys)) {
    if ($null -eq $Saved[$k]) {
      if (Test-Path -LiteralPath "Env:$k") { Remove-Item -LiteralPath "Env:$k" -ErrorAction SilentlyContinue }
    } else {
      Set-Item -LiteralPath "Env:$k" -Value $Saved[$k]
    }
  }
}

function Get-DisposableHttpRetryableWebExceptionStatuses {
  return @(
    'ConnectFailure', 'ConnectionClosed', 'ReceiveFailure', 'SendFailure', 'Timeout',
    'NameResolutionFailure', 'ProxyNameResolutionFailure', 'KeepAliveFailure'
  )
}

function Test-DisposableHttpTransportRetryable {
  <#
    Readiness polling gate: structured transport_fail (primary) or explicit retryable
    WebExceptionStatus on the observation. Does not inspect exception message prose.
  #>
  param($Observation)
  if ($null -eq $Observation) { return $false }
  if ([string]$Observation.classification -eq 'transport_fail') { return $true }
  $wes = $null
  $obsPropNames = @($Observation.PSObject.Properties | ForEach-Object { $_.Name })
  if ($obsPropNames -contains 'web_exception_status') {
    $wes = [string]$Observation.PSObject.Properties['web_exception_status'].Value
  }
  if ([string]::IsNullOrWhiteSpace([string]$wes)) { return $false }
  foreach ($allowed in (Get-DisposableHttpRetryableWebExceptionStatuses)) {
    if ([string]$wes -ceq $allowed) { return $true }
  }
  return $false
}

function Test-DisposableHttpTransportNotReady {
  <# Legacy message heuristic for reachability tests only; startup readiness uses Test-DisposableHttpTransportRetryable. #>
  param([Parameter(Mandatory = $true)][string] $ErrorMessage)
  if ($ErrorMessage -match '(?i)status=\d+\s+want=') { return $false }
  if ($ErrorMessage -match '(?i)missing expected body marker') { return $false }
  if ($ErrorMessage -match '(?i)body acquisition failed') { return $false }
  if ($ErrorMessage -match '(?i)malformed JSON|JSON code want=') { return $false }
  if ($ErrorMessage -match '(?i)unable to connect|connection refused|actively refused|No connection could be made|connection attempt failed|remote name could not be resolved|No such host is known|The operation has timed out|timed out') {
    return $true
  }
  return $false
}

function Get-PreG5DisposableHttpEndpointObservationsFileName {
  return "http-endpoint-observations.json"
}

function Get-PreG5FileSha256Hex {
  param([Parameter(Mandatory = $true)][string] $Path)
  if (-not (Test-Path -LiteralPath $Path)) { throw "sha256 path missing: $Path" }
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $fs = [System.IO.File]::OpenRead($Path)
    try {
      $hash = $sha.ComputeHash($fs)
    } finally {
      $fs.Dispose()
    }
  } finally {
    $sha.Dispose()
  }
  return ([BitConverter]::ToString($hash).Replace("-", "").ToUpperInvariant())
}

function Get-DisposableHttpObservationClassification {
  param([Parameter(Mandatory = $true)][string] $ProbeClassification)
  switch ($ProbeClassification) {
    'http_ok' { return 'http_ok' }
    'transport_fail' { return 'transport_fail' }
    'http_error' { return 'http_error' }
    default { return 'mismatches' }
  }
}

function Format-DisposableHttpObservationBodyFields {
  param(
    [AllowNull()] $Body,
    [int] $MaxBytes = 65536
  )
  if ($null -eq $Body) {
    return [ordered]@{
      body               = $null
      body_truncated     = $false
      body_full_sha256   = $null
    }
  }
  $text = [string]$Body
  $enc = [System.Text.Encoding]::UTF8
  $fullBytes = $enc.GetBytes($text)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $fullHash = ([BitConverter]::ToString($sha.ComputeHash($fullBytes)).Replace("-", "").ToUpperInvariant())
  } finally {
    $sha.Dispose()
  }
  $bounded = Limit-DisposableTextBytes -Text $text -MaxBytes $MaxBytes
  $truncated = ($bounded -cne $text)
  return [ordered]@{
    body               = $bounded
    body_truncated     = $truncated
    body_full_sha256   = $fullHash
  }
}

function New-DisposableHttpEndpointObservationEntry {
  param(
    [Parameter(Mandatory = $true)][string] $Uri,
    [Parameter(Mandatory = $true)][int] $ExpectStatus,
    [string[]] $BodyMustContain = @(),
    [string] $ExpectJsonCode = "",
    [Parameter(Mandatory = $true)] $ProbeResult
  )
  $rawBody = $ProbeResult.body
  $bodyForFormat = if ($null -eq $rawBody) { $null } else { [string]$rawBody }
  $bodyFields = Format-DisposableHttpObservationBodyFields -Body $bodyForFormat
  $class = Get-DisposableHttpObservationClassification -ProbeClassification ([string]$ProbeResult.classification)
  $wes = $null
  $probePropNames = @($ProbeResult.PSObject.Properties | ForEach-Object { $_.Name })
  if ($probePropNames -contains 'web_exception_status') {
    $wesVal = $ProbeResult.PSObject.Properties['web_exception_status'].Value
    if (-not [string]::IsNullOrWhiteSpace([string]$wesVal)) { $wes = [string]$wesVal }
  }
  $entry = [ordered]@{
    uri                 = $Uri
    expected_status     = $ExpectStatus
    http_status         = $ProbeResult.http_status
    parsed_code         = $ProbeResult.parsed_code
    classification      = $class
    acquisition_ok      = [bool]$ProbeResult.acquisition_ok
    acquisition_error   = $ProbeResult.acquisition_error
    expect_json_code    = $(if ([string]::IsNullOrWhiteSpace($ExpectJsonCode)) { $null } else { $ExpectJsonCode })
    body_must_contain   = @($BodyMustContain)
    observed_utc        = (Get-Date).ToUniversalTime().ToString("o")
    body                = $bodyFields.body
    body_truncated      = $bodyFields.body_truncated
    body_full_sha256    = $bodyFields.body_full_sha256
    probe_error         = $ProbeResult.error
  }
  if ($null -ne $wes) { $entry.web_exception_status = $wes }
  return $entry
}

$script:DisposableHttpEndpointObservationExceptionKey = 'DisposableHttpEndpointObservation'

function Get-DisposableHttpEndpointObservationFromErrorRecord {
  param($ErrorRecord)
  if ($null -eq $ErrorRecord) { return $null }
  $ex = $ErrorRecord.Exception
  while ($null -ne $ex) {
    if ($null -ne $ex.Data -and $ex.Data.Contains($script:DisposableHttpEndpointObservationExceptionKey)) {
      return $ex.Data[$script:DisposableHttpEndpointObservationExceptionKey]
    }
    $ex = $ex.InnerException
  }
  return $null
}

function Throw-DisposableHttpCheckFailed {
  param(
    [Parameter(Mandatory = $true)] $Observation,
    [string] $Message = $null
  )
  $msg = $Message
  if ([string]::IsNullOrWhiteSpace($msg)) {
    if ($Observation.probe_error) { $msg = [string]$Observation.probe_error }
    else { $msg = ("FAIL: HTTP $($Observation.uri) classification=$($Observation.classification)") }
  }
  $ex = [System.Management.Automation.RuntimeException]::new($msg)
  $ex.Data[$script:DisposableHttpEndpointObservationExceptionKey] = $Observation
  throw $ex
}

function Invoke-DisposableStartupHttpProbeCore {
  param(
    [Parameter(Mandatory = $true)][string] $Uri,
    [Parameter(Mandatory = $true)][int] $ExpectStatus,
    [string[]] $BodyMustContain = @(),
    [string] $ExpectJsonCode = "",
    [int] $TimeoutSec = 15,
    [string] $RequestUri = ""
  )
  $fetchUri = if ([string]::IsNullOrWhiteSpace($RequestUri)) { $Uri } else { $RequestUri }
  $cap = Invoke-HttpJsonCapture -Uri $fetchUri -TimeoutSec $TimeoutSec
  if ($fetchUri -ne $Uri) { $cap.uri = $Uri }
  $probe = Convert-HttpJsonCaptureToProbeResult -Capture $cap -ExpectStatus $ExpectStatus `
    -ExpectJsonCode $ExpectJsonCode -BodyMustContain $BodyMustContain
  return New-DisposableHttpEndpointObservationEntry -Uri $Uri -ExpectStatus $ExpectStatus `
    -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -ProbeResult $probe
}

function Invoke-DisposableStartupHttpProbe {
  param(
    [Parameter(Mandatory = $true)][string] $Uri,
    [Parameter(Mandatory = $true)][int] $ExpectStatus,
    [string[]] $BodyMustContain = @(),
    [string] $ExpectJsonCode = "",
    [int] $TimeoutSec = 15,
    [string] $RequestUri = ""
  )
  $obs = Invoke-DisposableStartupHttpProbeCore -Uri $Uri -ExpectStatus $ExpectStatus `
    -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -TimeoutSec $TimeoutSec `
    -RequestUri $RequestUri
  if ($obs.classification -ne 'http_ok') {
    Throw-DisposableHttpCheckFailed -Observation $obs
  }
  return $obs
}

function Write-DisposableHttpEndpointObservationsArtifact {
  param(
    [Parameter(Mandatory = $true)][string] $EvidenceDir,
    [Parameter(Mandatory = $true)][string] $AttemptId,
    [Parameter(Mandatory = $true)] $EndpointObservations
  )
  if ($script:PreG5DisposableFailHttpObservationsWrite -eq $true) {
    throw "PREG5_DISP_FAIL: http-endpoint-observations write blocked by test hook"
  }
  $fileName = Get-PreG5DisposableHttpEndpointObservationsFileName
  $path = Join-Path $EvidenceDir $fileName
  $doc = [ordered]@{
    artifact      = "http-endpoint-observations"
    attempt_id    = $AttemptId
    taken_utc     = (Get-Date).ToUniversalTime().ToString("o")
    endpoint_count = @($EndpointObservations).Count
    endpoints     = @($EndpointObservations)
  }
  Assert-DurablePathWritable $path | Out-Null
  ($doc | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $path -Encoding utf8
  return [ordered]@{
    path     = $fileName
    sha256   = (Get-PreG5FileSha256Hex -Path $path)
  }
}

function Get-DisposableStartupValidationHttpCheckMatrix {
  return @(
    @{ Uri = "http://127.0.0.1:18000/api/v1/auth/me"; Status = 401; Body = @(); JsonCode = "SETUP_REQUIRED" },
    @{ Uri = "http://127.0.0.1:18080/"; Status = 200; Body = @("<title>thePlan</title>"); JsonCode = "" },
    @{ Uri = "http://127.0.0.1:18080/api/v1/auth/me"; Status = 401; Body = @(); JsonCode = "SETUP_REQUIRED" }
  )
}

function Invoke-DisposableStartupValidationHttpChecks {
  param(
    [Parameter(Mandatory = $true)][string] $EvidenceDir,
    [Parameter(Mandatory = $true)][string] $AttemptId,
    [int] $HttpTimeoutSec = 20,
    [Parameter(Mandatory = $true)][datetime] $HttpDeadlineUtc,
    [int] $HttpReadinessPollSec = 2,
    [scriptblock] $HttpChecker = $null,
    [scriptblock] $HttpProbe = $null
  )
  $checks = Get-DisposableStartupValidationHttpCheckMatrix
  $collected = New-Object System.Collections.Generic.List[object]
  $defaultProbe = {
    param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
    Invoke-DisposableStartupHttpProbeCore -Uri $Uri -ExpectStatus $ExpectStatus -BodyMustContain $BodyMustContain `
      -ExpectJsonCode $ExpectJsonCode -TimeoutSec $TimeoutSec | ForEach-Object {
      if ($_.classification -ne 'http_ok') { Throw-DisposableHttpCheckFailed -Observation $_ }
      $_
    }
  }
  $probe = if ($null -ne $HttpProbe) { $HttpProbe } else { $defaultProbe }

  function _WritePartialArtifact {
    if ($collected.Count -lt 1) { return }
    Write-DisposableHttpEndpointObservationsArtifact -EvidenceDir $EvidenceDir -AttemptId $AttemptId `
      -EndpointObservations $collected.ToArray() | Out-Null
  }

  foreach ($hc in $checks) {
    try {
      if ($null -ne $HttpChecker) {
        $obs = & $HttpChecker -Uri $hc.Uri -ExpectStatus $hc.Status -BodyMustContain $hc.Body `
          -ExpectJsonCode $hc.JsonCode -TimeoutSec $HttpTimeoutSec
        if ($null -eq $obs) {
          throw "PREG5_DISP_FAIL: HttpChecker must return a structured endpoint observation"
        }
      } else {
        $obs = Invoke-DisposableHttpCheckWithReadiness -Uri $hc.Uri -ExpectStatus $hc.Status `
          -BodyMustContain $hc.Body -ExpectJsonCode $hc.JsonCode -DeadlineUtc $HttpDeadlineUtc `
          -PerRequestTimeoutSec $HttpTimeoutSec -PollSec $HttpReadinessPollSec -ProbeScriptBlock $probe
      }
      $collected.Add($obs) | Out-Null
    } catch {
      $failObs = Get-DisposableHttpEndpointObservationFromErrorRecord -ErrorRecord $_
      if ($null -ne $failObs) {
        $collected.Add($failObs) | Out-Null
      }
      if ($collected.Count -ge 1) {
        _WritePartialArtifact
      }
      throw
    }
  }

  return Write-DisposableHttpEndpointObservationsArtifact -EvidenceDir $EvidenceDir -AttemptId $AttemptId `
    -EndpointObservations $collected.ToArray()
}

function Invoke-DisposableHttpCheckWithReadiness {
  param(
    [Parameter(Mandatory = $true)][string] $Uri,
    [Parameter(Mandatory = $true)][int] $ExpectStatus,
    [string[]] $BodyMustContain = @(),
    [string] $ExpectJsonCode = "",
    [Parameter(Mandatory = $true)][datetime] $DeadlineUtc,
    [int] $PerRequestTimeoutSec = 15,
    [int] $PollSec = 2,
    [Parameter(Mandatory = $true)][scriptblock] $ProbeScriptBlock
  )
  $lastTransportObs = $null
  while ($true) {
    $remainSec = ($DeadlineUtc - [datetime]::UtcNow).TotalSeconds
    if ($remainSec -le 0) {
      if ($null -ne $lastTransportObs) {
        Throw-DisposableHttpCheckFailed -Observation $lastTransportObs `
          -Message ("PREG5_DISP_FAIL: HTTP transport-not-ready deadline exceeded for $Uri")
      }
      throw ("PREG5_DISP_FAIL: HTTP transport-not-ready deadline exceeded for $Uri")
    }
    $reqTimeout = [int][Math]::Min($PerRequestTimeoutSec, [Math]::Max(1, [Math]::Ceiling($remainSec)))
    try {
      $obs = & $ProbeScriptBlock -Uri $Uri -ExpectStatus $ExpectStatus -BodyMustContain $BodyMustContain `
        -ExpectJsonCode $ExpectJsonCode -TimeoutSec $reqTimeout
      if ($null -eq $obs) {
        $obs = Invoke-DisposableStartupHttpProbeCore -Uri $Uri -ExpectStatus $ExpectStatus `
          -BodyMustContain $BodyMustContain -ExpectJsonCode $ExpectJsonCode -TimeoutSec $reqTimeout
      }
      if ($obs.classification -eq 'http_ok') {
        return $obs
      }
      if (Test-DisposableHttpTransportRetryable -Observation $obs) {
        $lastTransportObs = $obs
        if ([datetime]::UtcNow -ge $DeadlineUtc) {
          Throw-DisposableHttpCheckFailed -Observation $obs `
            -Message ("PREG5_DISP_FAIL: HTTP transport-not-ready deadline exceeded for $Uri")
        }
        $remainSec = ($DeadlineUtc - [datetime]::UtcNow).TotalSeconds
        $sleepSec = [Math]::Min([double]$PollSec, $remainSec)
        if ($sleepSec -gt 0) { Start-Sleep -Seconds $sleepSec }
        continue
      }
      Throw-DisposableHttpCheckFailed -Observation $obs
    } catch {
      $failObs = Get-DisposableHttpEndpointObservationFromErrorRecord -ErrorRecord $_
      if ($null -ne $failObs -and (Test-DisposableHttpTransportRetryable -Observation $failObs)) {
        $lastTransportObs = $failObs
        if ([datetime]::UtcNow -ge $DeadlineUtc) {
          Throw-DisposableHttpCheckFailed -Observation $failObs `
            -Message ("PREG5_DISP_FAIL: HTTP transport-not-ready deadline exceeded for $Uri")
        }
        $remainSec = ($DeadlineUtc - [datetime]::UtcNow).TotalSeconds
        $sleepSec = [Math]::Min([double]$PollSec, $remainSec)
        if ($sleepSec -gt 0) { Start-Sleep -Seconds $sleepSec }
        continue
      }
      if ($null -ne $failObs) {
        Throw-DisposableHttpCheckFailed -Observation $failObs -Message $_.Exception.Message
      }
      throw
    }
  }
}

function Get-DisposableComposePsHealthExact {
  param(
    [Parameter(Mandatory = $true)][string] $PsJsonStdout,
    [Parameter(Mandatory = $true)][string] $ServiceName
  )
  if ([string]::IsNullOrWhiteSpace($PsJsonStdout)) { return $null }
  $parsed = $PsJsonStdout | ConvertFrom-Json
  $rows = @()
  if ($parsed -is [System.Array]) { $rows = @($parsed) } else { $rows = @($parsed) }
  foreach ($row in $rows) {
    $names = @($row.PSObject.Properties | ForEach-Object { $_.Name })
    $svc = ""
    if ($names -contains 'Service') { $svc = [string]$row.Service }
    elseif ($names -contains 'Name') {
      $svc = [string]$row.Name
      if ($svc -match '/([^/]+)$') { $svc = $Matches[1] }
      elseif ($svc -match '-([^-]+)-\d+$') { $svc = $Matches[1] }
    }
    if ($svc -ne $ServiceName) { continue }
    if ($names -contains 'Health') {
      return ([string]$row.Health).Trim()
    }
    return $null
  }
  return $null
}

function Wait-DisposablePostgresHealthyExact {
  param(
    [Parameter(Mandatory = $true)][datetime] $DeadlineUtc,
    [Parameter(Mandatory = $true)][scriptblock] $GetPostgresPsJson,
    [int] $PollSec = 2
  )
  $last = $null
  do {
    $out = [string](& $GetPostgresPsJson)
    $last = Get-DisposableComposePsHealthExact -PsJsonStdout $out -ServiceName "postgres"
    if ($last -ceq "healthy") { return $true }
    if ($last -ceq "unhealthy") { throw "PREG5_DISP_FAIL: postgres compose Health=unhealthy" }
    if ([datetime]::UtcNow -ge $DeadlineUtc) {
      throw ("PREG5_DISP_FAIL: postgres not healthy before timeout (last Health=$last)")
    }
    Start-Sleep -Seconds $PollSec
  } while ($true)
}

function Limit-DisposableTextBytes {
  param(
    [AllowNull()][string] $Text,
    [int] $MaxBytes = 65536
  )
  if ([string]::IsNullOrEmpty($Text)) { return "" }
  $enc = [System.Text.Encoding]::UTF8
  $bytes = $enc.GetBytes($Text)
  if ($bytes.Length -le $MaxBytes) { return $Text }
  return ($enc.GetString($bytes, 0, $MaxBytes) + "`n...[truncated]...")
}

function Get-DisposablePsObjectPropertyNames {
  param([AllowNull()] $Object)
  if ($null -eq $Object) { return ,@() }
  return ,@($Object.PSObject.Properties | ForEach-Object { $_.Name })
}

function Get-DisposableProjectServiceContainerId {
  param(
    [Parameter(Mandatory = $true)][string] $ProjectName,
    [Parameter(Mandatory = $true)][string] $ServiceName
  )
  $r = Invoke-PreG5DockerControl -What "ps -a $ServiceName id" -DockerArgs @(
    "ps", "-a", "-q", "--filter", "label=com.docker.compose.project=$ProjectName",
    "--filter", "label=com.docker.compose.service=$ServiceName"
  )
  $lines = @($r.StdOut -split "`r?`n" | Where-Object { $_ -and $_.Trim() } | ForEach-Object { $_.Trim() })
  if ($lines.Count -eq 0) { return $null }
  return [string]$lines[0]
}

function Get-DisposableContainerStateSnapshot {
  param([AllowNull()][string] $ContainerId)
  if ([string]::IsNullOrWhiteSpace($ContainerId)) {
    return [ordered]@{ Id = $null; Status = "missing"; Running = $false; ExitCode = $null; Health = $null }
  }
  $fmt = '{{json .State}}'
  $r = Invoke-PreG5DockerControlAllowFail -What "inspect container state $ContainerId" -DockerArgs @(
    "inspect", $ContainerId, "--format", $fmt
  )
  if ($r.Code -ne 0) {
    return [ordered]@{ Id = $ContainerId; Status = "inspect_unresolved"; Running = $null; ExitCode = $null; Health = $null; Err = $r.StdErr }
  }
  try {
    $st = ($r.StdOut | ConvertFrom-Json)
    $stNames = Get-DisposablePsObjectPropertyNames -Object $st
    $status = $null
    $running = $null
    $exitCode = $null
    if ($stNames -contains 'Status') { $status = [string]$st.Status }
    if ($stNames -contains 'Running') { $running = [bool]$st.Running }
    if ($stNames -contains 'ExitCode') { $exitCode = $st.ExitCode }
    $health = $null
    if ($stNames -contains 'Health') {
      $healthObj = $st.Health
      if ($null -ne $healthObj) {
        $healthNames = Get-DisposablePsObjectPropertyNames -Object $healthObj
        if ($healthNames -contains 'Status') { $health = [string]$healthObj.Status }
      }
    }
    return [ordered]@{
      Id       = $ContainerId
      Status   = $status
      Running  = $running
      ExitCode = $exitCode
      Health   = $health
    }
  } catch {
    return [ordered]@{ Id = $ContainerId; Status = "inspect_parse_fail"; Running = $null; ExitCode = $null; Health = $null }
  }
}

function Get-DisposableServiceContainerStateForDiagnostics {
  param(
    [Parameter(Mandatory = $true)][string] $ProjectName,
    [Parameter(Mandatory = $true)][string] $ServiceName
  )
  try {
    $cid = Get-DisposableProjectServiceContainerId -ProjectName $ProjectName -ServiceName $ServiceName
    if ([string]::IsNullOrWhiteSpace($cid)) {
      return [ordered]@{ Id = $null; Status = "missing"; Running = $false; ExitCode = $null; Health = $null; Service = $ServiceName }
    }
    $snap = Get-DisposableContainerStateSnapshot -ContainerId $cid
    $snap.Service = $ServiceName
    return $snap
  } catch {
    return [ordered]@{
      Id      = $null
      Status  = "lookup_fail"
      Running = $null
      ExitCode = $null
      Health  = $null
      Service = $ServiceName
      Err     = $_.Exception.Message
    }
  }
}

function Capture-DisposableFailureDiagnostics {
  param(
    [Parameter(Mandatory = $true)][string] $ProjectName,
    [Parameter(Mandatory = $true)][string] $EvidenceDir,
    [scriptblock] $ComposeInvoker,
    [int] $LogMaxBytes = 65536,
    [int] $ComposeTimeoutMs = 180000
  )
  $apiState = Get-DisposableServiceContainerStateForDiagnostics -ProjectName $ProjectName -ServiceName "api"
  $webState = Get-DisposableServiceContainerStateForDiagnostics -ProjectName $ProjectName -ServiceName "web"
  $apiLog = ""
  $webLog = ""
  $logNotes = New-Object System.Collections.Generic.List[string]
  if ($null -ne $ComposeInvoker) {
    foreach ($pair in @(@{ Svc = "api"; Var = "apiLog" }, @{ Svc = "web"; Var = "webLog" })) {
      try {
        $lr = & $ComposeInvoker -ComposeArgs @("logs", "--no-color", "--tail", "200", $pair.Svc) `
          -What ("compose logs " + $pair.Svc) -TimeoutMs $ComposeTimeoutMs
        if ($pair.Var -eq "apiLog") { $apiLog = Limit-DisposableTextBytes -Text ([string]$lr.StdOut) -MaxBytes $LogMaxBytes }
        else { $webLog = Limit-DisposableTextBytes -Text ([string]$lr.StdOut) -MaxBytes $LogMaxBytes }
      } catch {
        $logNotes.Add("$($pair.Svc)_logs:$($_.Exception.Message)")
      }
    }
  }
  $diag = [ordered]@{
    stage      = "failure_diagnostics"
    captured_utc = (Get-Date).ToUniversalTime().ToString("o")
    api        = $apiState
    web        = $webState
    log_notes  = @($logNotes)
  }
  $diagPath = Join-Path $EvidenceDir "failure-diagnostics.json"
  ($diag | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $diagPath -Encoding utf8
  Set-Content -LiteralPath (Join-Path $EvidenceDir "api.log.txt") -Value $apiLog -Encoding utf8
  Set-Content -LiteralPath (Join-Path $EvidenceDir "web.log.txt") -Value $webLog -Encoding utf8
  return $diag
}

function Assert-DisposableContainerRuntimeRunning {
  param(
    [Parameter(Mandatory = $true)][string] $ContainerId,
    [Parameter(Mandatory = $true)][string] $ServiceName
  )
  $snap = Get-DisposableContainerStateSnapshot -ContainerId $ContainerId
  if ($snap.Status -ceq "running" -and $snap.Running -eq $true) { return $snap }
  throw ("PREG5_DISP_FAIL: ${ServiceName} container not running Status=$($snap.Status) ExitCode=$($snap.ExitCode)")
}

function Invoke-DisposableAttemptCleanup {
  <#
    Single cleanup attempt. Always writes cleanup-outcome.final.json (overwrite OK).
    owned-resources-before-cleanup.json written once. cleanup.receipt.json only on verified success.
  #>
  param(
    [Parameter(Mandatory = $true)][string] $ProjectName,
    [Parameter(Mandatory = $true)][string] $EvidenceDir,
    [Parameter(Mandatory = $true)] $OwnedResources,
    [scriptblock] $ComposeInvoker,
    [int] $ComposeTimeoutMs = 180000,
    [switch] $WriteSuccessReceipt
  )
  $prePath = Join-Path $EvidenceDir "owned-resources-before-cleanup.json"
  if (-not (Test-Path -LiteralPath $prePath)) {
    ($OwnedResources | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $prePath -Encoding utf8
  }
  $downNotes = New-Object System.Collections.Generic.List[string]
  try {
    & $ComposeInvoker -ComposeArgs @("down", "-v", "--remove-orphans") -What "compose down -v" -TimeoutMs $ComposeTimeoutMs | Out-Null
  } catch {
    $downNotes.Add("down_v:" + $_.Exception.Message)
  }
  $verify = $null
  try {
    $verify = Assert-DisposableResourcesGone -Owned $OwnedResources -ProjectName $ProjectName
  } catch {
    $downNotes.Add("verify_gone:" + $_.Exception.Message)
    $verify = [ordered]@{ Ok = $false; Uncertain = $true; Notes = @($downNotes) }
  }
  if ($verify.Uncertain) {
    foreach ($n in @($verify.Notes)) { if ($n) { $downNotes.Add([string]$n) } }
  }
  $finalPath = Join-Path $EvidenceDir "cleanup-outcome.final.json"
  $outcome = [ordered]@{
    stage                 = "cleanup_outcome_final"
    cleanup_ok            = [bool]$verify.Ok
    cleanup_uncertain     = [bool]$verify.Uncertain
    notes                 = @($downNotes)
    owned_before_cleanup  = $OwnedResources
    verified_utc          = (Get-Date).ToUniversalTime().ToString("o")
  }
  ($outcome | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $finalPath -Encoding utf8
  if ($verify.Ok -and $WriteSuccessReceipt) {
    $cleanupPath = Join-Path $EvidenceDir "cleanup.receipt.json"
    Assert-DurablePathWritable $cleanupPath | Out-Null
    ($outcome | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $cleanupPath -Encoding utf8
  }
  if (-not $verify.Ok) {
    throw ("PREG5_DISP_FAIL: post-cleanup verification failed uncertain=$($verify.Uncertain) notes=" + ($downNotes -join '; '))
  }
  return $outcome
}

function Invoke-PreG5Disposable042ValidationCore {
  <#
    Testable disposable validation orchestration. Caller must dot-source PreG5-SnapshotHelpers.ps1 first.
    Returns [ordered]@{ ExitCode; RefusalNoCleanup; EvidenceDir; ... }
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
    [int] $HttpTimeoutSec = 20,
    [switch] $SkipHttpChecks,
    [scriptblock] $HttpChecker = $null,
    [scriptblock] $HttpProbe = $null,
    [int] $HttpReadinessDeadlineMs = 120000,
    [int] $HttpReadinessPollSec = 2,
    [int] $DiagnosticLogMaxBytes = 65536,
    [int[]] $PreflightHostPorts = @(18000, 18080),
    [ValidateSet('SingleNet', 'DualNet')]
    [string] $OwnedNetworkProfile = 'SingleNet',
    [switch] $DualNet
  )

  $useDualNet = $false
  if ($DualNet) {
    $useDualNet = $true
    $OwnedNetworkProfile = 'DualNet'
  } elseif ($OwnedNetworkProfile -eq 'DualNet') {
    $useDualNet = $true
  } elseif (Test-PreG5DisposableComposeFileImpliesDualNet -ComposeFile $ComposeFile) {
    $useDualNet = $true
    $OwnedNetworkProfile = 'DualNet'
  }

  $envKeys = @(
    'SNAPSHOT_API_IMAGE', 'SNAPSHOT_WEB_IMAGE', 'POSTGRES_IMAGE',
    'PREG5_SESSION_SECRET', 'PREG5_TOKEN_ENCRYPTION_KEY'
  )

  $st = @{
    OwnedProject     = $false
    OwnedResources   = $null
    EvidenceDir      = $null
    ProjectDir       = $null
    RefusalNoCleanup = $false
    ExitCode         = 1
    CleanupAttempted = $false
  }
  $durableNotes = New-Object System.Collections.Generic.List[string]

  function _Fail([string] $msg) { throw ("PREG5_DISP_FAIL: " + $msg) }
  function _FailRefuse([string] $msg) {
    $st.RefusalNoCleanup = $true
    throw ("PREG5_DISP_FAIL: " + $msg)
  }
  function _RefreshOwned([string] $why) {
    try {
      $st.OwnedResources = Get-DisposableOwnedResources -ProjectName $ProjectName -DualNet:$useDualNet
      $durableNotes.Add("refresh_owned:$why")
    } catch {
      $durableNotes.Add("refresh_owned_unresolved:${why}:$($_.Exception.Message)")
    }
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
      -OwnedResources $st.OwnedResources -ComposeInvoker $composeInvoker -ComposeTimeoutMs $ComposeTimeoutMs `
      -WriteSuccessReceipt:$WriteSuccessReceipt
  }

  function _WriteFailureReceipt {
    param($CleanupOutcome = $null)
    if (-not $st.EvidenceDir) { return }
    $failPath = Join-Path $st.EvidenceDir "failure.receipt.json"
    if (Test-Path -LiteralPath $failPath) { return }
    $httpObsFailRef = $null
    if ($st.EvidenceDir) {
      $httpObsPath = Join-Path $st.EvidenceDir (Get-PreG5DisposableHttpEndpointObservationsFileName)
      if (Test-Path -LiteralPath $httpObsPath) {
        $httpObsFailRef = [ordered]@{
          path   = (Get-PreG5DisposableHttpEndpointObservationsFileName)
          sha256 = (Get-PreG5FileSha256Hex -Path $httpObsPath)
        }
      }
    }
    $obj = [ordered]@{
      failed                = $true
      startup_validation_ok = $false
      rollback_acceptance   = $false
      not_backup_restore    = $true
      notes                 = @($durableNotes)
      owned                 = $st.OwnedResources
      cleanup_outcome       = $CleanupOutcome
      http_endpoint_observations = $httpObsFailRef
    }
    Assert-DurablePathWritable $failPath | Out-Null
    ($obj | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $failPath -Encoding utf8
  }

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
      Assert-DisposableAttemptDirClear -AttemptDir $evidence | Out-Null
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

    $envPath = Join-Path $st.ProjectDir ".env"
    $session = -join ((1..48) | ForEach-Object { "{0:x}" -f (Get-Random -Max 16) })
    $tok = -join ((1..48) | ForEach-Object { "{0:x}" -f (Get-Random -Max 16) })
    @(
      "SNAPSHOT_API_IMAGE=$SnapshotApiImage"
      "SNAPSHOT_WEB_IMAGE=$SnapshotWebImage"
      "POSTGRES_IMAGE=$PostgresImage"
      "PREG5_SESSION_SECRET=$session"
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
    $cfgYamlPath = Join-Path $evidence "compose.rendered.yaml"
    Set-Content -LiteralPath $cfgYamlPath -Value $yamlOut.StdOut -Encoding utf8

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

    $apiImgField = Assert-RunningContainerImagePin -ContainerId $apiCid -ExpectedImageId $SnapshotApiImage
    $webImgField = Assert-RunningContainerImagePin -ContainerId $webCid -ExpectedImageId $SnapshotWebImage

    $httpObsRef = $null
    if (-not $SkipHttpChecks) {
      $httpDeadline = [datetime]::UtcNow.AddMilliseconds($HttpReadinessDeadlineMs)
      $httpObsRef = Invoke-DisposableStartupValidationHttpChecks -EvidenceDir $evidence -AttemptId $AttemptId `
        -HttpTimeoutSec $HttpTimeoutSec -HttpDeadlineUtc $httpDeadline -HttpReadinessPollSec $HttpReadinessPollSec `
        -HttpChecker $HttpChecker -HttpProbe $HttpProbe
    }

    $sched = Invoke-PreG5DockerControlAllowFail -What "ps scheduler" -DockerArgs @(
      "ps", "-a", "--filter", "label=com.docker.compose.project=$ProjectName",
      "--filter", "label=com.docker.compose.service=scheduler", "--format", "{{.ID}}"
    )
    if ($sched.Code -ne 0) {
      _Fail "scheduler container list failed code=$($sched.Code) err=$($sched.StdErr)"
    }
    if (-not [string]::IsNullOrWhiteSpace($sched.StdOut)) {
      _Fail "scheduler container present in disposable project"
    }

    $optionB = Get-DisposableStartupValidationEgressDisclosure -AttemptId $AttemptId
    $candidatePath = Join-Path $evidence "validation.candidate.json"
    $candidate = [ordered]@{
      stage                         = "Disposable042StartupValidation_candidate"
      stamp                         = $stamp
      attempt_id                    = $AttemptId
      project                       = $ProjectName
      taken_utc                     = (Get-Date).ToUniversalTime().ToString("o")
      schema_method                 = "alembic_upgrade_on_empty_db_fresh_042_schema"
      not_backup_restore            = $true
      restored_data_rollback_proof  = $false
      startup_validation_ok         = $true
      dual_net                      = [bool]$useDualNet
      owned_network_profile         = $OwnedNetworkProfile
      auth_content_expectation      = "SETUP_REQUIRED"
      option_b                      = $optionB
      rollback_acceptance           = $false
      rollback_pin_updated          = $false
      snapshot_api_image_id         = $SnapshotApiImage
      snapshot_web_image_id         = $SnapshotWebImage
      postgres_image_id             = $PostgresImage
      expect_alembic                = $ExpectAlembic
      alembic_version_sql           = $sqlVer.Trim()
      api_container_id              = $apiCid
      web_container_id              = $webCid
      api_container_image_field     = $apiImgField
      web_container_image_field     = $webImgField
      household_unverified          = $true
      household_note                = "This run does not inspect household compose; no agent_credentials/household runtime claims."
      owned_resources               = $st.OwnedResources
      http_endpoint_observations    = $httpObsRef
    }
    Assert-DurablePathWritable $candidatePath | Out-Null
    ($candidate | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $candidatePath -Encoding utf8

    _AttemptOwnedCleanup -WriteSuccessReceipt | Out-Null

    $st.OwnedProject = $false
    $valPath = Join-Path $evidence "validation.receipt.json"
    $receipt = [ordered]@{}
    foreach ($k in $candidate.Keys) { $receipt[$k] = $candidate[$k] }
    $receipt.stage = "Disposable042StartupValidation"
    $receipt.cleanup_verified = $true
    $receipt.next = "STOP — restored-data rollback proof and pin update remain separately held"
    Assert-DurablePathWritable $valPath | Out-Null
    ($receipt | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $valPath -Encoding utf8
    $st.ExitCode = 0
  }
  catch {
    $durableNotes.Add("fail:" + $_.Exception.Message)
    if ($st.RefusalNoCleanup -or -not $st.OwnedProject) {
      $st.ExitCode = 1
    } else {
      $cleanupOutcome = $null
      if ($st.OwnedProject -and $st.EvidenceDir) {
        try {
          Capture-DisposableFailureDiagnostics -ProjectName $ProjectName -EvidenceDir $st.EvidenceDir `
            -ComposeInvoker $composeInvoker -LogMaxBytes $DiagnosticLogMaxBytes -ComposeTimeoutMs $ComposeTimeoutMs | Out-Null
        } catch {
          $durableNotes.Add("diagnostics_collect_fail:" + $_.Exception.Message)
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
      _WriteFailureReceipt -CleanupOutcome $cleanupOutcome
      $st.ExitCode = 1
    }
  }

  return ,[ordered]@{
    ExitCode           = $st.ExitCode
    RefusalNoCleanup   = $st.RefusalNoCleanup
    EvidenceDir        = $st.EvidenceDir
    OwnedProjectAtEnd  = $st.OwnedProject
    Notes              = @($durableNotes)
  }
}

function Get-PreG5DefaultDisposable042RestoredDataInventoryManifestPath {
  param([string] $RunbooksRoot = $PSScriptRoot)
  return Join-Path $RunbooksRoot "fixtures\preg5-g3b-042-restored-data-inventory-manifest.v1.json"
}

function Import-PreG5DisposableRestoredDataInventoryManifest {
  param([Parameter(Mandatory = $true)][string] $Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    throw ("PREG5_DISP_FAIL: inventory manifest missing path=$Path")
  }
  $raw = Get-Content -LiteralPath $Path -Raw
  $obj = $raw | ConvertFrom-Json
  if ([string]$obj.artifact -ne 'preg5-disposable-042-restored-data-inventory-manifest') {
    throw "PREG5_DISP_FAIL: inventory manifest artifact mismatch"
  }
  return $obj
}

function Get-PreG5DisposableAgentCredentialsAbsentProbeSql {
  <#
    Catalog-only probe: must not reference public.agent_credentials as a bare relation
    (PostgreSQL resolves missing relations before CASE branches evaluate).
  #>
  return @"
SELECT CASE
  WHEN NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'agent_credentials'
      AND c.relkind IN ('r', 'p')
  ) THEN 'absent'
  ELSE 'present'
END
"@
}

function Test-PreG5DisposableAgentCredentialsAbsentProbeSqlText {
  param([Parameter(Mandatory = $true)][string] $Sql)
  if ($Sql -match '(?i)(FROM|JOIN)\s+agent_credentials\b') {
    throw "PREG5_DISP_FAIL: agent_credentials probe SQL must not use bare FROM/JOIN on agent_credentials"
  }
  if ($Sql -notmatch 'pg_catalog\.pg_class') {
    throw "PREG5_DISP_FAIL: agent_credentials probe SQL must use catalog existence check"
  }
  return $true
}

function Test-PreG5LiveSqlBoundaryOptInRequested {
  param([switch] $AllowLivePostgres)
  if ($AllowLivePostgres) { return $true }
  $envVal = [Environment]::GetEnvironmentVariable('PREG5_LIVE_SQL_BOUNDARY')
  if ($envVal -eq '1' -or ($envVal -and $envVal.Trim().ToLowerInvariant() -ceq 'true')) { return $true }
  return $false
}

function Invoke-PreG5DisposableAgentCredentialsAbsentSqlBoundaryProof {
  <#
    Proves absent-table SQL runs on real Postgres without missing-relation errors.
    Default (no opt-in): returns mode=skipped — orchestration keeps injected PreG5DockerRunner and uses text proof only.
    Opt-in: -AllowLivePostgres, env PREG5_LIVE_SQL_BOUNDARY=1, or Invoke-PreG5DisposableAgentCredentialsSqlBoundaryLive.ps1 -Execute.
    Live path: pinned Postgres image digest, dedicated container name + isolated bridge network, verified rm/network cleanup.
  #>
  param(
    [string] $PostgresImage = "sha256:93d55776e04376e19adb2733e3ccebb4392ee7dd86d8ff238503b30fe719c84f",
    [int] $DockerTimeoutMs = 120000,
    [switch] $AllowLivePostgres
  )
  $sql = Get-PreG5DisposableAgentCredentialsAbsentProbeSql
  Test-PreG5DisposableAgentCredentialsAbsentProbeSqlText -Sql $sql | Out-Null
  if (-not (Test-PreG5LiveSqlBoundaryOptInRequested -AllowLivePostgres:$AllowLivePostgres)) {
    return [ordered]@{ mode = 'skipped'; live_postgres = $false; skip_reason = 'not_opt_in'; sql = $sql }
  }
  if ($null -ne $script:PreG5DockerRunner) {
    return [ordered]@{ mode = 'skipped'; live_postgres = $false; skip_reason = 'injected_runner'; sql = $sql }
  }
  $ver = Invoke-PreG5DockerControlAllowFail -What "docker version" -DockerArgs @("version", "--format", "{{.ServerVersion}}")
  if ($ver.Code -ne 0) {
    return [ordered]@{ mode = 'skipped'; live_postgres = $false; skip_reason = 'docker_unavailable'; sql = $sql }
  }
  $cid = $null
  $netName = $null
  $contName = "preg5-agent-cred-sql-boundary-" + [guid]::NewGuid().ToString("N").Substring(0, 12)
  try {
    $netName = "preg5-sql-boundary-net-" + [guid]::NewGuid().ToString("N").Substring(0, 12)
    $netCreate = Invoke-PreG5DockerControlAllowFail -What "boundary network create" -DockerArgs @("network", "create", $netName)
    if ($netCreate.Code -ne 0) {
      throw ("PREG5_DISP_FAIL: boundary network create failed code=$($netCreate.Code) err=$($netCreate.StdErr)")
    }
    $run = Invoke-PreG5DockerControlAllowFail -What "agent_credentials sql boundary postgres" -TimeoutMs $DockerTimeoutMs `
      -DockerArgs @("run", "-d", "--name", $contName, "--network", $netName, "-e", "POSTGRES_HOST_AUTH_METHOD=trust", $PostgresImage)
    if ($run.Code -ne 0) {
      throw ("PREG5_DISP_FAIL: boundary postgres run failed code=$($run.Code) err=$($run.StdErr)")
    }
    $cid = ($run.StdOut -split "`r?`n" | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1).Trim()
    if ([string]::IsNullOrWhiteSpace($cid)) { throw "PREG5_DISP_FAIL: boundary postgres container id empty" }
    $deadline = [datetime]::UtcNow.AddSeconds(60)
    $ready = $false
    while ([datetime]::UtcNow -lt $deadline) {
      $chk = Invoke-PreG5DockerControlAllowFail -What "boundary pg_isready" -DockerArgs @(
        "exec", $cid, "pg_isready", "-U", "postgres"
      )
      if ($chk.Code -eq 0) { $ready = $true; break }
      Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw "PREG5_DISP_FAIL: boundary postgres not ready" }
    $absent = Invoke-PreG5DockerControlAllowFail -What "boundary absent probe" -DockerArgs @(
      "exec", $cid, "psql", "-U", "postgres", "-d", "postgres", "-tAc", $sql
    )
    if ($absent.Code -ne 0) {
      throw ("PREG5_DISP_FAIL: boundary absent probe failed code=$($absent.Code) err=$($absent.StdErr)")
    }
    $absentVal = ($absent.StdOut -split "`r?`n" | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1)
    if ($null -eq $absentVal) { $absentVal = "" }
    $absentVal = $absentVal.Trim()
    if ($absentVal -cne 'absent') {
      throw ("PREG5_DISP_FAIL: boundary absent probe want=absent got=$absentVal")
    }
    $mk = Invoke-PreG5DockerControlAllowFail -What "boundary create agent_credentials" -DockerArgs @(
      "exec", $cid, "psql", "-U", "postgres", "-d", "postgres", "-c",
      "CREATE TABLE public.agent_credentials (id int);"
    )
    if ($mk.Code -ne 0) {
      throw ("PREG5_DISP_FAIL: boundary create table failed code=$($mk.Code) err=$($mk.StdErr)")
    }
    $present = Invoke-PreG5DockerControlAllowFail -What "boundary present probe" -DockerArgs @(
      "exec", $cid, "psql", "-U", "postgres", "-d", "postgres", "-tAc", $sql
    )
    if ($present.Code -ne 0) {
      throw ("PREG5_DISP_FAIL: boundary present probe failed code=$($present.Code) err=$($present.StdErr)")
    }
    $presentVal = ($present.StdOut -split "`r?`n" | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1)
    if ($null -eq $presentVal) { $presentVal = "" }
    $presentVal = $presentVal.Trim()
    if ($presentVal -cne 'present') {
      throw ("PREG5_DISP_FAIL: boundary present probe want=present got=$presentVal")
    }
    return [ordered]@{ mode = 'live_postgres'; live_postgres = $true; sql = $sql }
  }
  finally {
    if (-not [string]::IsNullOrWhiteSpace($cid)) {
      $rm = Invoke-PreG5DockerControlAllowFail -What "boundary postgres rm" -DockerArgs @("rm", "-f", $cid)
      if ($rm.Code -ne 0) {
        throw ("PREG5_DISP_FAIL: boundary postgres rm failed code=$($rm.Code) err=$($rm.StdErr)")
      }
    } elseif (-not [string]::IsNullOrWhiteSpace($contName)) {
      $rmByName = Invoke-PreG5DockerControlAllowFail -What "boundary postgres rm by name" -DockerArgs @("rm", "-f", $contName)
      if ($rmByName.Code -ne 0 -and $rmByName.StdErr -notmatch 'No such container') {
        throw ("PREG5_DISP_FAIL: boundary postgres rm by name failed code=$($rmByName.Code) err=$($rmByName.StdErr)")
      }
    }
    if (-not [string]::IsNullOrWhiteSpace($netName)) {
      $netRm = Invoke-PreG5DockerControlAllowFail -What "boundary network rm" -DockerArgs @("network", "rm", $netName)
      if ($netRm.Code -ne 0 -and $netRm.StdErr -notmatch 'No such network') {
        throw ("PREG5_DISP_FAIL: boundary network rm failed code=$($netRm.Code) err=$($netRm.StdErr)")
      }
    }
  }
}

function Limit-PreG5DisposableEvidenceText {
  param(
    [string] $Text,
    [int] $MaxBytes = 65536
  )
  if ([string]::IsNullOrEmpty($Text)) { return "" }
  $enc = [System.Text.Encoding]::UTF8
  $bytes = $enc.GetBytes($Text)
  if ($bytes.Length -le $MaxBytes) { return $Text }
  $slice = $enc.GetString($bytes, 0, $MaxBytes)
  return ($slice + "`n...(truncated at ${MaxBytes} bytes)")
}

function Write-PreG5DisposablePgRestoreOutcomeArtifact {
  param(
    [Parameter(Mandatory = $true)][string] $EvidenceDir,
    [Parameter(Mandatory = $true)] $RestoreResult,
    [int] $StderrMaxBytes = 65536
  )
  $path = Join-Path $EvidenceDir "pg-restore-outcome.json"
  $obj = [ordered]@{
    artifact     = "preg5-disposable-pg-restore-outcome"
    exit_code    = [int]$RestoreResult.Code
    stdout       = Limit-PreG5DisposableEvidenceText -Text ([string]$RestoreResult.StdOut) -MaxBytes $StderrMaxBytes
    stderr       = Limit-PreG5DisposableEvidenceText -Text ([string]$RestoreResult.StdErr) -MaxBytes $StderrMaxBytes
    timed_out    = [bool]$RestoreResult.TimedOut
    captured_utc = (Get-Date).ToUniversalTime().ToString("o")
  }
  Assert-DurablePathWritable $path | Out-Null
  ($obj | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $path -Encoding utf8
  return [ordered]@{
    path   = "pg-restore-outcome.json"
    sha256 = (Get-PreG5FileSha256Hex -Path $path)
  }
}

function Write-PreG5DisposableInventoryObservationsArtifact {
  param(
    [Parameter(Mandatory = $true)][string] $EvidenceDir,
    [Parameter(Mandatory = $true)] $Observations
  )
  $path = Join-Path $EvidenceDir "inventory-observations.json"
  $obj = [ordered]@{
    artifact          = "preg5-disposable-042-inventory-observations"
    captured_utc      = (Get-Date).ToUniversalTime().ToString("o")
    authority_source  = [string]$Observations.authority_source
    alembic_version   = [string]$Observations.alembic_version
    user_count        = [int]$Observations.user_count
    task_count        = [int]$Observations.task_count
    user_settings_count = [int]$Observations.user_settings_count
    user_ids_csv      = [string]$Observations.user_ids_csv
    task_ids_csv      = [string]$Observations.task_ids_csv
    agent_credentials = [string]$Observations.agent_credentials
  }
  Assert-DurablePathWritable $path | Out-Null
  ($obj | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $path -Encoding utf8
  return [ordered]@{
    path   = "inventory-observations.json"
    sha256 = (Get-PreG5FileSha256Hex -Path $path)
  }
}

function Assert-PreG5DisposableDumpSidecarAndMeta {
  param(
    [Parameter(Mandatory = $true)][string] $DumpPath,
    [Parameter(Mandatory = $true)][string] $ExpectedSha256,
    [string] $ExpectSourceAlembic = "042_task_occurrence_dispositions",
    [string] $ExpectSourceDatabase = "theplan",
    [string] $ExpectMode = "read_only_no_quiesce"
  )
  if (-not (Test-Path -LiteralPath $DumpPath)) {
    throw ("PREG5_DISP_FAIL: dump path missing $DumpPath")
  }
  $shaPath = "$DumpPath.sha256"
  $metaPath = "$DumpPath.meta.json"
  if (-not (Test-Path -LiteralPath $shaPath)) {
    throw ("PREG5_DISP_FAIL: dump .sha256 sidecar missing path=$shaPath")
  }
  if (-not (Test-Path -LiteralPath $metaPath)) {
    throw ("PREG5_DISP_FAIL: dump .meta.json sidecar missing path=$metaPath")
  }
  $computed = (Get-PreG5FileSha256Hex -Path $DumpPath).ToUpperInvariant()
  $want = $ExpectedSha256.Trim().ToUpperInvariant()
  if ($computed -cne $want) {
    throw ("PREG5_DISP_FAIL: dump sha256 mismatch want=$want got=$computed")
  }
  $side = (Get-Content -LiteralPath $shaPath -Raw).Trim().ToUpperInvariant()
  if ($side -match '^([A-F0-9]{64})') { $side = $Matches[1] }
  if ($side -cne $want) {
    throw ("PREG5_DISP_FAIL: dump sidecar sha256 mismatch want=$want got=$side")
  }
  $meta = Get-Content -LiteralPath $metaPath -Raw | ConvertFrom-Json
  if ([string]$meta.source_alembic -cne $ExpectSourceAlembic) {
    throw ("PREG5_DISP_FAIL: dump meta source_alembic mismatch want=$ExpectSourceAlembic got=$($meta.source_alembic)")
  }
  if ([string]$meta.source_database -cne $ExpectSourceDatabase) {
    throw ("PREG5_DISP_FAIL: dump meta source_database mismatch want=$ExpectSourceDatabase got=$($meta.source_database)")
  }
  $mode = [string]$meta.mode
  if ($mode -cne $ExpectMode -and $mode -cne 'read_only_no_quiesce_not_g1') {
    throw ("PREG5_DISP_FAIL: dump meta mode mismatch want=$ExpectMode got=$mode")
  }
  return [ordered]@{
    path          = $DumpPath
    sha256        = $want
    meta_path     = $metaPath
    source_alembic = [string]$meta.source_alembic
    source_database = [string]$meta.source_database
    mode          = $mode
  }
}

function Assert-PreG5DisposableDumpFileBinding {
  param(
    [Parameter(Mandatory = $true)][string] $DumpPath,
    [Parameter(Mandatory = $true)][string] $ExpectedSha256
  )
  return Assert-PreG5DisposableDumpSidecarAndMeta -DumpPath $DumpPath -ExpectedSha256 $ExpectedSha256
}

function Get-DisposableRestoredDataEgressDisclosure {
  param([string] $AttemptId = "")
  $base = Get-DisposableStartupValidationEgressDisclosure -AttemptId $AttemptId
  $base.startup_validation_scope = "Host probes on restored pg_restore data @ 042: API/web auth/me expect UNAUTHENTICATED (users exist); web shell title thePlan."
  $base.restored_data_note = "Disposable pg_restore rehearsal/G1-style dump proof — not household rollback_acceptance."
  return $base
}

function Get-DisposableRestoredDataHttpCheckMatrix {
  return @(
    @{ Uri = "http://127.0.0.1:18000/api/v1/auth/me"; Status = 401; Body = @(); JsonCode = "UNAUTHENTICATED" },
    @{ Uri = "http://127.0.0.1:18080/"; Status = 200; Body = @("<title>thePlan</title>"); JsonCode = "" },
    @{ Uri = "http://127.0.0.1:18080/api/v1/auth/me"; Status = 401; Body = @(); JsonCode = "UNAUTHENTICATED" }
  )
}

function Invoke-DisposableRestoredDataHttpChecks {
  param(
    [Parameter(Mandatory = $true)][string] $EvidenceDir,
    [Parameter(Mandatory = $true)][string] $AttemptId,
    [int] $HttpTimeoutSec = 20,
    [Parameter(Mandatory = $true)][datetime] $HttpDeadlineUtc,
    [int] $HttpReadinessPollSec = 2,
    [scriptblock] $HttpChecker = $null,
    [scriptblock] $HttpProbe = $null
  )
  $checks = Get-DisposableRestoredDataHttpCheckMatrix
  $collected = New-Object System.Collections.Generic.List[object]
  $defaultProbe = {
    param($Uri, $ExpectStatus, $BodyMustContain, $TimeoutSec, [string] $ExpectJsonCode = "")
    Invoke-DisposableStartupHttpProbeCore -Uri $Uri -ExpectStatus $ExpectStatus -BodyMustContain $BodyMustContain `
      -ExpectJsonCode $ExpectJsonCode -TimeoutSec $TimeoutSec | ForEach-Object {
      if ($_.classification -ne 'http_ok') { Throw-DisposableHttpCheckFailed -Observation $_ }
      $_
    }
  }
  $probe = if ($null -ne $HttpProbe) { $HttpProbe } else { $defaultProbe }

  function _WritePartialArtifact {
    if ($collected.Count -lt 1) { return }
    Write-DisposableHttpEndpointObservationsArtifact -EvidenceDir $EvidenceDir -AttemptId $AttemptId `
      -EndpointObservations $collected.ToArray() | Out-Null
  }

  foreach ($hc in $checks) {
    try {
      if ($null -ne $HttpChecker) {
        $obs = & $HttpChecker -Uri $hc.Uri -ExpectStatus $hc.Status -BodyMustContain $hc.Body `
          -ExpectJsonCode $hc.JsonCode -TimeoutSec $HttpTimeoutSec
        if ($null -eq $obs) {
          throw "PREG5_DISP_FAIL: HttpChecker must return a structured endpoint observation"
        }
      } else {
        $obs = Invoke-DisposableHttpCheckWithReadiness -Uri $hc.Uri -ExpectStatus $hc.Status `
          -BodyMustContain $hc.Body -ExpectJsonCode $hc.JsonCode -DeadlineUtc $HttpDeadlineUtc `
          -PerRequestTimeoutSec $HttpTimeoutSec -PollSec $HttpReadinessPollSec -ProbeScriptBlock $probe
      }
      $collected.Add($obs) | Out-Null
    } catch {
      $failObs = Get-DisposableHttpEndpointObservationFromErrorRecord -ErrorRecord $_
      if ($null -ne $failObs) {
        $collected.Add($failObs) | Out-Null
      }
      if ($collected.Count -ge 1) {
        _WritePartialArtifact
      }
      throw
    }
  }

  return Write-DisposableHttpEndpointObservationsArtifact -EvidenceDir $EvidenceDir -AttemptId $AttemptId `
    -EndpointObservations $collected.ToArray()
}

function Invoke-DisposableComposePostgresSql {
  param(
    [Parameter(Mandatory = $true)][scriptblock] $ComposeInvoker,
    [Parameter(Mandatory = $true)][string] $Sql,
    [string] $What = "postgres sql"
  )
  $out = & $ComposeInvoker -What $What -ComposeArgs @(
    "exec", "-T", "postgres",
    "psql", "-U", "preg5", "-d", "theplan_preg5", "-tAc", $Sql
  )
  $line = ($out.StdOut -split "`r?`n" | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1)
  if ($null -eq $line) { return "" }
  return $line.Trim()
}

function Assert-PreG5DisposableRestoredDbInventory {
  param(
    [Parameter(Mandatory = $true)] $Manifest,
    [Parameter(Mandatory = $true)][scriptblock] $ComposeInvoker,
    [Parameter(Mandatory = $true)][string] $EvidenceDir
  )
  if ([string]::IsNullOrWhiteSpace([string]$Manifest.user_ids_csv)) {
    throw "PREG5_DISP_FAIL: inventory manifest user_ids_csv required (non-empty authority)"
  }
  if ([string]::IsNullOrWhiteSpace([string]$Manifest.task_ids_csv)) {
    throw "PREG5_DISP_FAIL: inventory manifest task_ids_csv required (non-empty authority)"
  }
  if ($null -eq $Manifest.settings_count) {
    throw "PREG5_DISP_FAIL: inventory manifest settings_count required"
  }
  $authoritySource = [string]$Manifest.inventory_authority_source
  if ([string]::IsNullOrWhiteSpace($authoritySource)) {
    $authoritySource = "G3B-1793594054"
  }

  $sqlAlembic = "SELECT version_num FROM alembic_version;"
  $ver = Invoke-DisposableComposePostgresSql -ComposeInvoker $ComposeInvoker -Sql $sqlAlembic -What "alembic_version sql"
  if ([string]::IsNullOrWhiteSpace($ver)) { throw "PREG5_DISP_FAIL: alembic_version SQL empty after restore" }

  $users = [int](Invoke-DisposableComposePostgresSql -ComposeInvoker $ComposeInvoker `
    -Sql "SELECT count(*)::text FROM users" -What "users count")
  $tasks = [int](Invoke-DisposableComposePostgresSql -ComposeInvoker $ComposeInvoker `
    -Sql "SELECT count(*)::text FROM tasks" -What "tasks count")
  $settings = [int](Invoke-DisposableComposePostgresSql -ComposeInvoker $ComposeInvoker `
    -Sql "SELECT count(*)::text FROM user_settings" -What "user_settings count")
  $userIds = Invoke-DisposableComposePostgresSql -ComposeInvoker $ComposeInvoker `
    -Sql "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM users" -What "users ids"
  $taskIds = Invoke-DisposableComposePostgresSql -ComposeInvoker $ComposeInvoker `
    -Sql "SELECT string_agg(id::text, ',' ORDER BY id::text) FROM tasks" -What "tasks ids"

  $acSql = Get-PreG5DisposableAgentCredentialsAbsentProbeSql
  Test-PreG5DisposableAgentCredentialsAbsentProbeSqlText -Sql $acSql | Out-Null
  $ac = Invoke-DisposableComposePostgresSql -ComposeInvoker $ComposeInvoker -Sql $acSql -What "agent_credentials probe"

  $obsPayload = [ordered]@{
    authority_source      = $authoritySource
    alembic_version       = $ver
    user_count            = $users
    task_count            = $tasks
    user_settings_count   = $settings
    user_ids_csv          = $userIds
    task_ids_csv          = $taskIds
    agent_credentials     = $ac
  }
  $obsRef = Write-PreG5DisposableInventoryObservationsArtifact -EvidenceDir $EvidenceDir -Observations $obsPayload

  $wantAc = [string]$Manifest.agent_credentials
  if ([string]::IsNullOrWhiteSpace($wantAc)) { $wantAc = "absent" }
  if ($wantAc -ceq 'absent') {
    if ($ac -cne 'absent') { throw "PREG5_DISP_FAIL: agent_credentials expected absent got=$ac" }
  } elseif ($ac -cne $wantAc) {
    throw "PREG5_DISP_FAIL: agent_credentials expected $wantAc got=$ac"
  }

  if ($ver -cne [string]$Manifest.expect_alembic) {
    throw ("PREG5_DISP_FAIL: alembic_version mismatch want=$($Manifest.expect_alembic) got=$ver")
  }
  if ($users -ne [int]$Manifest.user_count) {
    throw ("PREG5_DISP_FAIL: restored user count mismatch want=$($Manifest.user_count) got=$users")
  }
  if ($tasks -ne [int]$Manifest.task_count) {
    throw ("PREG5_DISP_FAIL: restored task count mismatch want=$($Manifest.task_count) got=$tasks")
  }
  if ($settings -ne [int]$Manifest.settings_count) {
    throw ("PREG5_DISP_FAIL: restored user_settings count mismatch want=$($Manifest.settings_count) got=$settings")
  }
  if ($userIds -cne [string]$Manifest.user_ids_csv) {
    throw "PREG5_DISP_FAIL: restored user id list mismatch"
  }
  if ($taskIds -cne [string]$Manifest.task_ids_csv) {
    throw "PREG5_DISP_FAIL: restored task id list mismatch"
  }

  return [ordered]@{
    alembic_version       = $ver
    user_count            = $users
    task_count            = $tasks
    user_settings_count   = $settings
    user_ids_csv          = $userIds
    task_ids_csv          = $taskIds
    agent_credentials     = $ac
    agent_credentials_absent = ($ac -ceq 'absent')
    inventory_observations = $obsRef
    authority_source      = $authoritySource
  }
}

function Invoke-PreG5Disposable042RestoredDataProofCore {
  <#
    Disposable pg_restore @ 042 on fresh postgres volume + DualNet/SingleNet startup probes.
    NOT rollback_acceptance. Returns same shape as Invoke-PreG5Disposable042ValidationCore.
    Proposal: docs/delivery/0.7-AGENT-CLI-ACCESS-Phase1-PREG5-DISPOSABLE-042-RESTORED-DATA-PROOF-PROPOSAL-2026-11-02.md (Page).
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
    [Parameter(Mandatory = $true)][string] $DumpPath,
    [string] $InventoryManifestPath = "",
    [int] $ComposeTimeoutMs = 180000,
    [int] $HttpTimeoutSec = 20,
    [switch] $SkipHttpChecks,
    [scriptblock] $HttpChecker = $null,
    [scriptblock] $HttpProbe = $null,
    [int] $HttpReadinessDeadlineMs = 120000,
    [int] $HttpReadinessPollSec = 2,
    [int] $DiagnosticLogMaxBytes = 65536,
    [int[]] $PreflightHostPorts = @(18000, 18080),
    [ValidateSet('SingleNet', 'DualNet')]
    [string] $OwnedNetworkProfile = 'DualNet',
    [switch] $DualNet
  )

  if ([string]::IsNullOrWhiteSpace($InventoryManifestPath)) {
    $InventoryManifestPath = Get-PreG5DefaultDisposable042RestoredDataInventoryManifestPath
  }

  $useDualNet = $false
  if ($DualNet) {
    $useDualNet = $true
    $OwnedNetworkProfile = 'DualNet'
  } elseif ($OwnedNetworkProfile -eq 'DualNet') {
    $useDualNet = $true
  } elseif (Test-PreG5DisposableComposeFileImpliesDualNet -ComposeFile $ComposeFile) {
    $useDualNet = $true
    $OwnedNetworkProfile = 'DualNet'
  }

  $envKeys = @(
    'SNAPSHOT_API_IMAGE', 'SNAPSHOT_WEB_IMAGE', 'POSTGRES_IMAGE',
    'PREG5_SESSION_SECRET', 'PREG5_TOKEN_ENCRYPTION_KEY'
  )

  $st = @{
    OwnedProject     = $false
    OwnedResources   = $null
    EvidenceDir      = $null
    ProjectDir       = $null
    RefusalNoCleanup = $false
    ExitCode         = 1
    CleanupAttempted = $false
  }
  $durableNotes = New-Object System.Collections.Generic.List[string]

  function _Fail([string] $msg) { throw ("PREG5_DISP_FAIL: " + $msg) }
  function _FailRefuse([string] $msg) {
    $st.RefusalNoCleanup = $true
    throw ("PREG5_DISP_FAIL: " + $msg)
  }
  function _RefreshOwned([string] $why) {
    try {
      $st.OwnedResources = Get-DisposableOwnedResources -ProjectName $ProjectName -DualNet:$useDualNet
      $durableNotes.Add("refresh_owned:$why")
    } catch {
      $durableNotes.Add("refresh_owned_unresolved:${why}:$($_.Exception.Message)")
    }
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

  $composeInvokerAllowFail = {
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
      -OwnedResources $st.OwnedResources -ComposeInvoker $composeInvoker -ComposeTimeoutMs $ComposeTimeoutMs `
      -WriteSuccessReceipt:$WriteSuccessReceipt
  }

  function _WriteFailureReceipt {
    param(
      $CleanupOutcome = $null,
      $DumpBinding = $null,
      $PgRestoreOutcomeRef = $null,
      $InventoryObservationsRef = $null
    )
    if (-not $st.EvidenceDir) { return }
    $failPath = Join-Path $st.EvidenceDir "failure.receipt.json"
    if (Test-Path -LiteralPath $failPath) { return }
    $httpObsFailRef = $null
    $httpObsPath = Join-Path $st.EvidenceDir (Get-PreG5DisposableHttpEndpointObservationsFileName)
    if (Test-Path -LiteralPath $httpObsPath) {
      $httpObsFailRef = [ordered]@{
        path   = (Get-PreG5DisposableHttpEndpointObservationsFileName)
        sha256 = (Get-PreG5FileSha256Hex -Path $httpObsPath)
      }
    }
    $obj = [ordered]@{
      failed                         = $true
      startup_validation_ok          = $false
      restored_data_rollback_proof   = $false
      rollback_acceptance            = $false
      rollback_pin_updated           = $false
      not_backup_restore             = $false
      schema_method                  = "pg_restore_bound_dump_into_disposable_042"
      dump_binding                   = $DumpBinding
      pg_restore_outcome             = $PgRestoreOutcomeRef
      inventory_observations         = $InventoryObservationsRef
      notes                          = @($durableNotes)
      owned                          = $st.OwnedResources
      cleanup_outcome                = $CleanupOutcome
      http_endpoint_observations     = $httpObsFailRef
    }
    Assert-DurablePathWritable $failPath | Out-Null
    ($obj | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $failPath -Encoding utf8
  }

  $manifest = $null
  $dumpBinding = $null
  $pgRestoreOutcomeRef = $null
  $inventoryObservationsRef = $null

  try {
    if ([string]::IsNullOrWhiteSpace($AuditApprovalPath)) { _FailRefuse "AuditApprovalPath is required" }
    if (-not (Test-Path -LiteralPath $AuditApprovalPath)) { _FailRefuse "AuditApprovalPath missing" }

    $manifest = Import-PreG5DisposableRestoredDataInventoryManifest -Path $InventoryManifestPath
    $manifestSha = (Get-PreG5FileSha256Hex -Path $InventoryManifestPath).ToUpperInvariant()

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
      Assert-DisposableAttemptDirClear -AttemptDir $evidence | Out-Null
    } catch {
      _FailRefuse $_.Exception.Message
    }

    $approval = Get-Content -LiteralPath $AuditApprovalPath -Raw | ConvertFrom-Json
    if ($approval.approved -ne $true) { _FailRefuse "approval.approved != true" }
    if ([string]$approval.snapshot_api_image_id -ne $SnapshotApiImage) { _FailRefuse "approval api image mismatch" }
    if ([string]$approval.snapshot_web_image_id -ne $SnapshotWebImage) { _FailRefuse "approval web image mismatch" }
    if ($approval.PSObject.Properties.Name -contains 'postgres_image_id') {
      if ([string]$approval.postgres_image_id -ne $PostgresImage) { _FailRefuse "approval postgres image mismatch" }
    }
    $approvalDumpPath = ""
    if ($approval.PSObject.Properties.Name -contains 'dump_path') {
      $approvalDumpPath = [string]$approval.dump_path
    } elseif ($approval.PSObject.Properties.Name -contains 'restore_dump_path') {
      $approvalDumpPath = [string]$approval.restore_dump_path
    }
    if ([string]::IsNullOrWhiteSpace($approvalDumpPath)) {
      _FailRefuse "approval.dump_path required for restored-data proof"
    }
    if ($approvalDumpPath -ne $DumpPath) { _FailRefuse "approval dump_path mismatch" }
    $approvalDumpSha = ""
    if ($approval.PSObject.Properties.Name -contains 'dump_sha256') {
      $approvalDumpSha = ([string]$approval.dump_sha256).Trim().ToUpperInvariant()
    } elseif ($approval.PSObject.Properties.Name -contains 'restore_dump_sha256') {
      $approvalDumpSha = ([string]$approval.restore_dump_sha256).Trim().ToUpperInvariant()
    }
    if ([string]::IsNullOrWhiteSpace($approvalDumpSha)) { _FailRefuse "approval.dump_sha256 required" }
    if ($approvalDumpSha -cne ([string]$manifest.dump_binding.sha256).Trim().ToUpperInvariant()) {
      _FailRefuse "approval dump_sha256 mismatch manifest"
    }
    if ($approval.PSObject.Properties.Name -notcontains 'inventory_manifest_sha256') {
      _FailRefuse "approval.inventory_manifest_sha256 required"
    }
    $imSha = ([string]$approval.inventory_manifest_sha256).Trim().ToUpperInvariant()
    if ($imSha -cne $manifestSha) { _FailRefuse "approval inventory_manifest_sha256 mismatch" }
    if ($approval.PSObject.Properties.Name -notcontains 'dump_qualification') {
      _FailRefuse "approval.dump_qualification required"
    }
    if ([string]$approval.dump_qualification -cne 'read_only_no_quiesce_not_g1') {
      _FailRefuse "approval.dump_qualification must be read_only_no_quiesce_not_g1"
    }
    if ($approval.PSObject.Properties.Name -notcontains 'inventory_authority_source') {
      _FailRefuse "approval.inventory_authority_source required"
    }
    $wantAuthority = [string]$manifest.inventory_authority_source
    if ([string]::IsNullOrWhiteSpace($wantAuthority)) { $wantAuthority = "G3B-1793594054" }
    if ([string]$approval.inventory_authority_source -cne $wantAuthority) {
      _FailRefuse "approval.inventory_authority_source mismatch manifest"
    }

    $boundSha = ([string]$manifest.dump_binding.sha256).Trim().ToUpperInvariant()
    if ([string]$manifest.dump_binding.path -ne $DumpPath) {
      _FailRefuse "DumpPath must match inventory manifest dump_binding.path"
    }
    $dumpBinding = Assert-PreG5DisposableDumpFileBinding -DumpPath $DumpPath -ExpectedSha256 $boundSha

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

    $envPath = Join-Path $st.ProjectDir ".env"
    $session = -join ((1..48) | ForEach-Object { "{0:x}" -f (Get-Random -Max 16) })
    $tok = -join ((1..48) | ForEach-Object { "{0:x}" -f (Get-Random -Max 16) })
    @(
      "SNAPSHOT_API_IMAGE=$SnapshotApiImage"
      "SNAPSHOT_WEB_IMAGE=$SnapshotWebImage"
      "POSTGRES_IMAGE=$PostgresImage"
      "PREG5_SESSION_SECRET=$session"
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
    $cfgYamlPath = Join-Path $evidence "compose.rendered.yaml"
    Set-Content -LiteralPath $cfgYamlPath -Value $yamlOut.StdOut -Encoding utf8

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

    $emptySql = @"
SELECT count(*)::text FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r','p','S')
"@
    $emptyCount = Invoke-DisposableComposePostgresSql -ComposeInvoker $composeInvoker -Sql $emptySql -What "empty public relcount"
    if ($emptyCount -ne '0') {
      _Fail "postgres public relcount not empty before pg_restore got=$emptyCount"
    }

    $pgCid = Get-DisposableProjectServiceContainerId -ProjectName $ProjectName -ServiceName "postgres"
    if ([string]::IsNullOrWhiteSpace($pgCid)) { _Fail "postgres container missing before restore" }
    $tmpDump = "/tmp/preg5_restore_${AttemptId}.dump"
    Invoke-PreG5DockerControl -DockerArgs @("cp", $DumpPath, "${pgCid}:${tmpDump}") -What "docker cp dump into postgres" | Out-Null
    $restoreResult = & $composeInvokerAllowFail -What "pg_restore disposable" -TimeoutMs $ComposeTimeoutMs -ComposeArgs @(
      "exec", "-T", "postgres",
      "pg_restore", "-U", "preg5", "-d", "theplan_preg5", "--no-owner", "--role=preg5", "--exit-on-error", $tmpDump
    )
    $pgRestoreOutcomeRef = Write-PreG5DisposablePgRestoreOutcomeArtifact -EvidenceDir $evidence `
      -RestoreResult $restoreResult -StderrMaxBytes $DiagnosticLogMaxBytes
    if ($restoreResult.Code -ne 0) {
      _Fail ("pg_restore failed code=$($restoreResult.Code) stderr=" + (Limit-PreG5DisposableEvidenceText -Text ([string]$restoreResult.StdErr) -MaxBytes 512))
    }
    try {
      & $composeInvoker -What "rm restore tmp" -ComposeArgs @("exec", "-T", "postgres", "rm", "-f", $tmpDump) | Out-Null
    } catch {
      $durableNotes.Add("restore_tmp_rm_fail:" + $_.Exception.Message)
    }

    try {
      $inventory = Assert-PreG5DisposableRestoredDbInventory -Manifest $manifest -ComposeInvoker $composeInvoker -EvidenceDir $evidence
      $inventoryObservationsRef = $inventory.inventory_observations
    } catch {
      $invObsPath = Join-Path $evidence "inventory-observations.json"
      if (Test-Path -LiteralPath $invObsPath) {
        $inventoryObservationsRef = [ordered]@{
          path   = "inventory-observations.json"
          sha256 = (Get-PreG5FileSha256Hex -Path $invObsPath)
        }
      }
      throw
    }
    if ($ExpectAlembic -cne [string]$manifest.expect_alembic) {
      _Fail "ExpectAlembic param mismatch manifest"
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

    $apiImgField = Assert-RunningContainerImagePin -ContainerId $apiCid -ExpectedImageId $SnapshotApiImage
    $webImgField = Assert-RunningContainerImagePin -ContainerId $webCid -ExpectedImageId $SnapshotWebImage

    $httpObsRef = $null
    if (-not $SkipHttpChecks) {
      $httpDeadline = [datetime]::UtcNow.AddMilliseconds($HttpReadinessDeadlineMs)
      $httpObsRef = Invoke-DisposableRestoredDataHttpChecks -EvidenceDir $evidence -AttemptId $AttemptId `
        -HttpTimeoutSec $HttpTimeoutSec -HttpDeadlineUtc $httpDeadline -HttpReadinessPollSec $HttpReadinessPollSec `
        -HttpChecker $HttpChecker -HttpProbe $HttpProbe
    }

    $sched = Invoke-PreG5DockerControlAllowFail -What "ps scheduler" -DockerArgs @(
      "ps", "-a", "--filter", "label=com.docker.compose.project=$ProjectName",
      "--filter", "label=com.docker.compose.service=scheduler", "--format", "{{.ID}}"
    )
    if ($sched.Code -ne 0) {
      _Fail "scheduler container list failed code=$($sched.Code) err=$($sched.StdErr)"
    }
    if (-not [string]::IsNullOrWhiteSpace($sched.StdOut)) {
      _Fail "scheduler container present in disposable project"
    }

    $optionB = Get-DisposableRestoredDataEgressDisclosure -AttemptId $AttemptId
    $dumpQualification = "read_only_no_quiesce_not_g1"
    $authoritySource = [string]$inventory.authority_source
    $dumpBindingReceipt = [ordered]@{
      path           = $DumpPath
      sha256         = $boundSha
      qualification  = $dumpQualification
      meta_path      = [string]$manifest.dump_binding.meta_path
      source_alembic = [string]$dumpBinding.source_alembic
      source_database = [string]$dumpBinding.source_database
      mode           = [string]$dumpBinding.mode
    }
    $inventoryAuthority = [ordered]@{
      users          = [int]$inventory.user_count
      tasks          = [int]$inventory.task_count
      user_settings  = [int]$inventory.user_settings_count
      source         = $authoritySource
    }
    $candidatePath = Join-Path $evidence "validation.candidate.json"
    $candidate = [ordered]@{
      stage                         = "Disposable042RestoredDataProof_candidate"
      stamp                         = $stamp
      attempt_id                    = $AttemptId
      project                       = $ProjectName
      taken_utc                     = (Get-Date).ToUniversalTime().ToString("o")
      schema_method                 = "pg_restore_bound_dump_into_disposable_042"
      not_backup_restore            = $false
      restored_data_rollback_proof  = $true
      startup_validation_ok         = $false
      dual_net                      = [bool]$useDualNet
      owned_network_profile         = $OwnedNetworkProfile
      auth_content_expectation      = "UNAUTHENTICATED"
      option_b                      = $optionB
      rollback_acceptance           = $false
      rollback_pin_updated          = $false
      snapshot_api_image_id         = $SnapshotApiImage
      snapshot_web_image_id         = $SnapshotWebImage
      postgres_image_id             = $PostgresImage
      expect_alembic                = $ExpectAlembic
      alembic_version_sql           = $inventory.alembic_version
      agent_credentials_absent      = [bool]$inventory.agent_credentials_absent
      inventory_manifest_path       = $InventoryManifestPath
      inventory_manifest_sha256     = $manifestSha
      dump_path                     = $DumpPath
      dump_sha256                   = $boundSha
      dump_qualification            = $dumpQualification
      inventory_authority           = $inventoryAuthority
      inventory_observations        = $inventoryObservationsRef
      pg_restore_outcome            = $pgRestoreOutcomeRef
      restored_inventory            = $inventory
      dump_binding                  = $dumpBindingReceipt
      api_container_id              = $apiCid
      web_container_id              = $webCid
      api_container_image_field     = $apiImgField
      web_container_image_field     = $webImgField
      household_unverified          = $true
      household_note                = "Restored-data disposable proof only; does not invoke household rollback or mutate production DB."
      owned_resources               = $st.OwnedResources
      http_endpoint_observations    = $httpObsRef
    }
    Assert-DurablePathWritable $candidatePath | Out-Null
    ($candidate | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $candidatePath -Encoding utf8

    _AttemptOwnedCleanup -WriteSuccessReceipt | Out-Null

    $st.OwnedProject = $false
    $valPath = Join-Path $evidence "validation.receipt.json"
    $receipt = [ordered]@{}
    foreach ($k in $candidate.Keys) { $receipt[$k] = $candidate[$k] }
    $receipt.stage = "Disposable042RestoredDataProof"
    $receipt.cleanup_verified = $true
    $receipt.next = "STOP — operational rollback_acceptance and pin update remain held"
    Assert-DurablePathWritable $valPath | Out-Null
    ($receipt | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $valPath -Encoding utf8
    $st.ExitCode = 0
  }
  catch {
    $durableNotes.Add("fail:" + $_.Exception.Message)
    if ($st.RefusalNoCleanup -or -not $st.OwnedProject) {
      $st.ExitCode = 1
    } else {
      $cleanupOutcome = $null
      if ($st.OwnedProject -and $st.EvidenceDir) {
        try {
          Capture-DisposableFailureDiagnostics -ProjectName $ProjectName -EvidenceDir $st.EvidenceDir `
            -ComposeInvoker $composeInvoker -LogMaxBytes $DiagnosticLogMaxBytes -ComposeTimeoutMs $ComposeTimeoutMs | Out-Null
        } catch {
          $durableNotes.Add("diagnostics_collect_fail:" + $_.Exception.Message)
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
      if ($null -eq $dumpBinding -and $null -ne $manifest) {
        $dumpBinding = [ordered]@{
          path          = $DumpPath
          sha256        = ([string]$manifest.dump_binding.sha256).Trim().ToUpperInvariant()
          qualification = "read_only_no_quiesce_not_g1"
          meta_path     = [string]$manifest.dump_binding.meta_path
        }
      }
      if ($null -eq $pgRestoreOutcomeRef -and $st.EvidenceDir) {
        $pgPath = Join-Path $st.EvidenceDir "pg-restore-outcome.json"
        if (Test-Path -LiteralPath $pgPath) {
          $pgRestoreOutcomeRef = [ordered]@{
            path   = "pg-restore-outcome.json"
            sha256 = (Get-PreG5FileSha256Hex -Path $pgPath)
          }
        }
      }
      if ($null -eq $inventoryObservationsRef -and $st.EvidenceDir) {
        $invPath = Join-Path $st.EvidenceDir "inventory-observations.json"
        if (Test-Path -LiteralPath $invPath) {
          $inventoryObservationsRef = [ordered]@{
            path   = "inventory-observations.json"
            sha256 = (Get-PreG5FileSha256Hex -Path $invPath)
          }
        }
      }
      _WriteFailureReceipt -CleanupOutcome $cleanupOutcome -DumpBinding $dumpBinding `
        -PgRestoreOutcomeRef $pgRestoreOutcomeRef -InventoryObservationsRef $inventoryObservationsRef
      $st.ExitCode = 1
    }
  }

  return ,[ordered]@{
    ExitCode           = $st.ExitCode
    RefusalNoCleanup   = $st.RefusalNoCleanup
    EvidenceDir        = $st.EvidenceDir
    OwnedProjectAtEnd  = $st.OwnedProject
    Notes              = @($durableNotes)
  }
}
