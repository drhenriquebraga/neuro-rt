[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SuiteRoot,
    [string]$PackagePath,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$PackageSha256,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')][string]$TransactionId,
    [string]$BootstrapPython,
    [string]$HostVersion,
    [switch]$AcceptTerms,
    [switch]$LegacyPrepareForQA
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $LegacyPrepareForQA) {
    & (Join-Path $PSScriptRoot 'START_HERE.ps1') -SuiteRoot $SuiteRoot -Mode prepare
    exit $LASTEXITCODE
}
# Preparation is identical to first install and never replaces imported code.
# The host's comecar/esperar/interromper flow owns queue hold, activation and reload.
& (Join-Path $PSScriptRoot 'INSTALL.ps1') -SuiteRoot $SuiteRoot -PackagePath $PackagePath `
    -PackageSha256 $PackageSha256 -TransactionId $TransactionId -BootstrapPython $BootstrapPython -HostVersion $HostVersion -AcceptTerms:$AcceptTerms -LegacyPrepareForQA
exit $LASTEXITCODE
