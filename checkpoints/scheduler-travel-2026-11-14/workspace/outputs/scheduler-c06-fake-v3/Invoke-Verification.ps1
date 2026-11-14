# HELD. One invocation only after Trish's separate execution approval.
$ErrorActionPreference = 'Stop'
$packet = Join-Path $PSScriptRoot 'packet'
$verify = Join-Path $packet 'fake-only-c06-verification'
$python = 'C:\Users\trish\AppData\Local\Programs\Python\Python311\python.exe'
$admit = @{
    'TIP-FREEZE.json' = 'C00071D4EDD348EF4AF9F2941B0D5F488D97A6E14812980B04F74534C24EB8F5'
    'ARTIFACT-HASHES.txt' = 'BA3E8AEA0A148BFC33A250140CE2E964BD1ECFC651EF117D0AB33C5C9D79FDF9'
    'fake-only-c06-verification\OUTER-ADMISSION.json' = '586FFBCFF25170F19770F13C5680E14CCBF64707FCCDFCC2C7DD020A3F549AC4'
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
