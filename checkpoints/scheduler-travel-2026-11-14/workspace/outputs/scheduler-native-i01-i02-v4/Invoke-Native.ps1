# PREPARED ONLY. One launch outside the default sandbox requires Trish's exact-hash approval.
$ErrorActionPreference = 'Stop'
$payload = Join-Path $PSScriptRoot 'payload'
$python = 'C:\Users\trish\AppData\Local\Programs\Python\Python311\python.exe'
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$manifest = Join-Path $payload 'SHA256SUMS.txt'
$config = Join-Path $payload 'launch-config.json'
$evidence = Join-Path (Split-Path $PSScriptRoot -Parent) 'scheduler-native-i01-i02-v4.evidence'
if ((Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash -ne '5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC') {
    throw 'STOP: interpreter mismatch'
}
if ((Get-FileHash -LiteralPath $docker -Algorithm SHA256).Hash -ne '8985CD8AC002C3240B5AA48FE401FCB55DCA5D849B537E3C835564E8E8C49A70') {
    throw 'STOP: Docker executable mismatch'
}
if ((Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash -ne '4CC24980C83E71C0C43AB057B5802B54EF614AF9688C4783E381AAA298AA0A7B') {
    throw 'STOP: configuration mismatch'
}
if ((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash -ne '642C489AA4FA3B21E5F7C23540267C550186FE771B5F69476A7B0298DF88E4F3') {
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
if ($seen.Count -ne 268 -or @(Get-ChildItem -LiteralPath $payload -Recurse -File).Count -ne 269) {
    throw 'STOP: payload inventory mismatch'
}
& $python -I -S -B (Join-Path $payload 'invoke.py') --config-sha256 '4CC24980C83E71C0C43AB057B5802B54EF614AF9688C4783E381AAA298AA0A7B' --manifest-sha256 '642C489AA4FA3B21E5F7C23540267C550186FE771B5F69476A7B0298DF88E4F3'
if ($LASTEXITCODE -ne 0) {
    throw 'STOP: native launch failed; preserve evidence; no retry, repair or failure cleanup'
}
