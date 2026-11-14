# HELD. One invocation only after Trish's separate execution approval.
$ErrorActionPreference = 'Stop'
$packet = Join-Path $PSScriptRoot 'packet'
$verify = Join-Path $packet 'fake-only-c06-verification'
$python = 'C:\Users\trish\AppData\Local\Programs\Python\Python311\python.exe'
$admit = @{
    'TIP-FREEZE.json' = '5F8D87526F9D2C114C2B81A0D06D3ED2A5CEBC7E2DC97A562225C9C2FB23C602'
    'ARTIFACT-HASHES.txt' = '033A7963A5B502B6253C312EE1C0EC94BF1B5BA1C8E108F0DA4B6287838C09ED'
    'fake-only-c06-verification\OUTER-ADMISSION.json' = 'F9638C51B23D86B9CBC2D587002C676223134709CBEC45110B5D8E03FE89F5EF'
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
