[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SuiteRoot,
    [string]$HostVersion,
    [string]$BootstrapPython,
    [switch]$AcceptTerms,
    [switch]$LegacyPrepareForQA
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    $suite = (Resolve-Path -LiteralPath $SuiteRoot).Path
    if (-not $LegacyPrepareForQA) {
        & (Join-Path $PSScriptRoot 'START_HERE.ps1') -SuiteRoot $suite -Mode prepare
        exit $LASTEXITCODE
    }
    $trustedBootstrap = Split-Path -Parent $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($BootstrapPython)) {
        $BootstrapPython = Join-Path $suite 'python\python.exe'
    }
    $python = (Resolve-Path -LiteralPath $BootstrapPython).Path
    Write-Host 'NEURO RT: usando o Python ja instalado no Local Suite.'
    Write-Host 'NEURO RT: conferindo o termo antes de baixar o SETUP.'
    $consentEntry = 'import sys; sys.path.insert(0, sys.argv.pop(1)); from neuro_rt.plugin_consent import main; sys.exit(main())'
    $consentArgs = @('--suite-root', $suite)
    if ($AcceptTerms) { $consentArgs += '--accept-terms' }
    & $python -I -B -c $consentEntry $trustedBootstrap @consentArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    # The bundled host supplies Python. Nothing is installed globally.
    Write-Host 'NEURO RT: consultando a versao e preparando o instalador leve.'
    $entry = 'import sys; sys.path.insert(0, sys.argv.pop(1)); from neuro_rt.plugin_update import main; sys.exit(main())'
    & $python -I -B -c $entry $trustedBootstrap --suite-root $suite --host-version $HostVersion
    if ($LASTEXITCODE -eq 0) { Write-Host 'NEURO RT: preparo concluido. Abra o NEURO RT na suite para concluir a ativacao.' }
    exit $LASTEXITCODE
} catch {
    Write-Error 'Nao foi possivel preparar a release; o Local Suite existente foi preservado.' -ErrorAction Continue
    exit 1
}
