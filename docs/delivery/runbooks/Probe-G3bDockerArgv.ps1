#Requires -Version 5.1
<#
.SYNOPSIS
  Harmless docker argv + stdout/stderr drain probes for G3b process wrapper (PS 5.1).

.DESCRIPTION
  Uses the same ConvertTo-WindowsCommandLine* / Invoke-WindowsProcessCaptured helpers as
  Invoke-G3bMigrateRehearsal.ps1. Alpine argv case does not touch postgres or theplan DBs;
  drain case uses a local powershell child only (>64KiB on both streams).

.EXAMPLE
  powershell -NoProfile -File "F:\Code Repo\ThePlan\docs\delivery\runbooks\Probe-G3bDockerArgv.ps1"
#>
[CmdletBinding()]
param(
  [string] $ProbeImage = "alpine:3.20"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Redact([string] $text) {
  if ([string]::IsNullOrEmpty($text)) { return $text }
  $t = $text
  $pw = $env:THEPLAN_PGPASSWORD
  if ($pw) { $t = $t.Replace($pw, "***") }
  if ($env:DATABASE_URL) { $t = $t.Replace($env:DATABASE_URL, "DATABASE_URL=***") }
  return $t
}

. (Join-Path $PSScriptRoot "G3b-DockerProcess.ps1")

$expected = @(
  '-tAc'
  'SELECT 1 FROM pg_database WHERE datname = ''theplan'''
  'F:\Code Repo\ThePlan\apps\api'
  'embedded "double" quotes'
  ("line1" + [Environment]::NewLine + "line2")
)

$argvDumpSh = @'
i=0
for a in "$@"; do
  printf 'ARGV%d<<<' "$i"
  printf '%s' "$a"
  printf '>>>\n'
  i=$((i+1))
done
'@

$hostShDir = Join-Path ([System.IO.Path]::GetTempPath()) ("g3b_argv_probe_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $hostShDir | Out-Null
try {
  $enc = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText((Join-Path $hostShDir "dumpargv.sh"), $argvDumpSh, $enc)

  $dockerArgs = @(
    "run", "--rm",
    "-v", "${hostShDir}:/probe:ro",
    "--entrypoint", "/bin/sh",
    $ProbeImage,
    "/probe/dumpargv.sh"
  ) + $expected

  $r = Invoke-DockerCapturedCore -DockerArgs $dockerArgs -What "argv probe" -Redact { param($t) Redact $t }
  $out = ($r.StdOut | Out-String)

  $allPass = $true
  for ($i = 0; $i -lt $expected.Count; $i++) {
    $marker = "ARGV$i<<<"
    $pattern = [regex]::Escape($marker) + '(.*?)>>>'
    $m = [regex]::Match($out, $pattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if (-not $m.Success) {
      Write-Host "PROBE[$i]=FAIL reason=missing_marker"
      $allPass = $false
      continue
    }
    $observed = $m.Groups[1].Value
    if ($observed -ceq $expected[$i]) {
      Write-Host "PROBE[$i]=PASS len=$($observed.Length)"
    } else {
      Write-Host "PROBE[$i]=FAIL reason=mismatch expected_len=$($expected[$i].Length) observed_len=$($observed.Length)"
      $allPass = $false
    }
  }

  if (-not $allPass) {
    Write-Host "argv_probe_overall=FAIL"
    exit 1
  }
  Write-Host "argv_probe_overall=PASS"
}
finally {
  if (Test-Path -LiteralPath $hostShDir) {
    Remove-Item -LiteralPath $hostShDir -Recurse -Force -ErrorAction SilentlyContinue
  }
}

# --- concurrent stdout/stderr drain (pipe deadlock regression) ---
$drainOk = $true
$drainDir = Join-Path ([System.IO.Path]::GetTempPath()) ("g3b_drain_probe_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $drainDir | Out-Null
$drainChildPs1 = Join-Path $drainDir "DrainChild.ps1"
@'
param([int]$ExitCode = 0)
$chunk = 'D' * 70000
[Console]::Out.Write($chunk)
[Console]::Error.Write($chunk)
exit $ExitCode
'@ | Set-Content -LiteralPath $drainChildPs1 -Encoding utf8

try {
  $r0 = Invoke-WindowsProcessCaptured -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-File", $drainChildPs1, "-ExitCode", "0"
  ) -What "drain probe exit 0" -SuppressHostEcho -Redact { param($t) Redact $t }
  if ($r0.StdOut.Length -lt 65536 -or $r0.StdErr.Length -lt 65536) {
    Write-Host "drain_probe[0]=FAIL reason=short_capture stdout=$($r0.StdOut.Length) stderr=$($r0.StdErr.Length)"
    $drainOk = $false
  } else {
    Write-Host "drain_probe[0]=PASS stdout_len=$($r0.StdOut.Length) stderr_len=$($r0.StdErr.Length)"
  }

  $nonzeroOk = $false
  try {
    Invoke-WindowsProcessCaptured -FilePath "powershell.exe" -ArgumentList @(
      "-NoProfile", "-File", $drainChildPs1, "-ExitCode", "7"
    ) -What "drain probe exit 7" -SuppressHostEcho -Redact { param($t) Redact $t } | Out-Null
    Write-Host "drain_probe[1]=FAIL reason=expected_throw"
  } catch {
    if ($_.Exception.Message -match 'exited 7') {
      Write-Host "drain_probe[1]=PASS"
      $nonzeroOk = $true
    } else {
      Write-Host "drain_probe[1]=FAIL reason=$($_.Exception.Message)"
    }
  }
  if (-not $nonzeroOk) { $drainOk = $false }
}
catch {
  Write-Host "drain_probe=FAIL reason=$($_.Exception.Message)"
  $drainOk = $false
}
finally {
  if (Test-Path -LiteralPath $drainDir) {
    Remove-Item -LiteralPath $drainDir -Recurse -Force -ErrorAction SilentlyContinue
  }
}

if ($drainOk) {
  Write-Host "drain_probe_overall=PASS"
  exit 0
}
Write-Host "drain_probe_overall=FAIL"
exit 1
