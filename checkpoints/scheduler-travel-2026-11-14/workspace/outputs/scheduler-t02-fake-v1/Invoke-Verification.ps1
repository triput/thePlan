# HELD. One invocation only after Trish's separate exact-hash execution approval.
$ErrorActionPreference = 'Stop'
$packet = Join-Path $PSScriptRoot 'packet'
$verify = Join-Path $packet 'fake-only-t02-admission-verification'
$python = 'C:\Users\trish\AppData\Local\Programs\Python\Python311\python.exe'
$admit = @{
    'TIP-FREEZE.json' = '63C5DA9AB66B99FA9C883CEF36447895B31C8DEAF1EF538076B62039C69C6940'
    'ARTIFACT-HASHES.txt' = '4F11A04D62FFFDA44820B5A7703AB0698B575192EC3603EB266C3E14DBAABF96'
    'fake-only-t02-admission-verification\OUTER-ADMISSION.json' = '64D60ED788F8A399940BD0B6D18B27ABD393B9D72F9437586E3B8BA21F33250B'
}
foreach ($relative in $admit.Keys) {
    if ((Get-FileHash -LiteralPath (Join-Path $packet $relative) -Algorithm SHA256).Hash -ne $admit[$relative]) {
        throw ('STOP: reviewed pin mismatch: ' + $relative)
    }
}
if ((Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash -ne '5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC') {
    throw 'STOP: interpreter mismatch'
}
foreach ($output in @('FAKE-T02-RESULT.json','FAKE-T02-LAUNCH-RECEIPT.json')) {
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
