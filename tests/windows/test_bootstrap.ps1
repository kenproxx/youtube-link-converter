$ErrorActionPreference = 'Stop'
$Bootstrap = Join-Path $PSScriptRoot '../../tools/bootstrap_windows.ps1'
if (-not (Test-Path -LiteralPath $Bootstrap)) { throw 'Missing Windows Python bootstrap implementation' }
$script:Passed = 0
function Assert-True($Value, $Message) { if (-not $Value) { throw $Message } }
function Run-Case($Name, [scriptblock] $Body) {
    & {
        . $Bootstrap
        $TestRoot = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
        New-Item -ItemType Directory -Path $TestRoot | Out-Null
        try { & $Body $TestRoot; Write-Host "PASS: $Name"; $script:Passed++ }
        finally { Remove-Item -LiteralPath $TestRoot -Recurse -Force }
    }
}
Run-Case 'py exists but has no 3.12 runtime: try functioning python' {
    param($Root)
    function Get-PythonCandidates { param($RepoRoot)
        @([pscustomobject]@{Command='py'; Prefix=@('-3.12')},
          [pscustomobject]@{Command='python'; Prefix=@()})
    }
    function Test-PythonCandidate { param($Candidate, [switch] $RequirePip) $Candidate.Command -eq 'python' }
    $Actual = Find-BuildPython $Root
    Assert-True ($Actual.Command -eq 'python') 'Selected launcher instead of working interpreter'
}
Run-Case 'existing valid venv is reused without installation' {
    param($Root)
    $VenvPython = Join-Path $Root '.build-venv/Scripts/python.exe'
    function Test-PythonCandidate { param($Candidate, [switch] $RequirePip) $Candidate.Command -eq $VenvPython }
    function Install-BuildPython { throw 'Must not install when valid venv exists' }
    $Actual = Ensure-BuildEnvironment $Root
    Assert-True ($Actual -eq $VenvPython) 'Failed to reuse existing interpreter'
}
Run-Case 'no installed Python: bootstrap then create verified venv' {
    param($Root)
    function Find-BuildPython { param($RepoRoot) $null }
    function Install-BuildPython { param($RepoRoot)
        $Exe = Join-Path $RepoRoot '.build-tools/python312/python.exe'
        New-Item -ItemType Directory -Force -Path (Split-Path $Exe) | Out-Null
        Set-Content -LiteralPath $Exe -Value 'installed fixture'
        [pscustomobject]@{Command=$Exe; Prefix=@()}
    }
    function Test-PythonCandidate { param($Candidate, [switch] $RequirePip) Test-Path -LiteralPath $Candidate.Command }
    function Invoke-CreateVenv { param($Candidate, $VenvPath)
        if (-not (Test-Path -LiteralPath $Candidate.Command)) { throw 'Base interpreter missing' }
        New-Item -ItemType Directory -Path (Join-Path $VenvPath 'Scripts') -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $VenvPath 'Scripts/python.exe') -Value 'venv fixture'
    }
    $Actual = Ensure-BuildEnvironment $Root
    Assert-True (Test-Path -LiteralPath $Actual) 'Bootstrap did not create a usable venv'
}
Run-Case 'incomplete venv is preserved and replaced' {
    param($Root)
    $Old = Join-Path $Root '.build-venv'
    New-Item -ItemType Directory -Path $Old | Out-Null
    Set-Content -LiteralPath (Join-Path $Old 'keep.txt') -Value 'user data'
    function Test-PythonCandidate { param($Candidate, [switch] $RequirePip) Test-Path -LiteralPath $Candidate.Command }
    function Find-BuildPython { param($RepoRoot) [pscustomobject]@{Command='fixture'; Prefix=@()} }
    function Invoke-CreateVenv { param($Candidate, $VenvPath)
        New-Item -ItemType Directory -Path (Join-Path $VenvPath 'Scripts') -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $VenvPath 'Scripts/python.exe') -Value 'new venv'
    }
    $Actual = Ensure-BuildEnvironment $Root
    $Backups = @(Get-ChildItem -LiteralPath $Root -Force -Directory -Filter '.build-venv.backup-*')
    Assert-True ($Backups.Count -eq 1) 'Old venv was not preserved'
    Assert-True ((Get-Content -LiteralPath (Join-Path $Backups[0].FullName 'keep.txt')) -eq 'user data') 'Backup lost user data'
    Assert-True (Test-Path -LiteralPath $Actual) 'Replacement venv missing'
}
Run-Case 'installer failure stops before nonexistent venv can be executed' {
    param($Root)
    function Test-PythonCandidate { param($Candidate, [switch] $RequirePip) $false }
    function Find-BuildPython { param($RepoRoot) $null }
    function Install-BuildPython { param($RepoRoot) throw 'fixture installer failure' }
    function Invoke-CreateVenv { param($Candidate, $VenvPath) Set-Content (Join-Path $Root 'should-not-exist') 'bad' }
    $Failed = $false
    try { Ensure-BuildEnvironment $Root | Out-Null } catch {
        $Failed = $_.Exception.Message -eq 'fixture installer failure'
    }
    Assert-True $Failed 'Original installer error was not propagated'
    Assert-True (-not (Test-Path (Join-Path $Root 'should-not-exist'))) 'Venv creation ran after installer failed'
}
Run-Case 'untrusted or wrong-publisher installer is rejected' {
    param($Root)
    foreach ($Fixture in @(
        [pscustomobject]@{Status='NotTrusted'; SignerCertificate=[pscustomobject]@{Subject='CN=Python Software Foundation'}},
        [pscustomobject]@{Status='Valid'; SignerCertificate=[pscustomobject]@{Subject='CN=Another Publisher'}})) {
        function Get-AuthenticodeSignature { param($LiteralPath) $Fixture }
        $Failed = $false
        try { Assert-OfficialPythonInstaller 'fixture.exe' } catch { $Failed = $true }
        Assert-True $Failed 'Untrusted or wrong publisher installer accepted'
    }
    function Get-AuthenticodeSignature { param($LiteralPath)
        [pscustomobject]@{Status='Valid'; SignerCertificate=[pscustomobject]@{Subject='CN=Python Software Foundation, O=Python Software Foundation'}}
    }
    Assert-OfficialPythonInstaller 'fixture.exe'
}
Run-Case 'invalid signature prevents installer execution and removes download' {
    param($Root)
    function Invoke-WebRequest {
        param([switch] $UseBasicParsing, $Uri, $OutFile)
        Set-Content -LiteralPath $OutFile -Value 'untrusted fixture'
    }
    function Get-AuthenticodeSignature { param($LiteralPath)
        [pscustomobject]@{Status='NotTrusted'; SignerCertificate=$null}
    }
    function Start-Process {
        param($FilePath, $ArgumentList, [switch] $Wait, [switch] $PassThru)
        Set-Content -LiteralPath (Join-Path $Root 'installer-executed') -Value 'bad'
        [pscustomobject]@{ExitCode=0}
    }
    $Failed = $false
    try { Install-BuildPython $Root | Out-Null } catch { $Failed = $true }
    Assert-True $Failed 'Untrusted installer did not fail'
    Assert-True (-not (Test-Path (Join-Path $Root 'installer-executed'))) 'Untrusted installer was executed'
    Assert-True (@(Get-ChildItem (Join-Path $Root '.build-tools') -Force -Filter '*.exe').Count -eq 0) 'Untrusted download retained'
}
Run-Case 'native Python probe validates runnable interpreter and rejects missing path' {
    param($Root)
    $Python = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) '.venv/bin/python'
    if (-not (Test-Path -LiteralPath $Python)) { $Python = (Get-Command python -CommandType Application -ErrorAction Stop).Source }
    Assert-True (Test-PythonCandidate ([pscustomobject]@{Command=$Python; Prefix=@()})) 'Working Python 3.12 x64 with Tk not recognized'
    Assert-True (-not (Test-PythonCandidate ([pscustomobject]@{Command=(Join-Path $Root 'missing.exe'); Prefix=@()}))) 'Missing executable accepted'
}
Run-Case 'native venv without pip is usable as base but not reusable as build venv' {
    param($Root)
    $Python = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) '.venv/bin/python'
    if (-not (Test-Path -LiteralPath $Python)) { $Python = (Get-Command python -CommandType Application -ErrorAction Stop).Source }
    $WithoutPip = Join-Path $Root 'without-pip'
    & $Python -m venv --without-pip $WithoutPip
    if ($LASTEXITCODE -ne 0) { throw 'Could not create no-pip regression fixture' }
    $Exe = Join-Path $WithoutPip 'Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $Exe)) { $Exe = Join-Path $WithoutPip 'bin/python' }
    $Candidate = [pscustomobject]@{Command=$Exe; Prefix=@()}
    Assert-True (Test-PythonCandidate $Candidate) 'Base interpreter with ensurepip rejected'
    Assert-True (-not (Test-PythonCandidate $Candidate -RequirePip)) 'Incomplete build venv without pip was accepted'
}
Run-Case 'installer wait shows activity and preserves the real process exit code' {
    param($Root)
    $Shell = Join-Path $PSHOME 'powershell.exe'
    if (-not (Test-Path -LiteralPath $Shell)) { $Shell = Join-Path $PSHOME 'pwsh' }
    $Process = Start-Process -FilePath $Shell -ArgumentList @('-NoLogo', '-NoProfile', '-NonInteractive', '-Command', 'Start-Sleep -Milliseconds 1300; exit 7') -PassThru
    try {
        $Capture = @(Wait-InstallerWithProgress $Process 'Python' 6>&1)
        Assert-True ($Capture[-1] -eq 7) 'Installer process exit code was lost'
        $Text = ($Capture | ForEach-Object { $_.ToString() }) -join "`n"
        Assert-True ($Text -match 'still installing') 'No installer heartbeat was displayed'
        Assert-True ($Text -match 'elapsed') 'Elapsed installation time not displayed'
    } finally { $Process.Dispose() }
}
Write-Host "$script:Passed bootstrap checks passed."
