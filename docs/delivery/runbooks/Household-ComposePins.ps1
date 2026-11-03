#Requires -Version 5.1
<#
  Shared path pins for household Phase 1 G1/G4/G5/rollback scripts.
  Dot-source only. Planning pins — does not authorize execute.
#>

Set-StrictMode -Version Latest

$script:OperatorRoot = "F:\Code Repo\ThePlan"
$script:OperatorComposeDir = "F:\Code Repo\ThePlan\infra\compose"
$script:OperatorEnvFile = "F:\Code Repo\ThePlan\infra\compose\.env"
$script:SecretsHost = "F:\Code Repo\ThePlan\.secrets-backup"
$script:SecretsHostCompose = "F:/Code Repo/ThePlan/.secrets-backup"
$script:Override042 = "F:\Code Repo\ThePlan\infra\compose\compose.api-042-pin.override.yaml"
$script:RuntimeOverride = Join-Path $PSScriptRoot "compose.household-runtime.override.yaml"
$script:G4PreflightSh = Join-Path $PSScriptRoot "g4-preflight.sh"

$script:ReleaseRoot = "F:\DropFolder\scratch\theplan-release-agent-cli-phase1-g0b"
$script:ReleaseComposeDir = Join-Path $script:ReleaseRoot "infra\compose"
$script:ReleaseComposeFile = Join-Path $script:ReleaseComposeDir "compose.yaml"
$script:ReleaseApiContext = Join-Path $script:ReleaseRoot "apps\api"
$script:ReleaseWebContext = Join-Path $script:ReleaseRoot "apps\web"
$script:WantHead = "0c9430e8bb957981dd8b8a40b8f067ea5f2cddc0"
$script:WantApiSrcManifest = "B572CCC10429CA3BE9BF57E55276AAB0CF4C6934E15F41E1C5C0497077676635"

# Pre-rebuild household image digests (rollback targets). Full IDs required.
$script:ApiImageBaseline = "sha256:e4221a0e30c0f882cb95002cac3f7b3ef1704f7ff81d42032c7391f597a3a77b"
$script:WebImageBaseline = "sha256:636901afe16e8ffda36601af75f029e2b076287a2c5ca868ecedd42029351969"

$script:PostgresContainer = "compose-postgres-1"
$script:HouseholdDb = "theplan"
$script:ExpectAlembic042 = "042_task_occurrence_dispositions"
$script:ExpectAlembic044 = "044_agent_cli_access"
$script:PgUser = "theplan"

$script:BackupRoot = "F:\DropFolder\backups\theplan-household"
$script:WriterContainers = @("compose-scheduler-1", "compose-api-1", "compose-web-1")

function Get-HouseholdComposeArgs {
  param(
    [switch] $With042Pin,
    [string[]] $ExtraComposeFiles = @()
  )
  # project-directory = ReleaseRoot compose dir so relative paths cannot slip to operator tree;
  # build contexts are ALSO absolute in runtime override. Operator .env + absolute secrets via --env-file / override.
  $args = @(
    "-p", "compose",
    "--project-directory", $script:ReleaseComposeDir,
    "--env-file", $script:OperatorEnvFile,
    "-f", $script:ReleaseComposeFile,
    "-f", $script:RuntimeOverride
  )
  if ($With042Pin) {
    $args += @("-f", $script:Override042)
  }
  foreach ($f in $ExtraComposeFiles) {
    $args += @("-f", $f)
  }
  return , $args
}

function Assert-HouseholdRuntimePins {
  foreach ($p in @(
      $script:OperatorEnvFile,
      $script:SecretsHost,
      $script:Override042,
      $script:RuntimeOverride,
      $script:G4PreflightSh,
      $script:ReleaseComposeFile,
      $script:ReleaseApiContext,
      $script:ReleaseWebContext
    )) {
    if (-not (Test-Path -LiteralPath $p)) {
      throw "REFUSE: missing pin path $p"
    }
  }
}

function Assert-WriterContainersStopped {
  param([string] $Phase)
  foreach ($name in $script:WriterContainers) {
    $running = (docker inspect $name --format "{{.State.Running}}" 2>$null)
    if ($running -ne "false") {
      throw "REFUSE: $Phase requires $name stopped (Running=$running)"
    }
  }
}

function Assert-ExternalWritersQuiesced {
  param(
    [Parameter(Mandatory = $true)][string] $Evidence,
    [string] $Phase = "quiesce"
  )
  # Explicit operator attestation — scripts cannot see Julie/browser/automation writers.
  $want = "EXTERNAL_WRITERS_QUIESCED"
  if ($Evidence -cne $want) {
    throw "REFUSE: $Phase requires -ExternalWritersQuiescedConfirm:$want (got attestation mismatch)"
  }
}

function Test-NormalizedPathEquals([string] $a, [string] $b) {
  $na = [System.IO.Path]::GetFullPath(($a -replace '/', '\'))
  $nb = [System.IO.Path]::GetFullPath(($b -replace '/', '\'))
  return ($na -ieq $nb)
}

function Assert-HouseholdComposeBuildPins {
  <#
    Validates resolved compose config build contexts + secrets mount without dumping env/secret values.
  #>
  $composeArgs = Get-HouseholdComposeArgs
  $psiArgs = @("compose") + $composeArgs + @("config", "--format", "json")
  $raw = & docker @psiArgs 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "REFUSE: docker compose config failed (exit $LASTEXITCODE)"
  }
  $cfg = $raw | Out-String | ConvertFrom-Json

  $apiCtx = [string]$cfg.services.api.build.context
  $webCtx = [string]$cfg.services.web.build.context
  $schCtx = [string]$cfg.services.scheduler.build.context
  if (-not (Test-NormalizedPathEquals $apiCtx $script:ReleaseApiContext)) {
    throw "REFUSE: api build.context resolved to '$apiCtx' — want ReleaseRoot apps\api"
  }
  if (-not (Test-NormalizedPathEquals $webCtx $script:ReleaseWebContext)) {
    throw "REFUSE: web build.context resolved to '$webCtx' — want ReleaseRoot apps\web"
  }
  if (-not (Test-NormalizedPathEquals $schCtx $script:ReleaseApiContext)) {
    throw "REFUSE: scheduler build.context resolved to '$schCtx' — want ReleaseRoot apps\api"
  }

  # Volumes: find /secrets destination Source without printing other env.
  $secretOk = $false
  foreach ($v in @($cfg.services.api.volumes)) {
    $src = $null; $dst = $null
    if ($v -is [string]) {
      $parts = $v -split ':', 3
      $src = $parts[0]; $dst = $parts[1]
    } else {
      $src = [string]$v.source
      $dst = [string]$v.target
      if (-not $dst) { $dst = [string]$v.destination }
    }
    if ($dst -eq "/secrets") {
      if (Test-NormalizedPathEquals $src $script:SecretsHost) { $secretOk = $true }
      else { throw "REFUSE: api /secrets source '$src' != operator SecretsHost" }
    }
  }
  if (-not $secretOk) { throw "REFUSE: api /secrets absolute mount not resolved" }

  # Confirm operator tree is NOT the api build context.
  $operatorApi = Join-Path $script:OperatorRoot "apps\api"
  if (Test-NormalizedPathEquals $apiCtx $operatorApi) {
    throw "REFUSE: api build.context still operator tree"
  }

  Write-Host "compose_pin_ok api_context=ReleaseRoot\apps\api web_context=ReleaseRoot\apps\web secrets=operator_absolute project_dir=ReleaseRoot\infra\compose env_file=operator"
}
