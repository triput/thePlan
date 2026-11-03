#Requires -Version 5.1
<# Post–reach-1 dual-network reach-compare (prep; sources ReachabilityDiagnosisLib). #>
Set-StrictMode -Version Latest

function Get-PreG5ReachCompareDualNetComposeFile {
  param([string] $RunbooksRoot = $PSScriptRoot)
  return Join-Path $RunbooksRoot "compose.pre-g5-snapshot-disposable-dual-net.yaml"
}

function Get-ReachabilityCompareEgressDisclosure {
  <#
    Option B — explicit temporary egress relaxation for api/web publish interface only.
    Localhost host binds do NOT restrict container outbound traffic on a non-internal bridge.
    duration_bound binds to the LIVE AttemptId; prior attempt ids (e.g. compare-1) are never authority.
  #>
  param([string] $AttemptId = "")
  $boundAttempt = if ([string]::IsNullOrWhiteSpace($AttemptId)) {
    "the named disposable reach-compare AttemptId at EXECUTE"
  } else {
    $AttemptId
  }
  return [ordered]@{
    option                         = "B"
    summary                        = "Dual-net adds preg5_publish (non-internal bridge) on api+web only; postgres remains internal-only on preg5_net. This is a bounded temporary relaxation for host publish measurement — not a claim that overall stack isolation is unchanged."
    api_web_egress                 = "Default bridge masqueraded egress may be available to api/web via preg5_publish; not tested or restricted in this prep packet."
    postgres_egress                = "postgres stays on internal preg5_net only (no publish net membership)."
    localhost_bind_scope           = "127.0.0.1:18000/18080 host binds limit off-container listeners only; they are not outbound egress controls."
    optional_measurable_control    = "driver_opts.com.docker.network.bridge.enable_ip_masquerade=false on preg5_publish (Docker bridge driver) — not applied in compose until LIVE orchestration can assert/test; cite bridge driver docs."
    docker_compose_internal_ref    = "https://docs.docker.com/reference/compose-file/networks/#internal"
    docker_bridge_driver_ref       = "https://docs.docker.com/engine/network/drivers/bridge/#bridge-network-options"
    duration_bound                 = "Single attempt $boundAttempt only; prior sealed attempts (including disposable-042-reach-compare-1) are not authority for this run; no standing household adoption without separate auth."
    attempt_id_binding             = $boundAttempt
    supersession_note              = "Dex ACCEPT 1793639077 + fresh Trish EXECUTE for this AttemptId supersede any stale compare-1 wording in older tips/receipts."
    host_probe_scope               = "Matrix host probes: L1-I/L1-J target API 127.0.0.1:18000 (/api/v1/auth/me) only; L1-B publish instrumentation is API container port 8000→18000. Web 127.0.0.1:18080 is compose/preflight declared but not host-probed in this matrix (no web proxy hop test)."
  }
}

function Get-ReachabilityCompareApiImageProvenance {
  return [ordered]@{
    snapshot_api_image_sha256 = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b"
    setup_required_source     = "Extracted reconstructed image source: DropFolder reachability-api-source-extract/deps.py get_current_user → is_setup_required → ApiError(401, SETUP_REQUIRED) before UNAUTHENTICATED path."
    empty_db_expectation      = "SETUP_REQUIRED specifically (not UNAUTHENTICATED); transport reachability (TCP/HTTP) is classified separately from auth-content acceptance."
  }
}

function Invoke-PreG5Disposable042ReachCompareCore {
  param(
    [Parameter(Mandatory = $true)][string] $ScratchRoot,
    [Parameter(Mandatory = $true)][string] $ExportStamp,
    [Parameter(Mandatory = $true)][string] $AttemptId,
    [Parameter(Mandatory = $true)][string] $ProjectName,
    [string] $ComposeFile = "",
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
    [switch] $OrchestrationForceMatrixDeadlineBeforeProbes
  )

  if ([string]::IsNullOrWhiteSpace($ComposeFile)) {
    $ComposeFile = Get-PreG5ReachCompareDualNetComposeFile
  }
  if ($SnapshotApiImage -cne (Get-ReachabilityCompareApiImageProvenance).snapshot_api_image_sha256) {
    throw "PREG5_REACH_COMPARE_FAIL: SnapshotApiImage must match reconstructed reach-compare provenance pin"
  }

  $authExpect = Get-ReachabilityAuthMeExpectationSetupRequired
  $egress = Get-ReachabilityCompareEgressDisclosure -AttemptId $AttemptId
  $egress['api_image_provenance'] = Get-ReachabilityCompareApiImageProvenance

  $result = Invoke-PreG5Disposable042ReachabilityDiagnosisCore `
    -ScratchRoot $ScratchRoot `
    -ExportStamp $ExportStamp `
    -AttemptId $AttemptId `
    -ProjectName $ProjectName `
    -ComposeFile $ComposeFile `
    -SnapshotApiImage $SnapshotApiImage `
    -SnapshotWebImage $SnapshotWebImage `
    -PostgresImage $PostgresImage `
    -ExpectAlembic $ExpectAlembic `
    -AuditApprovalPath $AuditApprovalPath `
    -ComposeTimeoutMs $ComposeTimeoutMs `
    -HostHttpTimeoutSec $HostHttpTimeoutSec `
    -ProbeMatrixDeadlineMs $ProbeMatrixDeadlineMs `
    -ComposeExecProbeTimeoutMs $ComposeExecProbeTimeoutMs `
    -ComposeCleanupTimeoutMs $ComposeCleanupTimeoutMs `
    -PublishInspectTimeoutMs $PublishInspectTimeoutMs `
    -HostTcpTimeoutMs $HostTcpTimeoutMs `
    -NetstatTimeoutMs $NetstatTimeoutMs `
    -PreflightHostPorts $PreflightHostPorts `
    -HostHttpProbe $HostHttpProbe `
    -HostTcpProbe $HostTcpProbe `
    -NetstatProbe $NetstatProbe `
    -OrchestrationForceMatrixDeadlineBeforeProbes:$OrchestrationForceMatrixDeadlineBeforeProbes `
    -OwnedNetworkProfile 'DualNet' `
    -AuthMeExpectationOverride $authExpect `
    -EgressDisclosure $egress

  return $result
}
