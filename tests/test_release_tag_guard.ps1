param([string]$FixtureParent = [IO.Path]::GetTempPath())

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$workflow = Get-Content (Join-Path $root '.github/workflows/release.yml') -Raw
$step = [regex]::Match($workflow, '(?ms)- name: Create private draft with source only.*?run: \|\r?\n(?<body>(?:          [^\r\n]*(?:\r?\n|$))+)')
if (-not $step.Success) { throw 'Draft preparation step not found.' }
$body = $step.Groups['body'].Value -replace '(?m)^          ', ''
$boundary = $body.IndexOf('gh release create ')
if ($boundary -lt 0) { throw 'Draft creation boundary not found.' }
# Exercise the actual preparation, stopping before any release mutation.
$prepareDraft = [scriptblock]::Create($body.Substring(0, $boundary))
$tempParent = [IO.Path]::GetFullPath($FixtureParent)
$fixture = Join-Path $tempParent ('neuro-release-tags-' + [guid]::NewGuid().ToString('N'))
$savedEnv = @{}
foreach ($name in @('GITHUB_REPOSITORY', 'GITHUB_SHA', 'RELEASE_VERSION')) {
    $savedEnv[$name] = [Environment]::GetEnvironmentVariable($name)
}
$failures = 0

function Invoke-FixtureGit {
    & git -C $fixture @args
    if ($LASTEXITCODE -ne 0) { throw 'Synthetic Git fixture failed.' }
}

# Only the remote API is replaced. Tag refs and their commits are real local Git.
function gh {
    if (($args -join ' ') -eq 'api repos/synthetic/neuro --jq .private') {
        $global:LASTEXITCODE = 0
        return 'true'
    }
    if (($args -join ' ') -ne 'api repos/synthetic/neuro/git/matching-refs/tags/v1.0.0') {
        throw 'Unexpected gh call; releases and external access are forbidden in this test.'
    }
    if ($global:NeuroReleaseTagTestApiMode -eq 'transport-error') {
        $global:LASTEXITCODE = 1
        return '[]'
    }
    $global:LASTEXITCODE = 0
    if ($global:NeuroReleaseTagTestApiMode -eq 'invalid-json') { return '{invalid' }
    if ($global:NeuroReleaseTagTestApiMode -eq 'invalid-shape') { return '{}' }
    $refs = @(Invoke-FixtureGit for-each-ref '--format=%(refname)' refs/tags |
        Where-Object { $_.StartsWith('refs/tags/v1.0.0', [StringComparison]::Ordinal) })
    $response = @($refs | ForEach-Object {
        $ref = $_
        $sha = (Invoke-FixtureGit rev-parse $ref).Trim()
        $type = (Invoke-FixtureGit cat-file -t $sha).Trim()
        @{
            ref = $ref; node_id = 'synthetic'; url = 'https://example.invalid/ref'
            object = @{ sha = $sha; type = $type; url = 'https://example.invalid/object' }
        }
    })
    $global:LASTEXITCODE = 0
    ConvertTo-Json -InputObject $response -Depth 4 -Compress
}

try {
    New-Item -ItemType Directory -Path $fixture | Out-Null
    Invoke-FixtureGit init --bare --quiet
    $empty = Join-Path $fixture 'empty-tree'
    [IO.File]::WriteAllBytes($empty, [byte[]]@())
    $tree = (Invoke-FixtureGit hash-object -w -t tree -- $empty).Trim()
    $commitA = (Invoke-FixtureGit -c user.name=Synthetic -c user.email=synthetic@example.invalid commit-tree $tree -m A).Trim()
    $env:GITHUB_SHA = (Invoke-FixtureGit -c user.name=Synthetic -c user.email=synthetic@example.invalid commit-tree $tree -p $commitA -m B).Trim()
    $env:GITHUB_REPOSITORY = 'synthetic/neuro'
    $env:RELEASE_VERSION = '1.0.0'
    Push-Location $root
    try {
        $cases = @(
            @{ name = 'absent'; tag = $null; mode = 'ok'; error = '' },
            @{ name = 'similar-ref-only'; tag = 'similar'; mode = 'ok'; error = '' },
            @{ name = 'lightweight-divergent'; tag = 'lightweight'; mode = 'ok'; error = 'Release tag already exists.' },
            @{ name = 'annotated-divergent'; tag = 'annotated'; mode = 'ok'; error = 'Release tag already exists.' },
            @{ name = 'same-commit'; tag = 'same'; mode = 'ok'; error = 'Release tag already exists.' },
            @{ name = 'transport-error'; tag = $null; mode = 'transport-error'; error = 'Remote tag check failed.' },
            @{ name = 'invalid-json'; tag = $null; mode = 'invalid-json'; error = 'Remote tag response is invalid.' },
            @{ name = 'invalid-shape'; tag = $null; mode = 'invalid-shape'; error = 'Remote tag response is invalid.' }
        )
        foreach ($case in $cases) {
            foreach ($ref in @(Invoke-FixtureGit tag --list)) {
                Invoke-FixtureGit tag -d $ref | Out-Null
            }
            switch ($case.tag) {
                'similar' { Invoke-FixtureGit tag v1.0.0-extra $commitA }
                'lightweight' { Invoke-FixtureGit tag v1.0.0 $commitA }
                'annotated' { Invoke-FixtureGit -c user.name=Synthetic -c user.email=synthetic@example.invalid tag -a v1.0.0 $commitA -m synthetic }
                'same' { Invoke-FixtureGit tag v1.0.0 $env:GITHUB_SHA }
            }
            $before = @(Invoke-FixtureGit for-each-ref '--format=%(objectname) %(refname)' refs/tags)
            $global:NeuroReleaseTagTestApiMode = $case.mode
            $reason = ''
            try { & $prepareDraft } catch { $reason = $_.Exception.Message }
            $after = @(Invoke-FixtureGit for-each-ref '--format=%(objectname) %(refname)' refs/tags)
            $unchanged = (($before | Sort-Object) -join "`n") -eq (($after | Sort-Object) -join "`n")
            if ($reason -ceq $case.error -and $unchanged) {
                Write-Output ('PASS ' + $case.name)
            } else {
                $failures++
                Write-Output ('FAIL ' + $case.name + ': error="' + $reason + '", expected="' + $case.error + '", refs-unchanged=' + $unchanged)
            }
        }
    } finally { Pop-Location }
} finally {
    Remove-Variable -Name NeuroReleaseTagTestApiMode -Scope Global -ErrorAction SilentlyContinue
    foreach ($name in $savedEnv.Keys) { [Environment]::SetEnvironmentVariable($name, $savedEnv[$name]) }
    $resolvedFixture = [IO.Path]::GetFullPath($fixture)
    if ((Split-Path -Parent $resolvedFixture) -ne $tempParent.TrimEnd([IO.Path]::DirectorySeparatorChar) -or
        (Split-Path -Leaf $resolvedFixture) -notlike 'neuro-release-tags-*') {
        throw 'Refusing cleanup outside the synthetic fixture.'
    }
    if (Test-Path -LiteralPath $resolvedFixture) { Remove-Item -LiteralPath $resolvedFixture -Recurse -Force }
}
Write-Output ('Cases: 8; failures: ' + $failures + '; release creations: 0; network calls: 0')
if ($failures -ne 0) { exit 1 }
