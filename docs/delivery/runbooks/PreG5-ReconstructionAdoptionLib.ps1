#Requires -Version 5.1
<#
  Core logic for Pre-G5 reconstruction adoption + durable docker save preservation.
  Dot-source only. No household recreate, load, rollback, or G1.
#>
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "PreG5-SnapshotHelpers.ps1")

$script:PreG5ReconstructionAdoptionOperation = "reconstruction_adoption_preservation"
$script:PreG5ReconstructionDefaultApiDigest = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b"
$script:PreG5ReconstructionDefaultWebDigest = "sha256:636901afe16e8ffda36601af75f029e2b076287a2c5ca868ecedd42029351969"
$script:PreG5ReconstructionDefaultStamp = "20261102T055454Z-b349fb02"
$script:PreG5ReconstructionDefaultDestDir = "F:\DropFolder\backups\theplan-household-rollback-images"
$script:PreG5ReconstructionHistoricalDigests = @(
  "9aac7395a068d0761ad81c2339d60b69f5bd90e0cb7ef498f26d2634b0edfa36",
  "bff14006fb87757ce5c5ce28be24223195a01e4154de0d437430dfaa3f89c928"
)
$script:PreG5ReconstructionOldOperationalApi = "sha256:9aac7395a068d0761ad81c2339d60b69f5bd90e0cb7ef498f26d2634b0edfa36"
$script:PreG5ReconstructionOldOperationalWeb = "sha256:bff14006fb87757ce5c5ce28be24223195a01e4154de0d437430dfaa3f89c928"
$script:PreG5ReconstructionHouseholdApiContainer = "compose-api-1"
$script:PreG5ReconstructionHouseholdWebContainer = "compose-web-1"

# Orchestration-only mutation blocks (default off).
$script:PreG5ReconstructionOrchBlockPinWeb = $false
$script:PreG5ReconstructionOrchBlockTagWeb = $false
$script:PreG5ReconstructionOrchTagInspectFailTag = $null

function Add-PreG5ReconstructionMutationUncertain {
  param(
    [Parameter(Mandatory = $true)] $UncertainList,
    [Parameter(Mandatory = $true)][string] $MutationKey
  )
  if (-not $UncertainList.Contains($MutationKey)) {
    [void]$UncertainList.Add($MutationKey)
  }
}

function Complete-PreG5ReconstructionMutation {
  param(
    [Parameter(Mandatory = $true)] $UncertainList,
    [Parameter(Mandatory = $true)] $ChangedList,
    [Parameter(Mandatory = $true)][string] $MutationKey
  )
  if ($UncertainList.Contains($MutationKey)) {
    [void]$UncertainList.Remove($MutationKey)
  }
  if (-not $ChangedList.Contains($MutationKey)) {
    [void]$ChangedList.Add($MutationKey)
  }
}

function Get-PreG5ReconstructionAdoptionImagePlan {
  param(
    [string] $ExportStamp = $script:PreG5ReconstructionDefaultStamp,
    [string] $DestDir = $script:PreG5ReconstructionDefaultDestDir,
    [string] $ApiDigest = $script:PreG5ReconstructionDefaultApiDigest,
    [string] $WebDigest = $script:PreG5ReconstructionDefaultWebDigest
  )
  $apiShort = ($ApiDigest -replace '^sha256:', '').Substring(0, 8)
  $webShort = ($WebDigest -replace '^sha256:', '').Substring(0, 8)
  $apiTar = Join-Path $DestDir ("theplan-rollback-api-{0}-{1}.tar" -f $apiShort, $ExportStamp)
  $webTar = Join-Path $DestDir ("theplan-rollback-web-{0}-{1}.tar" -f $webShort, $ExportStamp)
  return [ordered]@{
    ApiDigest       = $ApiDigest
    WebDigest       = $WebDigest
    ApiTar          = $apiTar
    WebTar          = $webTar
    ApiTarBasename  = Split-Path $apiTar -Leaf
    WebTarBasename  = Split-Path $webTar -Leaf
    ApiTarSha       = "$apiTar.sha256"
    WebTarSha       = "$webTar.sha256"
    ApiTarMeta      = "$apiTar.meta.json"
    WebTarMeta      = "$webTar.meta.json"
    ApiAdoptedTag   = "theplan-rollback-api:adopted-$apiShort-$ExportStamp"
    WebAdoptedTag   = "theplan-rollback-web:adopted-$webShort-$ExportStamp"
  }
}

