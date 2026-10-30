[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SuiteRoot,
    [Parameter(Mandatory = $true)][string]$PackagePath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$PackageSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')][string]$TransactionId,
    [string]$BootstrapPython,
    [switch]$AcceptTerms
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

try {
    # No inferred install destination, downloads, credentials or global pip.
    $suite = (Resolve-Path -LiteralPath $SuiteRoot -ErrorAction Stop).Path
    $package = (Resolve-Path -LiteralPath $PackagePath -ErrorAction Stop).Path
    $bootstrapRoot = Split-Path -Parent $PSScriptRoot
    if (-not (Test-Path -LiteralPath (Join-Path $bootstrapRoot 'neuro_rt\install_state.py') -PathType Leaf)) {
        throw 'Bootstrap NeuroRT incompleto.'
    }
    if ([string]::IsNullOrWhiteSpace($BootstrapPython)) {
        $bundlePython = Join-Path $suite 'python\python.exe'
        $sourcePython = Join-Path $suite '.venv\Scripts\python.exe'
        if (Test-Path -LiteralPath $bundlePython -PathType Leaf) {
            $BootstrapPython = $bundlePython
        } elseif (Test-Path -LiteralPath $sourcePython -PathType Leaf) {
            $BootstrapPython = $sourcePython
        } else {
            throw 'Python existente do host ausente; informe -BootstrapPython com Python 3.10 ou posterior autorizado.'
        }
    }
    $python = (Resolve-Path -LiteralPath $BootstrapPython -ErrorAction Stop).Path
    # The same versioned document is used on first opening. AcceptTerms is only
    # for a caller that has already displayed it and obtained explicit agreement.
    $consentEntry = 'import sys; sys.path.insert(0, sys.argv.pop(1)); from neuro_rt.plugin_consent import main; sys.exit(main())'
    $consentArgs = @('--suite-root', $suite)
    if ($AcceptTerms) { $consentArgs += '--accept-terms' }
    & $python -I -B -c $consentEntry $bootstrapRoot @consentArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    # -I ignores user site/PYTHONPATH/current directory; -B preserves immutable code.
    # Bootstrap comes from the trusted installer distribution, never the ZIP payload.
    $entry = 'import sys; sys.path.insert(0, sys.argv.pop(1)); from neuro_rt.install_state import main; sys.exit(main())'
    & $python -I -B -c $entry $bootstrapRoot --suite-root $suite --package-path $package --package-sha256 $PackageSha256 --transaction-id $TransactionId
    $result = $LASTEXITCODE
    if ($result -ne 0) { exit $result }
    exit 0
} catch {
    Write-Error 'Instalacao NeuroRT interrompida. Confira SuiteRoot, pacote, hash externo e bootstrap autorizado.' -ErrorAction Continue
    exit 1
}
