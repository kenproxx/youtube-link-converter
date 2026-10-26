# Windows PowerShell 5.1 compatible. Downloads happen only on the build machine.
param([string] $RepoRoot = (Split-Path -Parent $PSScriptRoot))

$ErrorActionPreference = 'Stop'

function Test-PythonCandidate {
    param($Candidate, [switch] $RequirePip)
    $Prefix = @($Candidate.Prefix)
    $Probe = 'import sys,struct,tkinter,venv,ensurepip; assert sys.version_info[:2] == (3,12) and struct.calcsize(''P'') == 8'
    if ($RequirePip) { $Probe += '; import pip' }
    try {
        & $Candidate.Command @Prefix -c $Probe 1>$null 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

function Get-PythonCandidates {
    param([string] $RepoRoot)
    [pscustomobject]@{ Command=(Join-Path $RepoRoot '.build-tools/python312/python.exe'); Prefix=@() }
    $Launcher = Get-Command py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Launcher) { [pscustomobject]@{ Command=$Launcher.Source; Prefix=@('-3.12') } }
    if ($env:LOCALAPPDATA) {
        [pscustomobject]@{ Command=(Join-Path $env:LOCALAPPDATA 'Programs/Python/Python312/python.exe'); Prefix=@() }
    }
    $Python = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    # Do not open the Microsoft Store's python.exe alias during probing.
    if ($Python -and $Python.Source -notmatch '[\\/]WindowsApps[\\/]') {
        [pscustomobject]@{ Command=$Python.Source; Prefix=@() }
    }
}

function Find-BuildPython {
    param([string] $RepoRoot)
    foreach ($Candidate in @(Get-PythonCandidates $RepoRoot)) {
        if (Test-PythonCandidate $Candidate) { return $Candidate }
    }
    return $null
}

function Assert-OfficialPythonInstaller {
    param([string] $Installer)
    $Signature = Get-AuthenticodeSignature -LiteralPath $Installer
    if ($Signature.Status -ne 'Valid' -or -not $Signature.SignerCertificate -or
        $Signature.SignerCertificate.Subject -notmatch '(?:^|,\s*)CN=Python Software Foundation(?:,|$)') {
        throw 'Python installer signature is invalid or is not from Python Software Foundation. The installer was NOT executed.'
    }
}

function Wait-InstallerWithProgress {
    param($Process, [string] $Label)
    $Clock = [Diagnostics.Stopwatch]::StartNew()
    Write-Host "[$Label] Installing (elapsed 0s). Windows Installer does not provide a percentage."
    while (-not $Process.WaitForExit(1000)) {
        Write-Host ("[$Label] still installing | elapsed {0:N0}s | please wait..." -f $Clock.Elapsed.TotalSeconds)
    }
    $Process.WaitForExit()
    $Process.Refresh()
    $Code = $Process.ExitCode
    if ($null -eq $Code) { throw "$Label installer exit code is unavailable; setup cannot be verified." }
    Write-Host ("[$Label] Installer finished | elapsed {0:N1}s | exit code $Code" -f $Clock.Elapsed.TotalSeconds)
    return $Code
}

function Install-BuildPython {
    param([string] $RepoRoot)
    $Version = '3.12.10'
    $Tools = Join-Path $RepoRoot '.build-tools'
    $Target = Join-Path $Tools 'python312'
    $Installer = Join-Path $Tools ('python-' + [guid]::NewGuid().ToString() + '.exe')
    New-Item -ItemType Directory -Path $Tools -Force | Out-Null
    Write-Host "No working Python 3.12 x64 found. Preparing Python $Version for this build..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $ProgressPreference = 'Continue'
    try {
        Write-Host '[Python] Downloading official installer; native download progress below (network timeout 120s)...'
        Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/$Version/python-$Version-amd64.exe" -OutFile $Installer -TimeoutSec 120
        Write-Host '[Python] Download complete. Verifying publisher signature...'
        Assert-OfficialPythonInstaller $Installer
        Write-Host '[Python] Publisher signature verified. Starting installation...'
        # Per-user install; do not change PATH, file associations, shortcuts or launcher.
        $Arguments = @('/quiet', 'InstallAllUsers=0', ('TargetDir="' + $Target + '"'),
                       'Include_pip=1', 'Include_tcltk=1', 'Include_test=0', 'Include_doc=0',
                       'Include_launcher=0', 'InstallLauncherAllUsers=0', 'AssociateFiles=0',
                       'Shortcuts=0', 'PrependPath=0', '/log', ('"' + (Join-Path $Tools 'python-install.log') + '"'))
        Write-Host ('[Python] Installer log: ' + (Join-Path $Tools 'python-install.log'))
        $Process = Start-Process -FilePath $Installer -ArgumentList $Arguments -PassThru
        try { $Code = Wait-InstallerWithProgress $Process 'Python' }
        finally { $Process.Dispose() }
        if ($Code -notin @(0, 3010)) {
            throw "Python installer failed (exit $Code). See .build-tools/python-install.log; install Python 3.12 x64 with Tcl/Tk from python.org, then rerun build.bat."
        }
    } finally {
        if (Test-Path -LiteralPath $Installer) { Remove-Item -LiteralPath $Installer -Force }
    }
    $Candidate = [pscustomobject]@{ Command=(Join-Path $Target 'python.exe'); Prefix=@() }
    if (-not (Test-PythonCandidate $Candidate)) {
        throw 'Installed Python 3.12 x64 could not be verified with Tcl/Tk and venv. Build stopped before using it.'
    }
    return $Candidate
}

function Invoke-CreateVenv {
    param($Candidate, [string] $VenvPath)
    $Prefix = @($Candidate.Prefix)
    & $Candidate.Command @Prefix -m venv $VenvPath | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Creating the build virtual environment failed.' }
}

function Ensure-BuildEnvironment {
    param([string] $RepoRoot)
    $Venv = Join-Path $RepoRoot '.build-venv'
    $VenvPython = Join-Path $Venv 'Scripts/python.exe'
    $Existing = [pscustomobject]@{ Command=$VenvPython; Prefix=@() }
    if (Test-PythonCandidate $Existing -RequirePip) {
        Write-Host 'Using verified Python 3.12 x64 build environment.'
        return $VenvPython
    }
    $Candidate = Find-BuildPython $RepoRoot
    if (-not $Candidate) { $Candidate = Install-BuildPython $RepoRoot }
    if (Test-Path -LiteralPath $Venv) {
        $Backup = $Venv + '.backup-' + [guid]::NewGuid().ToString()
        Move-Item -LiteralPath $Venv -Destination $Backup
        Write-Host "Preserved incomplete or incompatible build environment: $Backup"
    }
    Write-Host '[Python] Creating build virtual environment and installing its pip...'
    Invoke-CreateVenv $Candidate $Venv
    if (-not (Test-PythonCandidate $Existing -RequirePip)) {
        throw 'Build virtual environment verification failed. No build commands were executed with the missing interpreter.'
    }
    Write-Host '[Python] Build environment and pip verified.'
    return $VenvPython
}

# Dot-sourcing exposes functions to the offline regression checks without installing.
if ($MyInvocation.InvocationName -ne '.') {
    try {
        $null = Ensure-BuildEnvironment ([IO.Path]::GetFullPath($RepoRoot))
        exit 0
    } catch {
        Write-Host ('PYTHON SETUP FAILED: ' + $_.Exception.Message) -ForegroundColor Red
        exit 1
    }
}
