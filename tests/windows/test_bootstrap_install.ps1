# Windows CI integration: force the missing-runtime branch, use real official installer.
$ErrorActionPreference = 'Stop'
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
. (Join-Path $RepoRoot 'tools/bootstrap_windows.ps1')
function Get-PythonCandidates { param($RepoRoot) @() }
$BuildPython = Ensure-BuildEnvironment $RepoRoot
& $BuildPython -c "import sys,struct,tkinter,venv,ensurepip; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8; r=tkinter.Tk(); r.withdraw(); r.destroy(); print('Bootstrapped Python/Tk verified')"
if ($LASTEXITCODE -ne 0) { throw 'Bootstrapped Python/Tk failed to run' }
$Again = Ensure-BuildEnvironment $RepoRoot
if ($Again -ne $BuildPython) { throw 'Second bootstrap did not reuse the verified environment' }
Write-Host 'Actual missing-runtime bootstrap and repeatability checks passed.'
