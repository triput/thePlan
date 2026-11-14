# HELD: one reviewed verification attempt only. Do not invoke without Trish's launch authorization.
$ErrorActionPreference = 'Stop'
$packet = Join-Path $PSScriptRoot 'packet'
$harness = Join-Path $packet 'fake-only-behavioral-harness'
$python = 'C:\Users\trish\AppData\Local\Programs\Python\Python311\python.exe'
if ((Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash -ne '5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC') { throw 'STOP: interpreter hash mismatch' }
$pins = @{
    'TIP-FREEZE.json' = '6D19C5963C3CF2F1FBADDAE64AE0BE039D32C2C419A4EDCAB940E6314EB5084E'
    'ARTIFACT-HASHES.txt' = '1545B0C27192650A5AE4BFD2A2AEEEEC0DCD1B6600E7D80EDE90792486245CA0'
    'workspace-payload\SHA256SUMS.txt' = '7D3A3D4AC89A13DE94EB6C9EFD7F2F183DD8DC121C07D3760B1FD43499EAB059'
    'fake-only-behavioral-harness\PACKET-SHA256SUMS.txt' = '7A87A4E1E06498B668B53BB1BF11872488BBF71B3892A0D2D6BA2A297D510ECA'
    'fake-only-behavioral-harness\OUTER-ADMISSION.json' = 'AACAAD3DDCD439AE50D51314172333A8E989DEB3C3E3C1A5824939F5490BBCAC'
    'fake-only-behavioral-harness\admit_outer.py' = 'A5BC16C076AA3CB9BD4B8E36C3895FEFF58E028DEE28532B1CCBD90A25E8A97B'
}
foreach ($entry in $pins.GetEnumerator()) {
    if ((Get-FileHash -LiteralPath (Join-Path $packet $entry.Key) -Algorithm SHA256).Hash -ne $entry.Value) { throw ('STOP: input pin mismatch: ' + $entry.Key) }
}
foreach ($relative in @('ARTIFACT-HASHES.txt', 'workspace-payload\SHA256SUMS.txt', 'fake-only-behavioral-harness\PACKET-SHA256SUMS.txt')) {
    $manifest = Join-Path $packet $relative
    $base = Split-Path -Parent $manifest
    foreach ($line in [IO.File]::ReadAllLines($manifest)) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith('#')) { continue }
        if ($line -notmatch '^([A-Fa-f0-9]{64})\s+\*?(.+)$') { throw 'STOP: malformed input manifest' }
        $expectedHash = $Matches[1]
        $target = [IO.Path]::GetFullPath((Join-Path $base $Matches[2]))
        if (-not $target.StartsWith(($packet + [IO.Path]::DirectorySeparatorChar), [StringComparison]::OrdinalIgnoreCase)) { throw 'STOP: manifest path outside staged packet' }
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $expectedHash) { throw ('STOP: manifest mismatch: ' + $target) }
    }
}
foreach ($name in @('FAKE-BEHAVIORAL-RESULT.json', 'FAKE-BEHAVIORAL-LAUNCH-RECEIPT.json')) {
    if (Test-Path -LiteralPath (Join-Path $harness $name)) { throw 'STOP: prior verification output exists; no overwrite or rerun' }
}
Push-Location -LiteralPath $harness
try {
    & $python -I -S -B (Join-Path $harness 'admit_outer.py')
    $verificationExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($verificationExitCode -ne 0) { throw ('STOP: verification exit ' + $verificationExitCode + '; preserve evidence; no retry or repair') }
Write-Output 'DEX_FAKE_VERIFICATION_RETURNED_0'