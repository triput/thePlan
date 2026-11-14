# PREPARED ONLY. Host operator admission scaffold for native-provider packet.
# One launch outside the default sandbox requires Trish's exact-hash approval.
# PREPARATION does not authorize invocation. Endpoint unbound.
# Host Docker ownership only. No new privileges. No failed-attempt retry.
#
# Configuration raw hash is admitted from an independently reviewed operator
# -ExpectedConfigSHA256 argument — NOT from configObj.self_sha256
# (avoids cryptographic self-hash fixed point). Optional document_preimage_sha256
# in launch-config is labeled separately and is not compared as the raw hash.
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedConfigSHA256,

    [Parameter(Mandatory = $false)]
    [string]$DockerConfigPath = '',

    [Parameter(Mandatory = $false)]
    [string]$ReceiptPath = ''
)

$ErrorActionPreference = 'Stop'
$payload = Join-Path $PSScriptRoot 'payload'
$fixture = Join-Path $payload 'fixture'
$python = 'C:\Users\trish\AppData\Local\Programs\Python\Python311\python.exe'
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$manifest = Join-Path $payload 'SHA256SUMS.txt'
$config = Join-Path $payload 'launch-config.json'
$evidence = Join-Path (Split-Path $PSScriptRoot -Parent) 'scheduler-native-provider-prep-v3.evidence'

# Pins are placeholders until a later launch card freezes exact hashes.
# Mismatch or unfrozen sentinel => STOP before any child/Docker call.
$Unfrozen = 'UNFROZEN_PENDING_LAUNCH_CARD_000000000000000000000000000000000000000000000000000000000000'

if (-not (Test-Path -LiteralPath $config)) {
    throw 'STOP: launch-config.json missing'
}
$configObj = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
if ($configObj.launch_ready -ne $true) {
    throw 'STOP: launch-config launch_ready is false; preparation scaffold only; no child started'
}
if ($configObj.endpoint -ne 'unbound' -and $configObj.endpoint_binding_authorized -ne $true) {
    throw 'STOP: endpoint binding not authorized'
}

# Exact-hash gates (frozen on later launch card). Refuse unfrozen sentinels.
$expectedPython = [string]$configObj.python_sha256
$expectedDocker = [string]$configObj.docker_sha256
$expectedManifest = [string]$configObj.manifest_sha256
$expectedConfig = $ExpectedConfigSHA256.ToUpperInvariant()
foreach ($pin in @($expectedPython, $expectedDocker, $expectedManifest, $expectedConfig)) {
    if ([string]::IsNullOrWhiteSpace($pin) -or $pin -eq $Unfrozen -or $pin -notmatch '^[A-F0-9]{64}$') {
        throw 'STOP: launch pins unfrozen; preparation does not authorize run'
    }
}
if ((Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash -ne $expectedPython) {
    throw 'STOP: interpreter mismatch'
}
if ((Get-FileHash -LiteralPath $docker -Algorithm SHA256).Hash -ne $expectedDocker) {
    throw 'STOP: Docker executable mismatch'
}
# Independently reviewed operator pin — not configObj.self_sha256.
if ((Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash -ne $expectedConfig) {
    throw 'STOP: configuration mismatch against external ExpectedConfigSHA256'
}
# Optional document preimage field (identity only) — never used as raw-hash pin.
if ($null -ne $configObj.document_preimage_sha256 -and [string]$configObj.document_preimage_sha256 -ne '') {
    $docPin = [string]$configObj.document_preimage_sha256
    if ($docPin -eq $expectedConfig) {
        throw 'STOP: document_preimage_sha256 must not equal raw config hash pin'
    }
}
if (-not (Test-Path -LiteralPath $manifest)) {
    throw 'STOP: manifest missing'
}
if ((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash -ne $expectedManifest) {
    throw 'STOP: manifest mismatch'
}
if (Test-Path -LiteralPath $evidence) {
    throw 'STOP: existing evidence directory; no replay or overwrite'
}

$seen = @{}
foreach ($line in Get-Content -LiteralPath $manifest) {
    if ($line -notmatch '^([A-F0-9]{64})  (.+)$') { throw 'STOP: malformed manifest' }
    $expected = $Matches[1]
    $relative = $Matches[2]
    if ($seen.ContainsKey($relative)) { throw 'STOP: duplicate manifest path' }
    $seen[$relative] = $true
    $path = [IO.Path]::GetFullPath((Join-Path $payload $relative))
    if (-not $path.StartsWith(($payload + [IO.Path]::DirectorySeparatorChar), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'STOP: manifest path outside payload'
    }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $expected) {
        throw ('STOP: payload mismatch: ' + $relative)
    }
}

if ([string]::IsNullOrWhiteSpace($DockerConfigPath)) {
    throw 'STOP: -DockerConfigPath required on launch card (reviewed docker ops config)'
}
if (-not (Test-Path -LiteralPath $DockerConfigPath)) {
    throw 'STOP: docker-config missing'
}
if ([string]::IsNullOrWhiteSpace($ReceiptPath)) {
    $ReceiptPath = Join-Path $evidence 'native-provider-host-receipt.jsonl'
}
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
if (Test-Path -LiteralPath $ReceiptPath) {
    throw 'STOP: existing receipt; no replay'
}

$supervisor = Join-Path $fixture 'np_supervisor.py'
# Host-side supervisor only. Never grant Docker socket to runner.
# Pass explicit config/receipt/docker-config — supervisor constructs Plan/ProviderDockerOps.
& $python -I -S -B $supervisor --config $config --receipt $ReceiptPath --docker-config $DockerConfigPath
if ($LASTEXITCODE -ne 0) {
    throw 'STOP: native-provider launch failed; preserve evidence; no retry, repair or failure cleanup'
}

