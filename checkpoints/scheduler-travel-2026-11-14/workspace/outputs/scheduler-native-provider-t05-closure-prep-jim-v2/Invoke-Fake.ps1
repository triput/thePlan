# HELD. Operator wrapper for separately held fake-only verification.
# Authoring only; never invoke without Trish's exact-hash one-shot approval.
# Preparation approval does NOT authorize this wrapper.
# t05-closure-prep-jim-v2: T05-CLOSURE-FOCUSED (+ R1–R5 extracted controls) authored inside check_native_provider;
# this wrapper still refuses while launch_authorized=false and does not expand the
# native launch batch beyond NP-V-MS-NONEXPIRED.
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$AdmissionSHA256
)

$ErrorActionPreference = 'Stop'
$admissionPath = Join-Path $PSScriptRoot 'verify\VERIFICATION-ADMISSION.json'
if (-not (Test-Path -LiteralPath $admissionPath)) {
    throw 'STOP: VERIFICATION-ADMISSION.json missing; preparation scaffold only; no child started'
}
if ((Get-FileHash -LiteralPath $admissionPath -Algorithm SHA256).Hash -ne $AdmissionSHA256) {
    throw 'STOP: reviewed admission bytes mismatch; no child started'
}
$admission = Get-Content -LiteralPath $admissionPath -Raw | ConvertFrom-Json
if ($admission.kind -ne 'scheduler-native-provider-one-shot-fake-admission') {
    throw 'STOP: admission schema mismatch; no child started'
}
if ($admission.launch_authorized -ne $true) {
    throw 'STOP: launch_authorized is false; prep scaffold; no child started'
}

$packetRoot = [IO.Path]::GetFullPath($PSScriptRoot)
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
        throw 'STOP: duplicate runtime pin'
    }
    if ((Get-FileHash -LiteralPath $runtimePath -Algorithm SHA256).Hash -ne $pin.sha256) {
        throw ('STOP: reviewed runtime pin mismatch: ' + $runtimePath)
    }
}

$pythonPath = [IO.Path]::GetFullPath($admission.interpreter_path)
if (-not $seenRuntimePaths.Contains($pythonPath)) {
    throw 'STOP: interpreter not included in reviewed runtime inventory'
}
$verifyRoot = Join-Path $PSScriptRoot 'verify'
foreach ($output in @('FAKE-NATIVE-PROVIDER-RESULT.json', 'FAKE-NATIVE-PROVIDER-LAUNCH-RECEIPT.json')) {
    if (Test-Path -LiteralPath (Join-Path $verifyRoot $output)) {
        throw ('STOP: existing evidence; no replay or overwrite: ' + $output)
    }
}

Push-Location -LiteralPath $verifyRoot
try {
    & $pythonPath -I -S -B (Join-Path $verifyRoot 'verify_admission.py')
    if ($LASTEXITCODE -ne 0) {
        throw ('STOP: fake verification exited ' + $LASTEXITCODE + '; preserve evidence; no retry or repair')
    }
}
finally {
    Pop-Location
}
