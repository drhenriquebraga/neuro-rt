[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SuiteRoot,
    [Parameter(Mandatory = $true)][string]$HostVersion,
    [string]$BootstrapPython
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    $suite = (Resolve-Path -LiteralPath $SuiteRoot).Path
    $trustedBootstrap = Split-Path -Parent $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($BootstrapPython)) {
        $BootstrapPython = Join-Path $suite 'python\python.exe'
    }
    $python = (Resolve-Path -LiteralPath $BootstrapPython).Path
    # The bundled host supplies Python. Nothing is installed globally.
    $entry = 'import sys; sys.path.insert(0, sys.argv.pop(1)); from neuro_rt.plugin_update import main; sys.exit(main())'
    & $python -I -B -c $entry $trustedBootstrap --suite-root $suite --host-version $HostVersion
    exit $LASTEXITCODE
} catch {
    Write-Error 'Nao foi possivel preparar a release; o Local Suite existente foi preservado.' -ErrorAction Continue
    exit 1
}
