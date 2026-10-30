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
# Preparation is identical to first install and never replaces imported code.
# The host's comecar/esperar/interromper flow owns queue hold, activation and reload.
& (Join-Path $PSScriptRoot 'INSTALL.ps1') -SuiteRoot $SuiteRoot -PackagePath $PackagePath `
    -PackageSha256 $PackageSha256 -TransactionId $TransactionId -BootstrapPython $BootstrapPython -AcceptTerms:$AcceptTerms
exit $LASTEXITCODE
