# HELD. One invocation only after Trish's separate execution approval.
$ErrorActionPreference = 'Stop'
$packet = Join-Path $PSScriptRoot 'packet'
$verify = Join-Path $packet 'fake-only-c06-verification'
$python = 'C:\Users\trish\AppData\Local\Programs\Python\Python311\python.exe'
$admit = @{
    'TIP-FREEZE.json' = '94BB0D3DDEBED09AF52174B37A478484F35F8B07175154B4F27991967C9024A4'
    'ARTIFACT-HASHES.txt' = '1B1F0D0CEB2CFC7EDBCA468BF4396D2F5C4559455EC439099B3C2378975BB824'
    'fake-only-c06-verification\OUTER-ADMISSION.json' = 'C9A0B5214F752F2FFED9ACE3E983501F44B4D78FA6D030774ABC61DDFBC212BF'
}
foreach ($relative in $admit.Keys) {
    if ((Get-FileHash -LiteralPath (Join-Path $packet $relative) -Algorithm SHA256).Hash -ne $admit[$relative]) {
        throw ('STOP: reviewed pin mismatch: ' + $relative)
    }
}
if ((Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash -ne '5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC') {
    throw 'STOP: interpreter mismatch'
}
foreach ($output in @('FAKE-C06-RESULT.json','FAKE-C06-LAUNCH-RECEIPT.json')) {
    if (Test-Path -LiteralPath (Join-Path $verify $output)) {
        throw ('STOP: existing evidence; no replay or overwrite: ' + $output)
    }
}
Push-Location -LiteralPath $verify
try {
    & $python -I -S -B (Join-Path $verify 'admit_outer.py')
    if ($LASTEXITCODE -ne 0) {
        throw ('STOP: verification exited ' + $LASTEXITCODE + '; preserve evidence; no retry or repair')
    }
}
finally {
    Pop-Location
}
