# PREPARED ONLY. Host operator admission scaffold for native-provider packet.
# One launch outside the default sandbox requires Trish's exact-hash approval.
# PREPARATION does not authorize invocation. Port unverified. Endpoint unbound.
# Host Docker ownership only. No new privileges. No failed-attempt retry.
$ErrorActionPreference = 'Stop'
$payload = Join-Path $PSScriptRoot 'payload'
$fixture = Join-Path $payload 'fixture'
$python = 'C:\Users\trish\AppData\Local\Programs\Python\Python311\python.exe'
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$manifest = Join-Path $payload 'SHA256SUMS.txt'
$config = Join-Path $payload 'launch-config.json'
$evidence = Join-Path (Split-Path $PSScriptRoot -Parent) 'scheduler-native-provider-prep-v1.evidence'

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
$expectedConfig = [string]$configObj.self_sha256
$expectedManifest = [string]$configObj.manifest_sha256
foreach ($pin in @($expectedPython, $expectedDocker, $expectedConfig, $expectedManifest)) {
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
if ((Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash -ne $expectedConfig) {
    throw 'STOP: configuration mismatch'
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

$supervisor = Join-Path $fixture 'np_supervisor.py'
# Host-side supervisor only. Never grant Docker socket to runner.
& $python -I -S -B $supervisor
if ($LASTEXITCODE -ne 0) {
    throw 'STOP: native-provider launch failed; preserve evidence; no retry, repair or failure cleanup'
}
