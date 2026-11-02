#Requires -Version 5.1
<#
  Shared Windows PowerShell 5.1 process launcher with MS C-runtime argv quoting.
  Dot-sourced by G3b runbook scripts. Preserves docker argv (no Start-Process -ArgumentList join bugs).
#>

Set-StrictMode -Version Latest

function ConvertTo-WindowsCommandLineArgument {
  param([AllowNull()][string] $Argument)

  if ($null -eq $Argument) { return '""' }
  if ($Argument.Length -eq 0) { return '""' }

  $needQuote = $false
  foreach ($c in $Argument.ToCharArray()) {
    if ($c -eq ' ' -or $c -eq "`t" -or $c -eq '"') {
      $needQuote = $true
      break
    }
  }
  if (-not $needQuote -and $Argument.IndexOfAny([char[]]@("`r", "`n")) -ge 0) {
    $needQuote = $true
  }
  if (-not $needQuote -and $Argument.EndsWith('\')) {
    $needQuote = $true
  }

  if (-not $needQuote) { return $Argument }

  $sb = New-Object System.Text.StringBuilder
  [void]$sb.Append('"')
  $bsCount = 0
  foreach ($c in $Argument.ToCharArray()) {
    if ($c -eq '\') {
      $bsCount++
    }
    elseif ($c -eq '"') {
      [void]$sb.Append('\', ($bsCount * 2 + 1))
      [void]$sb.Append('"')
      $bsCount = 0
    }
    else {
      if ($bsCount -gt 0) {
        [void]$sb.Append('\', $bsCount)
        $bsCount = 0
      }
      [void]$sb.Append($c)
    }
  }
  if ($bsCount -gt 0) {
    [void]$sb.Append('\', ($bsCount * 2))
  }
  [void]$sb.Append('"')
  return $sb.ToString()
}

function ConvertTo-WindowsCommandLine {
  param([Parameter(Mandatory = $true)][string[]] $ArgumentList)
  return (($ArgumentList | ForEach-Object { ConvertTo-WindowsCommandLineArgument $_ }) -join ' ')
}

function Invoke-WindowsProcessCaptured {
  param(
    [Parameter(Mandatory = $true)][string] $FilePath,
    [Parameter(Mandatory = $true)][string[]] $ArgumentList,
    [Parameter(Mandatory = $true)][string] $What,
    [scriptblock] $Redact = { param([string] $t) $t },
    [switch] $SuppressHostEcho
  )

  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FilePath
  $psi.Arguments = ConvertTo-WindowsCommandLine -ArgumentList $ArgumentList
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true

  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi
  try {
    [void]$proc.Start()
    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()
    $proc.WaitForExit()
    [void]$stdoutTask.Wait()
    [void]$stderrTask.Wait()
    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result

    if (-not $SuppressHostEcho) {
      if ($stdout) { Write-Host (& $Redact $stdout.TrimEnd()) }
      if ($stderr) { Write-Host ("docker_stderr_redacted=" + (& $Redact $stderr.TrimEnd())) }
    }
    if ($proc.ExitCode -ne 0) {
      throw ("G3b_FAIL: $What exited $($proc.ExitCode)")
    }
    return @{ Code = $proc.ExitCode; StdOut = $stdout; StdErr = $stderr }
  }
  finally {
    if ($proc -and -not $proc.HasExited) {
      try { $proc.Kill() } catch { }
    }
    if ($proc) { $proc.Dispose() }
  }
}

function Invoke-DockerCapturedCore {
  param(
    [Parameter(Mandatory = $true)][string[]] $DockerArgs,
    [Parameter(Mandatory = $true)][string] $What,
    [scriptblock] $Redact = { param([string] $t) $t }
  )
  return Invoke-WindowsProcessCaptured -FilePath "docker" -ArgumentList $DockerArgs -What $What -Redact $Redact
}
