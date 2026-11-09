param(
    [Parameter(Mandatory = $true)][string]$Repository,
    [Parameter(Mandatory = $true)][string]$Tag
)

$ErrorActionPreference = 'Stop'
$response = gh api ('repos/' + $Repository + '/git/matching-refs/tags/' + $Tag)
if ($LASTEXITCODE -ne 0) { throw 'Remote tag check failed.' }

try {
    $refs = ConvertFrom-Json -InputObject ($response -join "`n") -NoEnumerate
    if ($refs -isnot [array]) { throw 'Expected an array of refs.' }
    $exists = $false
    foreach ($ref in $refs) {
        if ($null -eq $ref -or $ref.ref -isnot [string]) { throw 'Invalid ref.' }
        if ($ref.ref -ceq ('refs/tags/' + $Tag)) { $exists = $true }
    }
} catch {
    throw 'Remote tag response is invalid.'
}

if ($exists) { throw 'Release tag already exists.' }
