# HELD. Authoring only; never invoke without Trish's exact-hash one-shot approval.
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$AdmissionSHA256
)

$ErrorActionPreference = 'Stop'
$admissionPath = Join-Path $PSScriptRoot 'VERIFICATION-ADMISSION.json'
if ((Get-FileHash -LiteralPath $admissionPath -Algorithm SHA256).Hash -ne $AdmissionSHA256) {
    throw 'STOP: reviewed admission bytes mismatch; no child started'
}
$admission = Get-Content -LiteralPath $admissionPath -Raw | ConvertFrom-Json
if ($admission.kind -ne 'scheduler-d2-one-shot-fake-verification-admission') {
    throw 'STOP: admission schema mismatch; no child started'
}

$packetRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'packet'))
$packetPrefix = $packetRoot.TrimEnd([char[]]'\/') + [IO.Path]::DirectorySeparatorChar
$comparison = [StringComparison]::OrdinalIgnoreCase
$seenPacketPaths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$packetPins = @($admission.packet_files)
if ($packetPins.Count -eq 0 -or $packetPins.Count -ne $admission.packet_file_pin_count) {
    throw 'STOP: missing or inconsistent packet pin inventory; no child started'
}
foreach ($pin in $packetPins) {
    if ([string]::IsNullOrWhiteSpace($pin.relative_path) -or $pin.sha256 -notmatch '^[A-Fa-f0-9]{64}$') {
        throw 'STOP: invalid packet pin; no child started'
    }
    $targetPath = [IO.Path]::GetFullPath((Join-Path $packetRoot $pin.relative_path))
    if (-not $targetPath.StartsWith($packetPrefix, $comparison) -or -not $seenPacketPaths.Add($targetPath)) {
        throw 'STOP: escaped or duplicate packet pin; no child started'
    }
    if ((Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash -ne $pin.sha256) {
        throw ('STOP: reviewed packet pin mismatch: ' + $pin.relative_path)
    }
}

# Runtime bytes are checked before Python starts, including its library imports.
$runtimePins = @($admission.runtime_files)
if ($runtimePins.Count -eq 0 -or $runtimePins.Count -ne $admission.runtime_file_pin_count) {
    throw 'STOP: missing or inconsistent runtime pin inventory; no child started'
}
$seenRuntimePaths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($pin in $runtimePins) {
    if ([string]::IsNullOrWhiteSpace($pin.absolute_path) -or -not [IO.Path]::IsPathRooted($pin.absolute_path) -or
            $pin.sha256 -notmatch '^[A-Fa-f0-9]{64}$') {
        throw 'STOP: invalid runtime pin; no child started'
    }
    $runtimePath = [IO.Path]::GetFullPath($pin.absolute_path)
    if (-not $seenRuntimePaths.Add($runtimePath)) {
        throw 'STOP: duplicate runtime pin; no child started'
    }
    if ((Get-FileHash -LiteralPath $runtimePath -Algorithm SHA256).Hash -ne $pin.sha256) {
        throw ('STOP: reviewed runtime pin mismatch: ' + $runtimePath)
    }
}

$pythonPath = [IO.Path]::GetFullPath($admission.interpreter_path)
if (-not $seenRuntimePaths.Contains($pythonPath)) {
    throw 'STOP: interpreter not included in reviewed runtime inventory'
}
$verifyRoot = Join-Path $packetRoot 'fake-only-d2-path-admission-verification'
foreach ($output in @('FAKE-D2-RESULT.json', 'FAKE-D2-LAUNCH-RECEIPT.json')) {
    if (Test-Path -LiteralPath (Join-Path $verifyRoot $output)) {
        throw ('STOP: existing evidence; no replay or overwrite: ' + $output)
    }
}

# The reviewed outer admission enforces the newly frozen launcher/check inputs.
# No tests, repairs, retries, fallback, installation or extra cleanup here.
Push-Location -LiteralPath $verifyRoot
try {
    & $pythonPath -I -S -B (Join-Path $verifyRoot 'admit_outer.py')
    if ($LASTEXITCODE -ne 0) {
        throw ('STOP: verification exited ' + $LASTEXITCODE + '; preserve evidence; no retry or repair')
    }
}
finally {
    Pop-Location
}