function Assert-PreG5RollbackImagesDestSafe {
  param([Parameter(Mandatory = $true)][string] $DestDir)
  if ([string]::IsNullOrWhiteSpace($DestDir)) { throw "REFUSE: DestDir empty" }
  if ($DestDir -match '\s') { throw "REFUSE: DestDir must not contain spaces: $DestDir" }
  $full = [System.IO.Path]::GetFullPath($DestDir)
  $backupsRoot = [System.IO.Path]::GetFullPath("F:\DropFolder\backups")
  $sep = [string][System.IO.Path]::DirectorySeparatorChar
  if ($full -ne $backupsRoot -and -not $full.StartsWith(($backupsRoot + $sep), [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "REFUSE: DestDir must be under F:\DropFolder\backups: $DestDir"
  }
  return $full
}

function Assert-PreG5ReconstructionCustodyAbsent {
  param([Parameter(Mandatory = $true)][string[]] $Paths)
  foreach ($p in $Paths) {
    if (Test-Path -LiteralPath $p) {
      throw ("REFUSE: custody target already exists (no silent overwrite): {0}" -f $p)
    }
  }
}

function Get-PreG5FileSha256Upper([string] $Path) {
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Get-PreG5Sha256HexLowerBytes {
  param([Parameter(Mandatory = $true)][byte[]] $Bytes)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    return ([BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-', '').ToLowerInvariant())
  }
  finally {
    $sha.Dispose()
  }
}

function Get-PreG5ImageConfigHexFromId([string] $ImageId) {
  if ($ImageId -notmatch '^sha256:([a-f0-9]{64})$') {
    throw "REFUSE: invalid image id for save verify: $ImageId"
  }
  return $Matches[1]
}

function Get-PreG5TarMemberBytes {
  param(
    [Parameter(Mandatory = $true)][string] $TarPath,
    [Parameter(Mandatory = $true)][string] $MemberPath
  )
  $extractRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("preg5-tar-extract-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $extractRoot | Out-Null
  try {
    & tar -xf $TarPath -C $extractRoot $MemberPath 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "REFUSE: tar extract member failed: $MemberPath" }
    $full = Join-Path $extractRoot ($MemberPath -replace '/', [IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $full)) { throw "REFUSE: tar member missing after extract: $MemberPath" }
    return [System.IO.File]::ReadAllBytes($full)
  }
  finally {
    Remove-Item -LiteralPath $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}

function Test-PreG5TarListsMember {
  param(
    [Parameter(Mandatory = $true)][string[]] $Entries,
    [Parameter(Mandatory = $true)][string] $MemberPath
  )
  $norm = $MemberPath.TrimStart('./')
  foreach ($e in $Entries) {
    $en = ([string]$e).TrimEnd('/').TrimStart('./')
    if ($en -eq $norm) { return $true }
  }
  return $false
}

function Get-PreG5UncompressedLayerDiffIdFromGzipBytes {
  param([Parameter(Mandatory = $true)][byte[]] $GzipLayerBytes)
  $inMs = New-Object System.IO.MemoryStream(,$GzipLayerBytes)
  $gzip = New-Object System.IO.Compression.GZipStream($inMs, [System.IO.Compression.CompressionMode]::Decompress)
  $outMs = New-Object System.IO.MemoryStream
  try {
    $gzip.CopyTo($outMs)
  }
  finally {
    $gzip.Dispose()
    $inMs.Dispose()
  }
  return Get-PreG5Sha256HexLowerBytes -Bytes $outMs.ToArray()
}

function Assert-PreG5DockerSaveTarIdentity {
  <#
    Verify docker save archive without docker load.
    Supports Docker Desktop OCI layout (blobs/sha256/...) and legacy manifest Config+json layout.
  #>
  param(
    [Parameter(Mandatory = $true)][string] $TarPath,
    [Parameter(Mandatory = $true)][string] $ExpectedImageId
  )
  if (-not (Test-Path -LiteralPath $TarPath)) { throw "REFUSE: save tar missing: $TarPath" }
  $len = (Get-Item -LiteralPath $TarPath).Length
  if ($len -le 0) { throw "REFUSE: save tar empty: $TarPath" }

  $listOut = & tar -tf $TarPath 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw ("REFUSE: tar list failed for save archive: {0}" -f ($listOut -join "`n"))
  }
  $entries = @($listOut | ForEach-Object { ([string]$_).Trim() })

  $wantHex = Get-PreG5ImageConfigHexFromId $ExpectedImageId
  $ociManifestMember = "blobs/sha256/$wantHex"
  if (Test-PreG5TarListsMember -Entries $entries -MemberPath $ociManifestMember) {
    $manifestBytes = Get-PreG5TarMemberBytes -TarPath $TarPath -MemberPath $ociManifestMember
    if ($manifestBytes.Length -le 0) { throw "REFUSE: OCI image manifest blob empty" }
    $manifestHash = Get-PreG5Sha256HexLowerBytes -Bytes $manifestBytes
    if ($manifestHash -ne $wantHex) {
      throw ("REFUSE: OCI manifest blob digest mismatch want={0} got={1}" -f $wantHex, $manifestHash)
    }
    $ociManifest = ([System.Text.Encoding]::UTF8.GetString($manifestBytes)) | ConvertFrom-Json
    $cfgRef = [string]$ociManifest.config.digest
    if ($cfgRef -notmatch '^sha256:([a-f0-9]{64})$') { throw "REFUSE: OCI manifest config.digest missing" }
    $cfgHex = $Matches[1]
    $cfgMember = "blobs/sha256/$cfgHex"
    if (-not (Test-PreG5TarListsMember -Entries $entries -MemberPath $cfgMember)) {
      throw "REFUSE: OCI config blob missing in tar: $cfgMember"
    }
    $cfgBytes = Get-PreG5TarMemberBytes -TarPath $TarPath -MemberPath $cfgMember
    if ($cfgBytes.Length -le 0) { throw "REFUSE: OCI config blob empty" }
    $cfgHash = Get-PreG5Sha256HexLowerBytes -Bytes $cfgBytes
    if ($cfgHash -ne $cfgHex) { throw "REFUSE: OCI config blob digest mismatch" }

    $layers = @($ociManifest.layers)
    if ($layers.Count -lt 1) { throw "REFUSE: OCI manifest layers empty" }
    $cfgObj = ([System.Text.Encoding]::UTF8.GetString($cfgBytes)) | ConvertFrom-Json
    $diffIds = @()
    if ($null -ne $cfgObj.rootfs -and $null -ne $cfgObj.rootfs.diff_ids) {
      $diffIds = @($cfgObj.rootfs.diff_ids)
    }
    if ($diffIds.Count -gt 0 -and $diffIds.Count -ne $layers.Count) {
      throw ("REFUSE: OCI config rootfs.diff_ids count {0} != layers count {1}" -f $diffIds.Count, $layers.Count)
    }

    for ($i = 0; $i -lt $layers.Count; $i++) {
      $layerRef = [string]$layers[$i].digest
      if ($layerRef -notmatch '^sha256:([a-f0-9]{64})$') { throw "REFUSE: OCI layer digest missing" }
      $layerHex = $Matches[1]
      $layerMember = "blobs/sha256/$layerHex"
      if (-not (Test-PreG5TarListsMember -Entries $entries -MemberPath $layerMember)) {
        throw "REFUSE: OCI layer blob missing in tar: $layerMember"
      }
      $layerBytes = Get-PreG5TarMemberBytes -TarPath $TarPath -MemberPath $layerMember
      if ($layerBytes.Length -le 0) { throw "REFUSE: OCI layer blob empty: $layerMember" }
      $layerHash = Get-PreG5Sha256HexLowerBytes -Bytes $layerBytes
      if ($layerHash -ne $layerHex) { throw "REFUSE: OCI layer blob digest mismatch: $layerMember" }
      if ($diffIds.Count -gt $i) {
        $wantDiff = ([string]$diffIds[$i]) -replace '^sha256:', ''
        $gotDiff = Get-PreG5UncompressedLayerDiffIdFromGzipBytes -GzipLayerBytes $layerBytes
        if ($gotDiff -ne $wantDiff) {
          throw ("REFUSE: OCI layer diff_id mismatch index={0} want={1} got={2}" -f $i, $wantDiff, $gotDiff)
        }
      }
    }
    return $true
  }

  # Legacy docker save (manifest.json + {configHex}.json + layer paths)
  $hasManifest = Test-PreG5TarListsMember -Entries $entries -MemberPath "manifest.json"
  if (-not $hasManifest) { throw "REFUSE: manifest.json missing in save tar" }

  $manifestRaw = & tar -xOf $TarPath manifest.json 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw ("REFUSE: could not extract manifest.json: {0}" -f ($manifestRaw -join "`n"))
  }
  $manifestObj = $manifestRaw | ConvertFrom-Json
  $items = @($manifestObj)
  if ($items.Count -lt 1) { throw "REFUSE: manifest.json empty" }
  $item = $items[0]
  $configFile = [string]$item.Config
  if ([string]::IsNullOrWhiteSpace($configFile)) { throw "REFUSE: manifest Config missing" }
  $layers = @($item.Layers)
  if ($layers.Count -lt 1) { throw "REFUSE: manifest Layers empty (incomplete archive)" }

  if (-not (Test-PreG5TarListsMember -Entries $entries -MemberPath $configFile)) {
    throw ("REFUSE: config blob {0} not present in tar listing" -f $configFile)
  }
  $configBytes = Get-PreG5TarMemberBytes -TarPath $TarPath -MemberPath $configFile
  if ($configBytes.Length -le 0) { throw "REFUSE: legacy config blob empty" }
  $configHash = Get-PreG5Sha256HexLowerBytes -Bytes $configBytes
  if ($configHash -ne $wantHex) {
    throw ("REFUSE: legacy config content digest mismatch want={0} got={1} (filename alone is insufficient)" -f $wantHex, $configHash)
  }

  $cfgObj = ([System.Text.Encoding]::UTF8.GetString($configBytes)) | ConvertFrom-Json
  $diffIds = @()
  if ($null -ne $cfgObj.rootfs -and $null -ne $cfgObj.rootfs.diff_ids) {
    $diffIds = @($cfgObj.rootfs.diff_ids)
  }
  if ($diffIds.Count -gt 0 -and $diffIds.Count -ne $layers.Count) {
    throw ("REFUSE: legacy rootfs.diff_ids count {0} != layers count {1}" -f $diffIds.Count, $layers.Count)
  }

  for ($i = 0; $i -lt $layers.Count; $i++) {
    $layerPath = [string]$layers[$i]
    if (-not (Test-PreG5TarListsMember -Entries $entries -MemberPath $layerPath)) {
      throw "REFUSE: legacy layer path missing in tar: $layerPath"
    }
    $layerBytes = Get-PreG5TarMemberBytes -TarPath $TarPath -MemberPath $layerPath
    if ($layerBytes.Length -le 0) { throw "REFUSE: legacy layer blob empty: $layerPath" }
    if ($diffIds.Count -gt $i) {
      $wantDiff = ([string]$diffIds[$i]) -replace '^sha256:', ''
      $gotDiff = Get-PreG5Sha256HexLowerBytes -Bytes $layerBytes
      if ($gotDiff -ne $wantDiff) {
        throw ("REFUSE: legacy layer diff_id mismatch index={0} want={1} got={2}" -f $i, $wantDiff, $gotDiff)
      }
    }
  }
  return $true
}

function Get-PreG5ReconstructionSaveFixturePath {
  param(
    [Parameter(Mandatory = $true)][string] $Digest,
    [switch] $AllowGenerateFromDocker
  )
  $hex = Get-PreG5ImageConfigHexFromId $Digest
  $short = $hex.Substring(0, 8)
  $cacheRoot = [System.IO.Path]::GetFullPath("F:\DropFolder\scratch\preg5-recon-save-fixtures")
  if (-not (Test-Path -LiteralPath $cacheRoot)) {
    New-Item -ItemType Directory -Path $cacheRoot | Out-Null
  }
  $fixture = Join-Path $cacheRoot ("save-{0}.tar" -f $short)
  if (Test-Path -LiteralPath $fixture) { return $fixture }
  if (-not $AllowGenerateFromDocker) { return $null }
  Write-Host ("preg5_recon_fixture_generate digest={0} path={1}" -f $Digest, $fixture)
  Invoke-PreG5DockerControl -What "docker save fixture $Digest" -DockerArgs @("save", $Digest, "-o", $fixture) -TimeoutMs 600000 | Out-Null
  if (-not (Test-Path -LiteralPath $fixture)) { throw "FAIL: fixture generation missing output" }
  Assert-PreG5DockerSaveTarIdentity -TarPath $fixture -ExpectedImageId $Digest | Out-Null
  return $fixture
}

function Copy-PreG5ReconstructionSaveFixture {
  param(
    [Parameter(Mandatory = $true)][string] $Digest,
    [Parameter(Mandatory = $true)][string] $DestPath,
    [switch] $AllowGenerateFromDocker
  )
  $fixture = Get-PreG5ReconstructionSaveFixturePath -Digest $Digest -AllowGenerateFromDocker:$AllowGenerateFromDocker
  if ($null -eq $fixture) {
    throw ("REFUSE: no save fixture for {0} (seed F:\DropFolder\scratch\preg5-recon-save-fixtures or run Validate with -AllowGenerateFromDocker)" -f $Digest)
  }
  Copy-Item -LiteralPath $fixture -Destination $DestPath -Force
}

function Assert-PreG5ReconstructionSaveFixturesCached {
  param(
    [Parameter(Mandatory = $true)][string[]] $Digests,
    [switch] $AllowGenerateFromDocker
  )
  if ($AllowGenerateFromDocker) { return }
  $missing = New-Object System.Collections.Generic.List[string]
  foreach ($d in $Digests) {
    $p = Get-PreG5ReconstructionSaveFixturePath -Digest $d
    if ($null -eq $p) { [void]$missing.Add($d) }
  }
  if ($missing.Count -gt 0) {
    throw ("REFUSE: offline orchestration requires cached save fixtures under F:\DropFolder\scratch\preg5-recon-save-fixtures; missing: {0}. Re-run Validate with -AllowGenerateFromDocker once to seed (RO docker save, not adoption EXECUTE)." -f ($missing -join ', '))
  }
}

function New-PreG5SyntheticDockerSaveTar {
  <# Invalid / edge-case tar builder for orchestration (not a bypass for real digests). #>
  param(
    [Parameter(Mandatory = $true)][string] $Path,
    [Parameter(Mandatory = $true)][string] $ImageId,
    [ValidateSet('valid_legacy', 'wrong_config_bytes', 'wrong_config_filename', 'missing_layer', 'truncated_layer', 'empty_archive')]
    [string] $Mode = 'valid_legacy'
  )
  if ($Mode -eq 'empty_archive') {
    $dir = Join-Path ([System.IO.Path]::GetTempPath()) ("preg5-save-empty-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $dir | Out-Null
    try {
      New-Item -ItemType File -Path (Join-Path $dir "empty.txt") -Force | Out-Null
      & tar -cf $Path -C $dir .
      if ($LASTEXITCODE -ne 0) { throw "FAIL: tar create empty archive exited $LASTEXITCODE" }
    }
    finally {
      Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
    }
    return @{ ImageId = $ImageId }
  }

  $dir = Join-Path ([System.IO.Path]::GetTempPath()) ("preg5-save-synth-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $dir | Out-Null
  try {
    $layerBytes = [System.Text.Encoding]::ASCII.GetBytes("PREG5_SYNTH_LAYER_V1")
    $diffHex = Get-PreG5Sha256HexLowerBytes -Bytes $layerBytes
    $diffId = "sha256:$diffHex"
    $layerRel = "$diffHex/layer.tar"
    $layerFull = Join-Path $dir ($layerRel -replace '/', [IO.Path]::DirectorySeparatorChar)
    New-Item -ItemType Directory -Path (Split-Path $layerFull -Parent) -Force | Out-Null
    if ($Mode -eq 'truncated_layer') {
      [System.IO.File]::WriteAllBytes($layerFull, @())
    } else {
      [System.IO.File]::WriteAllBytes($layerFull, $layerBytes)
    }

    $configObj = [ordered]@{
      architecture = "amd64"
      os           = "linux"
      rootfs       = [ordered]@{
        type     = "layers"
        diff_ids = @($diffId)
      }
    }
    $configJson = ($configObj | ConvertTo-Json -Compress -Depth 6)
    $configBytes = [System.Text.Encoding]::UTF8.GetBytes($configJson)
    $configHex = Get-PreG5Sha256HexLowerBytes -Bytes $configBytes
    $actualImageId = "sha256:$configHex"

    if ($Mode -eq 'wrong_config_bytes') {
      $wantHex = Get-PreG5ImageConfigHexFromId $ImageId
      $configName = "$wantHex.json"
      $badBytes = [System.Text.Encoding]::UTF8.GetBytes('{"architecture":"amd64","rootfs":{"type":"layers","diff_ids":[]}}')
      [System.IO.File]::WriteAllBytes((Join-Path $dir $configName), $badBytes)
    } elseif ($Mode -eq 'wrong_config_filename') {
      $wrongHex = ("0" * 63) + "1"
      [System.IO.File]::WriteAllBytes((Join-Path $dir ($wrongHex + ".json")), $configBytes)
    } else {
      [System.IO.File]::WriteAllBytes((Join-Path $dir ($configHex + ".json")), $configBytes)
    }

    $manifestLayers = @($layerRel)
    if ($Mode -eq 'missing_layer') {
      $manifestLayers = @("missing/deadbeef/layer.tar")
    }

    $configForManifest = if ($Mode -eq 'wrong_config_bytes') {
      (Get-PreG5ImageConfigHexFromId $ImageId) + ".json"
    } elseif ($Mode -eq 'wrong_config_filename') {
      ("0" * 63) + "1.json"
    } else {
      "$configHex.json"
    }

    $manifest = @(
      [ordered]@{
        Config   = $configForManifest
        RepoTags = $null
        Layers   = $manifestLayers
      }
    )
    ($manifest | ConvertTo-Json -Depth 5 -Compress) | Set-Content -LiteralPath (Join-Path $dir "manifest.json") -Encoding ascii
    if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Force }
    & tar -cf $Path -C $dir .
    if ($LASTEXITCODE -ne 0) { throw "FAIL: tar create synthetic save exited $LASTEXITCODE" }
    return @{ ImageId = $actualImageId }
  }
  finally {
    Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
  }
}

function Get-PreG5DockerImageRepoTagHint {
  param([Parameter(Mandatory = $true)][string] $Digest)
  $r = Invoke-PreG5DockerControlAllowFail -What "image inspect repotags $Digest" -DockerArgs @(
    "image", "inspect", $Digest, "--format", "{{json .RepoTags}}"
  )
  if ($r.Code -ne 0) { return $null }
  $raw = ([string]$r.StdOut).Trim()
  if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
  try {
    $tags = $raw | ConvertFrom-Json
    if ($null -eq $tags) { return $null }
    foreach ($t in @($tags)) {
      if (-not [string]::IsNullOrWhiteSpace([string]$t)) { return [string]$t }
    }
  } catch { }
  return $null
}

function Write-PreG5RollbackImageSidecars {
  param(
    [Parameter(Mandatory = $true)][string] $TarPath,
    [Parameter(Mandatory = $true)][string] $Digest,
    [Parameter(Mandatory = $true)][string] $Stamp,
    [string] $SourceTag = $null,
    [string[]] $HistoricalSourceDigests = $script:PreG5ReconstructionHistoricalDigests
  )
  $shaPath = "$TarPath.sha256"
  $metaPath = "$TarPath.meta.json"
  Assert-DurablePathWritable $shaPath | Out-Null
  Assert-DurablePathWritable $metaPath | Out-Null
  $sha = Get-PreG5FileSha256Upper $TarPath
  $leaf = Split-Path $TarPath -Leaf
  Set-Content -LiteralPath $shaPath -Value ("{0}  {1}" -f $sha, $leaf) -Encoding ascii
  $meta = [ordered]@{
    digest                    = $Digest
    source_tag                = $SourceTag
    stamp                     = $Stamp
    taken_utc                 = ([DateTime]::UtcNow.ToString("o"))
    not_original_digest       = $true
    historical_source_digests = @($HistoricalSourceDigests)
    reconstruction            = "container_fs_export_import"
  }
  ($meta | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $metaPath -Encoding utf8
  return @{ ShaPath = $shaPath; MetaPath = $metaPath; TarSha256 = $sha }
}

function Move-PreG5FileAtomicFinalize {
  param(
    [Parameter(Mandatory = $true)][string] $TempPath,
    [Parameter(Mandatory = $true)][string] $FinalPath
  )
  if (-not (Test-Path -LiteralPath $TempPath)) { throw "REFUSE: temp finalize source missing: $TempPath" }
  if (Test-Path -LiteralPath $FinalPath) { throw "REFUSE: finalize target exists: $FinalPath" }
  Move-Item -LiteralPath $TempPath -Destination $FinalPath
}

function Get-PreG5ComposePinsBaselines {
  param([Parameter(Mandatory = $true)][string] $PinsPath)
  if (-not (Test-Path -LiteralPath $PinsPath)) { throw "REFUSE: ComposePins missing: $PinsPath" }
  $text = Get-Content -LiteralPath $PinsPath -Raw -Encoding utf8
  $api = $null; $web = $null
  if ($text -match '\$script:ApiImageBaseline\s*=\s*"(sha256:[a-f0-9]{64})"') { $api = $Matches[1] }
  if ($text -match '\$script:WebImageBaseline\s*=\s*"(sha256:[a-f0-9]{64})"') { $web = $Matches[1] }
  if ([string]::IsNullOrWhiteSpace($api) -or [string]::IsNullOrWhiteSpace($web)) {
    throw "REFUSE: ComposePins missing ApiImageBaseline and/or WebImageBaseline"
  }
  return @{ Api = $api; Web = $web }
}

function Assert-PreG5ComposePinsBaselinesMatch {
  param(
    [Parameter(Mandatory = $true)][string] $PinsPath,
    [Parameter(Mandatory = $true)][string] $ApiDigest,
    [Parameter(Mandatory = $true)][string] $WebDigest
  )
  $got = Get-PreG5ComposePinsBaselines -PinsPath $PinsPath
  if ($got.Api -ne $ApiDigest) {
    throw ("REFUSE: ComposePins ApiImageBaseline readback mismatch want={0} got={1}" -f $ApiDigest, $got.Api)
  }
  if ($got.Web -ne $WebDigest) {
    throw ("REFUSE: ComposePins WebImageBaseline readback mismatch want={0} got={1}" -f $WebDigest, $got.Web)
  }
}

function Update-PreG5HouseholdComposePinsApiBaseline {
  param(
    [Parameter(Mandatory = $true)][string] $PinsPath,
    [Parameter(Mandatory = $true)][string] $ApiDigest
  )
  if (-not (Test-Path -LiteralPath $PinsPath)) { throw "REFUSE: ComposePins missing: $PinsPath" }
  $text = Get-Content -LiteralPath $PinsPath -Raw -Encoding utf8
  $newText = [regex]::Replace($text, '(\$script:ApiImageBaseline\s*=\s*")[^"]+(")', ('${1}' + $ApiDigest + '${2}'), 1)
  if ($newText -eq $text) { throw "REFUSE: ComposePins ApiImageBaseline unchanged (pattern miss): $PinsPath" }
  Set-Content -LiteralPath $PinsPath -Value $newText -Encoding utf8 -NoNewline
}

function Update-PreG5HouseholdComposePinsWebBaseline {
  param(
    [Parameter(Mandatory = $true)][string] $PinsPath,
    [Parameter(Mandatory = $true)][string] $WebDigest
  )
  if ($script:PreG5ReconstructionOrchBlockPinWeb) {
    throw "REFUSE: orchestration block web pin mutation"
  }
  if (-not (Test-Path -LiteralPath $PinsPath)) { throw "REFUSE: ComposePins missing: $PinsPath" }
  $text = Get-Content -LiteralPath $PinsPath -Raw -Encoding utf8
  $newText = [regex]::Replace($text, '(\$script:WebImageBaseline\s*=\s*")[^"]+(")', ('${1}' + $WebDigest + '${2}'), 1)
  if ($newText -eq $text) { throw "REFUSE: ComposePins WebImageBaseline unchanged (pattern miss): $PinsPath" }
  Set-Content -LiteralPath $PinsPath -Value $newText -Encoding utf8 -NoNewline
}

function Update-PreG5DecisionSheetOperationalDigests {
  param(
    [Parameter(Mandatory = $true)][string] $SheetPath,
    [Parameter(Mandatory = $true)][string] $NewApiDigest,
    [Parameter(Mandatory = $true)][string] $NewWebDigest,
    [Parameter(Mandatory = $true)][string] $HistoricalApiDigest,
    [Parameter(Mandatory = $true)][string] $HistoricalWebDigest
  )
  if (-not (Test-Path -LiteralPath $SheetPath)) { throw "REFUSE: decision sheet missing: $SheetPath" }
  $text = Get-Content -LiteralPath $SheetPath -Raw -Encoding utf8
  $histApiNote = "Historical pre-rebuild: ``$HistoricalApiDigest``"
  $histWebNote = "Historical pre-rebuild: ``$HistoricalWebDigest``"

  $newText = $text
  $newText = $newText.Replace($HistoricalApiDigest, $NewApiDigest)
  $newText = $newText.Replace($HistoricalWebDigest, $NewWebDigest)

  if ($newText -eq $text) { throw "REFUSE: decision sheet digests unchanged: $SheetPath" }

  if ($newText -notmatch [regex]::Escape($histApiNote)) {
    $newText = $newText.Replace(
      ('**`{0}`**' -f $NewApiDigest),
      ('**`{0}`** ({1})' -f $NewApiDigest, $histApiNote)
    )
  }
  if ($newText -notmatch [regex]::Escape($histWebNote)) {
    $newText = $newText.Replace(
      ('**`{0}`**' -f $NewWebDigest),
      ('**`{0}`** ({1})' -f $NewWebDigest, $histWebNote)
    )
  }

  Set-Content -LiteralPath $SheetPath -Value $newText -Encoding utf8 -NoNewline
}

function Assert-PreG5ReconstructionAdoptionApproval {
  param(
    [Parameter(Mandatory = $true)][string] $AuditApprovalPath,
    [Parameter(Mandatory = $true)][string] $ExportStamp,
    [Parameter(Mandatory = $true)][string] $ApiDigest,
    [Parameter(Mandatory = $true)][string] $WebDigest,
    [Parameter(Mandatory = $true)][string] $DestDir,
    [Parameter(Mandatory = $true)][object] $Plan,
    [Parameter(Mandatory = $true)][string] $ComposePinsPath,
    [Parameter(Mandatory = $true)][string] $DecisionSheetPath,
    [Parameter(Mandatory = $true)][bool] $ApplyOptionalAdoptedTags
  )
  if ([string]::IsNullOrWhiteSpace($AuditApprovalPath)) { throw "REFUSE: AuditApprovalPath is required" }
  if (-not (Test-Path -LiteralPath $AuditApprovalPath)) { throw "REFUSE: AuditApprovalPath missing" }
  $approval = Get-Content -LiteralPath $AuditApprovalPath -Raw | ConvertFrom-Json
  if ($approval.approved -ne $true) { throw "REFUSE: approval.approved != true" }

  $forbidden = @(
    'snapshot_api_image_id', 'snapshot_web_image_id', 'dump_path', 'restore_dump_path',
    'dump_sha256', 'restore_dump_sha256', 'inventory_manifest_sha256', 'continuation_attempt',
    'api_tar_sha256', 'web_tar_sha256', 'retained_api_image_id', 'private_content_reviewed'
  )
  foreach ($k in $forbidden) {
    if ($approval.PSObject.Properties.Name -contains $k) {
      throw ("REFUSE: approval field {0} indicates restore/import reuse; fresh adoption approval required" -f $k)
    }
  }

  $op = $null
  if ($approval.PSObject.Properties.Name -contains 'operation') { $op = [string]$approval.operation }
  elseif ($approval.PSObject.Properties.Name -contains 'approved_operation') { $op = [string]$approval.approved_operation }
  if ($op -ne $script:PreG5ReconstructionAdoptionOperation) {
    throw ("REFUSE: approval operation must be {0}" -f $script:PreG5ReconstructionAdoptionOperation)
  }

  function _MustMatch([string]$field, [string]$want) {
    if ($approval.PSObject.Properties.Name -notcontains $field) {
      throw ("REFUSE: approval missing required field {0}" -f $field)
    }
    $got = [string]$approval.$field
    if ($field -eq 'dest_dir' -or $field -eq 'compose_pins_path' -or $field -eq 'decision_sheet_path') {
      $got = [System.IO.Path]::GetFullPath($got)
      $want = [System.IO.Path]::GetFullPath($want)
    }
    if ($got -ne $want) { throw ("REFUSE: approval {0} mismatch want={1} got={2}" -f $field, $want, $got) }
  }

  _MustMatch 'stamp' $ExportStamp
  _MustMatch 'api_image_id' $ApiDigest
  _MustMatch 'web_image_id' $WebDigest
  _MustMatch 'dest_dir' $DestDir
  _MustMatch 'api_tar_basename' ([string]$Plan.ApiTarBasename)
  _MustMatch 'web_tar_basename' ([string]$Plan.WebTarBasename)
  _MustMatch 'compose_pins_path' $ComposePinsPath
  _MustMatch 'decision_sheet_path' $DecisionSheetPath
  if ($approval.PSObject.Properties.Name -notcontains 'apply_optional_adopted_tags') {
    throw "REFUSE: approval missing apply_optional_adopted_tags"
  }
  $wantTags = [bool]$ApplyOptionalAdoptedTags
  $gotTags = [bool]$approval.apply_optional_adopted_tags
  if ($gotTags -ne $wantTags) {
    throw ("REFUSE: approval apply_optional_adopted_tags mismatch want={0} got={1}" -f $wantTags, $gotTags)
  }
  return $approval
}

function Assert-PreG5HouseholdPreAdoptionGuard {
  param(
    [Parameter(Mandatory = $true)][string] $ExpectApiImage,
    [Parameter(Mandatory = $true)][string] $ExpectWebImage
  )
  foreach ($pair in @(
      @{ Name = $script:PreG5ReconstructionHouseholdApiContainer; Want = $ExpectApiImage },
      @{ Name = $script:PreG5ReconstructionHouseholdWebContainer; Want = $ExpectWebImage }
    )) {
    $name = $pair.Name
    $want = $pair.Want
    $rImg = Invoke-PreG5DockerControlAllowFail -What "inspect household image $name" -DockerArgs @(
      "inspect", $name, "--format", "{{.Image}}"
    )
    if ($rImg.Code -ne 0) { throw ("REFUSE: household guard inspect Image failed for {0}: {1}" -f $name, $rImg.StdErr) }
    $gotImg = ([string]$rImg.StdOut).Trim()
    if ($gotImg -ne $want) {
      throw ("REFUSE: household guard {0} Image={1} want historical {2}" -f $name, $gotImg, $want)
    }
    $rHealth = Invoke-PreG5DockerControlAllowFail -What "inspect household health $name" -DockerArgs @(
      "inspect", $name, "--format", "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}"
    )
    if ($rHealth.Code -ne 0) { throw ("REFUSE: household guard inspect health failed for {0}" -f $name) }
    $health = ([string]$rHealth.StdOut).Trim().ToLowerInvariant()
    if ($health -ne 'healthy' -and $health -ne 'running') {
      throw ("REFUSE: household guard {0} not healthy/running status={1}" -f $name, $health)
    }
  }
}

function Set-PreG5ReconstructionAdoptedTagVerified {
  param(
    [Parameter(Mandatory = $true)][string] $Tag,
    [Parameter(Mandatory = $true)][string] $WantId,
    [Parameter(Mandatory = $true)] $UncertainList,
    [Parameter(Mandatory = $true)] $ChangedList
  )
  $mutationKey = "docker_tag:" + $Tag
  Add-PreG5ReconstructionMutationUncertain -UncertainList $UncertainList -MutationKey $mutationKey
  if ($script:PreG5ReconstructionOrchBlockTagWeb -and $Tag -match ':adopted-636901af-') {
    throw "REFUSE: orchestration block web adopted tag"
  }
  $pres = Resolve-DockerImagePresence -Ref $Tag
  if ($pres.Status -eq "Present") {
    if ($pres.Id -ne $WantId) { throw ("REFUSE overwrite ${Tag} have=$($pres.Id) want=$WantId") }
    Complete-PreG5ReconstructionMutation -UncertainList $UncertainList -ChangedList $ChangedList -MutationKey $mutationKey
    return
  }
  if ($pres.Status -ne "Missing") { throw ("REFUSE unexpected tag presence for ${Tag}") }
  Invoke-PreG5DockerControl -What "tag $Tag" -DockerArgs @("tag", $WantId, $Tag) | Out-Null
  Assert-ImageIdMatchesTag -Tag $Tag -ExpectedId $WantId | Out-Null
  Complete-PreG5ReconstructionMutation -UncertainList $UncertainList -ChangedList $ChangedList -MutationKey $mutationKey
}

function Write-PreG5ReconstructionAdoptionFailureReceipt {
  param(
    [Parameter(Mandatory = $true)][hashtable] $Payload,
    [Parameter(Mandatory = $true)][string] $DestDir,
    [string] $WorkTemp = "",
    [string] $Stamp = ""
  )
  $name = "reconstruction-adoption-preservation.failure"
  if (-not [string]::IsNullOrWhiteSpace($Stamp)) { $name += ("-" + $Stamp) }
  $name += ".receipt.json"
  $candidates = @()
  if (-not [string]::IsNullOrWhiteSpace($DestDir)) {
    $candidates += Join-Path $DestDir $name
  }
  if (-not [string]::IsNullOrWhiteSpace($WorkTemp)) {
    $candidates += Join-Path $WorkTemp $name
  }
  foreach ($path in $candidates) {
    try {
      if (Test-Path -LiteralPath $path) { continue }
      $parent = Split-Path $path -Parent
      if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
      ($Payload | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $path -Encoding utf8
      return $path
    } catch { }
  }
  return $null
}

function Save-PreG5ReconstructionImageArchive {
  param(
    [Parameter(Mandatory = $true)][string] $Digest,
    [Parameter(Mandatory = $true)][string] $TempTarPath,
    [Parameter(Mandatory = $true)][string] $FinalTarPath,
    [Parameter(Mandatory = $true)][string] $Stamp,
    [Parameter(Mandatory = $true)][string] $WorkTempDir,
    [int] $SaveTimeoutMs = 600000
  )
  $tempPart = Join-Path $WorkTempDir ((Split-Path $FinalTarPath -Leaf) + ".part")
  if (Test-Path -LiteralPath $tempPart) { Remove-Item -LiteralPath $tempPart -Force }
  Invoke-PreG5DockerControl -What "docker save $Digest" -DockerArgs @("save", $Digest, "-o", $tempPart) -TimeoutMs $SaveTimeoutMs | Out-Null
  Assert-PreG5DockerSaveTarIdentity -TarPath $tempPart -ExpectedImageId $Digest | Out-Null
  Move-PreG5FileAtomicFinalize -TempPath $tempPart -FinalPath $TempTarPath | Out-Null
  $tagHint = Get-PreG5DockerImageRepoTagHint -Digest $Digest
  $hist = @()
  if ($Digest -ceq $script:PreG5ReconstructionDefaultApiDigest) {
    $hist = @($script:PreG5ReconstructionOldOperationalApi)
  } elseif ($Digest -ceq $script:PreG5ReconstructionDefaultWebDigest) {
    $hist = @($script:PreG5ReconstructionOldOperationalWeb)
  } else {
    $hist = @($script:PreG5ReconstructionHistoricalDigests)
  }
  $sidecars = Write-PreG5RollbackImageSidecars -TarPath $TempTarPath -Digest $Digest -Stamp $Stamp `
    -SourceTag $tagHint -HistoricalSourceDigests $hist
  Move-PreG5FileAtomicFinalize -TempPath $TempTarPath -FinalPath $FinalTarPath | Out-Null
  $tempSha = Join-Path (Split-Path $TempTarPath -Parent) ((Split-Path $TempTarPath -Leaf) + ".sha256")
  $tempMeta = Join-Path (Split-Path $TempTarPath -Parent) ((Split-Path $TempTarPath -Leaf) + ".meta.json")
  $finalSha = "$FinalTarPath.sha256"
  $finalMeta = "$FinalTarPath.meta.json"
  Move-PreG5FileAtomicFinalize -TempPath $tempSha -FinalPath $finalSha | Out-Null
  Move-PreG5FileAtomicFinalize -TempPath $tempMeta -FinalPath $finalMeta | Out-Null
  return @{
    TarPath   = $FinalTarPath
    ShaPath   = $finalSha
    MetaPath  = $finalMeta
    TarSha256 = $sidecars.TarSha256
    SourceTag = $tagHint
  }
}

function Invoke-PreG5ReconstructionAdoptionPreservationCore {
  param(
    [string] $DestDir = $script:PreG5ReconstructionDefaultDestDir,
    [string] $ExportStamp = $script:PreG5ReconstructionDefaultStamp,
    [string] $ApiDigest = $script:PreG5ReconstructionDefaultApiDigest,
    [string] $WebDigest = $script:PreG5ReconstructionDefaultWebDigest,
    [Parameter(Mandatory = $true)][string] $AuditApprovalPath,
    [string] $ComposePinsPath = "",
    [string] $DecisionSheetPath = "",
    [switch] $ApplyOptionalAdoptedTags,
    [switch] $SkipHouseholdGuard,
    [int] $SaveTimeoutMs = 600000
  )

  $notes = New-Object System.Collections.Generic.List[string]
  $changed = New-Object System.Collections.Generic.List[string]
  $uncertain = New-Object System.Collections.Generic.List[string]
  $evidence = New-Object System.Collections.Generic.List[string]
  $phase = "init"
  $dest = $null
  $workTemp = ""
  $stamp = $null
  $archivesFinalized = $false
  $failureReceiptPath = $null

  if ([string]::IsNullOrWhiteSpace($ComposePinsPath)) {
    $ComposePinsPath = Join-Path $PSScriptRoot "Household-ComposePins.ps1"
  }
  if ([string]::IsNullOrWhiteSpace($DecisionSheetPath)) {
    $DecisionSheetPath = Join-Path (Split-Path $PSScriptRoot -Parent) `
      "0.7-AGENT-CLI-ACCESS-Phase1-RELEASE-DEPLOYMENT-DECISION-SHEET-2026-11-01.md"
  }
  $ComposePinsPath = [System.IO.Path]::GetFullPath($ComposePinsPath)
  $DecisionSheetPath = [System.IO.Path]::GetFullPath($DecisionSheetPath)

  try {
    $stamp = Assert-ExportStampSafe $ExportStamp
    $dest = Assert-PreG5RollbackImagesDestSafe -DestDir $DestDir
    $plan = Get-PreG5ReconstructionAdoptionImagePlan -ExportStamp $stamp -DestDir $dest `
      -ApiDigest $ApiDigest -WebDigest $WebDigest

    $phase = "approval"
    Assert-PreG5ReconstructionAdoptionApproval -AuditApprovalPath $AuditApprovalPath `
      -ExportStamp $stamp -ApiDigest $ApiDigest -WebDigest $WebDigest -DestDir $dest -Plan $plan `
      -ComposePinsPath $ComposePinsPath -DecisionSheetPath $DecisionSheetPath `
      -ApplyOptionalAdoptedTags:([bool]$ApplyOptionalAdoptedTags) | Out-Null

    $phase = "preflight_inspect"
    Assert-ImageIdMatchesTag -Tag $ApiDigest -ExpectedId $ApiDigest | Out-Null
    Assert-ImageIdMatchesTag -Tag $WebDigest -ExpectedId $WebDigest | Out-Null

    if (-not (Test-Path -LiteralPath $dest)) {
      New-Item -ItemType Directory -Path $dest | Out-Null
      $notes.Add("dest_dir_created=true")
    }

    $custodyPaths = @(
      $plan.ApiTar, $plan.WebTar,
      $plan.ApiTarSha, $plan.WebTarSha,
      $plan.ApiTarMeta, $plan.WebTarMeta
    )
    $phase = "preflight_custody_absent"
    Assert-PreG5ReconstructionCustodyAbsent -Paths $custodyPaths

    $workTemp = Join-Path $dest (".tmp-owned-reconstruction-adopt-" + $stamp)
    if (Test-Path -LiteralPath $workTemp) {
      throw "REFUSE: owned temp already exists (prior partial run?): $workTemp"
    }
    New-Item -ItemType Directory -Path $workTemp | Out-Null
    $notes.Add("work_temp=$workTemp")

    $apiTempTar = Join-Path $workTemp (Split-Path $plan.ApiTar -Leaf)
    $webTempTar = Join-Path $workTemp (Split-Path $plan.WebTar -Leaf)

    $phase = "save_api"
    $apiSaved = Save-PreG5ReconstructionImageArchive -Digest $ApiDigest -TempTarPath $apiTempTar `
      -FinalTarPath $plan.ApiTar -Stamp $stamp -WorkTempDir $workTemp -SaveTimeoutMs $SaveTimeoutMs
    $evidence.Add($plan.ApiTar); $evidence.Add($plan.ApiTarSha); $evidence.Add($plan.ApiTarMeta)

    $phase = "save_web"
    $webSaved = Save-PreG5ReconstructionImageArchive -Digest $WebDigest -TempTarPath $webTempTar `
      -FinalTarPath $plan.WebTar -Stamp $stamp -WorkTempDir $workTemp -SaveTimeoutMs $SaveTimeoutMs
    $evidence.Add($plan.WebTar); $evidence.Add($plan.WebTarSha); $evidence.Add($plan.WebTarMeta)
    $archivesFinalized = $true
    $notes.Add("archives_finalized=true")

    if (-not $SkipHouseholdGuard) {
      $phase = "household_guard"
      Assert-PreG5HouseholdPreAdoptionGuard -ExpectApiImage $script:PreG5ReconstructionOldOperationalApi `
        -ExpectWebImage $script:PreG5ReconstructionOldOperationalWeb
    } else {
      $notes.Add("household_guard_skipped=true")
    }

    $pinApiKey = "compose_pins:ApiImageBaseline:" + $ComposePinsPath
    $pinWebKey = "compose_pins:WebImageBaseline:" + $ComposePinsPath
    $sheetKey = "decision_sheet:" + $DecisionSheetPath

    $phase = "pin_api_baseline"
    Add-PreG5ReconstructionMutationUncertain -UncertainList $uncertain -MutationKey $pinApiKey
    Update-PreG5HouseholdComposePinsApiBaseline -PinsPath $ComposePinsPath -ApiDigest $ApiDigest
    $apiRead = (Get-PreG5ComposePinsBaselines -PinsPath $ComposePinsPath).Api
    if ($apiRead -ne $ApiDigest) {
      throw ("REFUSE: ComposePins ApiImageBaseline readback failed after write want={0} got={1}" -f $ApiDigest, $apiRead)
    }
    Complete-PreG5ReconstructionMutation -UncertainList $uncertain -ChangedList $changed -MutationKey $pinApiKey

    $phase = "pin_web_baseline"
    Add-PreG5ReconstructionMutationUncertain -UncertainList $uncertain -MutationKey $pinWebKey
    Update-PreG5HouseholdComposePinsWebBaseline -PinsPath $ComposePinsPath -WebDigest $WebDigest
    $webRead = (Get-PreG5ComposePinsBaselines -PinsPath $ComposePinsPath).Web
    if ($webRead -ne $WebDigest) {
      throw ("REFUSE: ComposePins WebImageBaseline readback failed after write want={0} got={1}" -f $WebDigest, $webRead)
    }
    Complete-PreG5ReconstructionMutation -UncertainList $uncertain -ChangedList $changed -MutationKey $pinWebKey

    $phase = "decision_sheet"
    Add-PreG5ReconstructionMutationUncertain -UncertainList $uncertain -MutationKey $sheetKey
    Update-PreG5DecisionSheetOperationalDigests -SheetPath $DecisionSheetPath `
      -NewApiDigest $ApiDigest -NewWebDigest $WebDigest `
      -HistoricalApiDigest $script:PreG5ReconstructionOldOperationalApi `
      -HistoricalWebDigest $script:PreG5ReconstructionOldOperationalWeb
    $sheetText = Get-Content -LiteralPath $DecisionSheetPath -Raw -Encoding utf8
    if ($sheetText -notmatch [regex]::Escape($ApiDigest) -or $sheetText -notmatch [regex]::Escape($WebDigest)) {
      throw "REFUSE: decision sheet readback missing expected digests after write"
    }
    Complete-PreG5ReconstructionMutation -UncertainList $uncertain -ChangedList $changed -MutationKey $sheetKey

    $phase = "pin_readback_verify"
    Assert-PreG5ComposePinsBaselinesMatch -PinsPath $ComposePinsPath -ApiDigest $ApiDigest -WebDigest $WebDigest

    if ($ApplyOptionalAdoptedTags) {
      $phase = "optional_tag_api"
      Set-PreG5ReconstructionAdoptedTagVerified -Tag $plan.ApiAdoptedTag -WantId $ApiDigest `
        -UncertainList $uncertain -ChangedList $changed

      $phase = "optional_tag_web"
      Set-PreG5ReconstructionAdoptedTagVerified -Tag $plan.WebAdoptedTag -WantId $WebDigest `
        -UncertainList $uncertain -ChangedList $changed
    }

    $receiptPath = Join-Path $dest ("reconstruction-adoption-preservation.receipt.json")
    Assert-DurablePathWritable $receiptPath | Out-Null
    $receipt = [ordered]@{
      ok                         = $true
      stamp                      = $stamp
      phase_completed            = $phase
      rollback_acceptance        = $false
      not_household_recreate     = $true
      reconstruction             = "container_fs_export_import"
      api_digest                 = $ApiDigest
      web_digest                 = $WebDigest
      api_tar                    = $plan.ApiTar
      web_tar                    = $plan.WebTar
      api_tar_sha256             = $apiSaved.TarSha256
      web_tar_sha256             = $webSaved.TarSha256
      approval_path              = $AuditApprovalPath
      changed                    = @($changed)
      optional_adopted_tags      = $(if ($ApplyOptionalAdoptedTags) { @($plan.ApiAdoptedTag, $plan.WebAdoptedTag) } else { @() })
      household_compose_pins     = $ComposePinsPath
      decision_sheet             = $DecisionSheetPath
      override_042_unchanged     = $true
    }
    ($receipt | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $receiptPath -Encoding utf8
    $evidence.Add($receiptPath)

    try {
      if (Test-Path -LiteralPath $workTemp) { Remove-Item -LiteralPath $workTemp -Recurse -Force }
      $notes.Add("work_temp_removed=true")
    } catch {
      $notes.Add("work_temp_retained_for_review=true")
    }

    Write-Host "PREG5_RECON_ADOPT_OK rollback_acceptance=false"
    return @{
      ExitCode            = 0
      Phase               = $phase
      Notes               = @($notes)
      Changed             = @($changed)
      Uncertain           = @($uncertain)
      Evidence            = @($evidence)
      ArchivesFinalized   = $archivesFinalized
      FailureReceiptPath  = $null
    }
  }
  catch {
    $msg = $_.Exception.Message
    $notes.Add("error=$msg")
    if ($archivesFinalized) { $notes.Add("archives_ok_pins_not_applied_or_partial=" + ($phase -notmatch '^pin_|^decision|^optional|^pin_readback')) }

    $failObj = [ordered]@{
      ok                  = $false
      stamp               = $stamp
      phase               = $phase
      error               = $msg
      archives_finalized  = $archivesFinalized
      changed_completed   = @($changed)
      changed_uncertain   = @($uncertain)
      evidence_paths      = @($evidence)
      approval_path       = $AuditApprovalPath
      rollback_acceptance = $false
    }
    $failureReceiptPath = Write-PreG5ReconstructionAdoptionFailureReceipt -Payload $failObj `
      -DestDir $(if ($null -ne $dest) { $dest } else { "" }) -WorkTemp $workTemp -Stamp $(if ($null -ne $stamp) { $stamp } else { "" })

    Write-Host ("PREG5_RECON_ADOPT_FAIL phase={0} msg={1}" -f $phase, $msg)
    if ($failureReceiptPath) { Write-Host ("PREG5_RECON_FAIL_RECEIPT path={0}" -f $failureReceiptPath) }
    foreach ($p in $evidence) {
      if ($p) { Write-Host ("PREG5_RECON_EVIDENCE path={0}" -f $p) }
    }
    return @{
      ExitCode            = 1
      Phase               = $phase
      Notes               = @($notes)
      Changed             = @($changed)
      Uncertain           = @($uncertain)
      Evidence            = @($evidence)
      Error               = $msg
      ArchivesFinalized   = $archivesFinalized
      FailureReceiptPath  = $failureReceiptPath
    }
  }
}
