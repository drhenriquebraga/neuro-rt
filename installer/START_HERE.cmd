@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "RADAI_BOOTSTRAP_SELF=%~f0"
set "RADAI_BOOTSTRAP_HOME=%~dp0"
echo.
echo   NEURO RT
echo   ============================
echo.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -STA -Command "$text=[IO.File]::ReadAllText($env:RADAI_BOOTSTRAP_SELF);$body=($text -split '(?m)^# RADAI_BOOTSTRAP_POWERSHELL\r?$',2)[1];& ([scriptblock]::Create($body))"
set "RADAI_BOOTSTRAP_RC=%ERRORLEVEL%"
if not "%RADAI_BOOTSTRAP_RC%"=="0" pause
exit /b %RADAI_BOOTSTRAP_RC%

# RADAI_BOOTSTRAP_POWERSHELL
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Read-InstallerMetadata([string]$Path) {
    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    if ($item.Length -gt 8388608) { throw 'Installer metadata is too large.' }
    return [IO.File]::ReadAllText($item.FullName, [Text.Encoding]::UTF8)
}
function Test-InstallerIdentity([string]$Root, [string]$Product) {
    if ($Product -eq 'local-suite') {
        $stamp = Join-Path $Root 'entrega.txt'
        return ((Test-Path -LiteralPath $stamp -PathType Leaf) -and
            ((Read-InstallerMetadata $stamp) -match '(?m)^PROJETO=LOCAL_SUITE\s*$'))
    }
    $manifest = Join-Path $Root 'release-manifest.json'
    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { return $false }
    $record = (Read-InstallerMetadata $manifest) | ConvertFrom-Json
    return ($record.plugin_id -eq $Product -and $record.schema -eq ($Product + '/release-package/1'))
}
function Get-InstallerPayload([string]$SourceFolder, [string]$Product) {
    $homePath = [IO.Path]::GetFullPath($SourceFolder)
    $roots = @((Join-Path $homePath 'programa'), $homePath)
    if ((Split-Path $homePath -Leaf) -in @('installer', 'packager')) {
        $parent = Split-Path $homePath -Parent
        $roots += $parent
        $roots += (Split-Path $parent -Parent)
    }
    foreach ($root in $roots | Select-Object -Unique) {
        if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
        if (-not (Test-InstallerIdentity $root $Product)) { continue }
        $relative = switch ($Product) {
            'local-suite' { 'packager\prepare.ps1' }
            'neuro-rt' { 'code\installer\START_HERE.ps1' }
            'lung-rt' { 'INSTALL.ps1' }
        }
        $entry = Join-Path $root $relative
        if (-not (Test-Path -LiteralPath $entry -PathType Leaf)) { continue }
        return [pscustomobject]@{ Root = $root; Entry = $entry; Product = $Product }
    }
    return $null
}
function Get-SafeInstallerPath([string]$Root, [string]$Relative) {
    if ([string]::IsNullOrWhiteSpace($Relative)) { throw 'Empty archive path.' }
    $parts = $Relative.Replace('\','/').Split('/')
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative -match '[:<>"|?*\x00-\x1f]') { throw 'Invalid archive path.' }
    foreach ($part in $parts) {
        if ($part -eq '' -or $part -eq '.' -or $part -eq '..' -or $part.EndsWith('.') -or $part.EndsWith(' ') -or
            $part -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)') { throw 'Invalid archive path.' }
    }
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $target = [IO.Path]::GetFullPath((Join-Path $base ($parts -join '\')))
    if (-not $target.StartsWith($base, [StringComparison]::OrdinalIgnoreCase)) { throw 'Archive path escapes extraction folder.' }
    return $target
}
function Get-InstallerZipEntry($Zip, [string]$Name) {
    foreach ($entry in $Zip.Entries) {
        if ($entry.FullName.Replace('\','/') -ceq $Name) { return $entry }
    }
    return $null
}
function Read-ZipMetadata($Zip, [string]$Name) {
    $entry = Get-InstallerZipEntry $Zip $Name
    if (-not $entry -or $entry.Length -gt 8388608) { return $null }
    $reader = New-Object IO.StreamReader($entry.Open(), [Text.Encoding]::UTF8, $true)
    try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
}
function Find-InstallerZipRoot($Zip, [string]$Product) {
    $names = @($Zip.Entries | ForEach-Object { $_.FullName.Replace('\','/') })
    $candidates = @('', 'programa/')
    $tops = @($names | Where-Object { $_.Contains('/') } | ForEach-Object { $_.Split('/')[0] } | Select-Object -Unique)
    if ($tops.Count -eq 1) { $candidates += ($tops[0] + '/'); $candidates += ($tops[0] + '/programa/') }
    foreach ($prefix in $candidates | Select-Object -Unique) {
        if ($Product -eq 'local-suite') {
            $stamp = Read-ZipMetadata $Zip ($prefix + 'entrega.txt')
            if ($stamp -and $stamp -match '(?m)^PROJETO=LOCAL_SUITE\s*$' -and (Get-InstallerZipEntry $Zip ($prefix + 'packager/prepare.ps1'))) { return $prefix }
        } else {
            $raw = Read-ZipMetadata $Zip ($prefix + 'release-manifest.json')
            if (-not $raw) { continue }
            $manifest = $raw | ConvertFrom-Json
            if ($manifest.plugin_id -ne $Product -or $manifest.schema -ne ($Product + '/release-package/1')) { continue }
            $entry = if ($Product -eq 'neuro-rt') { 'code/installer/START_HERE.ps1' } else { 'INSTALL.ps1' }
            if ((Get-InstallerZipEntry $Zip ($prefix + $entry))) { return $prefix }
        }
    }
    throw 'Este ZIP nao corresponde ao instalador escolhido. / This ZIP is not the selected installer.'
}
function Expand-InstallerZip([string]$ArchivePath, [string]$Destination, [string]$Product) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($ArchivePath))
    try {
        if ($zip.Entries.Count -gt 20000) { throw 'Too many files in archive.' }
        $total = 0L
        $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName.Replace('\','/').TrimEnd('/')
            [void](Get-SafeInstallerPath $Destination $name)
            if (-not $seen.Add($name) -or (($entry.ExternalAttributes -shr 16) -band 61440) -eq 40960) { throw 'Duplicate paths or links are not allowed.' }
            $total += $entry.Length
            if ($total -gt 68719476736L) { throw 'Archive exceeds the allowed size.' }
        }
        $prefix = Find-InstallerZipRoot $zip $Product
        $drive = New-Object IO.DriveInfo([IO.Path]::GetPathRoot([IO.Path]::GetFullPath($Destination)))
        if ($drive.AvailableFreeSpace -lt ($total + 268435456L)) { throw 'Sem espaco para extrair o pacote. / Not enough disk space to extract the package.' }
        [void](New-Item -ItemType Directory -Path $Destination -ErrorAction Stop)
        $count = 0
        foreach ($entry in $zip.Entries) {
            if ($entry.FullName.Replace('\','/').EndsWith('/')) { continue }
            $target = Get-SafeInstallerPath $Destination $entry.FullName
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
            $incomingStream = $entry.Open()
            $output = New-Object IO.FileStream($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
            try {
                $buffer = New-Object byte[] 1048576
                $copied = 0L
                while (($length = $incomingStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $copied += $length
                    if ($copied -gt $entry.Length) { throw 'Archive entry exceeds its declared size.' }
                    $output.Write($buffer, 0, $length)
                }
                if ($copied -ne $entry.Length) { throw 'Truncated archive entry.' }
            } finally { $output.Dispose(); $incomingStream.Dispose() }
            $count++
            Write-Progress -Activity ('Extraindo / Extracting ' + $Product) -Status ($count.ToString() + ' arquivos / files') -PercentComplete ([math]::Min(99, [int](100.0*$count/[math]::Max(1,$zip.Entries.Count))))
        }
        Write-Progress -Activity ('Extraindo / Extracting ' + $Product) -Completed
        $payloadRoot = if ($prefix) { Join-Path $Destination $prefix.Replace('/', '\') } else { $Destination }
        $payload = Get-InstallerPayload $payloadRoot $Product
        if (-not $payload) { throw 'O pacote extraido esta incompleto. / Extracted package is incomplete.' }
        return $payload
    } finally { $zip.Dispose() }
}
function Select-InstallerZip([string]$Product) {
    Add-Type -AssemblyName System.Windows.Forms
    $picker = New-Object Windows.Forms.OpenFileDialog
    $picker.Title = 'Selecione o ZIP completo / Select the complete ZIP - ' + $Product
    $picker.Filter = 'ZIP (*.zip)|*.zip'
    $picker.CheckFileExists = $true
    $picker.Multiselect = $false
    try {
        if ($picker.ShowDialog() -ne [Windows.Forms.DialogResult]::OK) { return $null }
        return $picker.FileName
    } finally { $picker.Dispose() }
}
function Start-InstallerPayload($Payload) {
    Write-Host ('Abrindo / Opening ' + $Payload.Product + '...')
    $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -STA -File $Payload.Entry 2>&1 | ForEach-Object { Write-Host $_ }
        $result = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousErrorAction }
    return $result
}
function Invoke-InstallerBootstrap([string]$SourceFolder, [string]$Product, [string]$ArchivePath) {
    $payload = Get-InstallerPayload $SourceFolder $Product
    if (-not $payload) {
        Write-Host 'O Windows abriu somente o atalho dentro do ZIP. Selecione o ZIP completo; os arquivos serao extraidos automaticamente.'
        Write-Host 'Windows opened only this launcher inside the ZIP. Select the complete ZIP to extract all files automatically.'
        if (-not $ArchivePath) { $ArchivePath = Select-InstallerZip $Product }
        if (-not $ArchivePath) { Write-Host 'Cancelado / Cancelled. Nenhuma instalacao iniciada.'; return 0 }
        $destination = Join-Path ([IO.Path]::GetTempPath()) ('RadioterapiaAI-' + $Product + '-setup-' + [guid]::NewGuid().ToString('N'))
        Write-Host ('Extraindo / Extracting: ' + $ArchivePath)
        $payload = Expand-InstallerZip $ArchivePath $destination $Product
    }
    return (Start-InstallerPayload $payload)
}
try {
    $code = Invoke-InstallerBootstrap -SourceFolder $env:RADAI_BOOTSTRAP_HOME -Product 'neuro-rt'
    exit [int]$code
} catch {
    Write-Host ('Instalacao interrompida / Installation stopped: ' + $_.Exception.Message) -ForegroundColor Yellow
    Write-Host 'O programa e os dados existentes foram preservados. / Existing application and data were preserved.'
    exit 1
}
